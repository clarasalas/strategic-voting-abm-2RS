"""
empirical_2002_2022.py
----------------------
Empirical replay of the 2002 and 2022 French presidential first rounds.

This is pattern-oriented empirical calibration, not parameter recovery.  We
hold a behavioural parameter draw fixed and apply it to BOTH years (the primary
design), varying only the empirical environment (party positions, voter
ideology, poll signals) between years.  The question is whether the model
reproduces the 2002 fragmentation vs 2022 partial-coordination contrast under
plausible behavioural parameters.

Varied behavioural parameters (shared across years)
---------------------------------------------------
    tau_hat  in [0.5, 3.0]
    rho_pi   in [5, 200]
    alpha    in [0.0, 0.9]
    mu       in [0.0, 1.0]

Fixed / unused: theta, rho_s, eps_s, xi, c, eps_F -- the signal is exogenous
(empirical polls), so the signal-generating parameters play no role here.

Outputs (written to data/)
--------------------------
    empirical_runs_<year>.csv              one row per draw, all scalar metrics
    empirical_candidate_shares_<year>.csv  per-candidate aggregates
    empirical_robustness_<year>.csv        scalar metrics under 3 robustness
                                           variants

Usage
-----
    python analysis/empirical_2002_2022.py            # main + robustness
    python analysis/empirical_2002_2022.py --quick    # few draws, smoke run

Then build figures with:
    python analysis/empirical_figures.py
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "core_model"))

from model import run_simulation
from empirical_data import (
    load_year, sample_voters, perturb_positions,
    weekly_signal_timeline, individual_signal_timeline,
)
from empirical_outcomes import compute_run_outcomes

DATA_DIR = REPO / "data"
YEARS = (2002, 2022)

# =========================================================================== #
#  CONFIGURATION                                                               #
# =========================================================================== #

N_VOTERS = 2000
N_DRAWS = 300            # behavioural draws for the main experiment
N_DRAWS_ROBUST = 100     # draws per robustness variant
MASTER_SEED = 20020422   # reproducible parameter design

# Behavioural parameter ranges.
TAU_RANGE = (0.5, 3.0)
RHO_PI_RANGE = (5.0, 200.0)
ALPHA_RANGE = (0.0, 0.9)
MU_RANGE = (0.0, 1.0)

# Position perturbation magnitude on the [-1, 1] scale (robustness).
PERTURB_SIZE = 0.05

# Main spec: stop after the empirical signal sequence (no holding).
HOLD_LAST_SIGNAL = False
EXTRA_HOLD_ITERS = 10    # only used when HOLD_LAST_SIGNAL is True


# =========================================================================== #
#  PARAMETER DESIGN                                                            #
# =========================================================================== #

def _latin_hypercube(n: int, ranges: list, rng) -> np.ndarray:
    """Latin-hypercube sample (n x d) over the given (lo, hi) ranges."""
    d = len(ranges)
    out = np.empty((n, d))
    for j, (lo, hi) in enumerate(ranges):
        cut = (np.arange(n) + rng.random(n)) / n
        rng.shuffle(cut)
        out[:, j] = lo + cut * (hi - lo)
    return out


def sample_parameter_design(n_draws: int, rng) -> pd.DataFrame:
    """Shared behavioural parameter draws (one row per draw)."""
    lhs = _latin_hypercube(
        n_draws, [TAU_RANGE, RHO_PI_RANGE, ALPHA_RANGE, MU_RANGE], rng
    )
    return pd.DataFrame({
        "draw": np.arange(n_draws),
        "tau_hat": lhs[:, 0],
        "rho_pi": lhs[:, 1],
        "alpha": lhs[:, 2],
        "mu": lhs[:, 3],
    })


# =========================================================================== #
#  SINGLE RUN                                                                  #
# =========================================================================== #

def _max_iterations(signals: list) -> int:
    n = len(signals)
    return n + EXTRA_HOLD_ITERS if HOLD_LAST_SIGNAL else n


def run_single(params: dict, positions: np.ndarray, voters: np.ndarray,
               signals: list, results: np.ndarray, party_ids: list,
               seed: int) -> dict:
    """Run one empirical simulation and return its outcome dict."""
    res = run_simulation(
        K=len(positions),
        party_ids=party_ids,
        party_positions_override=positions,
        voter_positions_override=voters,
        exogenous_signals=signals,
        tau=params["tau_hat"],
        mu=params["mu"],
        alpha_prior=params["alpha"],
        rho_pi=params["rho_pi"],
        n_electors=len(voters),
        max_iterations=_max_iterations(signals),
        seed=seed,
        verbose=False,
        collect_diagnostics=True,
    )
    return compute_run_outcomes(res, results, signals[0])


# =========================================================================== #
#  MAIN EXPERIMENT                                                             #
# =========================================================================== #

_SCALAR_KEYS = [
    "rmse", "mae", "top2_acc", "top3_acc", "top4_acc",
    "enp_sincere", "enp_final", "delta_enp", "delta_cenp",
    "cliff_magnitude", "cliff_location", "cliff_ratio",
    "trigger_rate", "switching_rate", "conditional_switching_rate",
]


def _scalar_row(params: dict, outcome: dict) -> dict:
    row = {"draw": params["draw"], "tau_hat": params["tau_hat"],
           "rho_pi": params["rho_pi"], "alpha": params["alpha"],
           "mu": params["mu"]}
    row.update({k: outcome[k] for k in _SCALAR_KEYS})
    return row


def aggregate_candidates(bundle: dict, outcomes: list) -> pd.DataFrame:
    """Per-candidate aggregates across draws for one year."""
    finals = np.array([o["final_shares"] for o in outcomes])          # (D, K)
    changes = np.array([o["change_from_first_signal"] for o in outcomes])
    top2 = np.array([o["top2_member"] for o in outcomes])
    top3 = np.array([o["top3_member"] for o in outcomes])
    top4 = np.array([o["top4_member"] for o in outcomes])

    pct = lambda a, q: np.percentile(a, q, axis=0)
    return pd.DataFrame({
        "party": bundle["parties"],
        "block": bundle["blocks"],
        "position": bundle["positions"],
        "actual_share": bundle["results"],
        "first_signal_share": bundle["signals"][0],
        "mean_final_share": finals.mean(axis=0),
        "p05_final_share": pct(finals, 5),
        "p25_final_share": pct(finals, 25),
        "p50_final_share": pct(finals, 50),
        "p75_final_share": pct(finals, 75),
        "p95_final_share": pct(finals, 95),
        "mean_change_first_to_final": changes.mean(axis=0),
        "p05_change": pct(changes, 5),
        "p95_change": pct(changes, 95),
        "prob_top2": top2.mean(axis=0),
        "prob_top3": top3.mean(axis=0),
        "prob_top4": top4.mean(axis=0),
    })


def run_main_experiment(n_draws: int = N_DRAWS) -> None:
    rng = np.random.default_rng(MASTER_SEED)
    design = sample_parameter_design(n_draws, rng)

    bundles = {y: load_year(y, signal_mode="weekly") for y in YEARS}

    for year in YEARS:
        bundle = bundles[year]
        rows, outcomes = [], []
        for _, prow in design.iterrows():
            params = prow.to_dict()
            draw_seed = MASTER_SEED + int(params["draw"])
            voter_rng = np.random.default_rng(draw_seed * 7919 + year)
            voters = sample_voters(year, N_VOTERS, voter_rng)
            outcome = run_single(
                params, bundle["positions"], voters, bundle["signals"],
                bundle["results"], bundle["parties"], draw_seed,
            )
            rows.append(_scalar_row(params, outcome))
            outcomes.append(outcome)

        pd.DataFrame(rows).to_csv(
            DATA_DIR / f"empirical_runs_{year}.csv", index=False)
        aggregate_candidates(bundle, outcomes).to_csv(
            DATA_DIR / f"empirical_candidate_shares_{year}.csv", index=False)
        print(f"[main] {year}: wrote {len(rows)} runs "
              f"+ candidate aggregates.")


# =========================================================================== #
#  ROBUSTNESS                                                                  #
# =========================================================================== #

def run_robustness(n_draws: int = N_DRAWS_ROBUST) -> None:
    """
    Three robustness variants, each applied to both years:
        individual_signals : every poll is its own signal (no weekly mean)
        perturbed_positions: equal-size jitter of party positions
        resampled_voters   : fresh voter sample per draw (different seed)
    """
    rng = np.random.default_rng(MASTER_SEED + 1)
    design = sample_parameter_design(n_draws, rng)
    base = {y: load_year(y, signal_mode="weekly") for y in YEARS}
    indiv = {y: individual_signal_timeline(y, base[y]["parties"])
             for y in YEARS}

    for year in YEARS:
        bundle = base[year]
        rows = []
        for _, prow in design.iterrows():
            params = prow.to_dict()
            draw_seed = MASTER_SEED + int(params["draw"])

            # --- variant 1: individual polls as signals ---
            voter_rng = np.random.default_rng(draw_seed * 7919 + year)
            voters = sample_voters(year, N_VOTERS, voter_rng)
            o1 = run_single(params, bundle["positions"], voters,
                            indiv[year], bundle["results"],
                            bundle["parties"], draw_seed)
            rows.append({"variant": "individual_signals",
                         **_scalar_row(params, o1)})

            # --- variant 2: perturbed party positions ---
            pert_rng = np.random.default_rng(draw_seed * 104729 + year)
            pert_pos = perturb_positions(bundle["positions"],
                                         PERTURB_SIZE, pert_rng)
            o2 = run_single(params, pert_pos, voters, bundle["signals"],
                            bundle["results"], bundle["parties"], draw_seed)
            rows.append({"variant": "perturbed_positions",
                         **_scalar_row(params, o2)})

            # --- variant 3: resampled voters (different seed) ---
            rs_rng = np.random.default_rng(draw_seed * 999983 + year)
            voters2 = sample_voters(year, N_VOTERS, rs_rng)
            o3 = run_single(params, bundle["positions"], voters2,
                            bundle["signals"], bundle["results"],
                            bundle["parties"], draw_seed)
            rows.append({"variant": "resampled_voters",
                         **_scalar_row(params, o3)})

        pd.DataFrame(rows).to_csv(
            DATA_DIR / f"empirical_robustness_{year}.csv", index=False)
        print(f"[robustness] {year}: wrote {len(rows)} rows "
              f"({n_draws} draws x 3 variants).")


# =========================================================================== #
#  ENTRY POINT                                                                 #
# =========================================================================== #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="few draws for a fast smoke run")
    ap.add_argument("--draws", type=int, default=None,
                    help="number of main behavioural draws "
                         "(overrides default / --quick)")
    ap.add_argument("--robust-draws", type=int, default=None,
                    help="number of robustness draws per variant "
                         "(overrides default / --quick)")
    ap.add_argument("--no-robustness", action="store_true")
    args = ap.parse_args()

    n_main = 15 if args.quick else N_DRAWS
    n_rob = 5 if args.quick else N_DRAWS_ROBUST
    if args.draws is not None:
        n_main = args.draws
    if args.robust_draws is not None:
        n_rob = args.robust_draws

    run_main_experiment(n_main)
    if not args.no_robustness:
        run_robustness(n_rob)


if __name__ == "__main__":
    main()
