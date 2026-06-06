"""
empirical_diagnostics.py
------------------------
Mechanism diagnostics for the empirical 2002 / 2022 replay.

Purpose
-------
Before interpreting candidate-level outputs we need to know whether the
strategic mechanism activates *at all* under empirical configurations:

    Given empirical party positions, voter ideology and poll signals, do
    plausible shared behavioural draws generate non-trivial triggering,
    switching and coordination in BOTH 2002 and 2022?

This is a read-only, post-hoc analysis.  It consumes the CSVs already written
by ``empirical_2002_2022.py`` (``empirical_runs_<year>.csv``) and changes
nothing about the model, the trigger rule, the outcome definitions, or the
simulation design.

Outputs (data/)
---------------
    empirical_diagnostics_<year>.csv   tidy per-draw diagnostic table
    empirical_activation_summary.csv   activation shares by year + shared draws

Figures (figures/)
------------------
    fig_diag_region_<year>   trigger & switching rate over (tau_hat, mu)
    fig_diag_alpha_rhopi      rate summarised over alpha and rho_pi

Usage
-----
    python analysis/empirical_diagnostics.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DATA_DIR = REPO / "data"
FIG_DIR = REPO / "figures"
FIG_DIR.mkdir(exist_ok=True)

YEARS = (2002, 2022)
YEAR_COLORS = {2002: "#4C72B0", 2022: "#C44E52"}

# Behavioural parameter ranges (mirror the runner, for plot axes/bins).
TAU_RANGE = (0.5, 3.0)
MU_RANGE = (0.0, 1.0)
ALPHA_RANGE = (0.0, 0.9)
RHO_PI_RANGE = (5.0, 200.0)

# Activation thresholds for trigger_rate / switching_rate (as fractions).
THRESHOLDS = (0.01, 0.05, 0.10)

# The requested tidy diagnostic columns, mapped from empirical_runs columns.
_DIAG_MAP = {
    "tau_hat": "tau_hat",
    "rho_pi": "rho_pi",
    "alpha": "alpha",
    "mu": "mu",
    "trigger_rate": "trigger_rate",
    "switching_rate": "switching_rate",
    "conditional_switching_rate": "conditional_switching_rate",
    "delta_CENP": "delta_cenp",
    "final_ENP": "enp_final",
    "cliff_location": "cliff_location",
    "RMSE": "rmse",
    "MAE": "mae",
}

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


# =========================================================================== #
#  LOADING                                                                     #
# =========================================================================== #

def load_runs(year: int) -> pd.DataFrame:
    path = DATA_DIR / f"empirical_runs_{year}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run empirical_2002_2022.py first."
        )
    return pd.read_csv(path)


def tidy_diagnostics(year: int) -> pd.DataFrame:
    """Select + rename the requested per-draw diagnostic columns."""
    runs = load_runs(year)
    out = pd.DataFrame({"draw": runs["draw"]})
    for new, src in _DIAG_MAP.items():
        out[new] = runs[src]
    out.insert(1, "year", year)
    return out


# =========================================================================== #
#  ACTIVATION SUMMARIES                                                        #
# =========================================================================== #

def _activation_row(label: str, df: pd.DataFrame, n: int) -> dict:
    row = {"group": label, "n_draws": n}
    for thr in THRESHOLDS:
        pct = int(round(thr * 100))
        row[f"trigger_gt_{pct}pct"] = float((df["trigger_rate"] > thr).mean())
        row[f"switch_gt_{pct}pct"] = float((df["switching_rate"] > thr).mean())
    return row


def activation_summary(diags: dict) -> pd.DataFrame:
    """
    Build the activation-share table.

    Rows:
        one per year (share of that year's draws above each threshold);
        'shared_either' / 'shared_both' for the same draw index across both
        years (joint activation under a shared behavioural draw).
    """
    rows = []

    # Per-year shares.
    for year in YEARS:
        df = diags[year]
        rows.append(_activation_row(str(year), df, len(df)))

    # Shared-draw joint activation (same parameter draw in both years).
    merged = diags[YEARS[0]].merge(
        diags[YEARS[1]], on="draw", suffixes=(f"_{YEARS[0]}", f"_{YEARS[1]}")
    )
    n = len(merged)
    both = {"group": "shared_both", "n_draws": n}
    either = {"group": "shared_either", "n_draws": n}
    for thr in THRESHOLDS:
        pct = int(round(thr * 100))
        for metric, key in (("trigger_rate", "trigger"),
                            ("switching_rate", "switch")):
            a = merged[f"{metric}_{YEARS[0]}"] > thr
            b = merged[f"{metric}_{YEARS[1]}"] > thr
            both[f"{key}_gt_{pct}pct"] = float((a & b).mean())
            either[f"{key}_gt_{pct}pct"] = float((a | b).mean())
    rows.append(both)
    rows.append(either)

    return pd.DataFrame(rows)


# Minimum draws per bin; bins below this are masked (shown grey) so sparse
# regions are not over-interpreted.
MIN_BIN_COUNT = 3
N_BINS = 6


def _save(fig, name: str) -> None:
    for ext in ("png", "pdf"):
        fig.savefig(FIG_DIR / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote figures/{name}.png + .pdf")


# =========================================================================== #
#  PARAMETER-REGION PLOTS                                                       #
# =========================================================================== #

def _binned_stats(df: pd.DataFrame, xcol: str, ycol: str, vcol: str,
                  xrange: tuple, yrange: tuple, nbins: int = N_BINS):
    """
    Mean and count of vcol over an nbins x nbins grid of (xcol, ycol).

    Returns (mean_grid, count_grid, xedges, yedges).  mean_grid is NaN where a
    bin is empty; counts let the caller mask thinly-sampled bins.
    """
    xedges = np.linspace(*xrange, nbins + 1)
    yedges = np.linspace(*yrange, nbins + 1)
    mean_grid = np.full((nbins, nbins), np.nan)
    count_grid = np.zeros((nbins, nbins), dtype=int)
    xi = np.clip(np.digitize(df[xcol], xedges) - 1, 0, nbins - 1)
    yi = np.clip(np.digitize(df[ycol], yedges) - 1, 0, nbins - 1)
    vals = df[vcol].to_numpy()
    for ix in range(nbins):
        for iy in range(nbins):
            m = (xi == ix) & (yi == iy)
            count_grid[iy, ix] = int(m.sum())
            if m.any():
                mean_grid[iy, ix] = vals[m].mean()
    return mean_grid, count_grid, xedges, yedges


def fig_region_taumu(diags: dict, min_count: int = MIN_BIN_COUNT) -> None:
    """
    Trigger, switching and conditional-switching rate over (tau_hat, mu).

    Rows = metric, columns = year.  Each metric (row) shares one colour scale
    across years so 2002 and 2022 are directly comparable.  Bins with fewer
    than ``min_count`` draws are masked (grey); the per-bin draw count is
    printed in each cell.
    """
    metrics = [("trigger_rate", "trigger rate"),
               ("switching_rate", "switching rate"),
               ("conditional_switching_rate", "conditional switching rate")]
    cmap = plt.cm.viridis.copy()
    cmap.set_bad("#dddddd")

    fig, axes = plt.subplots(len(metrics), len(YEARS),
                             figsize=(5.2 * len(YEARS), 4.3 * len(metrics)))
    for i, (vcol, label) in enumerate(metrics):
        # Compute both years' grids first to share a colour scale per row.
        grids = {}
        vmax = 0.0
        for year in YEARS:
            g, c, xe, ye = _binned_stats(diags[year], "tau_hat", "mu", vcol,
                                         TAU_RANGE, MU_RANGE)
            g = np.ma.masked_where((c < min_count) | np.isnan(g), g)
            grids[year] = (g, c, xe, ye)
            if g.count() > 0:
                vmax = max(vmax, float(g.max()))
        vmax = vmax if vmax > 0 else 1.0

        for j, year in enumerate(YEARS):
            ax = axes[i, j]
            g, c, xe, ye = grids[year]
            im = ax.imshow(g, origin="lower", aspect="auto", cmap=cmap,
                           extent=[xe[0], xe[-1], ye[0], ye[-1]],
                           vmin=0, vmax=vmax)
            # Annotate per-bin draw counts.
            for iy in range(g.shape[0]):
                for ix in range(g.shape[1]):
                    cx = 0.5 * (xe[ix] + xe[ix + 1])
                    cy = 0.5 * (ye[iy] + ye[iy + 1])
                    ax.text(cx, cy, str(c[iy, ix]), ha="center", va="center",
                            fontsize=6, color="white")
            ax.scatter(diags[year]["tau_hat"], diags[year]["mu"], s=8,
                       c="white", edgecolor="black", lw=0.3, alpha=0.5)
            ax.set_xlabel(r"$\hat{\tau}$")
            ax.set_ylabel(r"$\mu$")
            ax.set_title(f"{year}: {label}")
            cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
            cb.set_label(label)
    fig.suptitle(r"Mechanism activation over $\hat{\tau}\times\mu$  "
                 f"(bins with <{min_count} draws masked; cell = draw count)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    _save(fig, "fig_diag_region_taumu")


def fig_alpha_rhopi_scatter(diags: dict) -> None:
    """
    Per-draw scatter of trigger / switching rate against alpha and rho_pi.

    Scatter (not lines) is used deliberately: with sparse draws a line would
    imply a continuity the data do not support.  Points are coloured by year.
    """
    params = [("alpha", r"$\alpha$"), ("rho_pi", r"$\rho_\pi$")]
    metrics = [("trigger_rate", "trigger rate"),
               ("switching_rate", "switching rate")]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for i, (vcol, vlabel) in enumerate(metrics):
        for j, (pcol, plabel) in enumerate(params):
            ax = axes[i, j]
            for year in YEARS:
                df = diags[year]
                ax.scatter(df[pcol], df[vcol], s=28,
                           color=YEAR_COLORS[year], edgecolor="black",
                           lw=0.3, alpha=0.75, label=str(year))
            ax.set_xlabel(plabel)
            ax.set_ylabel(vlabel)
            ax.set_ylim(bottom=0)
            if i == 0 and j == 0:
                ax.legend(frameon=False)
    fig.suptitle(r"Per-draw activation vs $\alpha$ and $\rho_\pi$",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    _save(fig, "fig_diag_alpha_rhopi")


# =========================================================================== #
#  SHARED-DRAW ACTIVATION                                                       #
# =========================================================================== #

def shared_activating_draws(diags: dict) -> pd.DataFrame:
    """
    Identify shared behavioural draws (same draw index in both years) where the
    mechanism activates jointly, under three criteria:

        both_trigger_gt_1pct : trigger_rate > 1% in BOTH years
        both_trigger_gt_5pct : trigger_rate > 5% in BOTH years
        both_switch_gt_1pct  : switching_rate > 1% in BOTH years

    Returns the subset of draws meeting at least one criterion, with the shared
    parameters, both years' rates, and the three boolean flags.
    """
    y0, y1 = YEARS
    m = diags[y0].merge(diags[y1], on="draw", suffixes=(f"_{y0}", f"_{y1}"))

    flags = pd.DataFrame({"draw": m["draw"]})
    # Shared parameters (identical across years for a given draw).
    for p in ("tau_hat", "rho_pi", "alpha", "mu"):
        flags[p] = m[f"{p}_{y0}"]
    for metric in ("trigger_rate", "switching_rate",
                   "conditional_switching_rate"):
        flags[f"{metric}_{y0}"] = m[f"{metric}_{y0}"]
        flags[f"{metric}_{y1}"] = m[f"{metric}_{y1}"]

    flags["both_trigger_gt_1pct"] = (
        (m[f"trigger_rate_{y0}"] > 0.01) & (m[f"trigger_rate_{y1}"] > 0.01))
    flags["both_trigger_gt_5pct"] = (
        (m[f"trigger_rate_{y0}"] > 0.05) & (m[f"trigger_rate_{y1}"] > 0.05))
    flags["both_switch_gt_1pct"] = (
        (m[f"switching_rate_{y0}"] > 0.01) & (m[f"switching_rate_{y1}"] > 0.01))

    any_flag = (flags["both_trigger_gt_1pct"] | flags["both_trigger_gt_5pct"]
                | flags["both_switch_gt_1pct"])
    return flags[any_flag].reset_index(drop=True)


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #

def main() -> None:
    print("Building mechanism diagnostics...")
    diags = {}
    for year in YEARS:
        d = tidy_diagnostics(year)
        d.to_csv(DATA_DIR / f"empirical_diagnostics_{year}.csv", index=False)
        print(f"  wrote data/empirical_diagnostics_{year}.csv ({len(d)} draws)")
        diags[year] = d

    summary = activation_summary(diags)
    summary.to_csv(DATA_DIR / "empirical_activation_summary.csv", index=False)
    print("  wrote data/empirical_activation_summary.csv")
    print("\nActivation summary:")
    print(summary.to_string(index=False))

    shared = shared_activating_draws(diags)
    shared.to_csv(DATA_DIR / "empirical_shared_activating_draws.csv",
                  index=False)
    print(f"\n  wrote data/empirical_shared_activating_draws.csv "
          f"({len(shared)} jointly-activating draws)")

    fig_region_taumu(diags)
    fig_alpha_rhopi_scatter(diags)
    print("Done.")


if __name__ == "__main__":
    main()
