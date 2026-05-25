"""
robustness_checks.py
--------------------
All protocol robustness checks, run from scratch and plotted in one pass.
No pre-existing CSV files required.

Panels
------
A — N robustness:        SE of ΔCENP across N ∈ {250, 500, 1000, 2000, 5000}
B — Tmax convergence:    hard fixed-point convergence time distribution
C — epsilon stability:   ΔCENP invariance across signal offset εs values
D — xi (mode position):  final vs sincere ENP across electorate centre ξ
E — signal temperature:  mechanical effect of θ (analytical, no simulation)
F — mu (expressive cost): conditional switching rate vs expressive cost μ

Panels A–D are the simulation protocol checks (Appendix B in the paper).
Panel E verifies the signal mechanism (Appendix C).
Panel F documents the behavioral parameter μ (Appendix D).

Run cost
--------
Approximate timings at 0.1 s/run (N=1000 or N=500 for most panels):
Panel A : 4 regimes × 5 N values × 30 reps     =  600 runs
Panel B : 4 regimes × 20 reps                  =   80 runs
Panel C : 4 configs × 5 eps values × 10 reps   =  200 runs
Panel D : 9 xi values × 20 reps                =  180 runs
Panel E : 0 (analytical)
Panel F : 2 regimes × 8 mu values × 30 reps    =  480 runs
Total   : ~1 540 runs  (~2–4 minutes)

Usage
-----
    python robustness_checks.py              # run all panels
    python robustness_checks.py --panels A B # run specific panels only

Outputs
-------
All files written to outputs/robustness_checks/
    panel_A_N_robustness.png   / panel_A_raw.csv
    panel_B_tmax_convergence.png / panel_B_raw.csv
    panel_C_epsilon_stability.png / panel_C_raw.csv
    panel_D_xi_analysis.png    / panel_D_raw.csv
    panel_E_signal_temperature.png
    panel_F_mu_analysis.png    / panel_F_raw.csv
    protocol_grid.png           2×2 grid of A–D  (requires Pillow)
"""

import argparse
import functools
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import functions
import signals as _signals
from model import run_simulation
from signals import transform_signal

# =========================================================================== #
#  OUTPUT DIRECTORY                                                            #
# =========================================================================== #

OUT_DIR = Path(__file__).parent / "outputs" / "robustness_checks"

# =========================================================================== #
#  GLOBAL STYLE                                                                #
# =========================================================================== #

plt.rcParams.update({
    "font.family":          "serif",
    "font.size":            9,
    "axes.titlesize":       10,
    "axes.titleweight":     "bold",
    "axes.labelsize":       9,
    "axes.spines.top":      False,
    "axes.spines.right":    False,
    "axes.grid":            True,
    "grid.color":           "#e0e0e0",
    "grid.linewidth":       0.5,
    "grid.alpha":           0.6,
    "xtick.labelsize":      8,
    "ytick.labelsize":      8,
    "legend.fontsize":      8,
    "legend.framealpha":    0.9,
    "legend.edgecolor":     "#cccccc",
    "lines.linewidth":      1.8,
    "lines.markersize":     5,
    "savefig.dpi":          300,
    "savefig.bbox":         "tight",
})

SPECTRAL = plt.cm.Spectral

# =========================================================================== #
#  SHARED SIMULATION PARAMETERS (panels A–D)                                  #
# =========================================================================== #
#
# Panels A–D use K=6, the protocol-check baseline.
# Panel F uses K=8 to match the main figures — see its own constants below.
#
# Note on rho_pi: the original T_max_check.py used rho_pi=10 while
# epsilon_check.py used rho_pi=100.  We unify on 100 here to match the
# main Saltelli baseline; the key finding (stability / convergence) is
# insensitive to this choice.

BASE_K       = 6
BASE_TAU_ABS = 1.0 * (2.0 / BASE_K)   # τ̂ = 1.0, converted to absolute units
BASE_THETA   = 1.0
BASE_MU      = 0.0
BASE_ALPHA   = 0.0
BASE_RHO_S   = 100.0
BASE_RHO_PI  = 100.0
BASE_FLOOR   = 0.1
BASE_TMAX    = 25

# Width regimes used across panels A and B
REGIMES: dict = {
    "baseline":   ("Low ($c=0.5$)",       0.5,  SPECTRAL(0.15)),
    "width_A":    ("Active A ($c=1.25$)", 1.25, SPECTRAL(0.38)),
    "width_B":    ("Active B ($c=1.5$)",  1.5,  SPECTRAL(0.70)),
    "high_width": ("Diffuse ($c=2.5$)",   2.5,  SPECTRAL(0.85)),
}

# =========================================================================== #
#  SHARED HELPERS                                                              #
# =========================================================================== #


def _enp(shares: np.ndarray) -> float:
    s = np.asarray(shares, dtype=float)
    s = s / s.sum() if s.sum() > 0 else s
    sq = (s ** 2).sum()
    return 1.0 / sq if sq > 0 else float("nan")


def _save(fig: plt.Figure, name: str) -> None:
    """Save figure to OUT_DIR and close it."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {path}")


# =========================================================================== #
#  PANEL A — N ROBUSTNESS                                                     #
# =========================================================================== #
#
# How many voters does the model need before ΔCENP estimates stabilise?
# We compute the SE of ΔCENP across N_REPS_A runs for each (regime, N) pair
# and plot SE as a function of N.  A dashed line marks N = N_CHOSEN,
# the value adopted for the main analyses.

N_VALUES_A = [250, 500, 1000, 2000, 5000]
N_REPS_A   = 30
N_CHOSEN   = 2000


def _simulate_N_robustness() -> pd.DataFrame:
    """
    Returns one row per (scenario_name, N, seed) with a delta_cenp column.
    """
    rows  = []
    total = len(REGIMES) * len(N_VALUES_A) * N_REPS_A
    done  = 0

    for scenario_name, (label, c_val, _) in REGIMES.items():
        for n in N_VALUES_A:
            for seed in range(N_REPS_A):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = run_simulation(
                        K=BASE_K, n_modes=1,
                        width_factor=c_val,
                        mode_position=0.0, floor_weight=BASE_FLOOR,
                        theta=BASE_THETA, rho=BASE_RHO_S, rho_pi=BASE_RHO_PI,
                        n_electors=n,
                        tau=BASE_TAU_ABS, mu=BASE_MU, alpha_prior=BASE_ALPHA,
                        K_runoff=2, max_iterations=BASE_TMAX,
                        seed=seed, verbose=False, collect_diagnostics=False,
                    )
                sincere = np.array(result["sincere_shares"])
                final   = np.array(result["final_shares"])
                cm      = functions.coordination_measures(sincere, final)
                rows.append({
                    "scenario_name": scenario_name,
                    "label":         label,
                    "N":             n,
                    "seed":          seed,
                    "delta_cenp":    cm["delta_cenp"],
                })
                done += 1
                if done % 100 == 0:
                    print(f"    Panel A: {done}/{total}")

    return pd.DataFrame(rows)


def _plot_N_robustness(df: pd.DataFrame) -> plt.Figure:
    agg = df.groupby(["scenario_name", "N"]).agg(
        se=("delta_cenp", lambda x: x.std() / np.sqrt(len(x)))
    ).reset_index()

    n_vals = sorted(agg["N"].unique())
    x_pos  = np.arange(len(n_vals))
    n_to_x = {n: i for i, n in enumerate(n_vals)}

    fig, ax = plt.subplots(figsize=(5.5, 4))

    for scenario_name, (label, _, color) in REGIMES.items():
        sub = agg[agg["scenario_name"] == scenario_name].sort_values("N")
        if sub.empty:
            continue
        ax.plot([n_to_x[n] for n in sub["N"]], sub["se"],
                marker="o", color=color, label=label)

    if N_CHOSEN in n_to_x:
        ax.axvline(n_to_x[N_CHOSEN], color="#aaaaaa", linewidth=0.9,
                   linestyle="--", alpha=0.8, label=f"$N = {N_CHOSEN:,}$")

    ax.set_xticks(x_pos)
    ax.set_xticklabels([f"{int(n):,}" for n in n_vals], fontsize=8)
    ax.set_xlabel("Number of voters $N$")
    ax.set_ylabel(r"SE of $\Delta C_{\mathrm{ENP}}$")
    ax.set_title("$N$ robustness")
    ax.legend(fontsize=7.5, bbox_to_anchor=(1.02, 1),
              loc="upper left", borderaxespad=0)
    fig.tight_layout()
    return fig


# =========================================================================== #
#  PANEL B — TMAX CONVERGENCE                                                 #
# =========================================================================== #
#
# Does the model reach a hard fixed point within Tmax iterations?
# Criterion: no voter changes their vote intention between two consecutive
# iterations.  This is the strictest possible convergence check.
# Runs that hit the Tmax ceiling are counted and annotated in the figure.

TMAX_CEILING_B = 30   # generous ceiling to observe tail behaviour
N_B            = 500  # cheap N — sufficient for timing the fixed point
N_REPS_B       = 20


def _find_convergence_iter(intention_history: list, tmax: int) -> int:
    """
    Return the first iteration t at which no voter changed their intention
    compared to t−1.  Returns tmax if convergence never occurs.
    """
    for t in range(1, len(intention_history)):
        if np.array_equal(intention_history[t], intention_history[t - 1]):
            return t
    return tmax


def _simulate_tmax() -> pd.DataFrame:
    """
    Returns one row per (scenario_name, seed) with convergence_iter.
    """
    rows  = []
    total = len(REGIMES) * N_REPS_B
    done  = 0

    for scenario_name, (label, c_val, _) in REGIMES.items():
        for seed in range(N_REPS_B):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = run_simulation(
                    K=BASE_K, n_modes=1,
                    width_factor=c_val,
                    mode_position=0.0, floor_weight=BASE_FLOOR,
                    theta=BASE_THETA, rho=BASE_RHO_S, rho_pi=BASE_RHO_PI,
                    n_electors=N_B,
                    tau=BASE_TAU_ABS, mu=BASE_MU, alpha_prior=BASE_ALPHA,
                    K_runoff=2, max_iterations=TMAX_CEILING_B,
                    seed=seed, verbose=False, collect_diagnostics=False,
                )
            ct = _find_convergence_iter(
                result["intention_history"], TMAX_CEILING_B)
            rows.append({
                "scenario_name":    scenario_name,
                "regime":           label,
                "seed":             seed,
                "convergence_iter": ct,
            })
            done += 1
            if done % 10 == 0:
                print(f"    Panel B: {done}/{total}")

    return pd.DataFrame(rows)


def _build_tmax_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-run convergence times to summary statistics per regime."""
    rows = []
    for scenario_name, (label, _, _) in REGIMES.items():
        times    = df[df["scenario_name"] == scenario_name]["convergence_iter"].values
        n_binding = int(np.sum(times == TMAX_CEILING_B))
        converged = times[times < TMAX_CEILING_B]
        p95 = (float(np.percentile(converged, 95))
               if len(converged) > 1 else float("nan"))
        rows.append({
            "regime":         label,
            "median_conv":    float(np.median(times)),
            "p95_conv":       p95,
            "n_tmax_binding": n_binding,
        })
    return pd.DataFrame(rows)


def _plot_tmax(df_raw: pd.DataFrame) -> plt.Figure:
    df = _build_tmax_summary(df_raw)
    label_to_color = {label: color for _, (label, _, color) in REGIMES.items()}

    fig, ax = plt.subplots(figsize=(5.5, 4))
    x   = np.arange(len(df))
    bw  = 0.32
    colors = [label_to_color.get(r, SPECTRAL(0.7)) for r in df["regime"]]

    ax.bar(x - bw / 2, df["median_conv"], bw,
           label="Median", alpha=0.85, color=colors, zorder=3)
    ax.bar(x + bw / 2, df["p95_conv"], bw,
           label="$p_{95}$", alpha=0.4, color=colors,
           hatch="///", edgecolor="white", linewidth=0.4, zorder=3)

    for i, (_, row) in enumerate(df.iterrows()):
        if row["n_tmax_binding"] > 0:
            ax.text(i + bw / 2, row["p95_conv"] + 0.4,
                    f"{int(row['n_tmax_binding'])}/{N_REPS_B} did not converge",
                    ha="center", fontsize=6.5, color="#333333", style="italic")

    ax.axhline(BASE_TMAX, color="#aaaaaa", linewidth=0.9,
               linestyle="--", zorder=2, label=f"$T_{{\\max}} = {BASE_TMAX}$")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [r.replace(" (", "\n(") for r in df["regime"]], fontsize=7.5)
    ax.set_ylabel("Convergence iteration")
    ax.set_title("$T_{\\max}$ convergence diagnostic")
    ax.legend(fontsize=7.5, loc="upper left")
    fig.tight_layout()
    return fig


# =========================================================================== #
#  PANEL C — EPSILON STABILITY                                                #
# =========================================================================== #
#
# Is ΔCENP invariant to the numerical offset εs added before the temperature
# transformation?  We vary εs across five values and check that outcome
# measures remain flat.  The most sensitive case is θ < 1 with concentrated
# support (low c), where some parties may have near-zero share.
#
# Implementation note: run_simulation does not expose εs as a parameter, so
# we temporarily patch signals.generate_signal to inject the desired value.
# The original function is always restored in the finally block.

EPS_VALUES_C = [1e-6, 1e-4, 1e-3, 1e-2, 1e-1]
CHOSEN_EPS   = 1e-4   # value adopted in all main analyses
N_C          = 1000
N_REPS_C     = 10
TMAX_C       = 10     # short run is sufficient for a stability check

CONFIGS_C = [
    ("Baseline, theta=0.3",   0.5, 0.3),
    ("Baseline, theta=1.0",   0.5, 1.0),
    ("Sweet-spot, theta=0.3", 1.5, 0.3),
    ("Sweet-spot, theta=1.0", 1.5, 1.0),
]


def _run_with_eps(eps_value: float, **kwargs) -> dict:
    """Run run_simulation with a patched εs value in signals.generate_signal."""
    original = _signals.generate_signal

    @functools.wraps(original)
    def _patched(true_support, theta=1.0, rho=100.0, eps=1e-12, rng=None):
        return original(true_support, theta=theta, rho=rho,
                        eps=eps_value, rng=rng)

    _signals.generate_signal = _patched
    try:
        return run_simulation(**kwargs)
    finally:
        _signals.generate_signal = original   # always restore


def _simulate_epsilon() -> pd.DataFrame:
    rows  = []
    total = len(CONFIGS_C) * len(EPS_VALUES_C) * N_REPS_C
    done  = 0

    for (label, c, theta) in CONFIGS_C:
        for eps in EPS_VALUES_C:
            delta_cenps, trigger_rates, cond_sws, total_sws = [], [], [], []

            for seed in range(N_REPS_C):
                result = _run_with_eps(
                    eps,
                    K=BASE_K, n_modes=1,
                    width_factor=c,
                    mode_position=0.0, floor_weight=BASE_FLOOR,
                    theta=theta, rho=BASE_RHO_S, rho_pi=BASE_RHO_PI,
                    n_electors=N_C,
                    tau=BASE_TAU_ABS, mu=BASE_MU, alpha_prior=BASE_ALPHA,
                    K_runoff=2, max_iterations=TMAX_C,
                    seed=seed, verbose=False, collect_diagnostics=True,
                )
                sincere = np.array(result["sincere_shares"])
                final   = np.array(result["final_shares"])
                diag    = result["diagnostics"]
                cm      = functions.coordination_measures(sincere, final)

                delta_cenps.append(cm["delta_cenp"])
                trigger_rates.append(diag["trigger_rate_final"])
                cond_sws.append(
                    diag["conditional_switching_given_triggered"])
                total_sws.append(result["switching"]["pct_strategic"])

                done += 1
                if done % 20 == 0:
                    print(f"    Panel C: {done}/{total}")

            rows.append({
                "config":               label,
                "c":                    c,
                "theta":                theta,
                "eps":                  eps,
                "delta_cenp_mean":      float(np.mean(delta_cenps)),
                "delta_cenp_sd":        float(np.std(delta_cenps)),
                "trigger_rate_mean":    float(np.mean(trigger_rates)),
                "cond_switching_mean":  float(np.mean(cond_sws)),
                "total_switching_mean": float(np.mean(total_sws)),
            })

    return pd.DataFrame(rows)


def _plot_epsilon(df: pd.DataFrame) -> plt.Figure:
    configs_to_plot = [
        ("Baseline, theta=0.3",   SPECTRAL(0.15), "-",  r"Baseline, $\theta=0.3$"),
        ("Baseline, theta=1.0",   SPECTRAL(0.38), "--", r"Baseline, $\theta=1.0$"),
        ("Sweet-spot, theta=0.3", SPECTRAL(0.70), "-",  r"Active, $\theta=0.3$"),
        ("Sweet-spot, theta=1.0", SPECTRAL(0.85), "--", r"Active, $\theta=1.0$"),
    ]
    eps_vals = sorted(df["eps"].unique())
    x_eps    = np.arange(len(eps_vals))

    fig, ax = plt.subplots(figsize=(5.5, 4))

    for config, color, ls, label in configs_to_plot:
        sub = df[df["config"] == config].sort_values("eps")
        if sub.empty:
            continue
        ax.plot(x_eps, sub["delta_cenp_mean"].values,
                marker="o", color=color, linestyle=ls, label=label)
        ax.fill_between(
            x_eps,
            sub["delta_cenp_mean"].values - sub["delta_cenp_sd"].values,
            sub["delta_cenp_mean"].values + sub["delta_cenp_sd"].values,
            alpha=0.06, color=color,
        )

    try:
        chosen_idx = eps_vals.index(CHOSEN_EPS)
    except ValueError:
        chosen_idx = 1
    ax.axvline(chosen_idx, color="#aaaaaa", linewidth=0.9,
               linestyle="--", alpha=0.9,
               label=r"Chosen $\varepsilon_s = 10^{-4}$")

    ax.set_xticks(x_eps)
    ax.set_xticklabels(
        [f"$10^{{{int(np.log10(e))}}}$" for e in eps_vals], fontsize=8.5)
    ax.set_xlabel(r"Signal offset $\varepsilon_s$")
    ax.set_ylabel(r"$\Delta C_{\mathrm{ENP}}$")
    ax.set_title(r"Signal offset $\varepsilon_s$ stability")
    ax.legend(fontsize=7.5, bbox_to_anchor=(1.02, 1),
              loc="upper left", borderaxespad=0)
    fig.tight_layout()
    return fig


# =========================================================================== #
#  PANEL D — XI (MODE POSITION) ANALYSIS                                      #
# =========================================================================== #
#
# Does shifting the electorate centre ξ change coordination outcomes, or
# does the pattern just track the geometric relationship between ξ and the
# equal-spacing party positions?  We expect a zigzag in both sincere and
# final ENP that aligns with party positions — a geometric artefact, not a
# behavioural effect.  This motivates fixing ξ = 0 in the main analyses.

XI_VALUES_D = np.linspace(-0.75, 0.75, 9)
N_D         = 1000
N_REPS_D    = 20
C_D         = 0.5   # baseline width; keeps party geometry simple


def _simulate_xi() -> pd.DataFrame:
    rows  = []
    total = len(XI_VALUES_D) * N_REPS_D
    done  = 0

    for xi in XI_VALUES_D:
        for seed in range(N_REPS_D):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = run_simulation(
                    K=BASE_K, n_modes=1,
                    width_factor=C_D,
                    mode_position=float(xi), floor_weight=BASE_FLOOR,
                    theta=BASE_THETA, rho=BASE_RHO_S, rho_pi=BASE_RHO_PI,
                    n_electors=N_D,
                    tau=BASE_TAU_ABS, mu=BASE_MU, alpha_prior=BASE_ALPHA,
                    K_runoff=2, max_iterations=BASE_TMAX,
                    seed=seed, verbose=False, collect_diagnostics=False,
                )
            sincere = np.array(result["sincere_shares"])
            final   = np.array(result["final_shares"])
            rows.append({
                "xi":          float(xi),
                "theta":       BASE_THETA,
                "seed":        seed,
                "enp_sincere": _enp(sincere),
                "enp_final":   _enp(final),
            })
            done += 1
            if done % 20 == 0:
                print(f"    Panel D: {done}/{total}")

    return pd.DataFrame(rows)


def _plot_xi(df: pd.DataFrame) -> plt.Figure:
    sub = df[np.isclose(df["theta"], BASE_THETA)].copy()
    agg = sub.groupby("xi").agg(
        enp_final_mean   =("enp_final",   "mean"),
        enp_final_se     =("enp_final",   lambda x: x.std() / np.sqrt(len(x))),
        enp_sincere_mean =("enp_sincere", "mean"),
        enp_sincere_se   =("enp_sincere", lambda x: x.std() / np.sqrt(len(x))),
    ).reset_index().sort_values("xi")

    color_final   = SPECTRAL(0.15)
    color_sincere = SPECTRAL(0.85)
    party_positions = [-1 + (2 * j + 1) / BASE_K for j in range(BASE_K)]

    fig, ax = plt.subplots(figsize=(5.5, 4))

    for xp in party_positions:
        ax.axvline(xp, color="#dddddd", linewidth=0.6, linestyle=":", zorder=1)

    ax.plot(agg["xi"], agg["enp_sincere_mean"],
            color=color_sincere, linewidth=1.5, marker="s", markersize=4,
            linestyle="--", label="Sincere ENP", zorder=2)
    ax.fill_between(
        agg["xi"],
        agg["enp_sincere_mean"] - agg["enp_sincere_se"],
        agg["enp_sincere_mean"] + agg["enp_sincere_se"],
        alpha=0.10, color=color_sincere, zorder=2,
    )

    ax.plot(agg["xi"], agg["enp_final_mean"],
            color=color_final, linewidth=2, marker="o", markersize=5,
            label="Final ENP", zorder=3)
    ax.fill_between(
        agg["xi"],
        agg["enp_final_mean"] - agg["enp_final_se"],
        agg["enp_final_mean"] + agg["enp_final_se"],
        alpha=0.15, color=color_final, zorder=3,
    )

    ax.set_xlabel(r"Electorate centre $\xi$")
    ax.set_ylabel("ENP")
    ax.set_title(r"ENP across $\xi$  ($\theta = 1$, $c = 0.5$)")
    ax.legend(fontsize=8, loc="lower center",
              bbox_to_anchor=(0.5, -0.32), ncol=2, borderaxespad=0)
    fig.tight_layout()
    return fig


# =========================================================================== #
#  PANEL E — MECHANICAL EFFECT OF SIGNAL TEMPERATURE (ANALYTICAL)            #
# =========================================================================== #
#
# This panel requires no simulation.  It shows how θ distorts the signal
# shape deterministically before any voter responds.  The right subplot
# quantifies the distortion as ΔENP = ENP(s̃) − ENP(δ), which is negative
# for θ < 1 (concentration-amplifying) and positive for θ > 1 (flattening).

BASELINE_SHARES_E = np.array([0.05, 0.07, 0.18, 0.25, 0.22, 0.13, 0.07, 0.03])
THETA_VALUES_E    = [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0]
SHOW_THETAS_E     = [0.3, 1.0, 3.0]
SHOW_COLORS_E     = [SPECTRAL(0.32), SPECTRAL(0.70), SPECTRAL(0.90)]


def _plot_theta_mechanical() -> plt.Figure:
    delta0 = BASELINE_SHARES_E / BASELINE_SHARES_E.sum()
    K_e    = len(delta0)

    def _enp_local(shares):
        s = np.asarray(shares, dtype=float)
        s = s / s.sum()
        return 1.0 / (s ** 2).sum()

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(10, 4))

    # Left: transformed shares for three representative θ values
    x_parties = np.arange(K_e)
    bw = 0.22
    for theta_s, color, offset in zip(
            SHOW_THETAS_E, SHOW_COLORS_E, [-bw, 0, bw]):
        s_tilde = transform_signal(delta0, theta=theta_s)
        label = (r"$\theta = 1.0$ (sincere shares)"
                 if theta_s == 1.0 else f"$\\theta = {theta_s}$")
        ax0.bar(x_parties + offset, s_tilde, bw,
                color=color, alpha=0.7, label=label)

    ax0.set_xticks(x_parties)
    ax0.set_xticklabels([f"$P_{j + 1}$" for j in range(K_e)], fontsize=8)
    ax0.set_xlabel("Party")
    ax0.set_ylabel(r"Transformed signal share $\tilde{s}$")
    ax0.set_title(r"Signal distortion by $\theta$")
    ax0.legend(fontsize=7.5, ncol=1)

    # Right: ΔENP = ENP(s̃) − ENP(true shares) vs θ
    enp_orig  = _enp_local(delta0)
    delta_enp = [_enp_local(transform_signal(delta0, theta=t)) - enp_orig
                 for t in THETA_VALUES_E]

    ax1.plot(THETA_VALUES_E, delta_enp,
             color=SPECTRAL(0.90), linewidth=2, marker="o", markersize=5)
    ax1.axhline(0, color="#aaaaaa", linewidth=0.9,
                linestyle="--", label=r"No distortion ($\theta = 1$)")
    ax1.axvline(1.0, color="#aaaaaa", linewidth=0.7,
                linestyle=":", alpha=0.7)
    ax1.set_xlabel(r"Signal temperature $\theta$")
    ax1.set_ylabel(
        r"$\Delta\mathrm{ENP} = \mathrm{ENP}(\tilde{s}) - \mathrm{ENP}(\delta)$")
    ax1.set_title("Signal ENP deviation from true shares")
    ax1.legend(fontsize=7.5)

    fig.suptitle(
        r"Mechanical effect of $\theta$ before any behavioral response",
        fontsize=9, color="#555555", y=1.02,
    )
    fig.tight_layout()
    return fig


# =========================================================================== #
#  PANEL F — MU (EXPRESSIVE COST) ANALYSIS                                   #
# =========================================================================== #
#
# Does μ suppress conditional switching monotonically, independently of
# electorate width?  Panel F uses K=8 to match the main figures, not K=6.
# The two-regime comparison (active vs low width) shows that width governs
# the pool of triggered voters while μ governs what fraction of that pool
# acts — the two layers operate independently.

K_F       = 8
N_F       = 1000
TMAX_F    = 25
TAU_HAT_F = 1.75
TAU_ABS_F = TAU_HAT_F * (2.0 / K_F)
N_REPS_F  = 30

MU_VALUES_F = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]

REGIMES_F: dict = {
    "Active ($c=1.5$)": (1.5, SPECTRAL(0.70)),
    "Low ($c=0.5$)":    (0.5, SPECTRAL(0.15)),
}


def _simulate_mu() -> pd.DataFrame:
    rows  = []
    total = len(MU_VALUES_F) * len(REGIMES_F) * N_REPS_F
    done  = 0

    for regime_label, (c_val, _) in REGIMES_F.items():
        for mu_val in MU_VALUES_F:
            cond_sws = []
            for seed in range(N_REPS_F):
                try:
                    result = run_simulation(
                        K=K_F, n_modes=1, width_factor=c_val,
                        mode_position=0.0, floor_weight=0.1,
                        theta=1.0, rho=100.0, rho_pi=100.0,
                        n_electors=N_F, tau=TAU_ABS_F,
                        mu=mu_val, alpha_prior=0.0,
                        K_runoff=2, max_iterations=TMAX_F,
                        seed=seed, verbose=False,
                        collect_diagnostics=True,
                    )
                    cond_sws.append(
                        result["diagnostics"]["conditional_switching_given_triggered"]
                    )
                except Exception as e:
                    print(f"    WARNING: run failed ({e})")
                done += 1
                if done % 50 == 0:
                    print(f"    Panel F: {done}/{total}")

            rows.append({
                "regime":       regime_label,
                "c":            c_val,
                "mu":           mu_val,
                "cond_sw_mean": float(np.mean(cond_sws)) if cond_sws else float("nan"),
                "cond_sw_se":   (float(np.std(cond_sws) / np.sqrt(len(cond_sws)))
                                 if len(cond_sws) > 1 else float("nan")),
            })

    return pd.DataFrame(rows)


def _plot_mu(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(5.5, 4))

    for regime_label, (c_val, color) in REGIMES_F.items():
        sub = df[df["regime"] == regime_label].sort_values("mu")
        ax.plot(sub["mu"], sub["cond_sw_mean"],
                color=color, linewidth=2, marker="o",
                markersize=5, label=regime_label)
        ax.fill_between(
            sub["mu"],
            sub["cond_sw_mean"] - sub["cond_sw_se"],
            sub["cond_sw_mean"] + sub["cond_sw_se"],
            alpha=0.2, color=color,
        )

    ax.set_xlabel(r"Expressive cost $\mu$")
    ax.set_ylabel("Conditional switching rate")
    ax.set_title(r"Conditional switching vs expressive cost $\mu$")
    ax.legend(fontsize=8)
    ax.text(
        0.98, 0.95,
        f"$K={K_F}$, $\\hat{{\\tau}}={TAU_HAT_F}$, $\\theta=1.0$\n"
        f"({N_REPS_F} runs per condition)",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=7.5, color="#555555",
    )
    fig.tight_layout()
    return fig


# =========================================================================== #
#  COMBINED 2×2 GRID (PANELS A–D)                                             #
# =========================================================================== #


def _assemble_protocol_grid() -> None:
    """Tile panels A–D into a single 2×2 PNG.  Requires Pillow."""
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow not installed — skipping 2×2 grid. "
              "Install with: pip install Pillow")
        return

    names = [
        "panel_A_N_robustness.png",
        "panel_B_tmax_convergence.png",
        "panel_C_epsilon_stability.png",
        "panel_D_xi_analysis.png",
    ]
    try:
        imgs = [Image.open(OUT_DIR / n) for n in names]
    except FileNotFoundError as e:
        print(f"  Grid skipped — missing file: {e}")
        return

    w, h = imgs[0].size
    grid = Image.new("RGB", (w * 2, h * 2), "white")
    for img, pos in zip(imgs, [(0, 0), (w, 0), (0, h), (w, h)]):
        grid.paste(img, pos)
    grid.save(OUT_DIR / "protocol_grid.png", dpi=(300, 300))
    print(f"  → {OUT_DIR}/protocol_grid.png  (2×2: A–D)")


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #

ALL_PANELS = ["A", "B", "C", "D", "E", "F"]

_SIMULATE = {
    "A": (_simulate_N_robustness, _plot_N_robustness,   "panel_A_N_robustness.png"),
    "B": (_simulate_tmax,         _plot_tmax,           "panel_B_tmax_convergence.png"),
    "C": (_simulate_epsilon,      _plot_epsilon,        "panel_C_epsilon_stability.png"),
    "D": (_simulate_xi,           _plot_xi,             "panel_D_xi_analysis.png"),
    "F": (_simulate_mu,           _plot_mu,             "panel_F_mu_analysis.png"),
}


def main(panels: list = None) -> None:
    if panels is None:
        panels = ALL_PANELS
    panels = [p.upper() for p in panels]

    print(f"\nRunning robustness checks: {panels}")
    print(f"Output directory: {OUT_DIR}/\n")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for panel in panels:
        if panel == "E":
            # Analytical — no simulation
            print("Panel E — signal temperature (analytical) …")
            _save(_plot_theta_mechanical(), "panel_E_signal_temperature.png")
            continue

        if panel not in _SIMULATE:
            print(f"  [skip] unknown panel: {panel}")
            continue

        simulate_fn, plot_fn, fname = _SIMULATE[panel]
        print(f"Panel {panel} — {fname.split('_', 2)[-1].replace('.png', '')} …")
        df = simulate_fn()
        df.to_csv(OUT_DIR / f"panel_{panel}_raw.csv", index=False)
        _save(plot_fn(df), fname)

    if all(p in panels for p in ["A", "B", "C", "D"]):
        _assemble_protocol_grid()

    print("\nAll robustness checks done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run protocol robustness checks and generate figures.",
    )
    parser.add_argument(
        "--panels", nargs="+", default=None, metavar="PANEL",
        help="Panels to run, e.g. --panels A B C  (default: all)",
    )
    args = parser.parse_args()
    main(panels=args.panels)
