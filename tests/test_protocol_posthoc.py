"""
test_protocol_posthoc.py
------------------------
Tests for the post-hoc drift and variance-decomposition analysis.

The statistics here decide whether T=25 survives, so each formula is checked
against a fixture whose answer can be worked out by hand rather than against the
implementation's own output.

Run with:  pytest tests/test_protocol_posthoc.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis" / "synthetic"))

import protocol_posthoc as ph
import parameter_space as ps

RAW = REPO / "analysis" / "synthetic" / "outputs" / "protocol_validation" / "horizon_raw.csv"


# --------------------------------------------------------------------------- #
#  Fixtures                                                                    #
# --------------------------------------------------------------------------- #

def _fake_raw(n_configs=3, n_seeds=8, drift=0.0, seed=0):
    """
    Minimal frame with the real schema.  `drift` adds a deterministic linear
    increase per horizon so a known signal can be recovered.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for ci in range(n_configs):
        for s in range(n_seeds):
            row = {
                "config_id": f"K6-low-r{ci:05d}", "K": 6, "c_stratum": "low",
                "seed": s, "n_electors": 2000, "t_max": 100,
                "tail_window": 10, "signal_epsilon": 1e-12,
                "tau_hat": 1.0 + ci, "c": 0.5, "theta": 1.0, "rho_s": 100.0,
                "rho_pi": 50.0, "alpha": 0.1, "mu": 0.2, "epsilon": 0.1,
            }
            base = rng.normal(0, 0.001)
            for outcome in ph.OUTCOMES:
                for statistic in ph.STATISTICS:
                    for k, h in enumerate(ph.HORIZONS):
                        row[ph.column_for(outcome, statistic, h)] = (
                            base + drift * k)
            rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
#  Schema helper                                                               #
# --------------------------------------------------------------------------- #

def test_column_for_matches_the_real_schema():
    assert ph.column_for("delta_cenp", "endpoint", 25) == "delta_cenp_T25"
    assert ph.column_for("delta_cenp", "tail", 25) == "delta_cenp_tail_T25"
    assert ph.column_for("trigger_rate", "tail", 100) == "trigger_rate_tail_T100"
    with pytest.raises(ValueError):
        ph.column_for("delta_cenp", "bogus", 25)


# --------------------------------------------------------------------------- #
#  Input validation                                                            #
# --------------------------------------------------------------------------- #

def test_validation_accepts_a_complete_frame():
    df = _fake_raw(n_configs=3)
    exp = dict(ph.EXPECTED, n_configs=3, n_rows=24)
    info = ph.validate_horizon_raw(df, exp)
    assert info["n_configs"] == 3
    assert info["n_seeds_per_config"] == 8
    assert info["duplicate_keys"] == 0


def test_validation_detects_an_incomplete_configuration():
    """One configuration with 7 seeds instead of 8 must be caught."""
    df = _fake_raw(n_configs=3)
    df = df.drop(df.index[0]).reset_index(drop=True)
    exp = dict(ph.EXPECTED, n_configs=3, n_rows=23)
    with pytest.raises(ValueError, match="do not have 8 seeds"):
        ph.validate_horizon_raw(df, exp)


def test_validation_detects_duplicate_config_seed_keys():
    df = _fake_raw(n_configs=3)
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    exp = dict(ph.EXPECTED, n_configs=3, n_rows=25)
    with pytest.raises(ValueError, match="duplicate"):
        ph.validate_horizon_raw(df, exp)


def test_validation_detects_mixed_epsilon():
    df = _fake_raw(n_configs=3)
    df.loc[0, "signal_epsilon"] = 1e-4
    exp = dict(ph.EXPECTED, n_configs=3, n_rows=24)
    with pytest.raises(ValueError, match="signal_epsilon is not constant"):
        ph.validate_horizon_raw(df, exp)


def test_validation_detects_non_finite_outcomes():
    df = _fake_raw(n_configs=3)
    df.loc[0, "delta_cenp_T50"] = np.nan
    exp = dict(ph.EXPECTED, n_configs=3, n_rows=24)
    with pytest.raises(ValueError, match="NaN"):
        ph.validate_horizon_raw(df, exp)


def test_validation_detects_missing_columns():
    df = _fake_raw(n_configs=3).drop(columns=["delta_cenp_T100"])
    with pytest.raises(ValueError, match="missing required columns"):
        ph.validate_horizon_raw(df, dict(ph.EXPECTED, n_configs=3, n_rows=24))


# --------------------------------------------------------------------------- #
#  Paired changes                                                              #
# --------------------------------------------------------------------------- #

def test_paired_change_is_the_within_row_difference():
    df = _fake_raw(n_configs=2, drift=0.01)
    ch = ph.paired_changes(df, "delta_cenp", "endpoint", "T25_T50")
    # horizons are index 0 and 1, so exactly one drift step
    assert np.allclose(ch["change"].to_numpy(), 0.01)


def test_paired_change_pairs_the_same_config_and_seed():
    df = _fake_raw(n_configs=3, drift=0.0, seed=5)
    ch = ph.paired_changes(df, "enp", "endpoint", "T25_T100")
    manual = (df["enp_T100"] - df["enp_T25"]).to_numpy()
    assert np.allclose(ch["change"].to_numpy(), manual)
    assert list(ch["config_id"]) == list(df["config_id"])
    assert list(ch["seed"]) == list(df["seed"])


def test_unequal_interval_spans_are_recorded_and_normalised():
    """T25->T50 spans 25 iterations, T50->T100 spans 50, T25->T100 spans 75."""
    df = _fake_raw(n_configs=1, drift=0.02)
    spans = {"T25_T50": 25, "T50_T100": 50, "T25_T100": 75}
    for interval, span in spans.items():
        ch = ph.paired_changes(df, "delta_cenp", "endpoint", interval)
        assert (ch["span_iterations"] == span).all()
        assert np.allclose(ch["change_per_iteration"],
                           ch["change"] / span)


def test_per_iteration_rate_equalises_a_constant_drift():
    """
    With a constant per-step drift the two intervals have DIFFERENT raw changes
    (0.02 vs 0.02 here by construction of the fixture) but the point of the
    normalisation is that the per-iteration column divides by its own span.
    """
    df = _fake_raw(n_configs=1, drift=0.02)
    a = ph.paired_changes(df, "delta_cenp", "endpoint", "T25_T50")
    b = ph.paired_changes(df, "delta_cenp", "endpoint", "T50_T100")
    assert np.allclose(a["change_per_iteration"], 0.02 / 25)
    assert np.allclose(b["change_per_iteration"], 0.02 / 50)


def test_unknown_interval_raises():
    with pytest.raises(ValueError, match="unknown interval"):
        ph.paired_changes(_fake_raw(1), "enp", "endpoint", "T10_T20")


# --------------------------------------------------------------------------- #
#  Benjamini-Hochberg                                                          #
# --------------------------------------------------------------------------- #

def test_bh_textbook_example():
    """
    p = .001 .008 .039 .041 .042 .06 .074 .205 (m = 8).
    Step-up gives q = .008 .032 .0672 .0672 .0672 .08 .0846 .205.
    """
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205])
    q = ph.benjamini_hochberg(p)
    # written as the exact step-up expressions rather than rounded decimals
    expected = np.array([
        0.001 * 8 / 1,          # 0.008
        0.008 * 8 / 2,          # 0.032
        0.042 * 8 / 5,          # 0.0672, pulled down from rank 3 by the step-up
        0.042 * 8 / 5,
        0.042 * 8 / 5,
        0.06 * 8 / 6,           # 0.08
        0.074 * 8 / 7,          # 0.084571...
        0.205 * 8 / 8,          # 0.205
    ])
    np.testing.assert_allclose(q, expected, rtol=1e-12)


def test_bh_is_monotone_and_never_below_p():
    rng = np.random.default_rng(0)
    p = rng.random(50)
    q = ph.benjamini_hochberg(p)
    assert np.all(q >= p - 1e-12)
    assert np.all(q <= 1.0)
    order = np.argsort(p)
    assert np.all(np.diff(q[order]) >= -1e-12)


def test_bh_respects_input_order():
    p = np.array([0.2, 0.01, 0.05])
    q = ph.benjamini_hochberg(p)
    q_shuffled = ph.benjamini_hochberg(p[[1, 2, 0]])
    np.testing.assert_allclose(q[[1, 2, 0]], q_shuffled)


def test_bh_equal_scaled_values_all_share_a_q():
    """p_i = i * alpha / m gives an identical scaled value at every rank."""
    p = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    np.testing.assert_allclose(ph.benjamini_hochberg(p), np.full(5, 0.05))


def test_bh_rejects_nan():
    with pytest.raises(ValueError):
        ph.benjamini_hochberg([0.1, np.nan])


# --------------------------------------------------------------------------- #
#  Variance components                                                         #
# --------------------------------------------------------------------------- #

def test_variance_components_all_between():
    """
    Groups [1,1,1,1], [2,2,2,2], [3,3,3,3].  Grand mean 2.
    SS_between = 4*((-1)^2+0+1^2) = 8, MS_between = 8/2 = 4.
    SS_within = 0 -> MS_within = 0.
    sigma_config^2 = (4-0)/4 = 1, sigma_seed^2 = 0, ICC = 1.
    """
    values = [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]
    groups = ["a"] * 4 + ["b"] * 4 + ["c"] * 4
    out = ph.variance_components(values, groups)
    assert out["ms_between"] == pytest.approx(4.0)
    assert out["ms_within"] == pytest.approx(0.0)
    assert out["sigma_config_sq"] == pytest.approx(1.0)
    assert out["sigma_seed_sq"] == pytest.approx(0.0)
    assert out["icc"] == pytest.approx(1.0)
    assert out["n_per_group"] == 4


def test_variance_components_all_within():
    """
    Three groups each holding [1,2,3,4].  Group means identical -> MS_between 0.
    SS_within = 3 * 5 = 15, MS_within = 15/9 = 1.6667.
    sigma_config^2 truncates to 0, ICC = 0.
    """
    values = [1, 2, 3, 4] * 3
    groups = ["a"] * 4 + ["b"] * 4 + ["c"] * 4
    out = ph.variance_components(values, groups)
    assert out["ms_between"] == pytest.approx(0.0)
    assert out["ms_within"] == pytest.approx(15.0 / 9.0)
    assert out["sigma_config_sq"] == pytest.approx(0.0)
    assert out["icc"] == pytest.approx(0.0)
    assert out["truncated_at_zero"] is True


def test_variance_components_known_mixed_case():
    """
    Groups [0,2] and [10,12]: within variance 2 per group, means 1 and 11.
    SS_between = 2*((1-6)^2+(11-6)^2) = 100, MS_between = 100.
    SS_within = 2+2 = 4, MS_within = 4/2 = 2.
    sigma_config^2 = (100-2)/2 = 49, ICC = 49/51.
    """
    out = ph.variance_components([0, 2, 10, 12], ["a", "a", "b", "b"])
    assert out["ms_between"] == pytest.approx(100.0)
    assert out["ms_within"] == pytest.approx(2.0)
    assert out["sigma_config_sq"] == pytest.approx(49.0)
    assert out["icc"] == pytest.approx(49.0 / 51.0)


def test_variance_components_rejects_unbalanced_design():
    with pytest.raises(ValueError, match="unbalanced"):
        ph.variance_components([1, 2, 3], ["a", "a", "b"])


def test_variance_components_needs_two_groups():
    with pytest.raises(ValueError, match="at least two groups"):
        ph.variance_components([1, 2, 3, 4], ["a"] * 4)


def test_bootstrap_icc_is_deterministic_and_brackets_the_estimate():
    rng = np.random.default_rng(1)
    groups = np.repeat([f"g{i}" for i in range(12)], 8)
    values = np.repeat(rng.normal(0, 1, 12), 8) + rng.normal(0, 0.2, 96)
    point = ph.variance_components(values, groups)["icc"]

    lo1, hi1, n1 = ph.bootstrap_icc(values, groups, n_boot=200, seed=42)
    lo2, hi2, n2 = ph.bootstrap_icc(values, groups, n_boot=200, seed=42)
    assert (lo1, hi1, n1) == (lo2, hi2, n2)
    assert lo1 <= point <= hi1
    assert n1 == 200


# --------------------------------------------------------------------------- #
#  Assembled tables: schema and stable ordering                                #
# --------------------------------------------------------------------------- #

def test_drift_table_schema_and_ordering():
    df = _fake_raw(n_configs=4, seed=3)
    out = ph.drift_by_config(df)

    for col in ("config_id", "K", "c_stratum", "outcome", "statistic",
                "interval", "span_iterations", "n_seeds", "mean_signed_change",
                "mean_abs_change", "sd_change", "se_change", "ci95_lo",
                "ci95_hi", "p_value", "q_value", "ci_excludes_zero",
                "significant_bh", "mean_signed_change_per_iteration"):
        assert col in out.columns

    expected_rows = 4 * len(ph.OUTCOMES) * len(ph.STATISTICS) * len(ph.INTERVALS)
    assert len(out) == expected_rows

    key = out[["outcome", "statistic", "interval", "config_id"]]
    assert key.apply(tuple, axis=1).is_monotonic_increasing
    assert not key.duplicated().any()


def test_drift_table_is_deterministic():
    df = _fake_raw(n_configs=3, seed=7)
    pd.testing.assert_frame_equal(ph.drift_by_config(df),
                                  ph.drift_by_config(df))


def test_drift_recovers_a_planted_constant_drift():
    """
    A configuration with an identical change in every seed has zero SE, so the
    implementation reports it as a definite move rather than dividing by zero.
    """
    df = _fake_raw(n_configs=2, drift=0.05)
    out = ph.drift_by_config(df)
    row = out[(out.outcome == "delta_cenp") & (out.statistic == "endpoint")
              & (out.interval == "T25_T50")].iloc[0]
    assert row["mean_signed_change"] == pytest.approx(0.05)
    assert row["sd_change"] == pytest.approx(0.0, abs=1e-12)
    assert row["ci_excludes_zero"]


def test_bh_is_applied_within_each_outcome_statistic_interval_family():
    df = _fake_raw(n_configs=6, seed=11)
    out = ph.drift_by_config(df)
    for _, grp in out.groupby(["outcome", "statistic", "interval"]):
        expected = ph.benjamini_hochberg(grp["p_value"].to_numpy())
        np.testing.assert_allclose(grp["q_value"].to_numpy(), expected)


def test_persistence_summary_counts_direction_changes():
    df = _fake_raw(n_configs=5, seed=2)
    summary = ph.persistence_summary(ph.drift_by_config(df))
    assert len(summary) == len(ph.OUTCOMES) * len(ph.STATISTICS)
    for _, r in summary.iterrows():
        assert (r["n_same_direction_both_intervals"]
                + r["n_reversing_direction"]) == r["n_configurations"]


def test_decomposition_table_schema():
    df = _fake_raw(n_configs=5, seed=4)
    out = ph.decomposition_table(df, n_boot=50, seed=1)
    for col in ("outcome", "statistic", "ms_between", "ms_within",
                "sigma_config_sq", "sigma_seed_sq", "icc",
                "seed_noise_fraction", "icc_ci95_lo", "icc_ci95_hi",
                "n_bootstrap", "bootstrap_seed"):
        assert col in out.columns
    assert len(out) == len(ph.OUTCOMES) * len(ph.STATISTICS)
    assert out[["outcome", "statistic"]].apply(
        tuple, axis=1).is_monotonic_increasing


# --------------------------------------------------------------------------- #
#  Against the real run, when it is present                                    #
# --------------------------------------------------------------------------- #

def _horizon_frame(n_configs=54, n_seeds=8, **overrides):
    """A synthetic horizon_raw frame with the real schema.

    Built here rather than read from disk: the real file is a 213 KB generated
    output that is git-ignored, so a test depending on it can only skip in CI.
    The validator's contract does not need the real numbers, only the real
    *shape*, which this reproduces exactly.
    """
    rng = np.random.default_rng(0)
    rows = []
    for cfg in range(n_configs):
        for seed in range(n_seeds):
            row = {
                "config_id": f"K6-c1.25-{cfg:03d}",
                "K": 6,
                "c_stratum": "Active B",
                "seed": seed,
                "n_electors": 2000,
                "t_max": 100,
                "tail_window": 5,
                "signal_epsilon": 1e-12,
            }
            for name in ps.PROBLEM["names"]:
                lo, hi = ps.bounds_for(name)
                row[name] = float(rng.uniform(lo, hi))
            for o in ph.OUTCOMES:
                for st in ph.STATISTICS:
                    for h in ph.HORIZONS:
                        row[ph.column_for(o, st, h)] = float(rng.normal())
            row.update(overrides)
            rows.append(row)
    return pd.DataFrame(rows)


def test_horizon_raw_of_the_documented_shape_passes_validation():
    """The shape the real run produces: 54 configurations x 8 seeds = 432 rows."""
    info = ph.validate_horizon_raw(_horizon_frame())
    assert info["n_rows"] == 432
    assert info["n_configs"] == 54
    assert info["n_seeds_per_config"] == 8
    assert info["signal_epsilon"] == 1e-12
    assert info["t_max"] == 100
    assert info["n_electors"] == 2000


def test_horizon_raw_validation_rejects_a_short_run():
    """A missing configuration must be refused, not averaged over."""
    with pytest.raises(ValueError):
        ph.validate_horizon_raw(_horizon_frame(n_configs=53))


def test_horizon_raw_validation_rejects_a_wrong_signal_epsilon():
    """eps_s is part of the protocol; a file produced under another value is a
    different experiment."""
    with pytest.raises(ValueError):
        ph.validate_horizon_raw(_horizon_frame(signal_epsilon=1e-4))


def test_horizon_raw_validation_rejects_a_non_finite_outcome():
    df = _horizon_frame()
    df.loc[0, ph.column_for("delta_cenp", "endpoint", 25)] = np.nan
    with pytest.raises(ValueError):
        ph.validate_horizon_raw(df)
