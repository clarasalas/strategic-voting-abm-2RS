"""
behavioral_sweep.py
-------------------
Behavioral-parameter sweep for the achievable range of ΔCENP per election year,
with the real electoral structure held fixed.

Question
--------
Holding the real structure fixed (party positions, electorate, candidate set,
weekly-mean poll timeline), how wide is the achievable range of the coordination
gain ΔCENP under behavioral uncertainty, and where does the real poll→result
value fall inside that range?

Definitions (confirmed against the model code)
----------------------------------------------
Baseline s⁰  : the EXOGENOUS input poll, ``bundle["signals"][0]``.  It is fixed
               per year and identical across all draws/repeats.  It is NOT the
               per-iteration ``signal`` field returned by run_simulation, which
               is overwritten every iteration (model.py: the loop reassigns
               ``signal`` at each step, so res["signal"] is the FINAL-iteration
               signal, not s⁰).

ENP(δ)       : 1 / Σ_j δ_j²                          (main_results.enp)
CENP(δ)      : (K − ENP(δ)) / (K − 1)                (main_results.cenp)
ΔCENP        : CENP(δ_final) − CENP(s⁰)              (SAME s⁰ for every run)

NOTE: we do NOT use functions.coordination_measures()["delta_cenp"] here — that
quantity is defined relative to the model's iteration-0 SINCERE shares, a
different baseline.  The spec for this experiment is an s⁰ baseline, so ΔCENP is
computed explicitly below as cenp(final, K) − cenp(s⁰, K).

δ⁰ initialization
-----------------
Probabilistic favorite-draw:  P_a(j) ∝ s_j⁰ · exp(−β·(x_a − x_j)²).
In the model this is sincere_init_mode="probabilistic", salience_source="signal"
(salience = s⁰), with β swept.

Fixed per year
--------------
real party positions, real electorate (sampled once, fixed across draws/repeats),
real candidate set, weekly-mean polls, N = 2000, Tmax = 25, M = 2 (K_runoff).

Swept (Latin hypercube, one draw = one row)
-------------------------------------------
    tau_hat (τ̂)  ∈ [0.5, 3.0]      -> run_simulation(tau=…)
    mu      (µ)  ∈ [0.0, 1.0]      -> run_simulation(mu=…)
    alpha   (α)  ∈ [0.0, 0.9]      -> run_simulation(alpha_prior=…)
    rho_pi  (ρπ) ∈ [5, 200]        -> run_simulation(rho_pi=…)
    beta    (β)  ∈ [0, 20]         -> run_simulation(beta=…)

NOTE: ρs (signal precision ``rho``) is intentionally NOT swept.  The signal is
exogenous (empirical polls), so ``rho`` plays no role in empirical replay
(model.py uses exogenous_signals and never draws from rho); sweeping it would be
a pure placebo dimension.  It is left at the run_simulation default.

Output (one row per draw, flushed incrementally)
------------------------------------------------
    draw, tau_hat, mu, alpha, rho_pi, beta,
    mean_delta_cenp   (mean ΔCENP across repeats),
    mean_final_enp    (mean final ENP across repeats),
    std_delta_cenp    (repeat std of ΔCENP),
    n_repeats, seed
Rows are appended to the CSV as each draw completes, so Ctrl+C keeps all
completed draws.  The fixed RNG seed and the full LHS design are logged (design
CSV next to --out).

Usage
-----
    python analysis/behavioral_sweep.py --year 2002 --n_draws 300 \
        --n_repeats 4 --seed 20020422 --out data/behavioral_sweep_2002.csv

    python analysis/behavioral_sweep.py --year 2002 --time_one_run
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(ROOT))

from model import run_simulation                       # import & call; do not reimplement
from empirical_data import load_year, sample_voters
from metrics import cenp           # shared coordination metric (core_model)

YEARS = (2002, 2022)

# Fixed structure (per spec).
N_VOTERS = 2000
T_MAX = 25
K_RUNOFF = 2

# Swept behavioral-parameter ranges.
TAU_RANGE = (0.5, 3.0)
MU_RANGE = (0.0, 1.0)
ALPHA_RANGE = (0.0, 0.9)
RHO_PI_RANGE = (5.0, 200.0)
BETA_RANGE = (0.0, 20.0)

# Column order for the swept parameters (drives the LHS design).
PARAM_COLS = ["tau_hat", "mu", "alpha", "rho_pi", "beta"]
PARAM_RANGES = [TAU_RANGE, MU_RANGE, ALPHA_RANGE, RHO_PI_RANGE, BETA_RANGE]


# --------------------------------------------------------------------------- #
#  Latin-hypercube design                                                      #
# --------------------------------------------------------------------------- #
def latin_hypercube(n: int, ranges: list, rng) -> np.ndarray:
    """Latin-hypercube sample (n x d) over the given (lo, hi) ranges.

    Same construction as analysis/empirical_2002_2022.py (stratified, shuffled
    per dimension) so designs are comparable across scripts.
    """
    d = len(ranges)
    out = np.empty((n, d))
    for j, (lo, hi) in enumerate(ranges):
        cut = (np.arange(n) + rng.random(n)) / n
        rng.shuffle(cut)
        out[:, j] = lo + cut * (hi - lo)
    return out


def build_design(n_draws: int, rng) -> pd.DataFrame:
    lhs = latin_hypercube(n_draws, PARAM_RANGES, rng)
    design = pd.DataFrame({"draw": np.arange(n_draws)})
    for j, c in enumerate(PARAM_COLS):
        design[c] = lhs[:, j]
    return design


# --------------------------------------------------------------------------- #
#  Single run                                                                  #
# --------------------------------------------------------------------------- #
def run_one(params: dict, bundle: dict, voters: np.ndarray, seed: int) -> dict:
    """One empirical-replay simulation.  Returns {'delta_cenp', 'final_enp'}.

    ΔCENP is computed explicitly against the SAME exogenous s⁰ = signals[0].
    """
    signals = bundle["signals"]
    positions = bundle["positions"]
    K = len(positions)
    s0 = np.asarray(signals[0], dtype=float)            # baseline poll, fixed per year

    res = run_simulation(
        K=K,
        party_ids=bundle["parties"],
        party_positions_override=positions,
        voter_positions_override=voters,
        exogenous_signals=signals,
        tau=params["tau_hat"],
        mu=params["mu"],
        alpha_prior=params["alpha"],
        rho_pi=params["rho_pi"],
        sincere_init_mode="probabilistic",              # δ⁰ favorite-draw
        salience_source="signal",                       # salience = s⁰
        beta=params["beta"],
        n_electors=len(voters),
        K_runoff=K_RUNOFF,
        max_iterations=T_MAX,
        seed=seed,
        verbose=False,
        collect_diagnostics=False,
    )

    final = np.asarray(res["final_shares"], dtype=float)
    delta_cenp = cenp(final, K) - cenp(s0, K)           # CENP(δ_final) − CENP(s⁰)
    # final_enp computed the same way as main_results.enp: 1 / Σ δ²
    final_enp = 1.0 / float(((final / final.sum()) ** 2).sum()) if final.sum() > 0 else np.nan
    return {"delta_cenp": delta_cenp, "final_enp": final_enp}


# --------------------------------------------------------------------------- #
#  Sweep                                                                       #
# --------------------------------------------------------------------------- #
def run_sweep(year: int, n_draws: int, n_repeats: int, seed: int,
              out: Path) -> None:
    rng = np.random.default_rng(seed)
    bundle = load_year(year, signal_mode="weekly")

    # Real electorate: sampled ONCE and held fixed across all draws/repeats.
    voter_rng = np.random.default_rng(seed + 1)
    voters = sample_voters(year, N_VOTERS, voter_rng)

    design = build_design(n_draws, rng)

    # Log the design next to the output for full reproducibility.
    design_path = out.with_name(out.stem + "_design.csv")
    design.to_csv(design_path, index=False)
    print(f"[sweep] year={year}  n_draws={n_draws}  n_repeats={n_repeats}  "
          f"seed={seed}")
    print(f"[sweep] LHS design logged -> {design_path}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()        # fresh start; avoid appending to a stale run
    n_written = 0
    for _, prow in design.iterrows():
        params = {c: float(prow[c]) for c in PARAM_COLS}
        draw = int(prow["draw"])
        deltas, enps = [], []
        for r in range(n_repeats):
            # Deterministic per (draw, repeat) seed -> reproducible.
            run_seed = seed + 1000 * (draw + 1) + r
            o = run_one(params, bundle, voters, run_seed)
            deltas.append(o["delta_cenp"])
            enps.append(o["final_enp"])
        row = {
            "draw": draw,
            **params,
            "mean_delta_cenp": float(np.mean(deltas)),
            "mean_final_enp": float(np.mean(enps)),
            "std_delta_cenp": float(np.std(deltas, ddof=1)) if n_repeats > 1 else 0.0,
            "n_repeats": n_repeats,
            "seed": seed,
        }
        # Flush row-by-row: header only on the first write, append thereafter,
        # so a Ctrl+C keeps every completed draw.
        pd.DataFrame([row]).to_csv(out, mode="a", header=(n_written == 0), index=False)
        n_written += 1
        if (draw + 1) % 25 == 0 or draw == n_draws - 1:
            print(f"[sweep]   {draw + 1}/{n_draws} draws done")

    print(f"[sweep] wrote {n_written} rows -> {out}")


# --------------------------------------------------------------------------- #
#  Timing helper                                                               #
# --------------------------------------------------------------------------- #
def time_one_run(year: int, seed: int) -> None:
    """Run a single simulation at mid-range params, print wall-clock seconds."""
    bundle = load_year(year, signal_mode="weekly")
    voters = sample_voters(year, N_VOTERS, np.random.default_rng(seed + 1))
    params = {
        "tau_hat": float(np.mean(TAU_RANGE)),
        "mu": float(np.mean(MU_RANGE)),
        "alpha": float(np.mean(ALPHA_RANGE)),
        "rho_pi": float(np.mean(RHO_PI_RANGE)),
        "beta": float(np.mean(BETA_RANGE)),
    }
    t0 = time.perf_counter()
    out = run_one(params, bundle, voters, seed)
    dt = time.perf_counter() - t0
    print(f"[time_one_run] year={year}  N={N_VOTERS}  Tmax={T_MAX}")
    print(f"[time_one_run] mid-range params: {params}")
    print(f"[time_one_run] result: ΔCENP={out['delta_cenp']:+.4f}  "
          f"final_ENP={out['final_enp']:.3f}")
    print(f"[time_one_run] wall-clock seconds for ONE run: {dt:.3f}")


# --------------------------------------------------------------------------- #
#  CLI                                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, choices=YEARS, default=2002)
    ap.add_argument("--n_draws", type=int, default=300)
    ap.add_argument("--n_repeats", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20020422)
    ap.add_argument("--out", type=str, default=None,
                    help="output CSV path (default: data/behavioral_sweep_<year>.csv)")
    ap.add_argument("--time_one_run", action="store_true",
                    help="run a single simulation, print wall-clock seconds, exit")
    args = ap.parse_args()

    if args.time_one_run:
        time_one_run(args.year, args.seed)
        return

    out = Path(args.out) if args.out else REPO / "data" / f"behavioral_sweep_{args.year}.csv"
    run_sweep(args.year, args.n_draws, args.n_repeats, args.seed, Path(out))


if __name__ == "__main__":
    main()
