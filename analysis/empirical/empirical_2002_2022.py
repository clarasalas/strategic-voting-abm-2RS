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
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / "core_model"))

from model import run_simulation
from empirical_data import (
    load_year, sample_voters, perturb_positions,
    weekly_signal_timeline, individual_signal_timeline,
)
from empirical_outcomes import compute_run_outcomes, initialization_benchmarks

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
BETA_RANGE = (0.0, 20.0)   # ideological sharpness (probabilistic init only)

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


def sample_parameter_design(n_draws: int, rng,
                            include_beta: bool = False,
                            mu_zero: bool = False) -> pd.DataFrame:
    """
    Shared behavioural parameter draws (one row per draw).

    include_beta : add beta in BETA_RANGE (probabilistic initialization).
    mu_zero      : fix mu = 0 instead of sampling MU_RANGE (mu=0 variant).
    """
    ranges, cols = [TAU_RANGE, RHO_PI_RANGE, ALPHA_RANGE], ["tau_hat", "rho_pi", "alpha"]
    if not mu_zero:
        ranges.append(MU_RANGE)
        cols.append("mu")
    if include_beta:
        ranges.append(BETA_RANGE)
        cols.append("beta")

    lhs = _latin_hypercube(n_draws, ranges, rng)
    design = pd.DataFrame({"draw": np.arange(n_draws)})
    for j, c in enumerate(cols):
        design[c] = lhs[:, j]
    if mu_zero:
        design["mu"] = 0.0
    if not include_beta:
        design["beta"] = 0.0
    return design


# =========================================================================== #
#  SINGLE RUN                                                                  #
# =========================================================================== #

def _max_iterations(signals: list) -> int:
    n = len(signals)
    return n + EXTRA_HOLD_ITERS if HOLD_LAST_SIGNAL else n


def run_single(params: dict, positions: np.ndarray, voters: np.ndarray,
               signals: list, results: np.ndarray, party_ids: list,
               seed: int, cfg: dict = None) -> dict:
    """Run one empirical simulation and return its outcome dict.

    cfg : optional initialization config with keys 'sincere_init_mode' and
          'salience_source'.  Defaults to the nearest-party baseline.
    """
    cfg = cfg or {}
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
        sincere_init_mode=cfg.get("sincere_init_mode", "nearest"),
        beta=params.get("beta", 0.0),
        salience_source=cfg.get("salience_source", "signal"),
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
           "mu": params["mu"], "beta": params.get("beta", 0.0)}
    row.update({k: outcome[k] for k in _SCALAR_KEYS})
    return row


def output_suffix(cfg: dict) -> str:
    """
    Build a filename suffix encoding the initialization mode, salience source
    and mu setting, so probabilistic variants never overwrite the baseline.

        nearest                              -> ""  (baseline filenames)
        probabilistic, signal, mu varied     -> "_prob_signal"
        probabilistic, prior,  mu varied     -> "_prob_prior"
        probabilistic, signal, mu=0          -> "_prob_signal_mu0"
    """
    if cfg.get("sincere_init_mode", "nearest") != "probabilistic":
        return ""
    parts = ["prob", cfg.get("salience_source", "signal")]
    if cfg.get("mu_zero", False):
        parts.append("mu0")
    return "_" + "_".join(parts)


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


def per_draw_candidate_table(bundle: dict, design: pd.DataFrame,
                             outcomes: list) -> pd.DataFrame:
    """
    Long-format per-draw, per-candidate final shares for one year.

    One row per (draw, candidate), carrying the draw's behavioural parameters
    (incl. beta) alongside the candidate's simulated final share and the actual
    result.  This is the input for beta-binned candidate diagnostics
    (analysis/empirical_beta_bins.py); the wide candidate-shares CSV averages
    over all draws and so cannot be re-binned by beta.
    """
    parties = bundle["parties"]
    positions = bundle["positions"]
    blocks = bundle["blocks"]
    actual = bundle["results"]
    first_signal = bundle["signals"][0]

    rows = []
    for (_, prow), o in zip(design.iterrows(), outcomes):
        final = o["final_shares"]
        for k, party in enumerate(parties):
            rows.append({
                "draw": int(prow["draw"]),
                "tau_hat": prow["tau_hat"],
                "rho_pi": prow["rho_pi"],
                "alpha": prow["alpha"],
                "mu": prow["mu"],
                "beta": prow.get("beta", 0.0),
                "party": party,
                "block": blocks[k],
                "position": positions[k],
                "final_share": float(final[k]),
                "actual_share": float(actual[k]),
                "first_signal_share": float(first_signal[k]),
            })
    return pd.DataFrame(rows)


def run_main_experiment(n_draws: int = N_DRAWS, cfg: dict = None) -> None:
    cfg = cfg or {}
    probabilistic = cfg.get("sincere_init_mode", "nearest") == "probabilistic"
    mu_zero = cfg.get("mu_zero", False)
    suffix = output_suffix(cfg)

    rng = np.random.default_rng(MASTER_SEED)
    design = sample_parameter_design(
        n_draws, rng, include_beta=probabilistic, mu_zero=mu_zero
    )

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
                bundle["results"], bundle["parties"], draw_seed, cfg,
            )
            rows.append(_scalar_row(params, outcome))
            outcomes.append(outcome)

        pd.DataFrame(rows).to_csv(
            DATA_DIR / f"empirical_runs{suffix}_{year}.csv", index=False)
        aggregate_candidates(bundle, outcomes).to_csv(
            DATA_DIR / f"empirical_candidate_shares{suffix}_{year}.csv",
            index=False)
        per_draw_candidate_table(bundle, design, outcomes).to_csv(
            DATA_DIR / f"empirical_candidate_draws{suffix}_{year}.csv",
            index=False)
        print(f"[main{suffix or ' nearest'}] {year}: wrote {len(rows)} runs "
              f"+ candidate aggregates + per-draw candidate table.")


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
#  INITIALIZATION BENCHMARKS (diagnostic)                                       #
# =========================================================================== #

def run_init_benchmarks(beta: float = 5.0, rho_pi: float = 50.0) -> None:
    """
    Candidate-level comparison of sincere-initialization rules, written to
    ``data/empirical_init_benchmarks_<year>.csv``.

    Columns
    -------
        first_signal_share         : s^0
        nearest_share              : deterministic nearest-party benchmark
        prob_signal_share          : probabilistic init, salience = s^0
        prob_prior_share           : probabilistic init, salience = pi_a
        actual_share               : actual R1 result
    plus mean_final_share columns merged from any candidate-shares CSVs already
    written for the matching mode (nearest / prob_signal / prob_prior).

    The key question is whether prob_* reduce over-allocation to small parties
    near dense voter regions relative to nearest.
    """
    for year in YEARS:
        bundle = load_year(year, signal_mode="weekly")
        voter_rng = np.random.default_rng(MASTER_SEED * 7919 + year)
        voters = sample_voters(year, N_VOTERS, voter_rng)

        bench = initialization_benchmarks(
            bundle["positions"], voters, tau=2.0,
            first_signal=bundle["signals"][0], beta=beta,
            rho_pi=rho_pi, seed=MASTER_SEED + year,
        )

        table = pd.DataFrame({
            "party": bundle["parties"],
            "block": bundle["blocks"],
            "position": bundle["positions"],
            "first_signal_share": bundle["signals"][0],
            "nearest_share": bench["nearest"],
            "prob_signal_share": bench["prob_signal"],
            "prob_prior_share": bench["prob_prior"],
            "actual_share": bundle["results"],
        })

        # Merge mean final shares from any candidate-shares CSVs present.
        for tag in ("", "_prob_signal", "_prob_prior"):
            path = DATA_DIR / f"empirical_candidate_shares{tag}_{year}.csv"
            if path.exists():
                col = f"mean_final{tag or '_nearest'}"
                cs = pd.read_csv(path)[["party", "mean_final_share"]]
                cs = cs.rename(columns={"mean_final_share": col})
                table = table.merge(cs, on="party", how="left")

        out = DATA_DIR / f"empirical_init_benchmarks_{year}.csv"
        table.to_csv(out, index=False)
        print(f"[init-benchmarks] {year} (beta={beta}): wrote {out.name}")


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

    # --- Sincere initialization options ---
    ap.add_argument("--sincere-init", choices=["nearest", "probabilistic"],
                    default="nearest",
                    help="initial expressive-vote rule (default: nearest)")
    ap.add_argument("--salience-source", choices=["signal", "prior"],
                    default="signal",
                    help="salience for probabilistic init (default: signal)")
    ap.add_argument("--mu-zero", action="store_true",
                    help="fix mu=0 (probabilistic init variant B)")
    ap.add_argument("--init-benchmarks", action="store_true",
                    help="write candidate-level initialization benchmark CSVs "
                         "and exit (no strategic sweep)")
    ap.add_argument("--beta-benchmark", type=float, default=5.0,
                    help="beta used by --init-benchmarks (default: 5.0)")
    args = ap.parse_args()

    if args.init_benchmarks:
        run_init_benchmarks(beta=args.beta_benchmark)
        return

    cfg = {
        "sincere_init_mode": args.sincere_init,
        "salience_source": args.salience_source,
        "mu_zero": args.mu_zero,
    }

    n_main = 15 if args.quick else N_DRAWS
    n_rob = 5 if args.quick else N_DRAWS_ROBUST
    if args.draws is not None:
        n_main = args.draws
    if args.robust_draws is not None:
        n_rob = args.robust_draws

    run_main_experiment(n_main, cfg)
    # Robustness is defined for the nearest-party baseline only; probabilistic
    # variants write their own suffixed main outputs and skip robustness.
    if not args.no_robustness and args.sincere_init == "nearest":
        run_robustness(n_rob)


if __name__ == "__main__":
    main()
