"""
signal_figures.py
-----------------
Pedagogical figures illustrating the two-stage signal transformation.

Figure 1 — Deterministic distortion by theta
    True shares δ⁰ vs concentrated (θ < 1) and flattened (θ > 1) signals.
    No Dirichlet noise — isolates the temperature transformation only.

Figure 2 — Stochastic noise by rho_s
    Transformed signal s̃ vs low-precision and high-precision Dirichlet draws.
    Ghost outlines show s̃ in the noisy panels for reference.

Outputs
-------
    figure_signal_distortion_theta.png / .pdf
    figure_signal_noise_rhos.png / .pdf

Usage
-----
    python signal_figures.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent

# =========================================================================== #
#  HELPERS                                                                     #
# =========================================================================== #

def transform_signal(delta: np.ndarray,
                     theta: float,
                     epsilon_s: float = 1e-4) -> np.ndarray:
    """
    Deterministic temperature transformation.

        s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)
    """
    delta = np.asarray(delta, dtype=float)
    total = delta.sum()
    delta = delta / total if total > 0 else np.ones(len(delta)) / len(delta)
    transformed = (delta + epsilon_s) ** (1.0 / theta)
    return transformed / transformed.sum()


def draw_signal(tilde_s: np.ndarray,
                rho_s: float,
                rng: np.random.Generator) -> np.ndarray:
    """
    Single Dirichlet draw: s ~ Dirichlet(rho_s · s̃).
    """
    tilde_s = np.asarray(tilde_s, dtype=float)
    concentration = rho_s * tilde_s
    return rng.dirichlet(concentration)


def get_party_colors(K: int) -> list:
    """
    K evenly-spaced colours from the Spectral colormap,
    ordered left (red) to right (blue).
    """
    cmap = plt.colormaps.get_cmap("Spectral").resampled(K)
    return [cmap(i) for i in range(K)]


# =========================================================================== #
#  SHARED STYLE CONSTANTS                                                      #
# =========================================================================== #

FS_SUPTITLE = 14
FS_PANEL    = 12
FS_SUBTITLE = 10
FS_AXIS     = 10
FS_PCT      = 8
FS_NOTE     = 11
FS_FORMULA  = 11

C_TITLE  = "#1a1a1a"
C_SUB    = "#555555"
C_AXIS   = "#444444"
C_PCT    = "#222222"
C_SPINE  = "#bbbbbb"
C_GRID   = "#dddddd"

BAR_EDGE = dict(edgecolor="black", linewidth=0.5)
GRID_KW  = dict(axis="y", color=C_GRID, linewidth=0.5, linestyle="--", zorder=0)

plt.rcParams.update({
    "font.family":        "serif",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
})


# =========================================================================== #
#  INTERNAL DRAWING UTILITIES                                                  #
# =========================================================================== #

def _style_ax(ax, ymax_pct: float) -> None:
    ax.set_ylim(0, ymax_pct)
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.grid(**GRID_KW)
    ax.set_axisbelow(True)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color(C_SPINE)
        ax.spines[sp].set_linewidth(0.7)
    ax.tick_params(axis="both", labelsize=FS_AXIS, colors="#333333",
                   length=3, width=0.6)


def _panel_header(ax, title: str, subtitle: str) -> None:
    """
    Title at ~14% above axes top, subtitle at ~3% above axes top.
    Both in axes-fraction coords so spacing is figure-size independent.
    """
    ax.text(0.5, 1.14, title,
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=FS_PANEL, fontweight="bold", color=C_TITLE,
            clip_on=False)
    ax.text(0.5, 1.03, subtitle,
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=FS_SUBTITLE, fontstyle="italic", color=C_SUB,
            clip_on=False)


def _draw_bars(ax, values_pct: np.ndarray, colors: list,
               x_labels: list, ghost_pct: np.ndarray = None) -> None:
    """
    Main bars with optional ghost reference for s̃.

    Ghost strategy: draw the reference outline on TOP of the main bars
    (zorder=3) with no fill, so it is always visible — whether the
    realized bar grew above s̃ (outline sits inside the bar) or shrank
    below s̃ (outline sits above the bar). Both directions of deviation
    are immediately readable.
    """
    K  = len(values_pct)
    xs = np.arange(K)

    # Main bars — drawn first (zorder=2)
    bars = ax.bar(xs, values_pct, width=0.58, zorder=2,
                  color=colors, alpha=0.7, **BAR_EDGE)

    # Ghost reference outline — drawn on top (zorder=3), no fill
    if ghost_pct is not None:
        bar_w = 0.58
        for i, (x, gval) in enumerate(zip(xs, ghost_pct)):
            rect = plt.Rectangle(
                (x - bar_w / 2, 0),
                bar_w, gval,
                linewidth=0.9,
                edgecolor="#555555",
                linestyle=(0, (5, 3)),
                facecolor="none",
                zorder=3,
                clip_on=True,
            )
            ax.add_patch(rect)

    ax.set_xticks(xs)
    ax.set_xticklabels(x_labels, fontsize=FS_AXIS)
    ax.set_xlabel("Party", fontsize=FS_AXIS, color=C_AXIS, labelpad=4)

    # Percentage labels — compact, not bold
    for bar, val in zip(bars, values_pct):
        if val >= 2.0:
            ax.text(bar.get_x() + bar.get_width() / 2.0,
                    bar.get_height() + 0.35,
                    f"{val:.1f}%",
                    ha="center", va="bottom",
                    fontsize=FS_PCT, color=C_PCT)


# =========================================================================== #
#  FIGURE 1 — Deterministic distortion by theta                               #
# =========================================================================== #

def plot_signal_distortion_by_theta(
        delta0: np.ndarray,
        party_labels: list,
        theta_low: float  = 0.5,
        theta_high: float = 2.0,
        epsilon_s: float  = 1e-4,
        save_prefix=None,
) -> plt.Figure:
    """
    3-panel figure: true shares | theta<1 | theta>1.
    Deterministic only — no Dirichlet noise.
    """
    if save_prefix is None:
        save_prefix = str(ROOT / "figure_signal_distortion_theta")
    delta0 = np.asarray(delta0, dtype=float)
    delta0 = delta0 / delta0.sum()
    s_low  = transform_signal(delta0, theta_low,  epsilon_s)
    s_high = transform_signal(delta0, theta_high, epsilon_s)
    colors = get_party_colors(len(delta0))

    all_vals = np.concatenate([delta0, s_low, s_high]) * 100
    ymax     = all_vals.max() * 1.22 + 1.5

    fig, axes = plt.subplots(1, 3, figsize=(11, 4.0), sharey=True)
    fig.subplots_adjust(left=0.08, right=0.97,
                        top=0.72,  bottom=0.20,
                        wspace=0.12)

    panels = [
        (axes[0], delta0 * 100, "True vote shares",    r"$\delta^{\,0}$"),
        (axes[1], s_low  * 100, "Concentrated signal", rf"$\theta = {theta_low}$"),
        (axes[2], s_high * 100, "Flattened signal",    rf"$\theta = {theta_high}$"),
    ]

    for ax, vals, title, subtitle in panels:
        _style_ax(ax, ymax)
        _draw_bars(ax, vals, colors, party_labels)
        _panel_header(ax, title, subtitle)

    axes[0].set_ylabel("Vote share (%)", fontsize=FS_AXIS, color=C_AXIS)

    # Global title — above panel headers, enough top margin ensured by subplots_adjust
    fig.text(0.5, 0.98,
             r"Signal distortion by temperature parameter $\theta$",
             ha="center", va="top",
             fontsize=FS_SUPTITLE, fontweight="bold", color=C_TITLE)

    # Note
    fig.text(0.5, 0.07,
             r"$\theta < 1$ amplifies differences across parties; "
             r"$\theta > 1$ compresses them.",
             ha="center", va="top", fontsize=FS_NOTE, color=C_AXIS)

    # Formula — smaller, below note
    fig.text(0.5, 0.01,
             r"$\tilde{s}_i = "
             r"(\delta_i + \varepsilon)^{1/\theta} \,/\, "
             r"\sum_j (\delta_j + \varepsilon)^{1/\theta}$",
             ha="center", va="top",
             fontsize=FS_FORMULA, color="#666666")

    for fmt in ("png", "pdf"):
        fig.savefig(f"{save_prefix}.{fmt}",
                    dpi=300, bbox_inches="tight", facecolor="white")
        print(f"Saved {save_prefix}.{fmt}")

    return fig


# =========================================================================== #
#  FIGURE 2 — Stochastic noise by rho_s                                       #
# =========================================================================== #

def plot_signal_noise_by_precision(
        tilde_s: np.ndarray,
        party_labels: list,
        rho_low: float  = 10,
        rho_high: float = 200,
        rng: np.random.Generator = None,
        save_prefix=None,
) -> plt.Figure:
    """
    3-panel figure: transformed signal s̃ | low rho_s | high rho_s.
    Ghost outlines show s̃ in panels B and C.
    """
    if save_prefix is None:
        save_prefix = str(ROOT / "figure_signal_noise_rhos")
    if rng is None:
        rng = np.random.default_rng(42)

    tilde_s   = np.asarray(tilde_s, dtype=float)
    tilde_s   = tilde_s / tilde_s.sum()
    s_noisy   = draw_signal(tilde_s, rho_low,  rng)
    s_precise = draw_signal(tilde_s, rho_high, rng)
    colors    = get_party_colors(len(tilde_s))

    all_vals = np.concatenate([tilde_s, s_noisy, s_precise]) * 100
    ymax     = all_vals.max() * 1.22 + 1.5

    fig, axes = plt.subplots(1, 3, figsize=(11, 4.0), sharey=True)
    fig.subplots_adjust(left=0.08, right=0.97,
                        top=0.72,  bottom=0.20,
                        wspace=0.12)

    ghost_pct = tilde_s * 100

    panels = [
        (axes[0], tilde_s   * 100, "Transformed signal", r"$\tilde{s}$",                 None),
        (axes[1], s_noisy   * 100, "Low precision",       rf"$\rho_s = {int(rho_low)}$",  ghost_pct),
        (axes[2], s_precise * 100, "High precision",      rf"$\rho_s = {int(rho_high)}$", ghost_pct),
    ]

    for ax, vals, title, subtitle, ghost in panels:
        _style_ax(ax, ymax)
        _draw_bars(ax, vals, colors, party_labels, ghost_pct=ghost)
        _panel_header(ax, title, subtitle)

    axes[0].set_ylabel("Vote share (%)", fontsize=FS_AXIS, color=C_AXIS)

    # Reference-bar legend — minimal, top-left of panel B, away from bars
    ghost_patch = mpatches.Patch(
        facecolor="none",
        edgecolor="#555555", linewidth=0.9,
        linestyle=(0, (5, 3)),
        label=r"$\tilde{s}$ (reference)",
    )
    axes[1].legend(
        handles=[ghost_patch],
        fontsize=6.8, loc="upper left",
        framealpha=0.55, edgecolor="#cccccc",
        handlelength=1.4, handleheight=0.9,
        borderpad=0.4, labelspacing=0.2,
        handletextpad=0.5,
    )

    # Global title
    fig.text(0.5, 0.98,
             r"Signal noise by precision parameter $\rho_s$",
             ha="center", va="top",
             fontsize=FS_SUPTITLE, fontweight="bold", color=C_TITLE)

    # Note
    fig.text(0.5, 0.07,
             r"Higher $\rho_s$ produces signals closer to $\tilde{s}$; "
             r"lower $\rho_s$ produces noisier signals.",
             ha="center", va="top", fontsize=FS_NOTE, color=C_AXIS)

    # Formula
    fig.text(0.5, 0.01,
             r"$s \sim \mathrm{Dirichlet}(\rho_s \cdot \tilde{s})$",
             ha="center", va="top",
             fontsize=FS_FORMULA, color="#666666")

    for fmt in ("png", "pdf"):
        fig.savefig(f"{save_prefix}.{fmt}",
                    dpi=300, bbox_inches="tight", facecolor="white")
        print(f"Saved {save_prefix}.{fmt}")

    return fig


# =========================================================================== #
#  MAIN                                                                        #
# =========================================================================== #

if __name__ == "__main__":

    # ── Plug in your own delta0 and labels here ──────────────────────────────
    delta0       = np.array([0.09, 0.19, 0.23, 0.22, 0.14, 0.13])
    party_labels = ["A", "B", "D", "E", "F", "G"]
    epsilon_s    = 1e-4
    rng          = np.random.default_rng(42)

    # ── Figure 1: deterministic distortion by theta ──────────────────────────
    fig1 = plot_signal_distortion_by_theta(
        delta0       = delta0,
        party_labels = party_labels,
        theta_low    = 0.5,
        theta_high   = 2.0,
        epsilon_s    = epsilon_s,
    )

    # ── Figure 2: stochastic noise by rho_s ──────────────────────────────────
    # theta=1 (faithful) isolates noise from distortion cleanly
    tilde_s = transform_signal(delta0, theta=1.0, epsilon_s=epsilon_s)

    fig2 = plot_signal_noise_by_precision(
        tilde_s      = tilde_s,
        party_labels = party_labels,
        rho_low      = 10,
        rho_high     = 200,
        rng          = rng,
    )

    plt.show()
