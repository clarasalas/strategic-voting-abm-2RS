"""
distribution_figure.py
----------------------
Single-row figure: symmetric unimodal centrist electorate.

Shows:
  - K equal-width ideological zones with party labels
  - Gaussian density (+ uniform floor) centred at xi = 0
  - Sampled voter dots, coloured by zone
  - Annotations: ell = 2/K (inter-zone spacing), xi (location), omega (width)

Notation matches the paper's parameter table:
    xi        : location of the attractor
    omega     : distribution width  (= c * ell)
    epsilon_F : uniform floor weight
    ell       : zone length = 2/K
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy.stats import norm

# =========================================================================== #
#  GLOBAL PARAMETERS                                                           #
# =========================================================================== #

K            = 4
SPACE        = (-1.0, 1.0)
SEED         = 18
N_POINTS     = 600
N_SAMPLES    = 80
FLOOR_WEIGHT = 0.3       # epsilon_F in the paper

xmin, xmax     = SPACE
zone_length    = (xmax - xmin) / K
party_positions  = np.array([-1 + (2 * j + 1) / K for j in range(K)])
zone_boundaries  = np.array([-1 + j * zone_length for j in range(K + 1)])

# Spectral colormap — warm segment for left parties, cool for right
_cmap   = matplotlib.colormaps["Spectral"]
_n_warm = (K + 1) // 2
_n_cool = K // 2
_pts    = np.concatenate([np.linspace(0.02, 0.38, _n_warm),
                           np.linspace(0.76, 0.97, _n_cool)])
PARTY_COLORS = [_cmap(p) for p in _pts]
PARTY_LABELS = ["A", "B", "C", "D"]
DENSITY_COLOR = "#444444"

BAR_Y      = 0.0
BAR_H      = 0.40
CURVE_BASE = BAR_Y + BAR_H
CURVE_MAX  = 0.70

x = np.linspace(xmin, xmax, N_POINTS)


# =========================================================================== #
#  DENSITY HELPERS                                                             #
# =========================================================================== #

def mixture_density(x, xis, omegas, component_weights):
    """
    Gaussian mixture density.

    Parameters
    ----------
    xis               : list of location parameters xi_m
    omegas            : list of width parameters omega_m = c_m * ell
    component_weights : mixing weights (normalised internally)
    """
    component_weights = np.asarray(component_weights, dtype=float)
    component_weights /= component_weights.sum()
    d = np.zeros_like(x, dtype=float)
    for xi, omega, w in zip(xis, omegas, component_weights):
        d += w * norm.pdf(x, xi, omega)
    return d


def mixture_density_with_floor(x, xis, omegas, component_weights,
                                floor_w=FLOOR_WEIGHT):
    """
    Gaussian mixture blended with a scaled uniform floor (epsilon_F).
    The floor level equals the GMM mean, staying below both peaks.
    """
    gmm = mixture_density(x, xis, omegas, component_weights)
    flat_scaled = np.full_like(gmm, gmm.mean())
    return (1 - floor_w) * gmm + floor_w * flat_scaled


def sample_with_floor(xis, omegas, component_weights, n, rng,
                      floor_w=FLOOR_WEIGHT):
    """
    Draw n voter positions from a Gaussian mixture + uniform floor.

    Parameters
    ----------
    xis               : list of location parameters
    omegas            : list of width parameters (= c_m * ell)
    component_weights : mixing weights
    floor_w           : epsilon_F, uniform floor weight
    """
    component_weights = np.asarray(component_weights, dtype=float)
    component_weights /= component_weights.sum()
    samples = []
    for _ in range(n):
        if floor_w > 0 and rng.random() < floor_w:
            samples.append(float(rng.uniform(xmin, xmax)))
        else:
            i = rng.choice(len(xis), p=component_weights)
            s = rng.normal(xis[i], omegas[i])
            samples.append(float(np.clip(s, xmin, xmax)))
    return np.array(samples)


# =========================================================================== #
#  ROW CONFIGURATION                                                           #
# =========================================================================== #

def make_row() -> dict:
    """Build the data dict for the symmetric unimodal centrist row."""
    rng   = np.random.default_rng(SEED)
    c     = 0.45
    xi    = 0.0
    omega = c * zone_length

    density = mixture_density_with_floor(x, [xi], [omega], [1.0])
    samples = sample_with_floor([xi], [omega], [1.0], N_SAMPLES, rng)
    dmax    = density.max()

    return {
        "density_norm":   density / dmax if dmax > 0 else density,
        "samples":        samples,
        "annotate_ell":   True,
        "gaussian_params": {"xi": xi, "omega": omega, "c": c},
    }


# =========================================================================== #
#  DRAW ROW                                                                    #
# =========================================================================== #

def draw_row(ax, row: dict) -> None:
    """Render one distribution row onto *ax*."""
    density = row["density_norm"]
    samples = row["samples"]

    # Zone bars
    for j in range(K):
        xl, xr = zone_boundaries[j], zone_boundaries[j + 1]
        ax.add_patch(mpatches.FancyBboxPatch(
            (xl, BAR_Y), xr - xl, BAR_H,
            boxstyle="square,pad=0",
            facecolor=PARTY_COLORS[j], edgecolor="white",
            linewidth=1.5, alpha=0.25, zorder=2,
        ))
        ax.text(0.5 * (xl + xr), BAR_Y - 0.03, PARTY_LABELS[j],
                ha="center", va="top", fontsize=9, fontweight="bold",
                color=PARTY_COLORS[j], zorder=3)

    for b in zone_boundaries:
        ax.plot([b, b], [BAR_Y - 0.025, BAR_Y],
                color="#888888", lw=0.8, zorder=2)

    # Density curve
    curve_y = CURVE_BASE + density * CURVE_MAX
    ax.fill_between(x, CURVE_BASE, curve_y,
                    alpha=0.13, color=DENSITY_COLOR, zorder=4)
    ax.plot(x, curve_y, color=DENSITY_COLOR, lw=0.9, zorder=5)

    # Voter dots
    rng_j  = np.random.default_rng(SEED + 1)
    jitter = rng_j.uniform(0.01, BAR_H - 0.01, len(samples))
    dot_y  = BAR_Y + jitter
    dot_colors = [
        PARTY_COLORS[int(np.clip(int((s - xmin) / zone_length), 0, K - 1))]
        for s in samples
    ]
    ax.scatter(samples, dot_y, c=dot_colors, s=10,
               zorder=6, linewidths=0, alpha=0.85)

    # ell annotation (inter-party zone spacing)
    if row["annotate_ell"]:
        x0, x1 = zone_boundaries[1], zone_boundaries[2]
        y_ann  = CURVE_BASE + CURVE_MAX * 1.05
        ax.annotate("", xy=(x1, y_ann), xytext=(x0, y_ann),
                    arrowprops=dict(arrowstyle="<->", color="#333333",
                                    lw=1.1, mutation_scale=10),
                    zorder=7)
        ax.text(0.5 * (x0 + x1), y_ann + 0.025, r"$\ell = 2/K$",
                ha="center", va="bottom", fontsize=8, color="#333333")

    # Gaussian annotations: xi and omega = c*ell
    gp = row.get("gaussian_params")
    if gp is not None:
        xi_loc = gp["xi"]
        omega  = gp["omega"]
        ac     = "#1a5276"
        peak_y = CURVE_BASE + CURVE_MAX

        ax.plot([xi_loc, xi_loc], [BAR_Y, peak_y],
                color=ac, lw=0.9, ls="--", zorder=8, alpha=0.8)
        ax.text(xi_loc + 0.02, CURVE_BASE + 0.02, r"$\xi$",
                ha="left", va="bottom", fontsize=8.5, color=ac)

        y_om = CURVE_BASE + CURVE_MAX * 0.50
        ax.annotate("", xy=(xi_loc + omega, y_om),
                    xytext=(xi_loc - omega, y_om),
                    arrowprops=dict(arrowstyle="<->", color=ac,
                                    lw=0.9, mutation_scale=9), zorder=8)
        ax.text(xi_loc + omega, y_om, r"$\omega$",
                ha="left", va="center", fontsize=8.5, color=ac)

    # Axes
    ax.set_xlim(xmin - 0.05, xmax + 0.05)
    ax.set_ylim(BAR_Y - 0.12, CURVE_BASE + CURVE_MAX + 0.15)
    ax.set_yticks([])
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


# =========================================================================== #
#  FIGURE                                                                      #
# =========================================================================== #

def draw_figure() -> plt.Figure:
    """Build and return the symmetric unimodal distribution figure."""
    row = make_row()

    fig, ax = plt.subplots(figsize=(9.5, 2.3), facecolor="white")
    ax.set_facecolor("white")
    draw_row(ax, row)

    fig.legend(
        handles=[plt.Line2D([0], [0], marker="o", color="w",
                            markerfacecolor="#888888", markersize=5,
                            label="Sampled voters")],
        loc="lower center", bbox_to_anchor=(0.5, -0.01),
        ncol=1, fontsize=8.5, frameon=False,
    )

    return fig


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #

if __name__ == "__main__":
    fig = draw_figure()
    out = "distribution_figure.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Saved: {out}")
    plt.show()
