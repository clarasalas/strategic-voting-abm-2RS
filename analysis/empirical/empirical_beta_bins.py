"""
empirical_beta_bins.py
----------------------
Candidate-level diagnostics by beta bin for probabilistic sincere
initialization.

Question
--------
Does the ideological-sharpness parameter beta control the model's systematic
mis-allocation of first-round share?  Specifically, do larger beta values
reduce the *over*-weighting of the big convergent candidates (RE / PS / MDC)
and the *under*-weighting of the polar / smaller candidates (LFI / RN / FN)?

To answer this we split the probabilistic draws into three beta bins
(low / medium / high) and, within each bin, report:

    - mean simulated final share by candidate (vs the actual result);
    - RMSE and MAE of the final share against the actual result.

Input
-----
The per-draw, per-candidate table written by the runner:

    data/empirical_candidate_draws<suffix>_<year>.csv

Re-run the probabilistic sweep first if this file is missing, e.g.

    python analysis/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source signal

Outputs (data/, figures/  -- all tag-suffixed)
----------------------------------------------
    empirical_beta_bins_candidates_<tag>_<year>.csv  mean final share by
                                                     candidate x beta bin
    empirical_beta_bins_error_<tag>_<year>.csv       RMSE / MAE by beta bin
    fig_beta_bins_<year>_<tag>                       grouped bar: mean final
                                                     share by candidate across
                                                     bins, with actual overlaid

Usage
-----
    python analysis/empirical_beta_bins.py --tag main_prob_signal
    python analysis/empirical_beta_bins.py --tag main_prob_signal --bins quantile
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DATA_DIR = REPO / "data"
FIG_DIR = REPO / "figures"
FIG_DIR.mkdir(exist_ok=True)

YEARS = (2002, 2022)
BETA_RANGE = (0.0, 20.0)          # mirrors the runner's probabilistic range
BIN_LABELS = ("low", "medium", "high")

# Candidates of interest for the over/under-weighting question.  Membership is
# by party label; missing labels for a given year are simply skipped.
OVER_WEIGHTED = ("RE", "PS", "MDC")    # big convergent candidates
UNDER_WEIGHTED = ("LFI", "RN", "FN")   # polar / smaller candidates

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Shades for the three bins (light -> dark).
BIN_COLORS = {"low": "#bdd7e7", "medium": "#6baed6", "high": "#08519c"}


# =========================================================================== #
#  LOADING                                                                     #
# =========================================================================== #

def _resolve_draws_path(year: int, tag: str) -> Path:
    """
    Locate the per-draw candidate table, tolerating the runner's
    suffix-before-year naming and a leading ``main_`` in the tag (mirrors the
    resolution used in empirical_figures.py / empirical_diagnostics.py).
    """
    stem = "empirical_candidate_draws"
    if not tag:
        candidates = [f"{stem}_{year}.csv"]
    else:
        variants = [tag]
        for prefix in ("main_", "main"):
            if tag.startswith(prefix):
                variants.append(tag[len(prefix):].lstrip("_"))
        candidates = []
        for t in dict.fromkeys(variants):
            candidates += [f"{stem}_{t}_{year}.csv", f"{stem}_{year}_{t}.csv"]

    for name in candidates:
        path = DATA_DIR / name
        if path.exists():
            return path

    tried = "\n  ".join(candidates)
    raise FileNotFoundError(
        f"No {stem} file found for year={year}, tag={tag!r}. Run the "
        f"probabilistic sweep in empirical_2002_2022.py first. Tried:\n  {tried}"
    )


def load_draws(year: int, tag: str) -> pd.DataFrame:
    df = pd.read_csv(_resolve_draws_path(year, tag))
    if "beta" not in df.columns:
        raise ValueError(
            f"{_resolve_draws_path(year, tag).name} has no 'beta' column; "
            f"this diagnostic is only meaningful for probabilistic runs."
        )
    return df


# =========================================================================== #
#  BETA BINNING                                                                #
# =========================================================================== #

def assign_beta_bin(df: pd.DataFrame, scheme: str) -> pd.DataFrame:
    """
    Add a categorical 'beta_bin' column (low/medium/high) plus 'bin_lo'/'bin_hi'
    edges.

    scheme = "fixed"    -> equal thirds of the configured BETA_RANGE.
    scheme = "quantile" -> terciles of the observed beta values (per year).
    """
    beta = df["beta"].to_numpy(dtype=float)
    if scheme == "fixed":
        edges = np.linspace(BETA_RANGE[0], BETA_RANGE[1], len(BIN_LABELS) + 1)
    elif scheme == "quantile":
        qs = np.linspace(0, 1, len(BIN_LABELS) + 1)
        edges = np.quantile(np.unique(beta), qs)
        edges[0], edges[-1] = beta.min(), beta.max()
    else:
        raise ValueError("scheme must be 'fixed' or 'quantile'.")

    # np.digitize with right-open bins; clamp into [0, nbins-1].
    idx = np.clip(np.digitize(beta, edges[1:-1], right=False),
                  0, len(BIN_LABELS) - 1)
    out = df.copy()
    out["beta_bin"] = [BIN_LABELS[i] for i in idx]
    out["bin_lo"] = edges[idx]
    out["bin_hi"] = edges[idx + 1]
    return out


# =========================================================================== #
#  AGGREGATION                                                                 #
# =========================================================================== #

def candidate_means_by_bin(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mean simulated final share by candidate within each beta bin, wide format.

    Rows = candidate (left-to-right by position); columns = mean_final_<bin>,
    plus actual_share, first_signal_share, position, block, and the gap of each
    bin's mean to the actual result.
    """
    # Static per-candidate info (constant across draws).
    info = (df.groupby("party", sort=False)
              .agg(block=("block", "first"),
                   position=("position", "first"),
                   actual_share=("actual_share", "first"),
                   first_signal_share=("first_signal_share", "first")))

    means = (df.groupby(["party", "beta_bin"])["final_share"].mean()
               .unstack("beta_bin"))
    means = means.reindex(columns=list(BIN_LABELS))
    means.columns = [f"mean_final_{c}" for c in means.columns]

    table = info.join(means).reset_index()
    table = table.sort_values("position", kind="stable").reset_index(drop=True)

    for c in BIN_LABELS:
        col = f"mean_final_{c}"
        if col in table.columns:
            table[f"gap_to_actual_{c}"] = table[col] - table["actual_share"]
    return table


def error_by_bin(df: pd.DataFrame) -> pd.DataFrame:
    """
    RMSE and MAE of final share vs actual, by beta bin.

    Error is computed per draw (across that draw's candidates), then averaged
    over draws in the bin — so each draw weighs equally regardless of K.
    """
    def _per_draw(g):
        err = g["final_share"].to_numpy() - g["actual_share"].to_numpy()
        return pd.Series({"rmse": np.sqrt(np.mean(err ** 2)),
                          "mae": np.mean(np.abs(err))})

    per_draw = (df.groupby(["beta_bin", "draw"], group_keys=True)
                  .apply(_per_draw, include_groups=False)
                  .reset_index())
    beta_stats = (df.groupby("beta_bin")["beta"]
                    .agg(n_draws="nunique", beta_mean="mean",
                         beta_min="min", beta_max="max"))

    out = (per_draw.groupby("beta_bin")
                   .agg(RMSE=("rmse", "mean"), MAE=("mae", "mean"))
                   .join(beta_stats))
    out = out.reindex(list(BIN_LABELS)).reset_index()
    return out


# =========================================================================== #
#  FIGURE                                                                       #
# =========================================================================== #

def fig_beta_bins(year: int, table: pd.DataFrame, tag: str) -> None:
    """Grouped bars: mean final share by candidate across beta bins + actual."""
    parties = table["party"].tolist()
    x = np.arange(len(parties))
    present_bins = [c for c in BIN_LABELS if f"mean_final_{c}" in table.columns]
    width = 0.8 / max(len(present_bins), 1)

    fig, ax = plt.subplots(figsize=(max(9, 0.8 * len(parties)), 5.2))
    for i, b in enumerate(present_bins):
        ax.bar(x + (i - (len(present_bins) - 1) / 2) * width,
               table[f"mean_final_{b}"], width=width,
               color=BIN_COLORS[b], edgecolor="black", lw=0.4,
               label=f"{b} beta")
    ax.scatter(x, table["actual_share"], marker="D", color="black", s=40,
               zorder=5, label="actual result")

    # Emphasise the candidates the question is about (bold + ▲/▼ markers).
    ax.set_xticks(x)
    labels = []
    for party in parties:
        if party in OVER_WEIGHTED:
            labels.append(f"$\\bf{{{party}}}$▲")   # over-weighted marker
        elif party in UNDER_WEIGHTED:
            labels.append(f"$\\bf{{{party}}}$▼")   # under-weighted marker
        else:
            labels.append(party)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("mean simulated final share")
    ax.set_title(f"{year}: mean final share by candidate across beta bins "
                 f"(▲ expected over-weighted, ▼ under-weighted)")
    ax.legend(frameon=False, ncol=len(present_bins) + 1, loc="upper center")
    fig.tight_layout()

    name = f"fig_beta_bins_{year}_{tag}" if tag else f"fig_beta_bins_{year}"
    for ext in ("png", "pdf"):
        fig.savefig(FIG_DIR / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote figures/{name}.png + .pdf")


# =========================================================================== #
#  FOCUSED SUMMARY                                                              #
# =========================================================================== #

def print_focus_summary(year: int, table: pd.DataFrame) -> None:
    """Print the gap-to-actual trend across bins for the target candidates."""
    present_bins = [c for c in BIN_LABELS if f"gap_to_actual_{c}" in table.columns]
    targets = [p for p in (*OVER_WEIGHTED, *UNDER_WEIGHTED)
               if p in set(table["party"])]
    if not targets:
        return
    cols = [f"gap_to_actual_{c}" for c in present_bins]
    sub = table.set_index("party").loc[targets, cols]
    sub.columns = [f"gap_{c}" for c in present_bins]
    print(f"\n  [{year}] gap to actual (mean final - actual) by beta bin:")
    print(sub.round(4).to_string())


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default="",
                    help="tag of the probabilistic run (e.g. main_prob_signal)")
    ap.add_argument("--bins", choices=["fixed", "quantile"], default="fixed",
                    help="beta binning: equal thirds of [0,20] (fixed) or "
                         "observed terciles (quantile). Default: fixed")
    args = ap.parse_args()
    tag = args.tag

    label = f" [tag={tag}, bins={args.bins}]"
    print(f"Building beta-bin candidate diagnostics...{label}")

    for year in YEARS:
        df = assign_beta_bin(load_draws(year, tag), args.bins)

        cand = candidate_means_by_bin(df)
        err = error_by_bin(df)

        suffix = f"_{tag}" if tag else ""
        cand_out = DATA_DIR / f"empirical_beta_bins_candidates{suffix}_{year}.csv"
        err_out = DATA_DIR / f"empirical_beta_bins_error{suffix}_{year}.csv"
        cand.to_csv(cand_out, index=False)
        err.to_csv(err_out, index=False)
        print(f"  wrote data/{cand_out.name}")
        print(f"  wrote data/{err_out.name}")
        print(f"\n  [{year}] RMSE / MAE by beta bin:")
        print(err.round(4).to_string(index=False))
        print_focus_summary(year, cand)

        fig_beta_bins(year, cand, tag)
    print("Done.")


if __name__ == "__main__":
    main()
