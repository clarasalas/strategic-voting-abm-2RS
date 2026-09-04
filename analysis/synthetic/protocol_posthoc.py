"""
protocol_posthoc.py
-------------------
Two post-hoc questions the pooled horizon results cannot answer, both settled
from the COMPLETED horizon run.  This module launches no simulations.

1. Configuration-specific drift.
   Pooling 432 runs showed the signed mean change from T=25 is near zero.  That
   is consistent with a stationary process, and equally consistent with some
   parameter configurations drifting up while others drift down.  The two are
   distinguished by testing each configuration separately, and by asking whether
   movement PERSISTS from T25->T50 into T50->T100 or reverses.

2. Configuration variance versus seed variance.
   The Saltelli design evaluates one stochastic realisation per parameter row.
   If seed noise were comparable to the variation between parameter
   configurations, a variance decomposition over that design would be
   substantially decomposing noise.  A one-way random-effects decomposition on
   the balanced 54 x 8 validation design estimates the ratio directly.

   What the ratio licenses: a high ICC supports reading the broad importance
   structure with confidence.  It is NOT a replication audit of individual
   Saltelli rows, and it does not show that any individual Sobol estimate is
   unbiased.

   Stochastic variation that is independent of the parameters usually lowers
   first-order indices, by adding unexplained outcome variance; where the
   amount of it changes across the parameter space, as it may here, the effect
   is harder to predict.  With one realisation per row that variation feeds
   into the uncertainty of the estimated indices.  The bootstrap S1_conf and
   ST_conf columns describe uncertainty in the Sobol estimates from the
   observed design; they do not isolate seed uncertainty, and they are not a
   replication-based estimate of stochastic noise.  Total-order estimates come
   with no guarantee of the same attenuation, so closely spaced rankings can
   change while clearly separated importance groups stay the credible reading.

A "configuration" here is one fixed combination of ALL synthetic parameters:
K, c, tau_hat, mu, theta, rho_s, rho_pi, alpha, epsilon.  The eight seeds are
stochastic repetitions of that same combination.

Endpoint outcomes and the 10-iteration tail means are computed side by side,
and kept apart throughout.

Reads
-----
    analysis/synthetic/outputs/protocol_validation/horizon_raw.csv
        <- protocol_validation.py --mode horizon --full  (override with --raw)

Writes (results/tables/)
------------------------
    protocol_horizon_drift_by_config.csv
    protocol_horizon_drift_summary.csv
    protocol_seed_noise_decomposition.csv

Usage
-----
    python analysis/synthetic/protocol_posthoc.py
    python analysis/synthetic/protocol_posthoc.py --bootstrap 2000 --seed 20020422
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(ROOT))

from parameter_space import PROBLEM

RAW_PATH = ROOT / "outputs" / "protocol_validation" / "horizon_raw.csv"
TABLES_DIR = REPO / "results" / "tables"

OUTCOMES = ["delta_cenp", "enp", "trigger_rate", "switching_rate"]
STATISTICS = ["endpoint", "tail"]
HORIZONS = [25, 50, 100]

# (name, from, to, iterations spanned).  T25->T50 spans 25 iterations and
# T50->T100 spans 50, so comparing their raw sizes would compare unequal
# exposures; per-iteration rates are reported alongside.
INTERVALS = [
    ("T25_T50", 25, 50, 25),
    ("T50_T100", 50, 100, 50),
    ("T25_T100", 25, 100, 75),
]

EXPECTED = dict(n_configs=54, n_seeds=8, n_rows=432,
                n_electors=2000, t_max=100, signal_epsilon=1e-12)


def column_for(outcome: str, statistic: str, horizon: int) -> str:
    """Schema-accurate column name.  Inspected, not assumed."""
    if statistic not in STATISTICS:
        raise ValueError(f"unknown statistic {statistic!r}")
    infix = "_tail" if statistic == "tail" else ""
    return f"{outcome}{infix}_T{horizon}"


# =========================================================================== #
#  1. INPUT VALIDATION                                                         #
# =========================================================================== #

def validate_horizon_raw(df: pd.DataFrame, expected: dict = None) -> dict:
    """
    Check the raw file is the complete full run before computing anything on
    it.  Returns a dict of findings, and raises ValueError on anything that
    would make the analysis invalid.
    """
    exp = dict(EXPECTED if expected is None else expected)
    problems = []

    required = (["config_id", "K", "c_stratum", "seed", "n_electors", "t_max",
                 "tail_window", "signal_epsilon"] + PROBLEM["names"])
    for outcome in OUTCOMES:
        for statistic in STATISTICS:
            for h in HORIZONS:
                required.append(column_for(outcome, statistic, h))
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    n_configs = df["config_id"].nunique()
    if n_configs != exp["n_configs"]:
        problems.append(f"{n_configs} configurations, expected {exp['n_configs']}")
    if len(df) != exp["n_rows"]:
        problems.append(f"{len(df)} rows, expected {exp['n_rows']}")

    per_config = df.groupby("config_id")["seed"].nunique()
    bad = per_config[per_config != exp["n_seeds"]]
    if len(bad):
        problems.append(
            f"{len(bad)} configurations do not have {exp['n_seeds']} seeds: "
            f"{dict(bad.head())}")

    if df.duplicated(["config_id", "seed"]).any():
        n = int(df.duplicated(["config_id", "seed"]).sum())
        problems.append(f"{n} duplicate (config_id, seed) keys")

    for field in ("n_electors", "t_max", "signal_epsilon"):
        values = df[field].unique()
        if len(values) != 1:
            problems.append(f"{field} is not constant: {values}")
        elif not np.isclose(values[0], exp[field], rtol=0, atol=0):
            problems.append(f"{field} is {values[0]}, expected {exp[field]}")

    outcome_cols = [column_for(o, s, h)
                    for o in OUTCOMES for s in STATISTICS for h in HORIZONS]
    block = df[outcome_cols].to_numpy(dtype=float)
    n_nan = int(np.isnan(block).sum())
    n_inf = int((~np.isfinite(block)).sum())
    if n_nan or n_inf:
        problems.append(f"{n_nan} NaN and {n_inf} non-finite outcome values")

    if problems:
        raise ValueError("horizon_raw.csv failed validation:\n  - "
                         + "\n  - ".join(problems))

    return {
        "n_rows": len(df),
        "n_configs": n_configs,
        "n_seeds_per_config": int(per_config.iloc[0]),
        "n_outcome_columns": len(outcome_cols),
        "n_electors": int(df["n_electors"].iloc[0]),
        "t_max": int(df["t_max"].iloc[0]),
        "tail_window": int(df["tail_window"].iloc[0]),
        "signal_epsilon": float(df["signal_epsilon"].iloc[0]),
        "duplicate_keys": 0,
        "nan_or_inf": 0,
    }


# =========================================================================== #
#  2. PAIRED CHANGES AND PER-CONFIGURATION DRIFT                               #
# =========================================================================== #

def paired_changes(df: pd.DataFrame, outcome: str, statistic: str,
                   interval: str) -> pd.DataFrame:
    """
    Within-trajectory paired change for every (configuration, seed).

    Both horizons come from the SAME row, which is the same trajectory: the
    horizon run reads T=25, 50 and 100 out of one simulation, so these are
    genuinely paired rather than independent runs at different ceilings.
    """
    spec = {name: (a, b, span) for name, a, b, span in INTERVALS}
    if interval not in spec:
        raise ValueError(f"unknown interval {interval!r}")
    lo, hi, span = spec[interval]

    out = df[["config_id", "seed"]].copy()
    out["change"] = (df[column_for(outcome, statistic, hi)].to_numpy(dtype=float)
                     - df[column_for(outcome, statistic, lo)].to_numpy(dtype=float))
    out["span_iterations"] = span
    out["change_per_iteration"] = out["change"] / span
    return out


def benjamini_hochberg(pvalues) -> np.ndarray:
    """
    BH step-up adjusted q-values.

    q_(i) = min over j >= i of ( m * p_(j) / j ), clipped to 1, returned in the
    original order.  Monotone by construction.
    """
    p = np.asarray(pvalues, dtype=float)
    if p.size == 0:
        return p.copy()
    if np.any(np.isnan(p)):
        raise ValueError("BH correction requires finite p-values")

    m = p.size
    order = np.argsort(p, kind="mergesort")       # stable: ties keep input order
    ranked = p[order]
    scaled = ranked * m / np.arange(1, m + 1)
    q_sorted = np.minimum.accumulate(scaled[::-1])[::-1]
    q_sorted = np.clip(q_sorted, 0.0, 1.0)

    q = np.empty(m, dtype=float)
    q[order] = q_sorted
    return q


def _config_parameters(df: pd.DataFrame) -> pd.DataFrame:
    keep = ["config_id", "K", "c_stratum"] + PROBLEM["names"]
    return df[keep].drop_duplicates("config_id").set_index("config_id")


def drift_by_config(df: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """
    Per-configuration drift statistics for every outcome, statistic and interval.

    One row per (config_id, outcome, statistic, interval): mean signed change,
    mean absolute change, SD and SE across the eight paired changes, the 95%
    t-interval for the mean, a two-sided p-value against zero, and a BH q-value
    computed WITHIN each (outcome, statistic, interval) family of 54 tests.
    """
    params = _config_parameters(df)
    rows = []

    for outcome in OUTCOMES:
        for statistic in STATISTICS:
            for interval, _, _, span in INTERVALS:
                changes = paired_changes(df, outcome, statistic, interval)
                for config_id, grp in changes.groupby("config_id", sort=True):
                    x = grp["change"].to_numpy(dtype=float)
                    n = x.size
                    mean = float(np.mean(x))
                    sd = float(np.std(x, ddof=1)) if n > 1 else np.nan
                    se = sd / np.sqrt(n) if n > 1 else np.nan

                    if n > 1 and se > 0:
                        tcrit = stats.t.ppf(1 - alpha / 2, df=n - 1)
                        t_stat = mean / se
                        p = float(2 * stats.t.sf(abs(t_stat), df=n - 1))
                        ci_lo, ci_hi = mean - tcrit * se, mean + tcrit * se
                    elif n > 1:                      # zero variance
                        t_stat = 0.0 if mean == 0 else np.inf * np.sign(mean)
                        p = 1.0 if mean == 0 else 0.0
                        ci_lo = ci_hi = mean
                    else:
                        t_stat, p, ci_lo, ci_hi = (np.nan,) * 4

                    rows.append({
                        "config_id": config_id,
                        "outcome": outcome,
                        "statistic": statistic,
                        "interval": interval,
                        "span_iterations": span,
                        "n_seeds": n,
                        "mean_signed_change": mean,
                        "mean_abs_change": float(np.mean(np.abs(x))),
                        "sd_change": sd,
                        "se_change": se,
                        "ci95_lo": ci_lo,
                        "ci95_hi": ci_hi,
                        "t_stat": t_stat,
                        "p_value": p,
                        "mean_signed_change_per_iteration": mean / span,
                        "mean_abs_change_per_iteration":
                            float(np.mean(np.abs(x))) / span,
                    })

    out = pd.DataFrame(rows)

    # BH within each (outcome, statistic, interval) family.
    out["q_value"] = np.nan
    for key, idx in out.groupby(["outcome", "statistic", "interval"]).groups.items():
        out.loc[idx, "q_value"] = benjamini_hochberg(
            out.loc[idx, "p_value"].to_numpy())

    out["ci_excludes_zero"] = (out["ci95_lo"] > 0) | (out["ci95_hi"] < 0)
    out["significant_bh"] = out["q_value"] < alpha

    out = out.join(params, on="config_id")
    ordered = (["config_id", "K", "c_stratum"] + PROBLEM["names"]
               + ["outcome", "statistic", "interval", "span_iterations",
                  "n_seeds", "mean_signed_change", "mean_abs_change",
                  "sd_change", "se_change", "ci95_lo", "ci95_hi", "t_stat",
                  "p_value", "q_value", "ci_excludes_zero", "significant_bh",
                  "mean_signed_change_per_iteration",
                  "mean_abs_change_per_iteration"])
    out = out[ordered].sort_values(
        ["outcome", "statistic", "interval", "config_id"]).reset_index(drop=True)
    return out


def persistence_summary(drift: pd.DataFrame) -> pd.DataFrame:
    """
    Per (outcome, statistic): how many configurations move, and whether the
    movement persists into the second interval or reverses.

    Persistence is what discriminates.  A configuration that is genuinely
    drifting keeps going the same way; one fluctuating around a stable level is
    as likely to turn back.
    """
    rows = []
    for (outcome, statistic), grp in drift.groupby(["outcome", "statistic"]):
        wide = grp.pivot(index="config_id", columns="interval",
                         values="mean_signed_change")
        flags = grp.pivot(index="config_id", columns="interval",
                          values="ci_excludes_zero")
        qflags = grp.pivot(index="config_id", columns="interval",
                           values="significant_bh")

        same = np.sign(wide["T25_T50"]) == np.sign(wide["T50_T100"])
        both_move = flags["T25_T50"] & flags["T50_T100"]

        rows.append({
            "outcome": outcome,
            "statistic": statistic,
            "n_configurations": len(wide),
            "n_ci_excludes_zero_T25_T50": int(flags["T25_T50"].sum()),
            "n_ci_excludes_zero_T50_T100": int(flags["T50_T100"].sum()),
            "n_ci_excludes_zero_T25_T100": int(flags["T25_T100"].sum()),
            "n_bh_significant_T25_T50": int(qflags["T25_T50"].sum()),
            "n_bh_significant_T50_T100": int(qflags["T50_T100"].sum()),
            "n_bh_significant_T25_T100": int(qflags["T25_T100"].sum()),
            "n_same_direction_both_intervals": int(same.sum()),
            "n_reversing_direction": int((~same).sum()),
            "n_moving_and_persistent": int((both_move & same).sum()),
            "expected_false_positives_at_5pct": round(0.05 * len(wide), 2),
        })
    return pd.DataFrame(rows).sort_values(
        ["outcome", "statistic"]).reset_index(drop=True)


# =========================================================================== #
#  3. VARIANCE DECOMPOSITION                                                   #
# =========================================================================== #

def variance_components(values, groups, n_per_group: int = None) -> dict:
    """
    One-way random-effects decomposition for a balanced design.

        sigma_config^2 = max((MS_between - MS_within) / n, 0)
        sigma_seed^2   = MS_within
        ICC            = sigma_config^2 / (sigma_config^2 + sigma_seed^2)

    The max(., 0) truncation is standard for the ANOVA estimator, which can go
    negative when the true between-group variance is near zero.  A truncated
    estimate is reported as exactly 0, and the ICC with it.
    """
    values = np.asarray(values, dtype=float)
    groups = np.asarray(groups)

    labels, codes = np.unique(groups, return_inverse=True)
    k = labels.size
    N = values.size
    if k < 2:
        raise ValueError("variance decomposition needs at least two groups")

    counts = np.bincount(codes)
    if n_per_group is None:
        if counts.min() != counts.max():
            raise ValueError(
                f"unbalanced design: group sizes {counts.min()}-{counts.max()}; "
                f"this estimator assumes a balanced design")
        n_per_group = int(counts[0])

    grand = values.mean()
    group_means = np.bincount(codes, weights=values) / counts

    ss_between = float(np.sum(counts * (group_means - grand) ** 2))
    ss_within = float(np.sum((values - group_means[codes]) ** 2))

    ms_between = ss_between / (k - 1)
    ms_within = ss_within / (N - k) if N > k else np.nan

    sigma_config2 = max((ms_between - ms_within) / n_per_group, 0.0)
    sigma_seed2 = ms_within
    total = sigma_config2 + sigma_seed2
    icc = sigma_config2 / total if total > 0 else np.nan

    return {
        "n_groups": int(k),
        "n_total": int(N),
        "n_per_group": int(n_per_group),
        "ms_between": ms_between,
        "ms_within": ms_within,
        "sigma_config_sq": sigma_config2,
        "sigma_seed_sq": sigma_seed2,
        "icc": icc,
        "seed_noise_fraction": (sigma_seed2 / total) if total > 0 else np.nan,
        "truncated_at_zero": bool((ms_between - ms_within) / n_per_group < 0),
    }


def bootstrap_icc(values, groups, n_boot: int = 2000,
                  seed: int = 20020422) -> tuple:
    """
    Percentile CI for the ICC, resampling WHOLE configurations with replacement
    so the eight-seed clusters stay intact.  Resampling individual rows would
    destroy the very grouping being estimated.
    """
    values = np.asarray(values, dtype=float)
    groups = np.asarray(groups)
    labels = np.unique(groups)
    by_label = {g: values[groups == g] for g in labels}

    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        picked = rng.choice(labels, size=labels.size, replace=True)
        v = np.concatenate([by_label[g] for g in picked])
        # relabel so repeated configurations stay distinct groups
        gg = np.concatenate([np.full(by_label[g].size, i)
                             for i, g in enumerate(picked)])
        try:
            draws.append(variance_components(v, gg)["icc"])
        except ValueError:
            continue

    draws = np.asarray([d for d in draws if np.isfinite(d)])
    if draws.size == 0:
        return (np.nan, np.nan, 0)
    return (float(np.percentile(draws, 2.5)),
            float(np.percentile(draws, 97.5)), int(draws.size))


def decomposition_table(df: pd.DataFrame, n_boot: int = 2000,
                        seed: int = 20020422) -> pd.DataFrame:
    """Variance decomposition at T=25, for endpoint and tail statistics."""
    rows = []
    for outcome in OUTCOMES:
        for statistic in STATISTICS:
            col = column_for(outcome, statistic, 25)
            vals = df[col].to_numpy(dtype=float)
            grps = df["config_id"].to_numpy()
            comp = variance_components(vals, grps)
            lo, hi, n_ok = bootstrap_icc(vals, grps, n_boot=n_boot, seed=seed)
            rows.append({
                "outcome": outcome,
                "statistic": statistic,
                "horizon": 25,
                **comp,
                "icc_ci95_lo": lo,
                "icc_ci95_hi": hi,
                "n_bootstrap": n_boot,
                "n_bootstrap_used": n_ok,
                "bootstrap_seed": seed,
            })
    return pd.DataFrame(rows).sort_values(
        ["outcome", "statistic"]).reset_index(drop=True)


# =========================================================================== #
#  CLI                                                                         #
# =========================================================================== #

def _write(df: pd.DataFrame, name: str) -> Path:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    out = TABLES_DIR / name
    df.to_csv(out, index=False, float_format="%.6g")
    print(f"  -> {name}  ({len(df)} rows)")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=RAW_PATH)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20020422)
    args = ap.parse_args(argv)

    print("=" * 70)
    print("  Post-hoc analysis of the completed horizon validation")
    print("  (no simulations are launched)")
    print("=" * 70)

    df = pd.read_csv(args.raw)
    info = validate_horizon_raw(df)
    for k, v in info.items():
        print(f"  {k:22s} {v}")

    drift = drift_by_config(df)
    persist = persistence_summary(drift)
    decomp = decomposition_table(df, n_boot=args.bootstrap, seed=args.seed)

    _write(drift, "protocol_horizon_drift_by_config.csv")
    _write(persist, "protocol_horizon_drift_summary.csv")
    _write(decomp, "protocol_seed_noise_decomposition.csv")
    print("\nDone.")


if __name__ == "__main__":
    main()
