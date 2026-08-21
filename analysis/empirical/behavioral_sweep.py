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
    tau_hat (τ̂)  ∈ [0.5, 3.0]      -> run_simulation(tau=tau_absolute(τ̂, K))

Resuming
--------
A full sweep is ~3.5 h per year, so it must survive an interruption:

    python analysis/empirical/behavioral_sweep.py --year 2002 --resume ...

Rows are flushed one draw at a time.  --resume validates the sidecar
behavioral_sweep_<year>_meta.json (year, seed, n_draws, n_repeats, schema and a
fingerprint of the design) and cross-checks every retained row against the
recomputed design before continuing; anything that does not match is refused,
never merged.  Per-run seeds depend only on (seed, draw, repeat), so a resumed
sweep and an uninterrupted one produce the same output.
                                      τ̂ is NORMALISED in zone lengths; the model
                                      wants absolute units, so it is converted
                                      with tau = τ̂·(2/K).  K is year-specific,
                                      so the same τ̂ is 0.40 in 2002 (K=15) and
                                      0.50 in 2022 (K=12).
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

import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(ROOT))

from model import run_simulation                       # import & call; do not reimplement
from empirical_data import load_year, sample_voters
from metrics import cenp, tau_absolute   # shared metrics + unit conversion

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

    # tau_hat is normalised; run_simulation wants absolute units (2/K).
    # This is the ONLY tau conversion on the sweep path: the value written to
    # the CSV is read back out of this function's return value, so it is
    # literally the value handed to run_simulation.
    tau_abs = tau_absolute(params["tau_hat"], K)

    res = run_simulation(
        K=K,
        party_ids=bundle["parties"],
        party_positions_override=positions,
        voter_positions_override=voters,
        exogenous_signals=signals,
        tau=tau_abs,
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
    return {"delta_cenp": delta_cenp, "final_enp": final_enp,
            "tau_absolute": tau_abs, "K": K}


# --------------------------------------------------------------------------- #
#  Sweep                                                                       #
# --------------------------------------------------------------------------- #
SCHEMA_VERSION = 2      # 1 = pre-tau_absolute; 2 adds tau_absolute and K

# Canonical column order.  finalise_output() rewrites every file in this order,
# so a resumed run and an uninterrupted run produce identical output.
OUTPUT_COLS = [
    "draw", "tau_hat", "tau_absolute", "K",
    "mu", "alpha", "rho_pi", "beta",
    "mean_delta_cenp", "mean_final_enp", "std_delta_cenp",
    "n_repeats", "seed",
]


def design_path(out: Path) -> Path:
    return out.with_name(out.stem + "_design.csv")


def meta_path(out: Path) -> Path:
    return out.with_name(out.stem + "_meta.json")


def design_fingerprint(design: pd.DataFrame) -> str:
    """
    SHA-256 over the design's raw float64 bytes.

    Hashing the numbers rather than the rendered CSV keeps the fingerprint
    independent of float formatting, so a resume is not refused merely because
    the partial file was written by a different pandas version.
    """
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(
        design["draw"].to_numpy(dtype=np.int64)).tobytes())
    for c in PARAM_COLS:
        h.update(np.ascontiguousarray(
            design[c].to_numpy(dtype=np.float64)).tobytes())
    return h.hexdigest()


def build_meta(year: int, n_draws: int, n_repeats: int, seed: int,
               design: pd.DataFrame) -> dict:
    """Everything a later --resume needs in order to prove compatibility."""
    return {
        "schema_version": SCHEMA_VERSION,
        "year": int(year),
        "n_draws": int(n_draws),
        "n_repeats": int(n_repeats),
        "seed": int(seed),
        "n_voters": int(N_VOTERS),
        "t_max": int(T_MAX),
        "param_cols": list(PARAM_COLS),
        "design_sha256": design_fingerprint(design),
    }


def _refuse(msg: str):
    raise SystemExit("Refusing to resume: " + msg)


def load_resumable(out: Path, meta: dict, design: pd.DataFrame) -> set:
    """
    Validate an existing partial sweep and return the set of completed draws.

    Every check refuses rather than repairs.  A full sweep is roughly seven
    hours of compute, and silently merging two incompatible partial runs would
    produce a file that looks finished and is quietly wrong -- much worse than
    being told to start again.
    """
    mpath = meta_path(out)
    if not mpath.exists():
        _refuse(f"{out.name} exists but {mpath.name} does not, so the run that "
                f"produced it cannot be identified.  Move it aside, or pass "
                f"--overwrite to start again.")
    try:
        prev = json.loads(mpath.read_text())
    except (OSError, ValueError) as exc:
        _refuse(f"{mpath.name} is not readable JSON ({exc}).")

    for key in ("year", "seed", "n_draws", "n_repeats"):
        if prev.get(key) != meta[key]:
            _refuse(f"{key} differs -- the partial run used {prev.get(key)!r}, "
                    f"this one asks for {meta[key]!r}.  Different experiments.")
    if prev.get("schema_version") != meta["schema_version"]:
        _refuse(f"schema_version differs (file {prev.get('schema_version')!r}, "
                f"current {meta['schema_version']!r}): the columns differ.")
    if prev.get("design_sha256") != meta["design_sha256"]:
        _refuse("the recomputed design does not match the one the partial run "
                "used, although year, seed and n_draws agree.")

    try:
        done = pd.read_csv(out)
    except (OSError, ValueError) as exc:
        _refuse(f"{out.name} is not readable as CSV ({exc}).")
    if len(done) == 0:
        return set()

    missing = [c for c in OUTPUT_COLS if c not in done.columns]
    if missing:
        _refuse(f"{out.name} is missing column(s) {missing}.")

    raw = pd.to_numeric(done["draw"], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(raw).all():
        _refuse(f"{out.name} has {int((~np.isfinite(raw)).sum())} row(s) with a "
                f"missing or non-numeric draw id.")
    if not np.array_equal(raw, np.round(raw)):
        _refuse(f"{out.name} has non-integer draw ids.")
    draws = raw.astype(int)

    dup = sorted(set(draws[pd.Series(draws).duplicated().to_numpy()].tolist()))
    if dup:
        _refuse(f"{out.name} has duplicate draw id(s) {dup[:10]}"
                f"{' ...' if len(dup) > 10 else ''}.")

    bad_range = sorted({int(d) for d in draws
                        if d < 0 or d >= meta["n_draws"]})
    if bad_range:
        _refuse(f"{out.name} has draw id(s) outside [0, {meta['n_draws']}): "
                f"{bad_range[:10]}.")

    # A truncated final row -- the likely shape of a kill mid-write -- shows up
    # as a non-finite value here.
    for c in OUTPUT_COLS:
        if c == "draw":
            continue
        v = pd.to_numeric(done[c], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(v).all():
            bad = draws[~np.isfinite(v)][:5].tolist()
            _refuse(f"{out.name} has a missing or non-finite {c!r} at draw(s) "
                    f"{bad}.")

    # Per-row cross-check against the design: the strongest evidence that these
    # rows really belong to this experiment, not just to a run with the same
    # seed and size.
    idx = design.set_index("draw")
    for c in PARAM_COLS:
        expected = idx.loc[draws, c].to_numpy(dtype=float)
        got = done[c].to_numpy(dtype=float)
        close = np.isclose(expected, got, rtol=0, atol=1e-9)
        if not close.all():
            k = int(np.argmax(~close))
            _refuse(f"{out.name} row for draw {draws[k]} has {c}={got[k]!r} but "
                    f"the design says {expected[k]!r}.")

    # Row-level bookkeeping must agree with the sidecar too.
    for c, want in (("n_repeats", meta["n_repeats"]), ("seed", meta["seed"])):
        vals = sorted(set(pd.to_numeric(done[c]).astype(int).tolist()))
        if vals != [int(want)]:
            _refuse(f"{out.name} has {c} values {vals}, expected [{int(want)}].")

    return {int(d) for d in draws}


def finalise_output(out: Path) -> pd.DataFrame:
    """
    Sort by draw and rewrite in canonical column order.

    Both the uninterrupted and the resumed path end here, so append order stops
    mattering: the two produce the same file.
    """
    df = pd.read_csv(out)
    df = df.sort_values("draw", kind="mergesort").reset_index(drop=True)
    df = df[OUTPUT_COLS]
    df.to_csv(out, index=False)
    return df


def run_sweep(year: int, n_draws: int, n_repeats: int, seed: int,
              out: Path, resume: bool = False,
              overwrite: bool = False) -> None:
    rng = np.random.default_rng(seed)
    design = build_design(n_draws, rng)
    meta = build_meta(year, n_draws, n_repeats, seed, design)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    completed = set()
    if out.exists():
        if resume:
            completed = load_resumable(out, meta, design)
            print(f"[sweep] resuming {out.name}: {len(completed)}/{n_draws} "
                  f"draws already complete")
        elif overwrite:
            out.unlink()
        else:
            raise SystemExit(
                f"{out} already exists and nothing has been touched.\n"
                f"  --resume     continue it, keeping every completed draw\n"
                f"  --overwrite  discard it and start again"
            )
    elif resume:
        print(f"[sweep] --resume given but {out.name} does not exist; "
              f"starting from draw 0")

    # Load the environment only once the resume decision is settled, so a
    # refusal costs nothing.
    bundle = load_year(year, signal_mode="weekly")

    # Real electorate: sampled ONCE and held fixed across all draws/repeats.
    voter_rng = np.random.default_rng(seed + 1)
    voters = sample_voters(year, N_VOTERS, voter_rng)

    design.to_csv(design_path(out), index=False)
    meta_path(out).write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[sweep] year={year}  n_draws={n_draws}  n_repeats={n_repeats}  "
          f"seed={seed}")
    print(f"[sweep] design -> {design_path(out)}")
    print(f"[sweep] meta   -> {meta_path(out)}")

    todo = [row for _, row in design.iterrows()
            if int(row["draw"]) not in completed]
    if not todo:
        print(f"[sweep] all {n_draws} draws already present; finalising only")

    n_written = 0
    for prow in todo:
        params = {c: float(prow[c]) for c in PARAM_COLS}
        draw = int(prow["draw"])
        deltas, enps, taus, ks = [], [], [], []
        for r in range(n_repeats):
            # Deterministic per (draw, repeat) seed -> reproducible.  It depends
            # only on seed, draw and repeat, so resuming cannot change it.
            run_seed = seed + 1000 * (draw + 1) + r
            o = run_one(params, bundle, voters, run_seed)
            deltas.append(o["delta_cenp"])
            enps.append(o["final_enp"])
            taus.append(o["tau_absolute"])
            ks.append(o["K"])
        assert len(set(taus)) == 1 and len(set(ks)) == 1, \
            "tau_absolute must not vary across the repeats of one draw"

        row = {"draw": draw,
               "tau_hat": params["tau_hat"],
               "tau_absolute": taus[0],
               "K": ks[0]}
        row.update({c: params[c] for c in PARAM_COLS if c != "tau_hat"})
        row.update({
            "mean_delta_cenp": float(np.mean(deltas)),
            "mean_final_enp": float(np.mean(enps)),
            "std_delta_cenp": float(np.std(deltas, ddof=1)) if n_repeats > 1 else 0.0,
            "n_repeats": n_repeats,
            "seed": seed,
        })
        # Flush row-by-row: an interruption keeps every completed draw, and
        # --resume picks up at the next one.
        header = (not out.exists()) or out.stat().st_size == 0
        pd.DataFrame([row])[OUTPUT_COLS].to_csv(
            out, mode="a", header=header, index=False)
        n_written += 1
        if n_written % 25 == 0 or prow is todo[-1]:
            print(f"[sweep]   {len(completed) + n_written}/{n_draws} draws done")

    df = finalise_output(out)
    print(f"[sweep] wrote {n_written} new row(s); {len(df)} total -> {out}")


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
    ap.add_argument("--resume", action="store_true",
                    help="continue an interrupted sweep, keeping every "
                         "completed draw (validates year, seed, n_draws, "
                         "n_repeats and the design before merging)")
    ap.add_argument("--overwrite", action="store_true",
                    help="discard an existing output and start again")
    ap.add_argument("--time_one_run", action="store_true",
                    help="run a single simulation, print wall-clock seconds, exit")
    args = ap.parse_args()

    if args.time_one_run:
        time_one_run(args.year, args.seed)
        return

    if args.resume and args.overwrite:
        raise SystemExit("--resume and --overwrite are mutually exclusive.")

    out = Path(args.out) if args.out else REPO / "data" / f"behavioral_sweep_{args.year}.csv"
    run_sweep(args.year, args.n_draws, args.n_repeats, args.seed, Path(out),
              resume=args.resume, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
