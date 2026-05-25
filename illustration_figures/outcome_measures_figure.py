"""
outcome_measures_figure.py
--------------------------
Plot a three-column comparison of sincere and final vote-share distributions
with coordination outcome measures in the centre panel.

Layout
------
    Left   : sincere benchmark δ⁰  (bar plot; ENP, d*, r' annotated)
    Centre : comparison measures    (ΔCENP, k*, Δd*, Δr')
    Right  : final outcome δᵀ       (bar plot; cliff bracket annotated)

Bars within each panel are ranked highest-to-lowest independently;
the same rank does not correspond to the same candidate across panels.

Outputs
-------
    outputs/outcome_measures_bars.pdf
    outputs/outcome_measures_bars.png

Usage
-----
    python outcome_measures_figure.py
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.colors as mcolors

ROOT = Path(__file__).parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "core_model"))


# ============================================================================ #
#  MEASURE HELPERS                                                             #
# ============================================================================ #

def enp(v):
    v = np.asarray(v, dtype=float)
    sq = (v ** 2).sum()
    return 1.0 / sq if sq > 0 else float("nan")


def c_enp(v):
    v = np.asarray(v, dtype=float)
    K = len(v)
    return (K - enp(v)) / (K - 1) if K > 1 else float("nan")


def cliff_stats(v):
    v = np.asarray(v, dtype=float)
    K = len(v)
    if K <= 1:
        return dict(sorted_shares=v.copy(), d_star=0.0, k_star=1, r_prime=0.5)
    sv = np.sort(v)[::-1]
    if K == 2:
        return dict(sorted_shares=sv, d_star=float(sv[0] - sv[1]),
                    k_star=1, r_prime=1.0)
    drops = sv[:-1] - sv[1:]
    idx = int(np.argmax(drops))
    k_star = idx + 1
    d_star = float(drops[idx])
    other = np.concatenate([drops[:idx], drops[idx + 1:]])
    other_mean = float(other.mean()) if len(other) > 0 else 0.0
    denom = d_star + other_mean
    r_prime = d_star / denom if denom > 0 else 0.5
    return dict(sorted_shares=sv, d_star=d_star, k_star=k_star, r_prime=r_prime)


# ============================================================================ #
#  COLOUR UTILITY                                                              #
# ============================================================================ #

def _lighten(color, f=0.28):
    rgb = np.array(mcolors.to_rgb(color))
    return tuple((1.0 - f) * np.ones(3) + f * rgb)


# ============================================================================ #
#  MAIN PLOTTING FUNCTION                                                      #
# ============================================================================ #

def plot_outcome_measures_bars(
        delta_sincere,
        delta_final,
        save_path=None,
        figsize=(16.0, 5.0),
):
    # ── Normalise ─────────────────────────────────────────────────────────────
    s = np.asarray(delta_sincere, dtype=float);
    s /= s.sum()
    f = np.asarray(delta_final, dtype=float);
    f /= f.sum()
    assert len(s) == len(f)
    K = len(s)

    # ── Measures ──────────────────────────────────────────────────────────────
    enp_s = enp(s);
    enp_f = enp(f)
    cenp_s = c_enp(s);
    cenp_f = c_enp(f)
    d_cenp = cenp_f - cenp_s

    cs = cliff_stats(s);
    cf = cliff_stats(f)
    s_sorted = cs["sorted_shares"]
    f_sorted = cf["sorted_shares"]
    k_star = cf["k_star"]
    delta_d = cf["d_star"] - cs["d_star"]
    delta_rp = cf["r_prime"] - cs["r_prime"]

    y_hi = f_sorted[k_star - 1] * 100
    y_lo = f_sorted[k_star] * 100 if k_star < K else 0.0

    # ── Colours ───────────────────────────────────────────────────────────────
    _sp = matplotlib.colormaps["Spectral"]
    col_sin = _sp(0.32)
    col_fin = _sp(0.16)
    col_dark = "#1c1c1c"

    def _sgn(x, dec=3):
        return f"{x:+.{dec}f}"

    # ── Layout: three columns ─────────────────────────────────────────────────
    ranks = np.arange(1, K + 1)
    y_max = max(s_sorted[0], f_sorted[0]) * 100
    y_top = y_max * 1.35

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(
        1, 3,
        width_ratios=[4.5, 1, 4.5],
        wspace=0.2,
    )
    ax_sin = fig.add_subplot(gs[0, 0])
    ax_mid = fig.add_subplot(gs[0, 1])
    ax_fin = fig.add_subplot(gs[0, 2], sharey=ax_sin)
    ax_mid.axis("off")

    # ── Shared axis formatter ─────────────────────────────────────────────────
    def _fmt(ax, title, show_ylabel, show_ytick_labels=True):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_linewidth(0.7)
        ax.spines["bottom"].set_linewidth(0.7)
        ax.yaxis.grid(True, color="#e6e6e6", linewidth=0.6, zorder=0)
        ax.xaxis.grid(False)
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", which="major", labelsize=9.5)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
        ax.set_xlabel("Candidate rank", fontsize=10.5, labelpad=5)
        if show_ylabel:
            ax.set_ylabel("Vote share", fontsize=10.5)
        ax.set_xticks(ranks)
        ax.set_xticklabels([str(r) for r in ranks], fontsize=9.5)
        if show_ytick_labels:
            ax.yaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        else:
            ax.tick_params(axis="y", labelleft=False)
        ax.set_xlim(0.40, K + 0.60)
        ax.set_ylim(0, y_top)

    # ── Left panel: sincere ───────────────────────────────────────────────────
    ax_sin.bar(ranks, s_sorted * 100,
               color=col_sin, width=0.65, alpha=0.7,
               edgecolor="white", linewidth=0.5, zorder=3)
    _fmt(ax_sin, "Sincere benchmark  $\\delta^{0}$",
         show_ylabel=True, show_ytick_labels=True)

    sin_box = "\n".join([
        f"$\\mathrm{{ENP}}_{{0}}$  $= {enp_s:.2f}$",
        f"$d^*_{{0}}$  $= {cs['d_star'] * 100:.1f}$ pp",
        f"$r'_{{0}}$  $= {cs['r_prime']:.2f}$",
    ])
    ax_sin.text(
        0.97, 0.97, sin_box,
        transform=ax_sin.transAxes,
        fontsize=9.5, va="top", ha="right", linespacing=1.65,
        bbox=dict(boxstyle="round,pad=0.50",
                  facecolor=_lighten(col_sin, 0.28),
                  edgecolor=col_sin, linewidth=1.0, alpha=0.97),
        zorder=8,
    )

    # ── Right panel: final ────────────────────────────────────────────────────
    ax_fin.bar(ranks, f_sorted * 100,
               color=col_fin, width=0.65, alpha=0.7,
               edgecolor="white", linewidth=0.5, zorder=3)

    # Highlight ranks 1 … k* (the viable bloc above the cliff)
    for idx0 in range(k_star):
        ax_fin.bar(idx0 + 1, f_sorted[idx0] * 100,
                   color=col_fin, width=0.65, alpha=0.7,
                   edgecolor=col_dark, linewidth=2.2, zorder=4)

    # y-axis: keep grid lines but remove percentage labels (right panel)
    _fmt(ax_fin, "Final outcome  $\\delta^{T}$",
         show_ylabel=False, show_ytick_labels=False)

    # Bracket above the k* highlighted bars
    x_bk_l = 1 - 0.27
    x_bk_r = k_star + 0.27
    y_bk = f_sorted[0] * 100 + y_top * 0.09
    tick_h = y_top * 0.026
    for _x in [x_bk_l, x_bk_r]:
        ax_fin.plot([_x, _x], [y_bk - tick_h, y_bk],
                    color="#333333", lw=0.9, zorder=7, clip_on=False)
    ax_fin.plot([x_bk_l, x_bk_r], [y_bk, y_bk],
                color="#333333", lw=0.9, zorder=7, clip_on=False)
    ax_fin.text(
        (x_bk_l + x_bk_r) / 2, y_bk + y_top * 0.012,
        f"$k^*_{{\\mathrm{{final}}}} = {k_star}$",
        ha="center", va="bottom", fontsize=9.5, color="#333333", zorder=7,
    )

    # d*_final double-headed arrow between bars k* and k*+1
    x_arr = k_star + 0.50
    if (y_hi - y_lo) > 0.30:
        ax_fin.annotate(
            "",
            xy=(x_arr, y_lo), xytext=(x_arr, y_hi),
            arrowprops=dict(arrowstyle="<->", color=col_dark, lw=1.3,
                            mutation_scale=10, shrinkA=0, shrinkB=0),
            zorder=8,
        )
        ax_fin.text(
            x_arr + 0.10, 0.5 * (y_hi + y_lo),
            "$d^*_{\\mathrm{final}}$",
            ha="left", va="center", fontsize=9, color=col_dark, zorder=8,
        )

    fin_box = "\n".join([
        f"$\\mathrm{{ENP}}_{{T}}$  $= {enp_f:.2f}$",
        f"$d^*_{{\\mathrm{{final}}}}$  $= {cf['d_star'] * 100:.1f}$ pp",
        f"$r'_{{\\mathrm{{final}}}}$  $= {cf['r_prime']:.2f}$",
    ])
    ax_fin.text(
        0.97, 0.97, fin_box,
        transform=ax_fin.transAxes,
        fontsize=9.5, va="top", ha="right", linespacing=1.65,
        bbox=dict(boxstyle="round,pad=0.50",
                  facecolor=_lighten(col_fin, 0.28),
                  edgecolor=col_fin, linewidth=1.0, alpha=0.97),
        zorder=8,
    )

    # ── Centre column: comparison measures ───────────────────────────────────
    # Listed vertically so the column acts as a clear visual separator.
    mid_text = (
        "$\\Delta C_{\\mathrm{ENP}}$\n"
        f"$= {_sgn(d_cenp)}$"
        "\n\n"
        f"$k^*_{{\\mathrm{{final}}}} = {k_star}$"
        "\n\n"
        f"$\\Delta d^* = {_sgn(delta_d * 100, 2)}$ pp"
        "\n\n"
        f"$\\Delta r' = {_sgn(delta_rp)}$"
    )
    ax_mid.text(
        0.5, 0.5, mid_text,
        ha="center", va="center",
        fontsize=9.5, transform=ax_mid.transAxes,
        linespacing=1.7,
        bbox=dict(
            boxstyle="round,pad=0.60",
            facecolor="#f4f4f4",
            edgecolor="#c0c0c0", linewidth=0.9, alpha=0.97,
        ),
    )

    # ── Finalise ──────────────────────────────────────────────────────────────
    fig.tight_layout(pad=1.0)
    # Small ranking note below the figure — lightweight enough not to overlap
    fig.text(
        0.5, 0.002,
        "Candidates ranked separately within each panel — "
        "same rank ≠ same candidate.",
        ha="center", va="bottom", fontsize=7.8,
        style="italic", color="#707070",
    )

    if save_path is not None:
        stem = Path(save_path)
        stem.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(stem) + ".pdf", bbox_inches="tight")
        fig.savefig(str(stem) + ".png", dpi=300, bbox_inches="tight")
        print(f"  [saved]  {stem}.pdf")
        print(f"  [saved]  {stem}.png")

    return fig, (ax_sin, ax_mid, ax_fin)


# ============================================================================ #
#  EXAMPLE                                                                     #
# ============================================================================ #

if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent))

    from model import run_simulation

    _result = run_simulation(
        K=7, n_electors=1000,
        n_modes=1, mode_position=0.0, skewness=0.0,
        width_factor=1.25, floor_weight=0.1,
        theta=0.5,
        rho=100.0, rho_pi=50.0,
        tau=1.5 * (2.0 / 6),
        mu=0.0, alpha_prior=0.0, K_runoff=2,
        max_iterations=20,
        seed=6,
        verbose=False,
        collect_diagnostics=False,
    )

    delta_sincere = np.array(_result["sincere_shares"])
    delta_final = np.array(_result["final_shares"])

    matplotlib.use("Agg")

    fig, axes = plot_outcome_measures_bars(
        delta_sincere,
        delta_final,
        save_path=ROOT / "outputs" / "outcome_measures_bars",
    )

    s = delta_sincere / delta_sincere.sum()
    f = delta_final / delta_final.sum()
    cs_ex, cf_ex = cliff_stats(s), cliff_stats(f)
    print("\nMeasures from simulation output:")
    print(f"  ENP_0        = {enp(s):.3f}")
    print(f"  ENP_T        = {enp(f):.3f}")
    print(f"  ΔCENP        = {c_enp(f) - c_enp(s):+.3f}")
    print(f"  k*_final     = {cf_ex['k_star']}")
    print(f"  Δd*          = {(cf_ex['d_star'] - cs_ex['d_star']) * 100:+.2f} pp")
    print(f"  Δr'          = {cf_ex['r_prime'] - cs_ex['r_prime']:+.3f}")