"""
behavioral_sweep_figure.py
--------------------------
Summary figures for the behavioral ΔCENP sweep: achievable coordination range
per year vs. the real poll→result value.

Reads
-----
    data/behavioral_sweep_2002.csv   (one row per draw; column mean_delta_cenp)
    data/behavioral_sweep_2022.csv
    data/behavioral_targets.csv      (delta_cenp_real per year)

One point = one parameter draw, summarized as the mean ΔCENP over its repeats
(repeats denoise; they are NOT plotted as separate points).

Figures
-------
    1. Violin plot (behavioral_sweep.png / delta_cenp_violin_validation.*):
       two violins of mean-ΔCENP across draws, navy diamond at ΔCENP_real.
    2. Interval plot (delta_cenp_interval_validation.*):
       horizontal median + 50%/90% intervals per year, navy diamond at
       ΔCENP_real with "Observed: ..." labels.

Both saved as PNG (>= 200 dpi) and PDF.

Usage
-----
    python analysis/behavioral_sweep_figure.py
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D


def _setup_font() -> None:
    """Use Open Sans if installed (incl. ~/Library/Fonts); fall back quietly."""
    user_fonts = Path.home() / "Library" / "Fonts"
    if user_fonts.exists():
        for f in user_fonts.glob("OpenSans-*.ttf"):
            try:
                fm.fontManager.addfont(str(f))
            except Exception:
                pass
    installed = {f.name for f in fm.fontManager.ttflist}
    if "Open Sans" in installed:
        plt.rcParams["font.family"] = ["Open Sans", "DejaVu Sans", "sans-serif"]
    else:
        # Closest clean sans available on macOS, else DejaVu.
        fallback = next((n for n in ("Helvetica Neue", "PT Sans", "Arial")
                         if n in installed), "DejaVu Sans")
        plt.rcParams["font.family"] = [fallback, "DejaVu Sans", "sans-serif"]


_setup_font()

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

YEARS = (2002, 2022)
COLORS = {2002: "#e8862c", 2022: "#e8862c"}    # violins: soft orange
SIM_COLOR = "#e8862c"                           # simulated intervals
OBS_COLOR = "#0a235c"                           # observed: dark navy
DATA_DIR = REPO / "data"
FIG_DIR = REPO / "figures"


def load_sweep(year: int, data_dir: Path) -> np.ndarray:
    path = data_dir / f"behavioral_sweep_{year}.csv"
    if not path.exists():
        sys.exit(f"[figure] missing sweep CSV: {path} "
                 f"(run behavioral_sweep.py for {year} first)")
    df = pd.read_csv(path)
    return df["mean_delta_cenp"].to_numpy(dtype=float)


def load_targets(data_dir: Path) -> dict:
    path = data_dir / "behavioral_targets.csv"
    if not path.exists():
        sys.exit(f"[figure] missing targets CSV: {path} "
                 f"(run behavioral_targets.py first)")
    df = pd.read_csv(path)
    return {int(r["year"]): float(r["delta_cenp_real"]) for _, r in df.iterrows()}


def save_fig(fig, stem: Path, dpi: int) -> None:
    """Save a figure as PNG and PDF, white background, tight bbox."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    for ext in (".png", ".pdf"):
        out = stem.with_suffix(ext)
        fig.savefig(out, dpi=dpi, bbox_inches="tight", facecolor="white")
        print(f"[figure] saved -> {out}")


def plot_delta_cenp_violin(samples: dict, targets: dict, stem: Path, dpi: int) -> None:
    """Figure 1: violins of simulated draws + navy diamond at real ΔCENP."""
    fig, ax = plt.subplots(figsize=(7, 5))
    positions = list(range(1, len(YEARS) + 1))

    parts = ax.violinplot([samples[y] for y in YEARS], positions=positions,
                          showmeans=False, showmedians=False, showextrema=False)
    for body, y in zip(parts["bodies"], YEARS):
        body.set_facecolor(COLORS[y])
        body.set_edgecolor(COLORS[y])
        body.set_alpha(0.55)

    print("\n=== Behavioral ΔCENP sweep: per-year summary ===")
    for pos, y in zip(positions, YEARS):
        s = samples[y]
        p05, p50, p95 = np.percentile(s, [5, 50, 95])
        real = targets[y]
        inside = bool(p05 <= real <= p95)

        ax.plot(pos, real, marker="D", color=OBS_COLOR, markersize=9,
                zorder=5, linestyle="none")
        ax.annotate(f"{real:+.3f}".replace("-", "−"),
                    xy=(pos, real), xytext=(11, 0),
                    textcoords="offset points",
                    ha="left", va="center", fontsize=10,
                    fontweight="bold", color=OBS_COLOR, zorder=6)
        print(f"  {y}: n_draws={len(s)}  "
              f"p05={p05:+.4f}  p50={p50:+.4f}  p95={p95:+.4f}  "
              f"ΔCENP_real={real:+.4f}  inside_5_95={inside}")

    ax.axhline(0.0, color="grey", linewidth=1.0, linestyle="--", zorder=1)
    ax.set_xticks(positions)
    ax.set_xticklabels([str(y) for y in YEARS])
    ax.tick_params(axis="both", labelsize=11)
    ax.set_ylabel("ΔCENP (coordination gain, baseline = poll)", fontsize=12)
    ax.set_xlim(0.5, len(YEARS) + 0.6)
    ax.set_ylim(-0.13, 0.16)

    handles = [Patch(facecolor=COLORS[YEARS[0]], alpha=0.55,
                     label=f"{YEARS[0]}–{YEARS[-1]} draws"),
               Line2D([0], [0], marker="D", color=OBS_COLOR, linestyle="none",
                      markersize=10, label="real ΔCENP")]
    leg = ax.legend(handles=handles, loc="lower right",
                    bbox_to_anchor=(0.97, 0.04), frameon=True,
                    framealpha=0.9, edgecolor="#cccccc", borderpad=0.8)
    leg.get_frame().set_linewidth(0.8)

    fig.tight_layout()
    save_fig(fig, stem, dpi)
    plt.close(fig)


def plot_delta_cenp_horizontal_violin(samples: dict, targets: dict,
                                      stem: Path, dpi: int) -> None:
    """Figure 2: horizontal violins of simulated draws + navy observed diamond.

    Keeps the full simulated distribution visible (reachability intuition) while
    making the observed-vs-simulated comparison easy to read on a slide.
    """
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    y_pos = {2002: 1, 2022: 0}   # 2002 on top, 2022 below

    print("\n=== Horizontal-violin validation: per-year summary ===")
    for year in YEARS:
        s = samples[year]
        p025, p50, p975 = np.percentile(s, [2.5, 50, 97.5])
        yp = y_pos[year]
        real = targets[year]

        parts = ax.violinplot(s, positions=[yp], vert=False, widths=0.7,
                              showmeans=False, showmedians=False,
                              showextrema=False)
        for body in parts["bodies"]:
            body.set_facecolor(SIM_COLOR)
            body.set_edgecolor(SIM_COLOR)
            body.set_alpha(0.45)

        # Thin 95% interval line + median tick.
        ax.plot([p025, p975], [yp, yp], color=SIM_COLOR, linewidth=1.6,
                alpha=0.8, zorder=3, solid_capstyle="round")
        ax.plot(p50, yp, marker="|", color="#7a3f00", markersize=15,
                markeredgewidth=2.2, zorder=4)

        # Observed: navy diamond + small value label directly beside it.
        ax.plot(real, yp, marker="D", color=OBS_COLOR, markersize=11,
                zorder=5, linestyle="none")
        ha, dx = ("right", -11) if real < p50 else ("left", 11)
        ax.annotate(f"{real:+.3f}".replace("-", "−"),
                    xy=(real, yp), xytext=(dx, -1),
                    textcoords="offset points", ha=ha, va="center",
                    fontsize=10, fontweight="bold", color=OBS_COLOR, zorder=6)
        print(f"  {year}: 95% [{p025:+.3f}, {p975:+.3f}]  median={p50:+.3f}  "
              f"observed={real:+.3f}")

    ax.axvline(0.0, color="grey", linewidth=1.0, linestyle="--", zorder=1)

    ax.set_yticks([y_pos[y] for y in YEARS])
    ax.set_yticklabels([str(y) for y in YEARS], fontsize=13)
    ax.set_ylim(-0.7, 1.7)
    ax.set_xlim(-0.16, 0.16)
    ax.set_xlabel("ΔCENP (coordination gain, baseline = poll)", fontsize=12)
    ax.tick_params(axis="x", labelsize=11)

    # Minimal frame: faint x-grid + dashed x=0, no surrounding box.
    ax.xaxis.grid(True, color="#eeeeee", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)

    handles = [
        Patch(facecolor=SIM_COLOR, alpha=0.45, label="Simulated ABM outcomes"),
        Line2D([0], [0], marker="D", color=OBS_COLOR, linestyle="none",
               markersize=10, label="Observed ΔCENP"),
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.02),
              ncol=2, frameon=False, fontsize=10, handletextpad=0.6,
              columnspacing=1.6)

    fig.tight_layout()
    save_fig(fig, stem, dpi)
    plt.close(fig)


def plot_delta_cenp_faceted_vertical(samples: dict, targets: dict,
                                     stem: Path, dpi: int) -> None:
    """Faceted vertical violins: one panel per year, shared y-axis [-0.12, 0.15]."""
    fig, axes = plt.subplots(1, len(YEARS), figsize=(7, 5), sharey=True)

    print("\n=== Faceted vertical violin: per-year summary ===")
    for ax, year in zip(axes, YEARS):
        s = samples[year]
        real = targets[year]

        parts = ax.violinplot(s, positions=[1], showmeans=False,
                              showmedians=False, showextrema=False)
        for body in parts["bodies"]:
            body.set_facecolor(SIM_COLOR)
            body.set_edgecolor(SIM_COLOR)
            body.set_alpha(0.55)

        ax.axhline(0.0, color="grey", linewidth=1.0, linestyle="--", zorder=1)
        ax.plot(1, real, marker="D", color=OBS_COLOR, markersize=9,
                zorder=5, linestyle="none")
        ax.annotate(f"{real:+.3f}".replace("-", "−"),
                    xy=(1, real), xytext=(11, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=10, fontweight="bold",
                    color=OBS_COLOR, zorder=6)

        # Light grey panel background + thin frame for clear separation.
        ax.set_facecolor("#f4f4f4")
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_visible(True)
            ax.spines[side].set_color("#cccccc")
            ax.spines[side].set_linewidth(0.8)

        ax.set_title(str(year), fontsize=22, fontweight="bold", pad=16,
                     color=OBS_COLOR)
        ax.set_xticks([])
        ax.set_xlim(0.4, 1.7)
        print(f"  {year}: median={np.median(s):+.4f}  observed={real:+.4f}")

    axes[0].set_ylim(-0.13, 0.17)
    axes[0].set_ylabel(r"$\Delta$ CENP", fontsize=13)
    axes[0].tick_params(axis="y", labelsize=11)

    # Reading-guide arrows outside the left axis: up = coordination (top),
    # down = fragmentation (bottom). Bold grey.
    GUIDE = "#7a7a7a"
    ax0 = axes[0]
    xa = -0.42   # axes-fraction x, outside the panel
    arrow_kw = dict(arrowprops=dict(arrowstyle="-|>", color=GUIDE, linewidth=2.2),
                    xycoords="axes fraction", textcoords="axes fraction",
                    annotation_clip=False, zorder=10)
    ax0.annotate("", xy=(xa, 0.96), xytext=(xa, 0.56), **arrow_kw)   # up
    ax0.annotate("", xy=(xa, 0.04), xytext=(xa, 0.44), **arrow_kw)   # down
    text_kw = dict(xycoords="axes fraction", rotation=90, ha="center",
                   va="center", fontsize=12, fontweight="bold", color=GUIDE,
                   annotation_clip=False, zorder=10)
    ax0.annotate("COORDINATION", xy=(xa - 0.07, 0.76), **text_kw)
    ax0.annotate("FRAGMENTATION", xy=(xa - 0.07, 0.24), **text_kw)
    # Right panel: drop its y tick labels (shared scale on the left only),
    # but keep its frame for visual separation.
    for ax in axes[1:]:
        ax.tick_params(axis="y", length=0, labelleft=False)

    handles = [
        Patch(facecolor=SIM_COLOR, alpha=0.55, label="Simulated ABM outcomes"),
        Line2D([0], [0], marker="D", color=OBS_COLOR, linestyle="none",
               markersize=10, label="Observed ΔCENP"),
    ]

    fig.tight_layout(rect=(0, 0.04, 1, 1))
    # Center the legend over the panel area (not the whole figure, which would
    # be pushed off by the left-hand y-axis label/ticks).
    panel_mid = (axes[0].get_position().x0 + axes[-1].get_position().x1) / 2
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               fontsize=10, bbox_to_anchor=(panel_mid, -0.02))
    save_fig(fig, stem, dpi)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data_dir", type=str, default=str(DATA_DIR))
    ap.add_argument("--fig_dir", type=str, default=str(FIG_DIR))
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    fig_dir = Path(args.fig_dir)
    targets = load_targets(data_dir)
    samples = {y: load_sweep(y, data_dir) for y in YEARS}

    # Figure 1: keep the original violin (also under its legacy name).
    plot_delta_cenp_violin(samples, targets, fig_dir / "behavioral_sweep", args.dpi)
    plot_delta_cenp_violin(samples, targets,
                           fig_dir / "delta_cenp_violin_validation", args.dpi)
    # Figure 2: new horizontal-violin validation plot.
    plot_delta_cenp_horizontal_violin(
        samples, targets, fig_dir / "delta_cenp_horizontal_violin_validation", args.dpi)
    # Figure 3: faceted vertical violins, one panel per year.
    plot_delta_cenp_faceted_vertical(
        samples, targets, fig_dir / "delta_cenp_faceted_vertical", args.dpi)


if __name__ == "__main__":
    main()
