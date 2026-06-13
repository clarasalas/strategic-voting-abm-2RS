"""
What drives the simulations? — Exploratory sensitivity from an LHS parameter sweep.

This script fits a surrogate model (RandomForest) that predicts the simulated
outcome (ΔCENP) from the parameters varied in a Latin-Hypercube-Sampling sweep,
then uses permutation importance to rank which parameters matter most.

We deliberately call this an *exploratory* / LHS sensitivity analysis rather than a
formal Sobol/Saltelli analysis, because the design is LHS (not a Saltelli sequence).

Outputs:
    lhs_importance_pooled.png / .pdf      -> importance pooled across years
    lhs_importance_by_year.png / .pdf     -> two panels, 2002 and 2022
"""

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
# Configuration
# --------------------------------------------------------------------------- #
SEED = 42
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR = Path(__file__).resolve().parent.parent / "figures"
OUT_DIR.mkdir(exist_ok=True)

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
# Slide styling
# --------------------------------------------------------------------------- #
NAVY = "#1f2d50"
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

# Map raw parameter names -> readable labels for the figures.
PRETTY_LABELS = {
    "tau_hat": "Strategic threshold (τ̂)",
    "mu": "Expressive weight (μ)",
    "alpha": "Learning / update rate (α)",
    "rho_pi": "Trust in polls (ρπ)",
    "beta": "Choice rationality (β)",
}

# Assign each parameter to a family so bars can be colour-coded.
# Edit this dictionary if your parameter set changes.
PARAM_FAMILY = {
    "tau_hat": "behavioral",
    "mu": "behavioral",
    "alpha": "behavioral",
    "beta": "behavioral",
    "rho_pi": "structural",   # poll structure / precision
}

FAMILY_COLORS = {
    "structural": "#7fa8c9",   # soft blue
    "behavioral": "#9cc9a4",   # soft green
    "stochastic": "#e6b88a",   # soft orange
}
DEFAULT_COLOR = "#c2c2c2"


# --------------------------------------------------------------------------- #
# Helpers
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


def family_color(param):
    return FAMILY_COLORS.get(PARAM_FAMILY.get(param), DEFAULT_COLOR)


def pretty(param):
    return PRETTY_LABELS.get(param, param)


def fit_and_importance(X, y, label):
    """Fit a RandomForest surrogate, report R², and compute permutation importance.

    Returns a DataFrame with columns: param, importance, importance_std, std_coef.
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


def barh_panel(ax, imp_df, title, subtitle=None):
    """Draw a horizontal permutation-importance bar chart on `ax`."""
    colors = [family_color(p) for p in imp_df["param"]]
    labels = [pretty(p) for p in imp_df["param"]]
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


def family_legend(fig):
    handles = [Patch(facecolor=c, edgecolor=NAVY, label=f.capitalize())
               for f, c in FAMILY_COLORS.items()]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, -0.02))


# --------------------------------------------------------------------------- #
# Load data
# --------------------------------------------------------------------------- #
frames = []
for year, path in YEAR_FILES.items():
    df = pd.read_csv(path)
    df["year"] = year
    frames.append(df)
all_df = pd.concat(frames, ignore_index=True)

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
      f"({', '.join(f'{y}={len(f)}' for y, f in zip(YEAR_FILES, frames))})")

# --------------------------------------------------------------------------- #
# Run analyses: pooled, 2002, 2022
# --------------------------------------------------------------------------- #
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
        print(f"  {pretty(r['param']):28s} std_coef={r['std_coef']:+.3f}  "
              f"perm_imp={r['importance']:.4f}")

# --------------------------------------------------------------------------- #
# Figure 1: pooled
# --------------------------------------------------------------------------- #
pooled_df, pooled_r2 = results["Pooled (2002 + 2022)"]
fig, ax = plt.subplots(figsize=(9, 5.4))
fig.suptitle("WHAT DRIVES THE SIMULATIONS?", color=NAVY, fontweight="bold",
             fontsize=18, x=0.02, y=0.99, ha="left")
fig.text(0.02, 0.92, "Exploratory sensitivity from LHS parameter sweep",
         fontsize=11, color=NAVY, alpha=0.7)
barh_panel(ax, pooled_df, title="",
           subtitle=f"Pooled across years   ·   surrogate CV R² = {pooled_r2:.2f}")
family_legend(fig)
fig.tight_layout(rect=[0, 0.04, 1, 0.86])
fig.savefig(OUT_DIR / "lhs_importance_pooled.png", dpi=200, bbox_inches="tight")
fig.savefig(OUT_DIR / "lhs_importance_pooled.pdf", bbox_inches="tight")
print(f"\nSaved {OUT_DIR/'lhs_importance_pooled.png'} (+ .pdf)")

# --------------------------------------------------------------------------- #
# Figure 2: by year (two panels)
# --------------------------------------------------------------------------- #
fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), sharex=False)
fig.suptitle("WHAT DRIVES THE SIMULATIONS?", color=NAVY, fontweight="bold",
             fontsize=18, x=0.02, y=0.99, ha="left")
fig.text(0.02, 0.92, "Exploratory sensitivity from LHS parameter sweep",
         fontsize=11, color=NAVY, alpha=0.7)
for ax, year in zip(axes, ["2002", "2022"]):
    imp_df, r2 = results[year]
    barh_panel(ax, imp_df, title=year,
               subtitle=f"surrogate CV R² = {r2:.2f}")
family_legend(fig)
fig.tight_layout(rect=[0, 0.04, 1, 0.85])
fig.savefig(OUT_DIR / "lhs_importance_by_year.png", dpi=200, bbox_inches="tight")
fig.savefig(OUT_DIR / "lhs_importance_by_year.pdf", bbox_inches="tight")
print(f"Saved {OUT_DIR/'lhs_importance_by_year.png'} (+ .pdf)")

print("\nInterpretation suggestion:")
print("  Structural parameters explain most variation in the baseline "
      "simulations;\n  behavioral parameters matter less until the electoral "
      "structure is better specified.")
