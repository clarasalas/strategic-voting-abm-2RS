"""
What drives the simulations? — Exploratory sensitivity from an LHS parameter sweep.

This script fits a surrogate model (RandomForest) that predicts the simulated
outcome (ΔCENP) from the parameters varied in a Latin-Hypercube-Sampling sweep,
then uses permutation importance to rank which parameters matter most.

We deliberately call this an *exploratory* / LHS sensitivity analysis rather than a
formal Sobol/Saltelli analysis, because the design is LHS (not a Saltelli sequence).

Two output styles share the same surrogate-fitting core:

    (default)  Paper/analysis figures with in-figure titles and raw R²-drop units:
                   lhs_importance_pooled.png / .pdf      -> importance pooled across years
                   lhs_importance_by_year.png / .pdf     -> two panels, 2002 and 2022

    --slide    Presentation figure: no in-figure title/subtitle, importances
               normalized to % within each year, transparent background:
                   lhs_importance_by_year_slide.png / .pdf

Usage:
    python analysis/lhs_importance.py            # paper figures
    python analysis/lhs_importance.py --slide     # slide figure
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import cross_val_score, KFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

# --------------------------------------------------------------------------- #
# Configuration (shared)
# --------------------------------------------------------------------------- #
SEED = 42
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
OUT_DIR = Path(__file__).resolve().parent.parent.parent / "figures"
OUT_DIR.mkdir(exist_ok=True)

NAVY = "#1f2d50"

# Per-year input files (the "_design" files contain only inputs, so we use the
# full sweep files that also carry the outcome columns).
YEAR_FILES = {
    "2002": DATA_DIR / "behavioral_sweep_2002.csv",
    "2022": DATA_DIR / "behavioral_sweep_2022.csv",
}

# Candidate names for the outcome column, in priority order. The script is
# robust to naming differences across CSVs.
OUTCOME_CANDIDATES = [
    "delta_cenp", "mean_delta_cenp", "dcenp", "coordination_gain", "cenp_gain",
]

# Columns that are NEVER predictors: identifiers, seeds, metadata, and any
# OUTPUT/diagnostic column that is mechanically derived from the run (including
# the components used to compute ΔCENP).
NON_PREDICTOR_PATTERNS = [
    "draw", "run_id", "runid", "id", "seed", "filename", "file", "year",
    "n_repeats", "nrepeats", "repeat",
    # outputs / diagnostics (not parameters that were swept):
    "delta_cenp", "final_enp", "std_", "cenp_result", "cenp_poll",
    "cenp_s0", "cenp_real", "observed", "result", "mean_", "_real",
]


# --------------------------------------------------------------------------- #
# Surrogate-fitting core (shared)
# --------------------------------------------------------------------------- #
def find_outcome_column(df):
    """Return the outcome column name using the candidate list."""
    lower = {c.lower(): c for c in df.columns}
    for cand in OUTCOME_CANDIDATES:
        if cand in lower:
            return lower[cand]
    raise ValueError(f"No outcome column found among {OUTCOME_CANDIDATES}. "
                     f"Columns are: {list(df.columns)}")


def find_predictor_columns(df, outcome_col):
    """Return the numeric parameter columns, excluding ids/seeds/outputs."""
    predictors = []
    for col in df.columns:
        if col == outcome_col:
            continue
        name = col.lower()
        if any(pat in name for pat in NON_PREDICTOR_PATTERNS):
            continue
        if not np.issubdtype(df[col].dtype, np.number):
            continue
        predictors.append(col)
    return predictors


def fit_and_importance(X, y, label):
    """Fit a RandomForest surrogate, report R², and compute permutation importance.

    Returns (DataFrame, cv_r2_mean). The DataFrame has columns:
    param, importance (raw R² drop), importance_std, std_coef. Callers that want
    percentage-normalized importances derive them from `importance`.
    """
    rf = RandomForestRegressor(n_estimators=500, random_state=SEED, n_jobs=-1)

    # Cross-validated R² tells us whether the surrogate is meaningful at all.
    # Shuffle the folds: the rows are ordered by year, so without shuffling the
    # pooled folds would each train on one year and test on the other.
    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_r2 = cross_val_score(rf, X, y, cv=cv, scoring="r2")
    print(f"\n[{label}] surrogate RandomForest")
    print(f"  5-fold CV R² = {cv_r2.mean():.3f} ± {cv_r2.std():.3f}")
    if cv_r2.mean() < 0.1:
        print(f"  WARNING: very low predictive performance (CV R²={cv_r2.mean():.3f}). "
              f"Importances for [{label}] are not reliable — interpret with caution.")

    # Fit on all data, then permutation importance (main result).
    rf.fit(X, y)
    perm = permutation_importance(
        rf, X, y, n_repeats=30, random_state=SEED, scoring="r2", n_jobs=-1,
    )

    # Robustness check: standardized regression coefficients (linear model).
    Xs = StandardScaler().fit_transform(X)
    ys = (y - y.mean()) / y.std()
    lin = LinearRegression().fit(Xs, ys)

    out = pd.DataFrame({
        "param": X.columns,
        "importance": perm.importances_mean,
        "importance_std": perm.importances_std,
        "std_coef": lin.coef_,
    }).sort_values("importance", ascending=True).reset_index(drop=True)
    return out, cv_r2.mean()


def load_year_frames():
    """Read the per-year sweep CSVs, returning {year: DataFrame}."""
    return {year: pd.read_csv(path) for year, path in YEAR_FILES.items()}


# =========================================================================== #
# Paper figures (default)
# =========================================================================== #
PAPER_PRETTY_LABELS = {
    "tau_hat": "Strategic threshold (τ̂)",
    "mu": "Expressive weight (μ)",
    "alpha": "Learning / update rate (α)",
    "rho_pi": "Trust in polls (ρπ)",
    "beta": "Choice rationality (β)",
}

# Assign each parameter to a family so bars can be colour-coded.
PAPER_PARAM_FAMILY = {
    "tau_hat": "behavioral",
    "mu": "behavioral",
    "alpha": "behavioral",
    "beta": "behavioral",
    "rho_pi": "structural",   # poll structure / precision
}

PAPER_FAMILY_COLORS = {
    "structural": "#7fa8c9",   # soft blue
    "behavioral": "#9cc9a4",   # soft green
    "stochastic": "#e6b88a",   # soft orange
}
PAPER_DEFAULT_COLOR = "#c2c2c2"


def _paper_color(param):
    return PAPER_FAMILY_COLORS.get(PAPER_PARAM_FAMILY.get(param), PAPER_DEFAULT_COLOR)


def _paper_pretty(param):
    return PAPER_PRETTY_LABELS.get(param, param)


def _paper_barh_panel(ax, imp_df, title, subtitle=None):
    """Draw a horizontal permutation-importance bar chart on `ax`."""
    colors = [_paper_color(p) for p in imp_df["param"]]
    labels = [_paper_pretty(p) for p in imp_df["param"]]
    ax.barh(labels, imp_df["importance"], xerr=imp_df["importance_std"],
            color=colors, edgecolor=NAVY, linewidth=0.6,
            error_kw=dict(ecolor=NAVY, alpha=0.4, lw=1))
    ax.set_xlabel("Permutation importance (drop in R²)")
    ax.set_title(title, color=NAVY, fontweight="bold", loc="left", pad=22)
    if subtitle:
        ax.text(0, 1.01, subtitle, transform=ax.transAxes,
                fontsize=10, color=NAVY, alpha=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.margins(x=0.12)


def _paper_family_legend(fig):
    handles = [Patch(facecolor=c, edgecolor=NAVY, label=f.capitalize())
               for f, c in PAPER_FAMILY_COLORS.items()]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, -0.02))


def run_paper():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.edgecolor": NAVY,
        "axes.labelcolor": NAVY,
        "text.color": NAVY,
        "xtick.color": NAVY,
        "ytick.color": NAVY,
        "font.size": 12,
    })

    # Load data and pool.
    frames = load_year_frames()
    all_df = pd.concat(
        [df.assign(year=year) for year, df in frames.items()], ignore_index=True
    )

    outcome_col = find_outcome_column(all_df)
    predictor_cols = find_predictor_columns(all_df, outcome_col)

    print("=" * 60)
    print("Detected columns")
    print("=" * 60)
    print(f"Outcome column   : {outcome_col}")
    print(f"Year column      : year")
    print(f"Predictor columns: {predictor_cols}")
    print(f"Excluded columns : "
          f"{[c for c in all_df.columns if c not in predictor_cols + [outcome_col]]}")
    print(f"Rows: total={len(all_df)}  "
          f"({', '.join(f'{y}={len(f)}' for y, f in frames.items())})")

    # Run analyses: pooled, 2002, 2022.
    results = {}
    for label, subset in [
        ("Pooled (2002 + 2022)", all_df),
        ("2002", all_df[all_df["year"] == "2002"]),
        ("2022", all_df[all_df["year"] == "2022"]),
    ]:
        X = subset[predictor_cols].copy()
        y = subset[outcome_col].to_numpy()
        results[label] = fit_and_importance(X, y, label)

    # Print standardized-coefficient robustness table.
    print("\n" + "=" * 60)
    print("Robustness check: standardized regression coefficients")
    print("=" * 60)
    for label, (imp_df, _) in results.items():
        print(f"\n[{label}]")
        for _, r in imp_df.sort_values("std_coef", key=abs, ascending=False).iterrows():
            print(f"  {_paper_pretty(r['param']):28s} std_coef={r['std_coef']:+.3f}  "
                  f"perm_imp={r['importance']:.4f}")

    # Figure 1: pooled.
    pooled_df, pooled_r2 = results["Pooled (2002 + 2022)"]
    fig, ax = plt.subplots(figsize=(9, 5.4))
    fig.suptitle("WHAT DRIVES THE SIMULATIONS?", color=NAVY, fontweight="bold",
                 fontsize=18, x=0.02, y=0.99, ha="left")
    fig.text(0.02, 0.92, "Exploratory sensitivity from LHS parameter sweep",
             fontsize=11, color=NAVY, alpha=0.7)
    _paper_barh_panel(ax, pooled_df, title="",
                      subtitle=f"Pooled across years   ·   surrogate CV R² = {pooled_r2:.2f}")
    _paper_family_legend(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 0.86])
    fig.savefig(OUT_DIR / "lhs_importance_pooled.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT_DIR / "lhs_importance_pooled.pdf", bbox_inches="tight")
    print(f"\nSaved {OUT_DIR/'lhs_importance_pooled.png'} (+ .pdf)")

    # Figure 2: by year (two panels).
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), sharex=False)
    fig.suptitle("WHAT DRIVES THE SIMULATIONS?", color=NAVY, fontweight="bold",
                 fontsize=18, x=0.02, y=0.99, ha="left")
    fig.text(0.02, 0.92, "Exploratory sensitivity from LHS parameter sweep",
             fontsize=11, color=NAVY, alpha=0.7)
    for ax, year in zip(axes, ["2002", "2022"]):
        imp_df, r2 = results[year]
        _paper_barh_panel(ax, imp_df, title=year,
                          subtitle=f"surrogate CV R² = {r2:.2f}")
    _paper_family_legend(fig)
    fig.tight_layout(rect=[0, 0.04, 1, 0.85])
    fig.savefig(OUT_DIR / "lhs_importance_by_year.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT_DIR / "lhs_importance_by_year.pdf", bbox_inches="tight")
    print(f"Saved {OUT_DIR/'lhs_importance_by_year.png'} (+ .pdf)")

    print("\nInterpretation suggestion:")
    print("  Structural parameters explain most variation in the baseline "
          "simulations;\n  behavioral parameters matter less until the electoral "
          "structure is better specified.")


# =========================================================================== #
# Slide figure (--slide)
# =========================================================================== #
def _importance_pct(imp_df):
    """Map {param -> percentage importance}, clipping negatives before scaling."""
    imp = np.clip(imp_df["importance"].to_numpy(), 0, None)
    pct = 100 * imp / imp.sum() if imp.sum() > 0 else imp
    return dict(zip(imp_df["param"], pct))


def run_slide():
    # Prefer Open Sans if installed, otherwise a clean sans-serif fallback.
    from matplotlib import font_manager
    import matplotlib.colors as mcolors

    available = {f.name for f in font_manager.fontManager.ttflist}
    main_font = next((f for f in ("Open Sans", "Inter") if f in available),
                     "DejaVu Sans")
    print(f"Using font: {main_font}")

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [main_font, "DejaVu Sans", "Arial"],
        "figure.facecolor": "none",
        "axes.facecolor": "none",
        "savefig.facecolor": "none",
        "savefig.transparent": True,
        "axes.edgecolor": NAVY,
        "axes.labelcolor": NAVY,
        "text.color": NAVY,
        "xtick.color": NAVY,
        "ytick.color": NAVY,
        "font.size": 13,
    })

    # Load data and fit per year.
    frames = load_year_frames()
    sample = next(iter(frames.values()))
    outcome_col = find_outcome_column(sample)
    predictor_cols = find_predictor_columns(sample, outcome_col)

    print("=" * 60)
    print(f"Outcome column   : {outcome_col}")
    print(f"Predictor columns: {predictor_cols}")
    print("=" * 60)

    results = {}
    for year, df in frames.items():
        X = df[predictor_cols].copy()
        y = df[outcome_col].to_numpy()
        results[year] = fit_and_importance(X, y, year)

    # Figure: single panel, grouped horizontal bars (2002 vs 2022 per row).
    BLUE = "#4A7FC1"     # Preferences group color
    ORANGE = "#E07B3F"   # Beliefs group color
    BAND_GRAY = "#F2F2F2"

    def lighten(color, amount=0.45):
        """Blend `color` toward white by `amount` (0 = unchanged, 1 = white)."""
        r, g, b = mcolors.to_rgb(color)
        return (r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount)

    # Five rows, top-to-bottom, with the group each belongs to and the raw params
    # whose importances are summed for that row.
    ROWS = [
        ("Acceptable\ncandidates (τ̂)", "Preferences", BLUE,   ["tau_hat"]),
        ("Favorite\nchoice (β)",        "Preferences", BLUE,   ["beta"]),
        ("Strategic voting\ncost (μ)",  "Preferences", BLUE,   ["mu"]),
        ("Prior\ndecision (ρπ)",        "Beliefs",     ORANGE, ["rho_pi"]),
        ("Reaction to\nnew polls (α)",  "Beliefs",     ORANGE, ["alpha"]),
    ]

    def grouped_value(pct, params):
        return sum(pct.get(p, 0.0) for p in params)

    def fmt(val):
        return f"{round(val)}%" if val >= 5 else f"<{max(1, round(val))}%"

    # Row y-centers (top-to-bottom). Normal row gap = 1.0; the gap at the section
    # break (between Preferences rows 0–2 and Beliefs rows 3–4) is widened to
    # make the split obvious.
    ROW_Y = [6.0, 5.0, 4.0, 2.2, 1.2]
    BAR_H = 0.28
    OFFSET = 0.17               # half-distance between the paired bars
    pct02 = _importance_pct(results["2002"][0])
    pct22 = _importance_pct(results["2022"][0])

    fig, ax = plt.subplots(figsize=(14, 7))

    # Shaded background bands per group (very light gray), drawn behind everything.
    def band(rows_y, pad_top=0.55, pad_bot=0.55):
        return min(rows_y) - pad_bot, max(rows_y) + pad_top

    for grp_rows in (ROW_Y[0:3], ROW_Y[3:5]):
        lo, hi = band(grp_rows)
        ax.axhspan(lo, hi, xmin=0, xmax=1, color=BAND_GRAY, zorder=0)

    # Bars: 2002 (lighter shade, upper) and 2022 (full color, lower) per row.
    for ry, (label, grp, color, params) in zip(ROW_Y, ROWS):
        v02 = grouped_value(pct02, params)
        v22 = grouped_value(pct22, params)
        ax.barh(ry + OFFSET, v02, height=BAR_H, color=lighten(color), zorder=3)
        ax.barh(ry - OFFSET, v22, height=BAR_H, color=color, zorder=3)
        # Value labels at the end of each bar.
        ax.text(v02 + 1.2, ry + OFFSET, fmt(v02), va="center", ha="left",
                fontsize=12, color=NAVY)
        ax.text(v22 + 1.2, ry - OFFSET, fmt(v22), va="center", ha="left",
                fontsize=12, color=NAVY)

    # Group labels ("PREFERENCES" / "BELIEFS") in the group color, above each band.
    for grp_rows, grp_label, grp_color in (
        (ROW_Y[0:3], "Preferences parameters", BLUE),
        (ROW_Y[3:5], "Beliefs parameters", ORANGE),
    ):
        lo, hi = band(grp_rows)
        ax.text(1.5, hi + 0.08, grp_label.upper(), ha="left", va="bottom",
                fontsize=16, style="italic", fontweight="bold", color=grp_color,
                zorder=5)

    # Y tick labels = parameter names.
    ax.set_yticks(ROW_Y)
    ax.set_yticklabels([r[0] for r in ROWS], fontsize=12, fontweight="bold")
    ax.set_ylim(0.5, 7.0)  # high y at top (no inversion -> first row on top)

    # X axis.
    ax.set_xlim(0, 100)
    ax.set_xlabel("Relative permutation importance (%)", fontsize=12, color=NAVY)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(NAVY)
    ax.tick_params(length=0)
    ax.tick_params(axis="y", pad=14)  # extra space between labels and bars
    ax.grid(False)

    # Compact year legend (two squares) at the top-right of the chart area.
    year_handles = [
        Patch(facecolor=lighten(BLUE), label="2002"),
        Patch(facecolor=BLUE, label="2022"),
    ]
    ax.legend(handles=year_handles, loc="upper right", frameon=False, fontsize=11,
              handlelength=1.0, handleheight=1.0, ncol=2, columnspacing=1.2,
              bbox_to_anchor=(1.0, 1.05))

    fig.tight_layout(rect=[0, 0.05, 1, 1])

    fig.savefig(OUT_DIR / "lhs_importance_by_year_slide.png", dpi=300,
                bbox_inches="tight", transparent=True)
    fig.savefig(OUT_DIR / "lhs_importance_by_year_slide.pdf",
                bbox_inches="tight", transparent=True)
    print(f"\nSaved {OUT_DIR/'lhs_importance_by_year_slide.png'} (+ .pdf) at 300 dpi")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slide", action="store_true",
                        help="Render the presentation (slide) figure instead of "
                             "the paper figures.")
    args = parser.parse_args()
    if args.slide:
        run_slide()
    else:
        run_paper()


if __name__ == "__main__":
    main()
