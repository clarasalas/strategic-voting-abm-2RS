"""
By-year parameter-importance figure for slide use (no in-figure title/subtitle).

Conditional on FIXED empirical inputs within each year (party/candidate positions,
voter ideology distributions, and real weekly-mean pre-electoral polls), this shows
which behavioral / decision-process parameters matter for the simulated outcome
ΔCENP. Importances are permutation importances, normalized to % within each year.

Outputs:
    lhs_importance_by_year_slide.png / .pdf
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, FancyBboxPatch
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import cross_val_score, KFold

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
SEED = 42
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR = Path(__file__).resolve().parent.parent / "figures"
OUT_DIR.mkdir(exist_ok=True)

YEAR_FILES = {
    "2002": DATA_DIR / "behavioral_sweep_2002.csv",
    "2022": DATA_DIR / "behavioral_sweep_2022.csv",
}

OUTCOME_CANDIDATES = [
    "delta_cenp", "mean_delta_cenp", "dcenp", "coordination_gain", "cenp_gain",
]

# Columns that are never predictors (ids, seeds, metadata, outputs/diagnostics).
NON_PREDICTOR_PATTERNS = [
    "draw", "run_id", "runid", "id", "seed", "filename", "file", "year",
    "n_repeats", "nrepeats", "repeat",
    "delta_cenp", "final_enp", "std_", "result", "observed", "mean_", "_real",
]

# Friendly, slide-ready labels: wrapped to two lines, symbol appended (no parens).
PRETTY_LABELS = {
    "beta": "Ideological\ndeterminism β",
    "tau_hat": "Tolerance\nrange τ̂",
    "rho_pi": "Prior\nprecision ρπ",
    "alpha": "Anchoring α",
    "mu": "Switching\ncost μ",
}

# Three categories only.
PARAM_CATEGORY = {
    "beta": "Preference architecture",
    "tau_hat": "Preference architecture",
    "rho_pi": "Belief formation",
    "alpha": "Belief formation",
    "mu": "Switching friction",
}

# Muted, distinct colors per category.
CATEGORY_COLORS = {
    "Preference architecture": "#4A7FC1",   # blue
    "Belief formation": "#7EB5A0",           # teal
    "Switching friction": "#D4A85A",         # amber
}
DEFAULT_COLOR = "#c2c2c2"

NAVY = "#1f2d50"

# Prefer Open Sans if installed, otherwise a clean sans-serif fallback.
from matplotlib import font_manager
_available = {f.name for f in font_manager.fontManager.ttflist}
_main_font = next((f for f in ("Open Sans", "Inter") if f in _available),
                  "DejaVu Sans")
print(f"Using font: {_main_font}")

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": [_main_font, "DejaVu Sans", "Arial"],
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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def find_outcome_column(df):
    lower = {c.lower(): c for c in df.columns}
    for cand in OUTCOME_CANDIDATES:
        if cand in lower:
            return lower[cand]
    raise ValueError(f"No outcome column found among {OUTCOME_CANDIDATES}.")


def find_predictor_columns(df, outcome_col):
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


def category_color(param):
    return CATEGORY_COLORS.get(PARAM_CATEGORY.get(param), DEFAULT_COLOR)


def pretty(param):
    return PRETTY_LABELS.get(param, param)


def fit_and_importance(X, y, label):
    """RandomForest surrogate; report CV R²; return permutation importance (%)."""
    rf = RandomForestRegressor(n_estimators=500, random_state=SEED, n_jobs=-1)
    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_r2 = cross_val_score(rf, X, y, cv=cv, scoring="r2")
    print(f"[{label}] RandomForest surrogate  5-fold CV R² = "
          f"{cv_r2.mean():.3f} ± {cv_r2.std():.3f}")
    if cv_r2.mean() < 0.1:
        print(f"  WARNING: very low performance for {label}; importances unreliable.")

    rf.fit(X, y)
    perm = permutation_importance(
        rf, X, y, n_repeats=30, random_state=SEED, scoring="r2", n_jobs=-1,
    )
    imp = np.clip(perm.importances_mean, 0, None)  # negatives -> 0 before scaling
    pct = 100 * imp / imp.sum() if imp.sum() > 0 else imp

    out = pd.DataFrame({
        "param": X.columns,
        "importance_pct": pct,
    }).sort_values("importance_pct", ascending=True).reset_index(drop=True)
    return out, cv_r2.mean()


# --------------------------------------------------------------------------- #
# Load data
# --------------------------------------------------------------------------- #
frames = {}
for year, path in YEAR_FILES.items():
    frames[year] = pd.read_csv(path)

sample = next(iter(frames.values()))
outcome_col = find_outcome_column(sample)
predictor_cols = find_predictor_columns(sample, outcome_col)

print("=" * 60)
print(f"Outcome column   : {outcome_col}")
print("Predictor columns -> label  [category]:")
for p in predictor_cols:
    print(f"  {p:10s} -> {pretty(p):24s} [{PARAM_CATEGORY.get(p, 'uncategorized')}]")
print("=" * 60)

# --------------------------------------------------------------------------- #
# Fit per year
# --------------------------------------------------------------------------- #
results = {}
for year, df in frames.items():
    X = df[predictor_cols].copy()
    y = df[outcome_col].to_numpy()
    results[year] = fit_and_importance(X, y, year)

# --------------------------------------------------------------------------- #
# Figure: single panel, grouped horizontal bars (2002 vs 2022 per parameter)
# --------------------------------------------------------------------------- #
import matplotlib.colors as mcolors

MUTED_GRAY = "#6b6b6b"
BLUE = "#4A7FC1"     # Setup group color
ORANGE = "#E07B3F"   # Behavioral group color
BAND_GRAY = "#F2F2F2"


def lighten(color, amount=0.45):
    """Blend `color` toward white by `amount` (0 = unchanged, 1 = white)."""
    r, g, b = mcolors.to_rgb(color)
    return (r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount)


# Four rows, top-to-bottom, with the group each belongs to and the raw params
# whose importances are summed for that row.
ROWS = [
    ("Ideological\ndeterminism (β)", "Setup",      BLUE,   ["beta"]),
    ("Ideological\ntolerance (τ̂)",   "Setup",      BLUE,   ["tau_hat"]),
    ("Belief\nupdating\n(ρπ + α)",     "Behavioral", ORANGE, ["rho_pi", "alpha"]),
    ("Loyalty\ncost (μ)",             "Behavioral", ORANGE, ["mu"]),
]


def grouped_value(imp_df, params):
    pct = dict(zip(imp_df["param"], imp_df["importance_pct"]))
    return sum(pct.get(p, 0.0) for p in params)


def fmt(val):
    return f"{round(val)}%" if val >= 5 else f"<{max(1, round(val))}%"


# Row y-centers (top-to-bottom). Normal row gap = 1.0; the gap at the section
# break (between rows 2 and 3) is 1.8 (>1.5x) to make the split obvious.
ROW_Y = [4.8, 3.8, 2.0, 1.0]
BAR_H = 0.28
OFFSET = 0.17               # half-distance between the paired bars
imp02 = results["2002"][0]
imp22 = results["2022"][0]

fig, ax = plt.subplots(figsize=(14, 7))

# Shaded background bands per group (very light gray), drawn behind everything.
def band(rows_y, pad_top=0.55, pad_bot=0.55):
    return min(rows_y) - pad_bot, max(rows_y) + pad_top

for grp_rows in ([ROW_Y[0], ROW_Y[1]], [ROW_Y[2], ROW_Y[3]]):
    lo, hi = band(grp_rows)
    ax.axhspan(lo, hi, xmin=0, xmax=1, color=BAND_GRAY, zorder=0)

# Bars: 2002 (lighter shade, upper) and 2022 (full color, lower) per row.
for ry, (label, grp, color, params) in zip(ROW_Y, ROWS):
    v02 = grouped_value(imp02, params)
    v22 = grouped_value(imp22, params)
    ax.barh(ry + OFFSET, v02, height=BAR_H, color=lighten(color), zorder=3)
    ax.barh(ry - OFFSET, v22, height=BAR_H, color=color, zorder=3)
    # Value labels at the end of each bar.
    ax.text(v02 + 1.2, ry + OFFSET, fmt(v02), va="center", ha="left",
            fontsize=12, color=NAVY)
    ax.text(v22 + 1.2, ry - OFFSET, fmt(v22), va="center", ha="left",
            fontsize=12, color=NAVY)

# Group labels ("SETUP" / "BEHAVIORAL") in the group color, just above each band.
for grp_rows, grp_label, grp_color in (
    ([ROW_Y[0], ROW_Y[1]], "Setup parameters", BLUE),
    ([ROW_Y[2], ROW_Y[3]], "Behavioral parameters", ORANGE),
):
    lo, hi = band(grp_rows)
    ax.text(1.5, hi + 0.08, grp_label.upper(), ha="left", va="bottom",
            fontsize=16, style="italic", fontweight="bold", color=grp_color,
            zorder=5)

# Y tick labels = parameter names.
ax.set_yticks(ROW_Y)
ax.set_yticklabels([r[0] for r in ROWS], fontsize=12, fontweight="bold")
ax.set_ylim(0.3, 5.7)  # high y at top (no inversion -> first row on top)

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
