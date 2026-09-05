#!/usr/bin/env python3
"""
Run the real model across a parameter grid and write the demo's JSON.

The web demo does not reimplement the model.  It replays trajectories computed
here by core_model.model.run_simulation, so the page cannot drift from the
model in the paper: if the model changes, this script is re-run and the demo
changes with it.  Nothing about the dynamics lives in JavaScript.

Usage
-----
    python demo/precompute.py                 # full grid -> demo/data/grid.json
    python demo/precompute.py --smoke         # 8 cells  -> demo/data/smoke.json
    python demo/precompute.py --workers 4     # limit parallelism
    python demo/precompute.py --force         # allow overwriting the output

Deterministic: every cell is averaged over seeds 0-7, fixed here.  Cells are
independent and each carries its own seeds, so the result does not depend on
how many workers ran or in what order they finished.

Grid
----
c        12 values, 0.25 to 3.00 step 0.25   (full Saltelli bound)
tau_hat  11 values, 0.50 to 3.00 step 0.25   (full Saltelli bound)
mu        5 values, 0.00 to 1.00 step 0.25
                                             = 660 cells x 8 seeds = 5 280 runs

Everything else is held at the fixed baseline in
analysis/synthetic/main_results.py, so the demo sits on the same baseline as
the synthetic analysis rather than a second one invented for the web page.

Which run is animated
---------------------
The bar charts and the readouts are means over all 8 seeds.  The animation
replays ONE run, because averaging the poll signal across seeds does not
produce a poll: the signal is a Dirichlet draw at rho = 100 and is noisy by
construction.  Measured, two independent 8-seed means of the same cell disagree
by 0.055-0.073 on the signal, against 0.005-0.012 on the vote shares.  Averaging
it to a smooth line would show a path no single run ever takes.

The animated run is ALWAYS SEED 0.  The rule is fixed here, in advance, and
does not look at the outputs.  Picking the run closest to the seed-mean would
also be mechanical, but it would systematically select calm trajectories and so
understate how much a run actually moves.  Seed 0 is an unbiased draw.  The
page states which is which underneath the animation.

Output
------
demo/data/grid.json, about 1 MB.  Shares and signals are stored as per-mille
integers: 0.123 is written 123.  That is exactly three decimal places, the
precision the demo displays, at roughly 60% of the bytes of "0.123".
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core_model.model import run_simulation                      # noqa: E402
from core_model.metrics import tau_absolute, enp                 # noqa: E402
from core_model import empirical_data as ed                      # noqa: E402

# --------------------------------------------------------------------------- #
#  Fixed baseline: analysis/synthetic/main_results.py                          #
# --------------------------------------------------------------------------- #
K = 8
N_ELECTORS = 2000
MAX_ITERATIONS = 25
THETA = 1.0
RHO_S = 100.0
RHO_PI = 100.0
ALPHA = 0.0
K_RUNOFF = 2
N_MODES = 1
FLOOR_WEIGHT = 0.1

SEEDS = list(range(8))
CANONICAL_SEED = 0          # see "Which run is animated" above

C_VALUES = [round(0.25 * i, 2) for i in range(1, 13)]        # 0.25 .. 3.00
TAU_VALUES = [round(0.50 + 0.25 * i, 2) for i in range(11)]  # 0.50 .. 3.00
MU_VALUES = [0.0, 0.25, 0.5, 0.75, 1.0]


def _permille(a):
    """Round to three decimals and store as an integer: 0.123 -> 123."""
    return np.round(np.asarray(a, dtype=float) * 1000).astype(int).tolist()


def _one_run(c, tau_hat, mu, seed):
    return run_simulation(
        K=K, n_modes=N_MODES, width_factor=c, floor_weight=FLOOR_WEIGHT,
        theta=THETA, rho=RHO_S, rho_pi=RHO_PI,
        n_electors=N_ELECTORS, tau=tau_absolute(tau_hat, K), mu=mu,
        alpha_prior=ALPHA, K_runoff=K_RUNOFF, max_iterations=MAX_ITERATIONS,
        seed=seed, verbose=False, collect_diagnostics=True,
    )


def compute_cell(task):
    """One grid cell.  Runs every seed; returns the stored record."""
    ic, it, im, c, tau_hat, mu = task
    sincere, final, switched, gain = [], [], [], []
    canon_shares = canon_signal = None

    for seed in SEEDS:
        r = _one_run(c, tau_hat, mu, seed)
        sincere.append(np.asarray(r["sincere_shares"], dtype=float))
        final.append(np.asarray(r["final_shares"], dtype=float))
        switched.append(r["switching"]["pct_strategic"])
        # Coordination gain: how much the effective number of parties falls
        # between the sincere tally and the final one.
        gain.append(enp(r["sincere_shares"]) - enp(r["final_shares"]))

        if seed == CANONICAL_SEED:
            counts = np.array(r["history"], dtype=float)
            canon_shares = counts / counts.sum(axis=1, keepdims=True)
            canon_signal = np.array(
                [d["signal"] for d in r["diagnostics"]["iterations"]]
            )

    return f"{ic}_{it}_{im}", {
        "sh": [_permille(row) for row in canon_shares],
        "sg": [_permille(row) for row in canon_signal],
        "sinc": _permille(np.mean(sincere, axis=0)),
        "fin": _permille(np.mean(final, axis=0)),
        "sw": int(round(float(np.mean(switched)) * 1000)),
        "gain": int(round(float(np.mean(gain)) * 1000)),
    }


def preset_2022():
    """
    The 2022 first round, replayed with the real candidates, electorate and
    poll timeline.

    One illustrative behavioural draw, stated below and on the page.  Nothing
    here is fitted and no actual result is stored alongside it: this shows what
    the mechanism does on a real environment, not how well it does it.
    """
    params = {"tau_hat": 1.75, "mu": 0.3, "alpha": 0.3, "rho_pi": 50.0,
              "seed": 0, "n_electors": 2000}
    env = ed.load_year(2022)
    k = env["K"]
    rng = np.random.default_rng(params["seed"])
    r = run_simulation(
        K=k, party_ids=env["parties"],
        party_positions_override=env["positions"],
        voter_positions_override=ed.sample_voters(
            2022, params["n_electors"], rng),
        exogenous_signals=env["signals"],
        tau=tau_absolute(params["tau_hat"], k), mu=params["mu"],
        alpha_prior=params["alpha"], rho_pi=params["rho_pi"],
        n_electors=params["n_electors"], max_iterations=len(env["signals"]),
        seed=params["seed"], verbose=False, collect_diagnostics=True,
    )
    counts = np.array(r["history"], dtype=float)
    shares = counts / counts.sum(axis=1, keepdims=True)
    return {
        "parties": env["parties"],
        "positions": [round(float(p), 3) for p in env["positions"]],
        "params": params,
        "sh": [_permille(row) for row in shares],
        "sg": [_permille(d["signal"]) for d in r["diagnostics"]["iterations"]],
        "sinc": _permille(r["sincere_shares"]),
        "fin": _permille(r["final_shares"]),
        "sw": int(round(r["switching"]["pct_strategic"] * 1000)),
        "gain": int(round(
            (enp(r["sincere_shares"]) - enp(r["final_shares"])) * 1000)),
    }


def git_commit():
    """The commit the data was generated from; shown on the demo page."""
    def _git(*args):
        return subprocess.run(["git", "-C", str(REPO), *args],
                              capture_output=True, text=True).stdout.strip()
    commit = _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    return {"commit": commit, "short": commit[:7], "dirty": dirty}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--smoke", action="store_true",
                    help="8 cells, to a separate file, for checking the "
                         "pipeline without a full run")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting an existing output file")
    args = ap.parse_args()

    c_vals, tau_vals, mu_vals = C_VALUES, TAU_VALUES, MU_VALUES
    if args.smoke:
        c_vals, tau_vals, mu_vals = C_VALUES[:2], TAU_VALUES[:2], MU_VALUES[:2]

    # A smoke run writes to its own file by default, so it can never quietly
    # replace the real grid.
    default_name = "smoke.json" if args.smoke else "grid.json"
    out = args.out or (REPO / "demo" / "data" / default_name)
    if out.exists() and not args.force:
        sys.exit(f"{out} exists; pass --force to overwrite it.")
    out.parent.mkdir(parents=True, exist_ok=True)

    tasks = [(ic, it, im, c, t, m)
             for ic, c in enumerate(c_vals)
             for it, t in enumerate(tau_vals)
             for im, m in enumerate(mu_vals)]

    n_runs = len(tasks) * len(SEEDS)
    print(f"{len(tasks)} cells x {len(SEEDS)} seeds = {n_runs} runs")

    start = time.perf_counter()
    with Pool(processes=args.workers) as pool:
        cells = {}
        for i, (key, rec) in enumerate(
                pool.imap_unordered(compute_cell, tasks, chunksize=1), 1):
            cells[key] = rec
            if i % 25 == 0 or i == len(tasks):
                el = time.perf_counter() - start
                print(f"  {i}/{len(tasks)} cells  {el:6.1f}s elapsed  "
                      f"{el / i * (len(tasks) - i):6.1f}s left", flush=True)
    elapsed = time.perf_counter() - start

    payload = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc)
                             .strftime("%Y-%m-%d %H:%M:%S"),
            "git": git_commit(),
            "script": "demo/precompute.py",
            "encoding": "shares and signals are per-mille integers "
                        "(0.123 stored as 123)",
            "seeds": SEEDS,
            "canonical_seed": CANONICAL_SEED,
            "animated": "one run, seed 0",
            "averaged": f"{len(SEEDS)} seeds, for the bars and readouts",
            "baseline": {
                "K": K, "n_electors": N_ELECTORS,
                "max_iterations": MAX_ITERATIONS, "theta": THETA,
                "rho_s": RHO_S, "rho_pi": RHO_PI, "alpha": ALPHA,
                "K_runoff": K_RUNOFF, "n_modes": N_MODES,
                "floor_weight": FLOOR_WEIGHT,
            },
            "grid": {"c": c_vals, "tau_hat": tau_vals, "mu": mu_vals},
            "runs": n_runs,
            "compute_seconds": round(elapsed, 1),
        },
        "cells": cells,
        "preset_2022": preset_2022(),
    }

    out.write_text(json.dumps(payload, separators=(",", ":")))
    size = out.stat().st_size
    print(f"\nwrote {out.relative_to(REPO)}  {size / 1e6:.2f} MB  "
          f"({len(cells)} cells, {elapsed / 60:.1f} min)")


if __name__ == "__main__":
    main()
