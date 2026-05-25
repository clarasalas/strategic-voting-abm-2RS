"""
preferences_figure.py
---------------------
Plot the contender set Ca and opponent set Oa for a single voter on the
ideological interval.

The figure shows K equal-width zones with party kernels as tick marks on
the zone boundary. A voter triangle at position x_a is placed near a zone
boundary, with symmetric τ-radius lines demarcating Ca (contenders) from
Oa (opponents). Opponent zones are faded for visual contrast; group labels
appear above the zone bar.

Outputs
-------
    figure_contender_opponent_v3.pdf
    figure_contender_opponent_v3.png

Usage
-----
    python preferences_figure.py
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

ROOT = Path(__file__).parent

# ── Global style ───────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":      "sans-serif",
    "font.sans-serif":  ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "mathtext.fontset": "dejavusans",
})

# ── Parameters ─────────────────────────────────────────────────────────────────
K           = 6
party_names = ["A", "B", "D", "E", "F", "G"]

w            = 1.0 / K
zone_edges   = np.array([i * w for i in range(K + 1)])
zone_kernels = np.array([(i + 0.5) * w for i in range(K)])

voter_x = 0.685          # just inside zone F, very close to E/F border
tau     = 0.250           # lo=0.435 (inside D, past D's kernel), hi=0.935 (inside G)

lo = voter_x - tau
hi = voter_x + tau

is_contender = np.array([abs(voter_x - k) <= tau for k in zone_kernels])

# ── Colours ────────────────────────────────────────────────────────────────────
zone_base = ["#f2c4c8", "#f5dbc0", "#f5f0d0", "#d4e8b8", "#a8d8c8", "#c8b8d8"]

C_CONTENDER = "#4a9e7a"
C_OPPONENT  = "#c08080"
FADE_ALPHA  = 0.55

VOTER_C    = "#333333"
BNDRY_C    = "#444444"
KERNEL_C_C = "#777777"
KERNEL_C_O = "#c0b0b0"

# ── Layout ─────────────────────────────────────────────────────────────────────
BAR_Y   = 0.28
BAR_H   = 0.36
BAR_MID = BAR_Y + BAR_H / 2

VOTER_TY  = BAR_Y + BAR_H + 0.11
LABEL_TY  = VOTER_TY + 0.05
TAU_Y     = BAR_Y - 0.22
GUIDE_END = BAR_Y - 0.05
GRP_LBL_Y = BAR_Y + BAR_H + 0.31

TICK_H   = 0.045
DOT_SIZE = 22


# ── Figure ─────────────────────────────────────────────────────────────────────

def draw_figure() -> plt.Figure:
    """Build and return the contender/opponent sets figure."""

    fig, ax = plt.subplots(figsize=(10.5, 2.6))
    ax.set_xlim(-0.01, 1.01)
    ax.set_ylim(0.0,   1.0)
    ax.axis("off")

    # 1. Zone rectangles
    for i in range(K):
        x0 = i * w
        ax.add_patch(mpatches.Rectangle(
            (x0, BAR_Y), w, BAR_H,
            facecolor=zone_base[i], edgecolor="white", linewidth=1.8, zorder=1,
        ))
        if not is_contender[i]:
            ax.add_patch(mpatches.Rectangle(
                (x0, BAR_Y), w, BAR_H,
                facecolor="white", edgecolor="none", alpha=FADE_ALPHA, zorder=2,
            ))
        lc = "#555555" if is_contender[i] else "#c0b0b0"
        ax.text(x0 + w / 2, BAR_MID, party_names[i],
                ha="center", va="center",
                fontsize=15, fontweight="bold", color=lc, zorder=4)

    # Thin outline around the contender set
    c_start = np.where(is_contender)[0][0] * w
    c_end   = (np.where(is_contender)[0][-1] + 1) * w
    ax.add_patch(mpatches.Rectangle(
        (c_start, BAR_Y), c_end - c_start, BAR_H,
        facecolor="none", edgecolor="#888888",
        linewidth=1.5, linestyle="-", zorder=6,
    ))

    # 2. Party kernel markers
    for i, kx in enumerate(zone_kernels):
        color = KERNEL_C_C if is_contender[i] else KERNEL_C_O
        ax.plot([kx, kx], [BAR_Y - TICK_H, BAR_Y], color=color, lw=1.2, zorder=3)
        ax.scatter([kx], [BAR_Y - TICK_H], s=DOT_SIZE, color=color, zorder=4, clip_on=False)

    ax.text(zone_kernels[2] - 0.003, BAR_Y - TICK_H - 0.035,
            r"$x_j$", ha="center", va="top",
            fontsize=11, color="#999999", style="italic")

    # 3. Boundary lines at x_a ± τ
    for bx in [lo, hi]:
        ax.plot([bx, bx], [GUIDE_END, BAR_Y + BAR_H + 0.07],
                color=BNDRY_C, lw=1.5, ls=(0, (5, 3)), zorder=5)
        ax.plot([bx, bx], [TAU_Y + 0.01, GUIDE_END],
                color="#cccccc", lw=0.9, ls=":", zorder=3)

    # 4. Voter triangle and label
    ax.plot(voter_x, VOTER_TY, marker="v", color=VOTER_C, markersize=9,
            zorder=6, markeredgecolor="white", markeredgewidth=0.8)
    ax.text(voter_x, LABEL_TY, r"agent $a$",
            ha="center", va="bottom", fontsize=11, color=VOTER_C)
    ax.plot([voter_x, voter_x], [BAR_Y + BAR_H, VOTER_TY - 0.015],
            color="#999999", lw=0.8, ls=":", zorder=3)

    # 5. Symmetric τ arrows
    AKW = dict(arrowstyle="<->", color="#666666", lw=1.2, mutation_scale=8)
    ax.annotate("", xy=(lo, TAU_Y), xytext=(voter_x, TAU_Y), arrowprops=AKW)
    ax.text((lo + voter_x) / 2, TAU_Y - 0.052, r"$\tau$",
            ha="center", va="top", fontsize=13, color="#666666")
    ax.annotate("", xy=(hi, TAU_Y), xytext=(voter_x, TAU_Y), arrowprops=AKW)
    ax.text((voter_x + hi) / 2, TAU_Y - 0.052, r"$\tau$",
            ha="center", va="top", fontsize=13, color="#666666")

    # 6. Group labels: C_a and O_a
    def _bracket(x_start, x_end, y, label, color):
        pad = 0.008
        ax.plot([x_start + pad, x_end - pad], [y, y],
                color=color, lw=1.0, solid_capstyle="round", zorder=4)
        ax.text((x_start + x_end) / 2, y + 0.03, label,
                ha="center", va="bottom",
                fontsize=13, color=color, fontweight="bold")

    _bracket(0.0, 3 * w, GRP_LBL_Y, r"$\mathbf{O_a}$  (opponents)",  C_OPPONENT)
    _bracket(3 * w, 1.0, GRP_LBL_Y, r"$\mathbf{C_a}$  (contenders)", C_CONTENDER)

    # 7. Legend
    ax.legend(
        handles=[
            mpatches.Patch(facecolor="#a8d8c8", edgecolor="#888888", linewidth=1.5,
                           label=r"contender set  $C_a = \{j : |x_a - x_j| \leq \tau\}$"),
            mpatches.Patch(facecolor="#e8d0d0", edgecolor="#bbbbbb", linewidth=0.7,
                           label=r"opponent set  $O_a = \{j : |x_a - x_j| > \tau\}$"),
        ],
        loc="upper left", bbox_to_anchor=(0.0, 0.10),
        frameon=False, fontsize=11,
        labelspacing=0.4, handlelength=1.0, handleheight=0.85, handletextpad=0.5,
    )

    return fig


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    fig = draw_figure()
    plt.tight_layout(pad=0.2)
    fig.savefig(ROOT / "figure_contender_opponent_v3.pdf", bbox_inches="tight", dpi=300)
    fig.savefig(ROOT / "figure_contender_opponent_v3.png", bbox_inches="tight", dpi=300)
    print("Saved figure_contender_opponent_v3.pdf / .png")
    plt.show()
