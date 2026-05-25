"""
saltelli_sensitivity.py
-----------------------
Global variance-based sensitivity analysis using Saltelli sampling and
Sobol indices, implemented via SALib.

Fixed parameters (justified by preliminary analyses)
-----------------------------------------------------
    N          = 2000     (N robustness check)
    M          = 2        (French two-round institutional rule)
    Tmax       = 25       (convergence diagnostic: p95 across regimes)
    eps_signal = 1e-4     (epsilon stability check)
    xi         = 0.0      (symmetric benchmark; xi analysis showed
                           geometric artifact, not behavioral signal)
    K          ∈ {6,8,9}  (run separately; odd/even geometry distinction)

Free parameters (Saltelli parameter space)
------------------------------------------
    tau_hat  ∈ [0.5,  3.0]   normalized tolerance threshold
    c        ∈ [0.25, 3.0]   electorate width factor
    theta    ∈ [0.3,  3.0]   signal temperature
    rho_s    ∈ [10,   200]   signal precision
    rho_pi   ∈ [5,    200]   prior precision
    alpha    ∈ [0.0,  0.9]   prior weight in belief update
    mu       ∈ [0.0,  1.0]   expressive cost weight
    epsilon  ∈ [0.05, 0.5]   uniform floor weight

Outcome measures
----------------
    delta_cenp              coordination gain (primary)
    trigger_rate            strategic pressure
    cond_switching          behavioral response given pressure
    total_switching         overall switching rate
    enp_final               final effective number of parties

Run cost
--------
    SALib Saltelli: N_saltelli * (2*k + 2) evaluations
    k=8 parameters → N_saltelli * 18 runs
    N_saltelli=1024 → 18,432 runs per K value
    3 K values     → 55,296 total runs

    At ~0.1s per run (N=2000 electors): ~1.5 hours total.
    At ~0.05s per run: ~45 minutes.
    Recommend running overnight or on a machine with multiprocessing.

Outputs
-------
    saltelli_samples_K{k}.csv           raw parameter samples
    saltelli_results_K{k}.csv           outcomes for each sample
    saltelli_sobol_K{k}.csv             S1 and ST indices per parameter
    saltelli_sobol_K{k}.png             bar chart of Sobol indices
    saltelli_comparison_{outcome}.png   S1 and ST across K values (overlay)
    saltelli_sobol_all.csv              combined index table across all K

Usage
-----
    python saltelli_sensitivity.py

    To run a single K value only, set K_VALUES = [6] at the top.
    To do a quick test run, set N_SALTELLI = 64 (gives 1152 runs per K).
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from SALib.analyze import sobol
from SALib.sample import saltelli

ROOT = Path(__file__).parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "core_model"))

import functions
from model import run_simulation

# =========================================================================== #
#  CONFIGURATION                                                               #
# =========================================================================== #

# K values to run separately
K_VALUES = [6, 8, 9]

# Saltelli sample size (power of 2 recommended)
# N_SALTELLI = 64      # quick test: 64 * 18 = 1152 runs per K
N_SALTELLI = 1024      # full run:   1024 * 18 = 18432 runs per K

# Fixed parameters
N_ELECTORS = 2000
M_RUNOFF   = 2
TMAX       = 25
EPS_SIGNAL = 1e-4
XI         = 0.0       # mode position (symmetric)
N_MODES    = 1         # unimodal electorate

# Saltelli parameter space
PROBLEM = {
    "num_vars": 8,
    "names": [
        "tau_hat",   # normalized tolerance threshold
        "c",         # electorate width factor
        "theta",     # signal temperature
        "rho_s",     # signal precision
        "rho_pi",    # prior precision
        "alpha",     # prior weight
        "mu",        # expressive cost
        "epsilon",   # floor weight
    ],
    "bounds": [
        [0.5,   3.0],    # tau_hat
        [0.25,  3.0],    # c
        [0.3,   3.0],    # theta
        [10.0,  200.0],  # rho_s
        [5.0,   200.0],  # rho_pi
        [0.0,   0.9],    # alpha
        [0.0,   1.0],    # mu
        [0.05,  0.5],    # epsilon (floor weight)
    ],
}

# Outcome measures to analyse
OUTCOMES = [
    "delta_cenp",
    "trigger_rate",
    "cond_switching",
    "total_switching",
    "enp_final",
]

OUTCOME_LABELS = {
    "delta_cenp":      "ΔCENP",
    "trigger_rate":    "Trigger rate",
    "cond_switching":  "Cond. switching",
    "total_switching": "Total switching",
    "enp_final":       "Final ENP",
}

# Plot colours — defined once, reused across all K iterations
COLOR_S1 = plt.cm.Spectral(0.32)
COLOR_ST = plt.cm.Spectral(0.1)

# =========================================================================== #
#  SINGLE RUN WRAPPER                                                          #
# =========================================================================== #


def run_one(params: dict, K: int, seed: int) -> dict:
    """
    Run one simulation and return outcome measures.

    Parameters are drawn from the Saltelli sample and passed directly
    to run_simulation.  tau is converted from normalised (tau_hat) to
    absolute units here.
    """
    zone_length = 2.0 / K
    tau_abs = params["tau_hat"] * zone_length

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = run_simulation(
            K=K,
            n_modes=N_MODES,
            width_factor=params["c"],
            mode_position=XI,
            floor_weight=params["epsilon"],
            theta=params["theta"],
            rho=params["rho_s"],
            rho_pi=params["rho_pi"],
            n_electors=N_ELECTORS,
            tau=tau_abs,
            mu=params["mu"],
            alpha_prior=params["alpha"],
            K_runoff=M_RUNOFF,
            max_iterations=TMAX,
            seed=seed,
            verbose=False,
            collect_diagnostics=True,
        )

    sincere_shares = np.array(result["sincere_shares"])
    final_shares   = np.array(result["final_shares"])
    measures       = functions.coordination_measures(sincere_shares, final_shares)
    diag           = result["diagnostics"]

    return {
        "delta_cenp":      measures["delta_cenp"],
        "trigger_rate":    diag["trigger_rate_final"],
        "cond_switching":  diag["conditional_switching_given_triggered"],
        "total_switching": result["switching"]["pct_strategic"],
        "enp_final":       measures["enp_final"],
    }


# =========================================================================== #
#  PER-K SALTELLI ANALYSIS                                                     #
# =========================================================================== #


def _run_analysis(K: int) -> dict:
    """
    Run the full Saltelli analysis for one value of K.

    Returns
    -------
    dict mapping outcome name → SALib Si dict (S1, ST, confidence intervals).
    """
    n_total = N_SALTELLI * (2 * PROBLEM["num_vars"] + 2)
    print(f"\n{'=' * 60}")
    print(f"  K = {K}  |  {n_total} runs")
    print(f"{'=' * 60}")

    # ── 1. Generate Saltelli samples ──────────────────────────────────────
    param_values = saltelli.sample(
        PROBLEM,
        N=N_SALTELLI,
        calc_second_order=False,   # S2 not needed; saves N*k extra runs
    )
    n_runs = len(param_values)
    print(f"  Generated {n_runs} parameter samples.")

    pd.DataFrame(param_values, columns=PROBLEM["names"]).to_csv(
        ROOT / f"saltelli_samples_K{K}.csv", index=False
    )

    # ── 2. Run model for each sample ──────────────────────────────────────
    results_rows  = []
    outcome_arrays = {o: np.zeros(n_runs) for o in OUTCOMES}

    for i, sample in enumerate(param_values):
        if i % 500 == 0:
            print(f"    Run {i}/{n_runs}...")

        params = dict(zip(PROBLEM["names"], sample))
        try:
            outcomes = run_one(params, K=K, seed=i)
        except Exception as e:
            # On rare failures (e.g. degenerate parameter combinations),
            # fill with NaN and continue rather than crashing the whole run.
            print(f"    WARNING: run {i} failed ({e}). Filling with NaN.")
            outcomes = {o: np.nan for o in OUTCOMES}

        for o in OUTCOMES:
            outcome_arrays[o][i] = outcomes[o]
        results_rows.append({"run": i, **params, **outcomes})

    pd.DataFrame(results_rows).to_csv(REPO / "data" / f"saltelli_results_K{K}.csv", index=False)
    print(f"  Raw results saved to saltelli_results_K{K}.csv")

    # ── 3. Sobol analysis ─────────────────────────────────────────────────
    sobol_rows    = []
    sobol_results = {}

    for outcome in OUTCOMES:
        Y = outcome_arrays[outcome]

        n_nan = np.isnan(Y).sum()
        if n_nan > 0:
            print(f"    WARNING: {n_nan} NaN values in {outcome}. "
                  f"Replacing with mean.")
            Y = np.where(np.isnan(Y), np.nanmean(Y), Y)

        Si = sobol.analyze(
            PROBLEM, Y,
            calc_second_order=False,
            print_to_console=False,
        )
        sobol_results[outcome] = Si

        for j, param in enumerate(PROBLEM["names"]):
            sobol_rows.append({
                "K":       K,
                "outcome": outcome,
                "param":   param,
                "S1":      Si["S1"][j],
                "S1_conf": Si["S1_conf"][j],
                "ST":      Si["ST"][j],
                "ST_conf": Si["ST_conf"][j],
            })

    pd.DataFrame(sobol_rows).to_csv(ROOT / f"saltelli_sobol_K{K}.csv", index=False)
    print(f"  Sobol indices saved to saltelli_sobol_K{K}.csv")

    # ── 4. Per-K Sobol bar chart ───────────────────────────────────────────
    fig, axes = plt.subplots(
        1, len(OUTCOMES),
        figsize=(4 * len(OUTCOMES), 5),
        sharey=False,
    )
    params_list = PROBLEM["names"]
    x     = np.arange(len(params_list))
    width = 0.35

    for col, outcome in enumerate(OUTCOMES):
        ax = axes[col]
        Si = sobol_results[outcome]
        s1 = np.clip(Si["S1"], 0, None)  # clip numerical negatives near zero
        st = Si["ST"]

        ax.bar(x - width / 2, s1, width, label="S1 (first-order)",
               color=COLOR_S1, alpha=0.7,
               yerr=Si["S1_conf"], capsize=3)
        ax.bar(x + width / 2, st, width, label="ST (total)",
               color=COLOR_ST, alpha=0.7,
               yerr=Si["ST_conf"], capsize=3)

        ax.set_title(OUTCOME_LABELS[outcome], fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(params_list, rotation=45, ha="right", fontsize=8)
        ax.set_ylim(bottom=0)
        ax.set_ylabel("Sobol index")
        ax.axhline(0, color="black", linewidth=0.5)
        if col == 0:
            ax.legend(fontsize=8)

    fig.suptitle(
        f"Sobol sensitivity indices — K={K}\n"
        f"(N_saltelli={N_SALTELLI}, {n_runs} model runs, "
        f"N_electors={N_ELECTORS})",
        fontsize=11,
    )
    plt.tight_layout()
    plt.savefig(ROOT / f"saltelli_sobol_K{K}.png", dpi=150)
    plt.close()
    print(f"  Plot saved to saltelli_sobol_K{K}.png")

    return sobol_results


# =========================================================================== #
#  CROSS-K COMPARISON PLOTS                                                    #
# =========================================================================== #


def _plot_cross_k(all_sobol: dict) -> None:
    """Plot S1 and ST side-by-side for each outcome, overlaying all K values."""
    print("\nGenerating cross-K comparison plots...")

    k_colors     = [plt.cm.Spectral(v) for v in [0.1, 0.2, 0.32]]
    params_list  = PROBLEM["names"]
    x            = np.arange(len(params_list))
    width        = 0.25

    for outcome in OUTCOMES:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        for idx_k, K in enumerate(K_VALUES):
            Si     = all_sobol[K][outcome]
            s1     = np.clip(Si["S1"], 0, None)
            st     = Si["ST"]
            color  = k_colors[idx_k]
            offset = (idx_k - len(K_VALUES) / 2 + 0.5) * width

            axes[0].bar(x + offset, s1, width,
                        label=f"K={K}", color=color, alpha=0.6)
            axes[1].bar(x + offset, st, width,
                        label=f"K={K}", color=color, alpha=0.6)

        for ax, title in zip(axes, ["S1 (first-order)", "ST (total-order)"]):
            ax.set_title(f"{OUTCOME_LABELS[outcome]} — {title}", fontsize=10)
            ax.set_xticks(x)
            ax.set_xticklabels(params_list, rotation=45, ha="right", fontsize=9)
            ax.set_ylim(bottom=0)
            ax.set_ylabel("Sobol index")
            ax.axhline(0, color="black", linewidth=0.5)
            ax.legend(fontsize=9)

        plt.tight_layout()
        plt.savefig(ROOT / f"saltelli_comparison_{outcome}.png", dpi=150)
        plt.close()

    print("Cross-K comparison plots saved.")


# =========================================================================== #
#  SUMMARY TABLE                                                               #
# =========================================================================== #


def _print_summary() -> None:
    """Read per-K Sobol CSVs, combine, and print top parameters by ST."""
    combined = pd.concat(
        [pd.read_csv(ROOT / f"saltelli_sobol_K{K}.csv") for K in K_VALUES],
        ignore_index=True,
    )
    combined.to_csv(ROOT / "saltelli_sobol_all.csv", index=False)

    print("\nTop parameters by total-order index (ST), averaged across outcomes:")
    summary = (
        combined.groupby(["K", "param"])["ST"]
        .mean()
        .reset_index()
        .sort_values(["K", "ST"], ascending=[True, False])
    )
    print(summary.to_string(index=False))

    print("""
Done. Key output files:
  saltelli_sobol_K{6,8,9}.png           — Sobol indices per K
  saltelli_comparison_{outcome}.png     — cross-K comparison per outcome
  saltelli_sobol_all.csv                — all indices in one file

Interpretation guide
--------------------
S1 (first-order): direct contribution of each parameter to output variance.
ST (total-order): direct + all interaction effects.
ST - S1 >> 0    : parameter matters mainly through interactions.
ST ≈ S1 ≈ 0     : parameter has negligible effect across its full range.

Parameters with high ST but low S1 (e.g. rho_pi) are worth noting:
they only matter in combination with other parameters, not on their own.
""")


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #


def main() -> None:
    all_sobol = {}
    for K in K_VALUES:
        all_sobol[K] = _run_analysis(K)
    _plot_cross_k(all_sobol)
    _print_summary()


if __name__ == "__main__":
    main()
