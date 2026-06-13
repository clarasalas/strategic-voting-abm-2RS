"""
empirical_figures.py
--------------------
Thesis-ready figures for the empirical 2002 / 2022 replay.

Reads the CSVs produced by ``empirical_2002_2022.py`` and writes high-resolution
PNG + PDF figures to ``figures/``.

Design conventions
------------------
- Candidates are always ordered left-to-right by ideological position.
- Candidate colours come from a single Spectral_r mapping of position on
  [-1, 1], so the SAME colour means the same ideological location in every plot
  and across both years (left = red, right = blue).
- Years (when compared as groups) use two fixed, consistent colours.
- Clean spacing, readable labels, no cluttered legends; colour carries meaning.

Figures
-------
    fig_sim_vs_actual           scatter of mean simulated vs actual share
    fig_candidate_shares_<year> mean final share + p05-p95 + actual marker
    fig_candidate_change_<year> mean change first-signal -> final
    fig_candidate_topk_<year>   top-2/3/4 probability by candidate
    fig_enp_deltacenp           ENP and ΔCENP distributions, 2002 vs 2022
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DATA_DIR = REPO / "data"
FIG_DIR = REPO / "figures"
FIG_DIR.mkdir(exist_ok=True)

YEARS = (2002, 2022)
YEAR_COLORS = {2002: "#4C72B0", 2022: "#C44E52"}

# Position colour mapping: shared across all plots and both years.
POS_NORM = Normalize(vmin=-1.0, vmax=1.0)
POS_CMAP = plt.cm.Spectral_r

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e6e6e6",
    "grid.linewidth": 0.6,
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


# =========================================================================== #
#  HELPERS                                                                     #
# =========================================================================== #

def pos_colors(positions) -> np.ndarray:
    """Spectral_r colours for ideological positions on [-1, 1]."""
    return POS_CMAP(POS_NORM(np.asarray(positions, dtype=float)))


def _tagged(stem: str, tag: str, ext: str) -> str:
    """Append a tag to a filename stem: 'stem_tag.ext' (or 'stem.ext' if no tag)."""
    return f"{stem}_{tag}.{ext}" if tag else f"{stem}.{ext}"


def save(fig, name: str, tag: str = "") -> None:
    """Save a figure as both PNG and PDF in figures/, tag-suffixed."""
    name = _tagged(name, tag, "").rstrip(".")
    for ext in ("png", "pdf"):
        fig.savefig(FIG_DIR / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote figures/{name}.png + .pdf")


def _resolve_data_path(stem: str, year: int, tag: str) -> Path:
    """
    Locate a data CSV (stem = 'empirical_candidate_shares' or 'empirical_runs')
    for a given year and tag.

    The runner writes the mode suffix *before* the year, e.g.
    ``empirical_candidate_shares_prob_signal_2002.csv``, with no ``main_``
    prefix.  To be forgiving we try several conventions and also strip a leading
    ``main_``/``main`` from the tag, so all of these resolve to the same file:

        --tag main_prob_signal
        --tag prob_signal
        --tag main_prob_signal_mu0

    Returns the first existing path, else raises FileNotFoundError listing the
    patterns tried.
    """
    if not tag:
        candidates = [f"{stem}_{year}.csv"]
    else:
        variants = [tag]
        for prefix in ("main_", "main"):
            if tag.startswith(prefix):
                variants.append(tag[len(prefix):].lstrip("_"))
        candidates = []
        for t in dict.fromkeys(variants):  # de-dup, preserve order
            candidates += [
                f"{stem}_{t}_{year}.csv",   # suffix-before-year (runner)
                f"{stem}_{year}_{t}.csv",   # suffix-after-year
            ]

    for name in candidates:
        path = DATA_DIR / name
        if path.exists():
            return path

    tried = "\n  ".join(candidates)
    raise FileNotFoundError(
        f"No {stem} file found for year={year}, tag={tag!r}. "
        f"Run empirical_2002_2022.py first. Tried:\n  {tried}"
    )


def load_candidates(year: int, tag: str = "") -> pd.DataFrame:
    df = pd.read_csv(_resolve_data_path("empirical_candidate_shares", year, tag))
    return df.sort_values("position", kind="stable").reset_index(drop=True)


def load_runs(year: int, tag: str = "") -> pd.DataFrame:
    return pd.read_csv(_resolve_data_path("empirical_runs", year, tag))


def _position_colorbar(fig, ax):
    sm = ScalarMappable(norm=POS_NORM, cmap=POS_CMAP)
    cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label("ideological position  (left $\\rightarrow$ right)")
    cb.set_ticks([-1, 0, 1])
    cb.set_ticklabels(["left", "centre", "right"])


# =========================================================================== #
#  FIGURE: simulated vs actual scatter                                         #
# =========================================================================== #

def fig_sim_vs_actual(tag: str = "") -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))
    for ax, year in zip(axes, YEARS):
        df = load_candidates(year, tag)
        colors = pos_colors(df["position"])
        hi = max(df["actual_share"].max(), df["mean_final_share"].max()) * 1.1
        ax.plot([0, hi], [0, hi], ls="--", lw=1, color="#999999", zorder=0)
        ax.errorbar(
            df["actual_share"], df["mean_final_share"],
            yerr=[(df["mean_final_share"] - df["p05_final_share"]).clip(lower=0),
                  (df["p95_final_share"] - df["mean_final_share"]).clip(lower=0)],
            fmt="none", ecolor="#cccccc", lw=1, zorder=1,
        )
        ax.scatter(df["actual_share"], df["mean_final_share"],
                   c=colors, s=70, edgecolor="black", lw=0.5, zorder=2)
        for _, r in df.iterrows():
            ax.annotate(r["party"], (r["actual_share"], r["mean_final_share"]),
                        textcoords="offset points", xytext=(4, 4), fontsize=7)
        ax.set_title(f"{year}")
        ax.set_xlabel("actual first-round share")
        ax.set_ylabel("mean simulated final share")
        ax.set_xlim(0, hi)
        ax.set_ylim(0, hi)
        ax.set_aspect("equal")
    fig.suptitle("Simulated vs actual first-round shares",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig_sim_vs_actual", tag)


# =========================================================================== #
#  FIGURE: candidate final shares with intervals + actual                      #
# =========================================================================== #

def fig_candidate_shares(year: int, tag: str = "") -> None:
    df = load_candidates(year, tag)
    x = np.arange(len(df))
    colors = pos_colors(df["position"])
    fig, ax = plt.subplots(figsize=(max(8, 0.7 * len(df)), 5))
    ax.bar(x, df["mean_final_share"], color=colors, edgecolor="black",
           lw=0.4, width=0.7, zorder=2)
    ax.errorbar(
        x, df["mean_final_share"],
        yerr=[(df["mean_final_share"] - df["p05_final_share"]).clip(lower=0),
              (df["p95_final_share"] - df["mean_final_share"]).clip(lower=0)],
        fmt="none", ecolor="#444444", lw=1.1, capsize=3, zorder=3,
    )
    ax.scatter(x, df["actual_share"], marker="D", color="black", s=42,
               zorder=4, label="actual result")
    ax.set_xticks(x)
    ax.set_xticklabels(df["party"], rotation=45, ha="right")
    ax.set_ylabel("first-round share")
    ax.set_title(f"{year}: simulated final share (mean, p05–p95) vs actual")
    ax.legend(frameon=False, loc="upper left")
    _position_colorbar(fig, ax)
    fig.tight_layout()
    save(fig, f"fig_candidate_shares_{year}", tag)


# =========================================================================== #
#  FIGURE: candidate change from first signal to final                         #
# =========================================================================== #

def fig_candidate_change(year: int, tag: str = "") -> None:
    df = load_candidates(year, tag)
    x = np.arange(len(df))
    colors = pos_colors(df["position"])
    fig, ax = plt.subplots(figsize=(max(8, 0.7 * len(df)), 5))
    ax.bar(x, df["mean_change_first_to_final"], color=colors,
           edgecolor="black", lw=0.4, width=0.7, zorder=2)
    ax.errorbar(
        x, df["mean_change_first_to_final"],
        yerr=[(df["mean_change_first_to_final"] - df["p05_change"]).clip(lower=0),
              (df["p95_change"] - df["mean_change_first_to_final"]).clip(lower=0)],
        fmt="none", ecolor="#444444", lw=1.1, capsize=3, zorder=3,
    )
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(df["party"], rotation=45, ha="right")
    ax.set_ylabel("share change  (final − first signal)")
    ax.set_title(f"{year}: mean simulated change from first signal to final")
    _position_colorbar(fig, ax)
    fig.tight_layout()
    save(fig, f"fig_candidate_change_{year}", tag)


# =========================================================================== #
#  FIGURE: top-k probabilities by candidate                                    #
# =========================================================================== #

def fig_candidate_topk(year: int, tag: str = "") -> None:
    df = load_candidates(year, tag)
    x = np.arange(len(df))
    colors = pos_colors(df["position"])
    keys = [("prob_top2", "P(top 2)"), ("prob_top3", "P(top 3)"),
            ("prob_top4", "P(top 4)")]
    fig, axes = plt.subplots(3, 1, figsize=(max(8, 0.7 * len(df)), 9),
                             sharex=True)
    for ax, (key, label) in zip(axes, keys):
        ax.bar(x, df[key], color=colors, edgecolor="black", lw=0.4,
               width=0.7)
        ax.set_ylim(0, 1.02)
        ax.set_ylabel(label)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(df["party"], rotation=45, ha="right")
    axes[0].set_title(f"{year}: probability of finishing in the top k")
    _position_colorbar(fig, axes[1])
    fig.tight_layout()
    save(fig, f"fig_candidate_topk_{year}", tag)


# =========================================================================== #
#  FIGURE: ENP and ΔCENP distributions, 2002 vs 2022                            #
# =========================================================================== #

def fig_enp_deltacenp(tag: str = "") -> None:
    runs = {y: load_runs(y, tag) for y in YEARS}
    metrics = [("enp_final", "ENP (final)"),
               ("delta_enp", "ΔENP (final − sincere)"),
               ("delta_cenp", "ΔCENP (coordination gain)")]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    for ax, (key, label) in zip(axes, metrics):
        data = [runs[y][key].to_numpy() for y in YEARS]
        parts = ax.violinplot(data, showmeans=True, showextrema=False)
        for body, y in zip(parts["bodies"], YEARS):
            body.set_facecolor(YEAR_COLORS[y])
            body.set_alpha(0.65)
            body.set_edgecolor("black")
        if "cmeans" in parts:
            parts["cmeans"].set_color("black")
        ax.set_xticks([1, 2])
        ax.set_xticklabels([str(y) for y in YEARS])
        ax.set_title(label)
    fig.suptitle("Coordination / fragmentation: 2002 vs 2022",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig_enp_deltacenp", tag)


# =========================================================================== #
#  CONTACT SHEET  (temporary preview helper)                                   #
# =========================================================================== #

def contact_sheet(names: list) -> None:
    """
    Tile all generated PNGs into one preview image for fast eyeballing.
    Temporary helper — safe to delete once the layouts are settled.
    """
    paths = [FIG_DIR / f"{n}.png" for n in names]
    paths = [p for p in paths if p.exists()]
    if not paths:
        print("  no figures found to tile.")
        return
    ncols = 2
    nrows = int(np.ceil(len(paths) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 5.2 * nrows))
    axes = np.atleast_1d(axes).ravel()
    for ax, p in zip(axes, paths):
        ax.imshow(mpimg.imread(p))
        ax.set_title(p.stem, fontsize=10)
        ax.axis("off")
    for ax in axes[len(paths):]:
        ax.axis("off")
    fig.tight_layout()
    out = FIG_DIR / "_contact_sheet.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"  wrote {out.relative_to(REPO)}")


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contact-sheet", action="store_true",
                    help="also tile all PNGs into figures/_contact_sheet.png")
    ap.add_argument(
        "--tag", default="",
        help="build figures from tagged empirical output files (e.g. "
             "'main_prob_signal'). Default: baseline empirical_*_<year>.csv. "
             "Figures are suffixed with the tag so they do not overwrite "
             "baseline figures.",
    )
    args = ap.parse_args()
    tag = args.tag

    label = f" [tag={tag}]" if tag else ""
    print(f"Building empirical figures...{label}")
    names = ["fig_sim_vs_actual", "fig_enp_deltacenp"]
    fig_sim_vs_actual(tag)
    fig_enp_deltacenp(tag)
    for year in YEARS:
        fig_candidate_shares(year, tag)
        fig_candidate_change(year, tag)
        fig_candidate_topk(year, tag)
        names += [f"fig_candidate_shares_{year}",
                  f"fig_candidate_change_{year}",
                  f"fig_candidate_topk_{year}"]
    if args.contact_sheet:
        print("Tiling contact sheet...")
        contact_sheet([_tagged(n, tag, "").rstrip(".") for n in names])
    print("Done.")


if __name__ == "__main__":
    main()
