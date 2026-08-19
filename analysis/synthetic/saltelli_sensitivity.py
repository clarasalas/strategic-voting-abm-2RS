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
    This design uses calc_second_order=False, so the Saltelli sample size is
    N_saltelli * (k + 2) evaluations -- NOT the N * (2k + 2) of the full
    second-order design.  Second-order indices are not estimated, which is what
    saves the extra N * k runs.

    k=8 parameters → N_saltelli * 10 runs
    N_saltelli=1024 → 10,240 runs per K value
    3 K values     → 30,720 total runs

    That is exactly the row count of the committed
    data/saltelli_results_K{6,8,9}.csv files (10,240 each); the 2k+2 formula
    would imply a non-integer base sample of 568.9 and is simply wrong here.

    At ~0.1s per run (N=2000 electors): ~50 minutes total.
    At ~0.05s per run: ~25 minutes.

    The committed result files mean this cost can be avoided entirely: use
    --analyze-existing to recompute the Sobol indices from them.

Outputs
-------
    saltelli_samples_K{k}.csv           raw parameter samples
    saltelli_results_K{k}.csv           outcomes for each sample
    saltelli_sobol_K{k}.csv             S1 and ST indices per parameter
    saltelli_sobol_K{k}.png             bar chart of Sobol indices
    saltelli_comparison_{outcome}.png   S1 and ST across K values (overlay)
    saltelli_sobol_all.csv              combined index table across all K
    results/tables/sobol_indices.csv    committed reader-facing table
                                        (K, outcome, parameter, S1, S1_conf,
                                         ST, ST_conf, n_base, n_evaluations)

Usage
-----
    python analysis/synthetic/saltelli_sensitivity.py                    # full re-run
    python analysis/synthetic/saltelli_sensitivity.py --analyze-existing # indices only

    --analyze-existing recomputes the Sobol indices from the committed
    data/saltelli_results_K{6,8,9}.csv without re-running a single simulation,
    and writes results/tables/sobol_indices.csv.

    To run a single K value only, set K_VALUES = [6] at the top.
    To do a quick test run, set N_SALTELLI = 64 (gives 640 runs per K).
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
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / "core_model"))

import functions
from metrics import tau_absolute
from model import run_simulation

# =========================================================================== #
#  CONFIGURATION                                                               #
# =========================================================================== #

# K values to run separately
K_VALUES = [6, 8, 9]

# Saltelli sample size (power of 2 recommended)
# calc_second_order=False, so evaluations = N_SALTELLI * (num_vars + 2).
# N_SALTELLI = 64      # quick test: 64 * 10 = 640 runs per K
N_SALTELLI = 1024      # full run:   1024 * 10 = 10240 runs per K

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
    tau_abs = tau_absolute(params["tau_hat"], K)

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
    n_total = N_SALTELLI * (PROBLEM["num_vars"] + 2)   # calc_second_order=False
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
#  REANALYSIS FROM COMMITTED RESULTS                                           #
# =========================================================================== #
#
# The 30,720 model evaluations behind data/saltelli_results_K{6,8,9}.csv are
# committed, so the Sobol indices can be recomputed without running the model
# at all.  Everything below reads those files and writes the reader-facing
# table; it never calls run_simulation.

TABLES_DIR = REPO / "results" / "tables"

# Fixed seed for the bootstrap confidence intervals, so repeated runs of
# --analyze-existing reproduce the same S1_conf / ST_conf to the last digit.
CONF_SEED = 20020422

SOBOL_TABLE_COLUMNS = [
    "K", "outcome", "parameter",
    "S1", "S1_conf", "ST", "ST_conf",
    "n_base", "n_evaluations",
]


def infer_base_sample(n_rows: int, num_vars: int = None) -> int:
    """
    Recover the Saltelli base sample size N from a result file's row count.

    With calc_second_order=False the design is N * (D + 2) evaluations, so
    N = n_rows / (D + 2).  Raises if that is not an exact integer -- a
    non-integer means the file does not come from this design at all.
    """
    D = PROBLEM["num_vars"] if num_vars is None else num_vars
    per_base = D + 2
    if n_rows % per_base != 0:
        raise ValueError(
            f"{n_rows} rows is not a multiple of (D + 2) = {per_base}, so it "
            f"cannot come from a calc_second_order=False Saltelli design "
            f"(implied base sample {n_rows / per_base:.4f}). Note that the "
            f"full second-order formula N*(2D+2) does NOT apply here."
        )
    return n_rows // per_base


def load_existing_results(K: int, verify_design: bool = True) -> tuple:
    """
    Load data/saltelli_results_K{K}.csv and validate it against the design.

    Validates, in order:
      * every parameter column and every outcome column is present;
      * the row count implies an integer Saltelli base sample size;
      * (verify_design) the parameter columns reproduce the Saltelli sample
        that saltelli.sample(PROBLEM, N, calc_second_order=False) generates --
        this checks row ORDER as well as count, and the Sobol estimator is
        order-sensitive, so it is the check that actually matters.

    Returns (dataframe, n_base).
    """
    path = REPO / "data" / f"saltelli_results_K{K}.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing committed result file: {path}")

    df = pd.read_csv(path)

    missing_params = [c for c in PROBLEM["names"] if c not in df.columns]
    if missing_params:
        raise ValueError(f"{path.name}: missing parameter columns {missing_params}")
    missing_outcomes = [c for c in OUTCOMES if c not in df.columns]
    if missing_outcomes:
        raise ValueError(f"{path.name}: missing outcome columns {missing_outcomes}")

    n_base = infer_base_sample(len(df))

    if verify_design:
        expected = saltelli.sample(PROBLEM, N=n_base, calc_second_order=False)
        actual = df[PROBLEM["names"]].to_numpy(dtype=float)
        if actual.shape != expected.shape:
            raise ValueError(
                f"{path.name}: parameter block is {actual.shape}, "
                f"design expects {expected.shape}")
        max_dev = float(np.abs(actual - expected).max())
        if max_dev > 1e-9:
            raise ValueError(
                f"{path.name}: rows do not match the Saltelli design for "
                f"N={n_base} (max deviation {max_dev:.3e}). Row order matters "
                f"to the Sobol estimator, so this file cannot be analysed."
            )

    return df, n_base


def analyze_existing(K: int, verify_design: bool = True) -> tuple:
    """
    Recompute Sobol indices for one K from the committed results.

    Returns (sobol_results, n_base, n_evaluations) where sobol_results maps
    outcome -> the SALib Si object.  The table writer and the plots both take
    that same object, so their numbers cannot diverge.
    """
    df, n_base = load_existing_results(K, verify_design=verify_design)
    n_eval = len(df)
    print(f"  K={K}: {n_eval} evaluations, base sample N={n_base} "
          f"(N x (D+2) = {n_base} x {PROBLEM['num_vars'] + 2})")

    sobol_results = {}
    for outcome in OUTCOMES:
        Y = df[outcome].to_numpy(dtype=float)
        n_nan = int(np.isnan(Y).sum())
        if n_nan:
            print(f"    WARNING: {n_nan} NaN in {outcome}; replacing with mean.")
            Y = np.where(np.isnan(Y), np.nanmean(Y), Y)
        sobol_results[outcome] = sobol.analyze(
            PROBLEM, Y,
            calc_second_order=False,
            print_to_console=False,
            seed=CONF_SEED,
        )
    return sobol_results, n_base, n_eval


def sobol_table(all_sobol: dict, meta: dict) -> pd.DataFrame:
    """
    Build the combined reader-facing table from the SAME Si objects the plots
    consume.

    all_sobol : {K: {outcome: Si}}
    meta      : {K: (n_base, n_evaluations)}
    """
    rows = []
    for K in sorted(all_sobol):
        n_base, n_eval = meta[K]
        for outcome in OUTCOMES:
            Si = all_sobol[K][outcome]
            for j, parameter in enumerate(PROBLEM["names"]):
                rows.append({
                    "K": K,
                    "outcome": outcome,
                    "parameter": parameter,
                    "S1": float(Si["S1"][j]),
                    "S1_conf": float(Si["S1_conf"][j]),
                    "ST": float(Si["ST"][j]),
                    "ST_conf": float(Si["ST_conf"][j]),
                    "n_base": int(n_base),
                    "n_evaluations": int(n_eval),
                })
    df = pd.DataFrame(rows, columns=SOBOL_TABLE_COLUMNS)
    # Stable sort order so regeneration is byte-identical.
    return df.sort_values(["K", "outcome", "parameter"]).reset_index(drop=True)


def write_sobol_table(df: pd.DataFrame) -> Path:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    out = TABLES_DIR / "sobol_indices.csv"
    df.to_csv(out, index=False)
    print(f"  -> {out}  ({len(df)} rows)")
    return out


def run_analyze_existing() -> None:
    """CLI mode: indices and table from committed results, no simulation."""
    print("=" * 60)
    print("  Sobol reanalysis from committed results (no model runs)")
    print("=" * 60)
    all_sobol, meta = {}, {}
    for K in K_VALUES:
        sob, n_base, n_eval = analyze_existing(K)
        all_sobol[K] = sob
        meta[K] = (n_base, n_eval)

    write_sobol_table(sobol_table(all_sobol, meta))
    _plot_cross_k(all_sobol)          # same Si objects as the table
    print("\nDone. No model evaluations were performed.")


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Saltelli / Sobol sensitivity.")
    ap.add_argument(
        "--analyze-existing", action="store_true",
        help="recompute Sobol indices from the committed "
             "data/saltelli_results_K*.csv instead of re-running the model, "
             "and write results/tables/sobol_indices.csv",
    )
    args = ap.parse_args()

    if args.analyze_existing:
        run_analyze_existing()
        return

    all_sobol, meta = {}, {}
    for K in K_VALUES:
        all_sobol[K] = _run_analysis(K)
        meta[K] = (N_SALTELLI, N_SALTELLI * (PROBLEM["num_vars"] + 2))
    _plot_cross_k(all_sobol)
    write_sobol_table(sobol_table(all_sobol, meta))
    _print_summary()


if __name__ == "__main__":
    main()
