"""
protocol_validation.py
----------------------
Do the fixed protocol choices Tmax = 25 and N = 2000 hold up across the WHOLE
Saltelli parameter domain?

This is not another sensitivity analysis and it estimates no indices.  It is a
targeted validation of two constants that the Saltelli design treats as settled,
across the same eight-parameter box that design sweeps.

Why it is separate from robustness_checks.py
--------------------------------------------
Those panels are baseline diagnostics: they vary one protocol constant at a time
around a single hand-picked baseline (K = 6, tau_hat = 1.0, mu = 0, one theta).
That answers "is the constant defensible at the baseline?".  It cannot answer
"is it defensible at the parameter combinations the Saltelli analysis actually
evaluated?", because a baseline is one point and the Saltelli design is 10 240
of them per K.  Panel G already showed the answer is regime-dependent: at
c = 2.5 individual runs drift more between T=25 and T=60 than they vary across
seeds, while the mean is stable.  This script asks the same question everywhere.

Design
------
Configurations are a deterministic stratified subset of the COMMITTED Saltelli
parameter rows (data/saltelli_results_K{6,8,9}.csv), not a fresh LHS.  See
build_design() for why.

Part 1: horizon validation
    One run per (config, seed) to T = 100.  The states at T = 25, 50 and 100 are
    read out of that single trajectory, so the three horizons lie on exactly the
    same stochastic path; running three separate simulations would confound the
    horizon with the path.  Endpoint values and tail-window means (mean over the
    last W iterations ending at each horizon) are both recorded, because the
    synthetic model keeps drawing noisy signals forever and a single endpoint can
    move even when the process is stationary.

Part 2: population validation
    A smaller subset of the same configurations at N in {1000, 2000, 5000},
    same config_ids and seeds.  N = 5000 is the higher-resolution reference.

Reads
-----
    Nothing.  Simulates from scratch; parameter_space.py is an imported
    library, not a prior stage.  Its horizon_raw.csv output is what
    protocol_posthoc.py later consumes.

Outputs
-------
    analysis/synthetic/outputs/protocol_validation/    detailed, git-ignored
        design.csv, horizon_raw.csv, population_raw.csv
    results/tables/                                     compact, committed
        protocol_horizon_validation.csv
        protocol_horizon_stability_by_c.csv
        protocol_population_validation.csv
        protocol_population_stability_by_c.csv

Continuous differences are the result.  Threshold flags exist, are configurable
via --stability-threshold, and are reported ALONGSIDE the continuous values,
never in place of them.

Usage
-----
    python analysis/synthetic/protocol_validation.py --mode horizon --quick
    python analysis/synthetic/protocol_validation.py --mode population --quick
    python analysis/synthetic/protocol_validation.py --mode horizon --full
    python analysis/synthetic/protocol_validation.py --mode population --full

Neither mode runs without an explicit --quick or --full.

Signal offset eps_s
-------------------
eps_s gives zero-support components a strictly positive Dirichlet
concentration, so they are not pinned at zero signal share.  1e-12 is the fixed
synthetic specification.  It is distinct from the Saltelli parameter named
``epsilon``, which is the electorate floor weight.  It is a real parameter of
run_simulation (``signal_epsilon``), so this script sets it
explicitly and records it in every raw and summary row.  --full REQUIRES
--signal-epsilon: a validation whose epsilon is inherited silently is a
validation of an undocumented protocol.

The value every result in this repository was produced under is 1e-12.  The
corrected Panel C found identical voting outcomes across 1e-12, 1e-6 and 1e-4 in
the four configurations it tests: local robustness at those points, not
invariance across the Saltelli space.
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(ROOT))

from metrics import tau_absolute
from model import run_simulation
from parameter_space import (
    C_STRATA, K_VALUES, N_MODES, PROBLEM, XI, M_RUNOFF,
    c_stratum, signal_epsilon_in_force, within_bounds,
)

# The value every committed result was produced under.  Used only as the
# --quick default; --full must state its epsilon explicitly.
DEFAULT_SIGNAL_EPSILON = 1e-12

DATA_DIR = REPO / "data"
OUT_DIR = ROOT / "outputs" / "protocol_validation"
TABLES_DIR = REPO / "results" / "tables"

# --------------------------------------------------------------------------- #
#  Defaults                                                                    #
# --------------------------------------------------------------------------- #

DEFAULT_HORIZONS = [25, 50, 100]
DEFAULT_POPULATIONS = [1000, 2000, 5000]
DEFAULT_TAIL_WINDOW = 10
DEFAULT_DESIGN_SEED = 20020422

# Full run.
FULL_CONFIGS_PER_CELL = 6      # per (K, c stratum) -> 6 * 3 * 3 = 54 configs
FULL_SEEDS = 8
FULL_POP_CONFIGS_PER_CELL = 2  # -> 18 configs for part 2

# Quick smoke run: small enough to finish in seconds, still covers every cell.
QUICK_CONFIGS_PER_CELL = 1
QUICK_SEEDS = 2
QUICK_POP_CONFIGS_PER_CELL = 1
QUICK_HORIZONS = [5, 10, 20]
QUICK_POPULATIONS = [200, 400]
QUICK_TAIL_WINDOW = 3
QUICK_N_ELECTORS = 300

# Outcomes compared across horizons and population sizes.
VALIDATION_OUTCOMES = ["delta_cenp", "enp", "trigger_rate", "switching_rate"]

# Default flag threshold.  A convenience, never the result.
DEFAULT_STABILITY_THRESHOLD = 0.01


# =========================================================================== #
#  DESIGN                                                                      #
# =========================================================================== #

def _load_saltelli_rows(K: int) -> pd.DataFrame:
    path = DATA_DIR / f"saltelli_results_K{K}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is required to build the validation design. It is "
            f"committed; if it is missing, restore it rather than regenerating."
        )
    df = pd.read_csv(path, usecols=["run"] + PROBLEM["names"])
    return df


def config_id(K: int, stratum: str, source_row: int) -> str:
    """
    Stable identifier for one configuration.

    Encodes everything needed to find the parameters again: which K file, which
    stratum it was drawn for, and which row of that file it is.  Stable across
    runs, machines and changes to how many configurations are selected.
    """
    return f"K{K}-{stratum}-r{int(source_row):05d}"


def build_design(configs_per_cell: int,
                 k_values=None,
                 design_seed: int = DEFAULT_DESIGN_SEED) -> pd.DataFrame:
    """
    Deterministic stratified subset of the committed Saltelli rows.

    Why a subset of the actual Saltelli rows rather than a fresh seeded LHS:
    the question is whether the protocol constants hold for the evaluations the
    Sobol analysis ACTUALLY performed.  Rows drawn from that very sample are
    configurations the analysis really visited, so a finding transfers directly.
    A fresh LHS would only share the bounding box, and any conclusion would need
    the extra step of assuming the two designs explore it comparably.

    Selection inside a (K, c stratum) cell is by evenly spaced positions in
    the file's own order.  The Saltelli sequence is low-discrepancy, so evenly
    spaced positions inherit its spread, and with no random draw involved the
    design reproduces without depending on an RNG implementation.
    design_seed is recorded but unused here; it is accepted so that switching
    to an LHS design later cannot silently change the CLI.

    Returns one row per configuration: config_id, K, c_stratum, source_row and
    the eight parameter values.
    """
    k_values = list(K_VALUES if k_values is None else k_values)
    rows = []

    for K in k_values:
        df = _load_saltelli_rows(K)
        for stratum, (lo, hi) in C_STRATA.items():
            mask = (df["c"] >= lo) & (df["c"] < hi)
            if stratum == "high":                      # closed upper bound
                mask = (df["c"] >= lo) & (df["c"] <= hi)
            cell = df[mask].sort_values("run").reset_index(drop=True)
            if cell.empty:
                raise RuntimeError(
                    f"K={K} stratum {stratum!r} has no Saltelli rows; the "
                    f"design cannot cover it.")

            n_take = min(configs_per_cell, len(cell))
            positions = np.unique(
                np.linspace(0, len(cell) - 1, n_take).round().astype(int))

            for pos in positions:
                r = cell.iloc[int(pos)]
                entry = {
                    "config_id": config_id(K, stratum, r["run"]),
                    "K": K,
                    "c_stratum": stratum,
                    "source_row": int(r["run"]),
                }
                entry.update({name: float(r[name]) for name in PROBLEM["names"]})
                rows.append(entry)

    design = pd.DataFrame(rows)
    design = design.sort_values(["K", "c_stratum", "source_row"])
    return design.reset_index(drop=True)


def validate_design(design: pd.DataFrame, k_values=None) -> None:
    """Fail loudly if the design does not do what it claims."""
    k_values = set(K_VALUES if k_values is None else k_values)

    if design["config_id"].duplicated().any():
        raise ValueError("design has duplicate config_id values")

    for name in PROBLEM["names"]:
        bad = [v for v in design[name] if not within_bounds(name, v)]
        if bad:
            raise ValueError(f"{name} outside Saltelli bounds: {bad[:3]}")

    missing = k_values - set(design["K"])
    if missing:
        raise ValueError(f"design misses K values {sorted(missing)}")

    for K in sorted(k_values):
        present = set(design[design["K"] == K]["c_stratum"])
        gap = set(C_STRATA) - present
        if gap:
            raise ValueError(f"K={K} misses c strata {sorted(gap)}")

    for _, r in design.iterrows():
        if c_stratum(r["c"]) != r["c_stratum"]:
            raise ValueError(
                f"{r['config_id']}: c={r['c']} is not in stratum {r['c_stratum']}")


# =========================================================================== #
#  RUNNING                                                                     #
# =========================================================================== #

def _simulate(params: dict, K: int, n_electors: int, t_max: int,
              seed: int, signal_epsilon: float) -> dict:
    """One run, with diagnostics, at the given population, ceiling and eps_s."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_simulation(
            K=K,
            n_modes=N_MODES,
            width_factor=params["c"],
            mode_position=XI,
            floor_weight=params["epsilon"],       # eps_F, the FLOOR weight
            theta=params["theta"],
            rho=params["rho_s"],
            rho_pi=params["rho_pi"],
            n_electors=n_electors,
            tau=tau_absolute(params["tau_hat"], K),
            mu=params["mu"],
            alpha_prior=params["alpha"],
            K_runoff=M_RUNOFF,
            signal_epsilon=signal_epsilon,
            max_iterations=t_max,
            seed=seed,
            verbose=False,
            collect_diagnostics=True,
        )


def _cenp(counts, K: int) -> float:
    s = np.asarray(counts, dtype=float)
    total = s.sum()
    if total <= 0:
        return float("nan")
    s = s / total
    return (K - 1.0 / (s ** 2).sum()) / (K - 1)


def _enp(counts) -> float:
    s = np.asarray(counts, dtype=float)
    total = s.sum()
    if total <= 0:
        return float("nan")
    s = s / total
    return 1.0 / (s ** 2).sum()


def trajectory_outcomes(res: dict, K: int) -> pd.DataFrame:
    """
    Per-iteration outcome table for one run: t, delta_cenp, enp, trigger_rate,
    switching_rate.

    history[t] holds the counts after iteration t, with history[0] the sincere
    iteration-0 state; sw_history[t-1] and the diagnostics record for t both
    describe iteration t.  Rather than trusting those offsets, the diagnostics
    are matched on their own "t" field.
    """
    history = res["history"]
    sw_history = res["sw_history"]
    cenp_sincere = _cenp(history[0], K)

    trigger_by_t = {int(d["t"]): float(d["trigger_rate"])
                    for d in (res["diagnostics"] or {}).get("iterations", [])}

    rows = []
    for t in range(1, len(history)):
        counts = history[t]
        rows.append({
            "t": t,
            "delta_cenp": _cenp(counts, K) - cenp_sincere,
            "enp": _enp(counts),
            "trigger_rate": trigger_by_t.get(t, np.nan),
            "switching_rate": (sw_history[t - 1] / 100.0
                               if t - 1 < len(sw_history) else np.nan),
        })
    return pd.DataFrame(rows)


def state_at(traj: pd.DataFrame, horizon: int) -> dict:
    """Endpoint outcome values at one horizon."""
    row = traj[traj["t"] == horizon]
    if row.empty:
        return {o: np.nan for o in VALIDATION_OUTCOMES}
    return {o: float(row.iloc[0][o]) for o in VALIDATION_OUTCOMES}


def tail_mean_at(traj: pd.DataFrame, horizon: int, window: int) -> dict:
    """
    Mean of each outcome over the last `window` iterations ENDING at `horizon`,
    i.e. iterations (horizon - window, horizon].

    The synthetic model keeps drawing noisy signals, so a single endpoint can
    move by pure signal noise while the process itself is stationary.  The tail
    mean is the statistic that separates the two.
    """
    lo = max(1, horizon - window + 1)
    win = traj[(traj["t"] >= lo) & (traj["t"] <= horizon)]
    if win.empty:
        return {o: np.nan for o in VALIDATION_OUTCOMES}
    return {o: float(win[o].mean()) for o in VALIDATION_OUTCOMES}


# =========================================================================== #
#  RESUME SUPPORT                                                              #
# =========================================================================== #

HORIZON_KEY = ["config_id", "seed", "n_electors", "t_max", "tail_window"]
POPULATION_KEY = ["config_id", "seed", "n_electors", "horizon", "tail_window"]


def _load_done(path: Path, key: list) -> set:
    """Identifying keys already present in a raw output file."""
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return set()
    if not set(key).issubset(df.columns):
        return set()
    return set(map(tuple, df[key].astype(object).to_numpy()))


def _append_rows(path: Path, rows: list) -> None:
    """Append incrementally so an interrupted run keeps completed work."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    header = not path.exists() or path.stat().st_size == 0
    df.to_csv(path, mode="a", header=header, index=False)


# =========================================================================== #
#  PART 1: HORIZON                                                             #
# =========================================================================== #

def run_horizon(design: pd.DataFrame, seeds: list, horizons: list,
                tail_window: int, n_electors: int, out_dir: Path,
                signal_epsilon: float = DEFAULT_SIGNAL_EPSILON,
                resume: bool = True) -> pd.DataFrame:
    """One run per (config, seed) to max(horizons); states read from it."""
    raw_path = out_dir / "horizon_raw.csv"
    t_max = int(max(horizons))
    done = _load_done(raw_path, HORIZON_KEY) if resume else set()
    if done:
        print(f"  resume: {len(done)} (config, seed) rows already present")

    eps_s = signal_epsilon
    total = len(design) * len(seeds)
    started = time.perf_counter()
    n_new = 0

    for _, cfg in design.iterrows():
        params = {name: cfg[name] for name in PROBLEM["names"]}
        for seed in seeds:
            key = (cfg["config_id"], seed, n_electors, t_max, tail_window)
            if key in done:
                continue

            res = _simulate(params, int(cfg["K"]), n_electors, t_max, seed,
                            signal_epsilon)
            traj = trajectory_outcomes(res, int(cfg["K"]))

            row = {
                "config_id": cfg["config_id"], "K": int(cfg["K"]),
                "c_stratum": cfg["c_stratum"], "seed": int(seed),
                "n_electors": n_electors, "t_max": t_max,
                "tail_window": tail_window, "signal_epsilon": eps_s,
            }
            row.update({name: float(cfg[name]) for name in PROBLEM["names"]})
            for h in horizons:
                for o, v in state_at(traj, h).items():
                    row[f"{o}_T{h}"] = v
                for o, v in tail_mean_at(traj, h, tail_window).items():
                    row[f"{o}_tail_T{h}"] = v

            _append_rows(raw_path, [row])
            n_new += 1
            if n_new % 10 == 0:
                el = time.perf_counter() - started
                print(f"    horizon: {n_new} new runs, {el:.0f}s "
                      f"({el / n_new:.2f}s/run)")

    print(f"  {n_new} new runs (of {total} requested) -> {raw_path.name}")
    return pd.read_csv(raw_path)


def summarise_horizon(raw: pd.DataFrame, horizons: list,
                      threshold: float) -> tuple:
    """
    Two summaries: per (K, c stratum, outcome) and per (c stratum, outcome).

    Reports continuous absolute changes from the reference horizon to each later
    one, for endpoints and for tail-window means, as median and p95.  The
    threshold flag is an extra column, never a substitute.
    """
    ref = int(min(horizons))
    later = [h for h in sorted(horizons) if h != ref]
    rows = []

    for (K, stratum), grp in raw.groupby(["K", "c_stratum"]):
        for outcome in VALIDATION_OUTCOMES:
            entry = {
                "K": K, "c_stratum": stratum, "outcome": outcome,
                "n_configurations": grp["config_id"].nunique(),
                "n_runs": len(grp),
                "reference_horizon": ref,
                "signal_epsilon": (raw["signal_epsilon"].iloc[0]
                                   if "signal_epsilon" in raw.columns else np.nan),
                "stability_threshold": threshold,
            }
            for h in later:
                for kind, suffix in (("endpoint", ""), ("tail", "_tail")):
                    a = grp[f"{outcome}{suffix}_T{ref}"].to_numpy(dtype=float)
                    b = grp[f"{outcome}{suffix}_T{h}"].to_numpy(dtype=float)
                    d = np.abs(b - a)
                    d = d[np.isfinite(d)]
                    p = f"{kind}_abs_change_T{ref}_to_T{h}"
                    entry[f"median_{p}"] = float(np.median(d)) if d.size else np.nan
                    entry[f"p95_{p}"] = (float(np.percentile(d, 95))
                                         if d.size else np.nan)
                    entry[f"prop_within_threshold_{p}"] = (
                        float(np.mean(d <= threshold)) if d.size else np.nan)
            rows.append(entry)

    by_k = pd.DataFrame(rows).sort_values(
        ["outcome", "K", "c_stratum"]).reset_index(drop=True)

    pooled = []
    for stratum, grp in raw.groupby("c_stratum"):
        for outcome in VALIDATION_OUTCOMES:
            entry = {
                "c_stratum": stratum, "outcome": outcome,
                "n_configurations": grp["config_id"].nunique(),
                "n_runs": len(grp),
                "reference_horizon": ref,
                "signal_epsilon": (raw["signal_epsilon"].iloc[0]
                                   if "signal_epsilon" in raw.columns else np.nan),
                "stability_threshold": threshold,
            }
            for h in later:
                for kind, suffix in (("endpoint", ""), ("tail", "_tail")):
                    a = grp[f"{outcome}{suffix}_T{ref}"].to_numpy(dtype=float)
                    b = grp[f"{outcome}{suffix}_T{h}"].to_numpy(dtype=float)
                    d = np.abs(b - a)
                    d = d[np.isfinite(d)]
                    p = f"{kind}_abs_change_T{ref}_to_T{h}"
                    entry[f"median_{p}"] = float(np.median(d)) if d.size else np.nan
                    entry[f"p95_{p}"] = (float(np.percentile(d, 95))
                                         if d.size else np.nan)
                    entry[f"prop_within_threshold_{p}"] = (
                        float(np.mean(d <= threshold)) if d.size else np.nan)
            pooled.append(entry)

    by_c = pd.DataFrame(pooled).sort_values(
        ["outcome", "c_stratum"]).reset_index(drop=True)
    return by_k, by_c


# =========================================================================== #
#  PART 2: POPULATION                                                          #
# =========================================================================== #

def run_population(design: pd.DataFrame, seeds: list, populations: list,
                   horizon: int, tail_window: int, out_dir: Path,
                   signal_epsilon: float = DEFAULT_SIGNAL_EPSILON,
                   resume: bool = True) -> pd.DataFrame:
    """Same configurations and seeds at each population size."""
    raw_path = out_dir / "population_raw.csv"
    done = _load_done(raw_path, POPULATION_KEY) if resume else set()
    if done:
        print(f"  resume: {len(done)} rows already present")

    eps_s = signal_epsilon
    started = time.perf_counter()
    n_new = 0

    for _, cfg in design.iterrows():
        params = {name: cfg[name] for name in PROBLEM["names"]}
        for n_el in populations:
            for seed in seeds:
                key = (cfg["config_id"], seed, n_el, horizon, tail_window)
                if key in done:
                    continue

                res = _simulate(params, int(cfg["K"]), n_el, horizon, seed,
                                signal_epsilon)
                traj = trajectory_outcomes(res, int(cfg["K"]))

                row = {
                    "config_id": cfg["config_id"], "K": int(cfg["K"]),
                    "c_stratum": cfg["c_stratum"], "seed": int(seed),
                    "n_electors": n_el, "horizon": horizon,
                    "tail_window": tail_window, "signal_epsilon": eps_s,
                }
                row.update({name: float(cfg[name]) for name in PROBLEM["names"]})
                row.update(state_at(traj, horizon))
                row.update({f"{o}_tail": v
                            for o, v in tail_mean_at(traj, horizon,
                                                     tail_window).items()})
                _append_rows(raw_path, [row])
                n_new += 1
                if n_new % 10 == 0:
                    el = time.perf_counter() - started
                    print(f"    population: {n_new} new runs, {el:.0f}s "
                          f"({el / n_new:.2f}s/run)")

    print(f"  {n_new} new runs -> {raw_path.name}")
    return pd.read_csv(raw_path)


def summarise_population(raw: pd.DataFrame, reference_n: int,
                         compare_n: int, threshold: float) -> tuple:
    """
    Compare the outcome distribution at compare_n against reference_n.

    Paired on (config_id, seed), so each difference holds the configuration
    and the seed fixed.  That difference is NOT pure finite-population error:
    two runs at different N consume different numbers of random draws, so what
    it measures is the total run-to-run variation between the two settings,
    with population size one component of it.  seed_sd gives the spread across
    seeds at the reference size, for scale.
    """
    rows_k, rows_c = [], []

    def _pair(grp):
        ref = grp[grp["n_electors"] == reference_n]
        cmp_ = grp[grp["n_electors"] == compare_n]
        merged = ref.merge(cmp_, on=["config_id", "seed"],
                           suffixes=("_ref", "_cmp"))
        return merged

    for keys, grp in raw.groupby(["K", "c_stratum"]):
        merged = _pair(grp)
        for outcome in VALIDATION_OUTCOMES:
            d = np.abs(merged[f"{outcome}_cmp"] - merged[f"{outcome}_ref"])
            d = d[np.isfinite(d)].to_numpy()
            dt = np.abs(merged[f"{outcome}_tail_cmp"]
                        - merged[f"{outcome}_tail_ref"])
            dt = dt[np.isfinite(dt)].to_numpy()
            seed_sd = (grp[grp["n_electors"] == reference_n]
                       .groupby("config_id")[outcome].std().mean())
            rows_k.append({
                "K": keys[0], "c_stratum": keys[1], "outcome": outcome,
                "reference_N": reference_n, "compare_N": compare_n,
                "signal_epsilon": (raw["signal_epsilon"].iloc[0]
                                   if "signal_epsilon" in raw.columns else np.nan),
                "n_configurations": merged["config_id"].nunique(),
                "n_pairs": len(merged),
                "median_abs_diff": float(np.median(d)) if d.size else np.nan,
                "p95_abs_diff": float(np.percentile(d, 95)) if d.size else np.nan,
                "median_abs_diff_tail": float(np.median(dt)) if dt.size else np.nan,
                "p95_abs_diff_tail": (float(np.percentile(dt, 95))
                                      if dt.size else np.nan),
                "mean_seed_sd_at_reference": (float(seed_sd)
                                              if np.isfinite(seed_sd) else np.nan),
                "stability_threshold": threshold,
                "prop_within_threshold": (float(np.mean(d <= threshold))
                                          if d.size else np.nan),
            })

    for stratum, grp in raw.groupby("c_stratum"):
        merged = _pair(grp)
        for outcome in VALIDATION_OUTCOMES:
            d = np.abs(merged[f"{outcome}_cmp"] - merged[f"{outcome}_ref"])
            d = d[np.isfinite(d)].to_numpy()
            dt = np.abs(merged[f"{outcome}_tail_cmp"]
                        - merged[f"{outcome}_tail_ref"])
            dt = dt[np.isfinite(dt)].to_numpy()
            seed_sd = (grp[grp["n_electors"] == reference_n]
                       .groupby("config_id")[outcome].std().mean())
            rows_c.append({
                "c_stratum": stratum, "outcome": outcome,
                "reference_N": reference_n, "compare_N": compare_n,
                "signal_epsilon": (raw["signal_epsilon"].iloc[0]
                                   if "signal_epsilon" in raw.columns else np.nan),
                "n_configurations": merged["config_id"].nunique(),
                "n_pairs": len(merged),
                "median_abs_diff": float(np.median(d)) if d.size else np.nan,
                "p95_abs_diff": float(np.percentile(d, 95)) if d.size else np.nan,
                "median_abs_diff_tail": float(np.median(dt)) if dt.size else np.nan,
                "p95_abs_diff_tail": (float(np.percentile(dt, 95))
                                      if dt.size else np.nan),
                "mean_seed_sd_at_reference": (float(seed_sd)
                                              if np.isfinite(seed_sd) else np.nan),
                "stability_threshold": threshold,
                "prop_within_threshold": (float(np.mean(d <= threshold))
                                          if d.size else np.nan),
            })

    by_k = pd.DataFrame(rows_k).sort_values(
        ["outcome", "K", "c_stratum"]).reset_index(drop=True)
    by_c = pd.DataFrame(rows_c).sort_values(
        ["outcome", "c_stratum"]).reset_index(drop=True)
    return by_k, by_c


# =========================================================================== #
#  CLI                                                                         #
# =========================================================================== #

def _write_table(df: pd.DataFrame, name: str) -> Path:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    out = TABLES_DIR / name
    df.to_csv(out, index=False)
    try:                                   # cosmetic: never let logging abort a
        shown = out.relative_to(REPO)      # completed run just because the
    except ValueError:                     # output dir sits outside the repo
        shown = out
    print(f"  -> {shown}  ({len(df)} rows)")
    return out


def resolve_signal_epsilon(requested, is_full: bool) -> float:
    """
    Decide the eps_s this run uses, and refuse to guess for a --full run.

    A full validation that inherited its epsilon silently would be validating
    an undocumented protocol, which is the failure this whole change exists to
    fix.  --quick may default, because a smoke run asserts nothing.
    """
    if requested is None:
        if is_full:
            raise SystemExit(
                "\n--full requires --signal-epsilon to be stated explicitly.\n"
                f"The value every committed result was produced under is "
                f"{DEFAULT_SIGNAL_EPSILON:g}; pass\n"
                f"    --signal-epsilon {DEFAULT_SIGNAL_EPSILON:g}\n"
                "to validate the current protocol, or another value to validate "
                "a different one.\n")
        requested = DEFAULT_SIGNAL_EPSILON

    eps = float(requested)
    if not np.isfinite(eps) or eps < 0:
        raise SystemExit(f"--signal-epsilon must be finite and non-negative, "
                         f"got {requested!r}")

    default_in_signals = signal_epsilon_in_force()
    note = "" if eps == default_in_signals else "  (differs from signals default)"
    print(f"  signal offset eps_s: {eps:g}{note}")
    return eps


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["horizon", "population"], required=True)

    size = p.add_mutually_exclusive_group()
    size.add_argument("--quick", action="store_true",
                      help="tiny smoke run: every cell covered, seconds to run")
    size.add_argument("--full", action="store_true",
                      help="the real validation run (see --dry-run for size)")

    p.add_argument("--dry-run", action="store_true",
                   help="build and validate the design, print the run size, "
                        "then stop without simulating")
    p.add_argument("--design-seed", type=int, default=DEFAULT_DESIGN_SEED)
    p.add_argument("--configs-per-cell", type=int, default=None,
                   help="configurations per (K, c stratum) cell")
    p.add_argument("--n-seeds", type=int, default=None,
                   help="stochastic seeds per configuration")
    p.add_argument("--horizons", type=int, nargs="+", default=None)
    p.add_argument("--populations", type=int, nargs="+", default=None)
    p.add_argument("--horizon", type=int, default=None,
                   help="population mode: horizon to compare at. Do not leave "
                        "at 25 if the horizon validation shows the relevant "
                        "configurations are unstable there.")
    p.add_argument("--n-electors", type=int, default=None,
                   help="horizon mode: population size to run at")
    p.add_argument("--tail-window", type=int, default=None)
    p.add_argument("--k-values", type=int, nargs="+", default=None)
    p.add_argument("--stability-threshold", type=float,
                   default=DEFAULT_STABILITY_THRESHOLD,
                   help="absolute change counted as 'stable' in the FLAG "
                        "columns. Continuous medians and p95 are reported "
                        "regardless and are the actual result.")
    p.add_argument("--signal-epsilon", type=float, default=None,
                   help="numerical floor eps_s added before the temperature "
                        "transform. REQUIRED with --full so the validated "
                        "protocol is on the record; --quick defaults to "
                        f"{DEFAULT_SIGNAL_EPSILON:g}, the value every committed "
                        "result was produced under.")
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--no-resume", action="store_true",
                   help="ignore existing raw rows and recompute everything")
    return p


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not (args.quick or args.full or args.dry_run):
        parser.print_help()
        raise SystemExit(
            "\nRefusing to run without an explicit size: pass --quick for a "
            "smoke run,\n--full for the real thing, or --dry-run to see what "
            "--full would cost.\n")

    quick = args.quick
    cfg_per_cell = args.configs_per_cell if args.configs_per_cell is not None else (
        (QUICK_CONFIGS_PER_CELL if quick else FULL_CONFIGS_PER_CELL)
        if args.mode == "horizon" else
        (QUICK_POP_CONFIGS_PER_CELL if quick else FULL_POP_CONFIGS_PER_CELL))
    n_seeds = args.n_seeds if args.n_seeds is not None else (
        QUICK_SEEDS if quick else FULL_SEEDS)
    horizons = args.horizons or (QUICK_HORIZONS if quick else DEFAULT_HORIZONS)
    populations = args.populations or (
        QUICK_POPULATIONS if quick else DEFAULT_POPULATIONS)
    tail_window = args.tail_window if args.tail_window is not None else (
        QUICK_TAIL_WINDOW if quick else DEFAULT_TAIL_WINDOW)
    n_electors = args.n_electors if args.n_electors is not None else (
        QUICK_N_ELECTORS if quick else 2000)
    horizon = args.horizon if args.horizon is not None else (
        max(QUICK_HORIZONS) if quick else 25)
    seeds = list(range(n_seeds))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"  Protocol validation: mode={args.mode} "
          f"({'quick' if quick else 'full' if args.full else 'dry-run'})")
    print("=" * 70)
    signal_epsilon = resolve_signal_epsilon(args.signal_epsilon, args.full)

    design = build_design(cfg_per_cell, args.k_values, args.design_seed)
    validate_design(design, args.k_values)
    design.to_csv(out_dir / "design.csv", index=False)
    print(f"  design: {len(design)} configurations "
          f"({design['K'].nunique()} K x {design['c_stratum'].nunique()} strata) "
          f"-> {(out_dir / 'design.csv').name}")

    if args.mode == "horizon":
        n_runs = len(design) * len(seeds)
        print(f"  plan: {len(design)} configs x {len(seeds)} seeds = {n_runs} "
              f"runs to T={max(horizons)} at N={n_electors}")
    else:
        n_runs = len(design) * len(seeds) * len(populations)
        print(f"  plan: {len(design)} configs x {len(seeds)} seeds x "
              f"{len(populations)} populations = {n_runs} runs "
              f"at T={horizon}")

    if args.dry_run:
        print("\n  --dry-run: stopping before any simulation.")
        return

    if args.mode == "horizon":
        raw = run_horizon(design, seeds, horizons, tail_window, n_electors,
                          out_dir, signal_epsilon=signal_epsilon,
                          resume=not args.no_resume)
        by_k, by_c = summarise_horizon(raw, horizons, args.stability_threshold)
        _write_table(by_k, "protocol_horizon_validation.csv")
        _write_table(by_c, "protocol_horizon_stability_by_c.csv")
    else:
        raw = run_population(design, seeds, populations, horizon, tail_window,
                             out_dir, signal_epsilon=signal_epsilon,
                             resume=not args.no_resume)
        ref = 2000 if 2000 in populations else populations[len(populations) // 2]
        cmp_ = max(populations)
        by_k, by_c = summarise_population(raw, ref, cmp_,
                                          args.stability_threshold)
        _write_table(by_k, "protocol_population_validation.csv")
        _write_table(by_c, "protocol_population_stability_by_c.csv")

    print("\nDone.")


if __name__ == "__main__":
    main()
