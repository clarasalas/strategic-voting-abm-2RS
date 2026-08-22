"""
Schema and regeneration contract for the committed empirical result tables.

These tables are cited, so the properties that matter are structural: the key
columns identify a row uniquely, the ordering is deterministic, nothing is
missing or infinite, and regenerating from unchanged inputs reproduces the
committed bytes.

The regeneration test is skipped when the raw empirical outputs are absent,
because ``data/`` is git-ignored and a fresh clone has no simulation output.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "results" / "tables"
DATA = ROOT / "data"

# table -> (key columns, expected row count)
SPEC = {
    "empirical_replay_summary.csv": (["specification", "year", "metric"], 112),
    "empirical_robustness_summary.csv": (["variant", "year", "metric"], 84),
    "empirical_activation_summary.csv": (["specification", "year"], 8),
    "behavioral_sweep_quantiles.csv": (["year"], 2),
    "empirical_year_contrast.csv": (["specification", "metric"], 56),
    "empirical_candidate_fit.csv": (["specification", "year", "party"], 108),
}

SPECIFICATIONS = {"nearest", "prob_signal", "prob_prior", "prob_signal_mu0"}
K_BY_YEAR = {2002: 15, 2022: 12}


def _load(name):
    path = TABLES / name
    if not path.exists():
        pytest.skip(f"{name} not generated yet")
    return pd.read_csv(path)


@pytest.mark.parametrize("name", sorted(SPEC))
def test_table_exists_and_has_expected_rows(name):
    df = _load(name)
    _, n = SPEC[name]
    assert len(df) == n


@pytest.mark.parametrize("name", sorted(SPEC))
def test_key_columns_are_present_and_unique(name):
    df = _load(name)
    keys, _ = SPEC[name]
    for k in keys:
        assert k in df.columns, f"{name} is missing key column {k}"
    assert not df.duplicated(subset=keys).any(), f"{name} has duplicate keys"


@pytest.mark.parametrize("name", sorted(SPEC))
def test_row_order_is_deterministic(name):
    """Rows are sorted by their key, so a regenerated table diffs cleanly."""
    df = _load(name)
    keys, _ = SPEC[name]
    got = df[keys].reset_index(drop=True)
    want = df[keys].sort_values(keys).reset_index(drop=True)
    assert got.equals(want), f"{name} is not sorted by {keys}"


@pytest.mark.parametrize("name", sorted(SPEC))
def test_no_missing_or_non_finite_values(name):
    df = _load(name)
    assert not df.isna().any().any(), f"{name} contains NaN"
    num = df.select_dtypes(include=[np.number])
    assert np.isfinite(num.to_numpy()).all(), f"{name} contains non-finite values"


@pytest.mark.parametrize(
    "name", ["empirical_replay_summary.csv", "empirical_activation_summary.csv",
             "empirical_year_contrast.csv", "empirical_candidate_fit.csv"])
def test_specification_labels_are_the_known_set(name):
    df = _load(name)
    assert set(df["specification"]) == SPECIFICATIONS


@pytest.mark.parametrize(
    "name", ["empirical_replay_summary.csv", "empirical_robustness_summary.csv",
             "empirical_activation_summary.csv", "behavioral_sweep_quantiles.csv",
             "empirical_candidate_fit.csv"])
def test_K_matches_the_year(name):
    """K is metadata that identifies the electorate; a wrong K would silently
    invalidate every tau conversion downstream."""
    df = _load(name)
    for year, K in K_BY_YEAR.items():
        sub = df[df["year"] == year]
        assert (sub["K"] == K).all(), f"{name}: year {year} should have K={K}"


def test_candidate_fit_has_K_rows_per_specification_and_year():
    df = _load("empirical_candidate_fit.csv")
    counts = df.groupby(["specification", "year"]).size()
    for (spec, year), n in counts.items():
        assert n == K_BY_YEAR[year], f"{spec} {year}: {n} parties, want {K_BY_YEAR[year]}"


def test_candidate_fit_error_column_is_consistent():
    df = _load("empirical_candidate_fit.csv")
    recomputed = df["mean_final_share"] - df["actual_share"]
    assert np.allclose(df["error_final_minus_actual"], recomputed, atol=1e-12)


def test_sweep_quantiles_are_monotone_and_bracket_the_mean():
    df = _load("behavioral_sweep_quantiles.csv")
    qcols = ["sim_q000", "sim_q005", "sim_q025", "sim_q050",
             "sim_q075", "sim_q095", "sim_q100"]
    for _, r in df.iterrows():
        vals = [r[c] for c in qcols]
        assert vals == sorted(vals), f"year {r['year']}: quantiles not monotone"
        assert vals[0] <= r["sim_mean"] <= vals[-1]


def test_sweep_quantiles_use_the_exogenous_poll_baseline():
    """The sweep's ΔCENP is measured against s⁰, not against the model's own
    iteration-0 shares.  The two baselines are different quantities and the
    table must say which one it reports."""
    df = _load("behavioral_sweep_quantiles.csv")
    assert (df["baseline"] == "exogenous_poll_s0").all()


def test_year_contrast_effect_size_flag_matches_the_pooled_sd():
    df = _load("empirical_year_contrast.csv")
    assert (df.loc[df["sd_pooled"] == 0, "effect_size_defined"] == False).all()
    assert (df.loc[df["sd_pooled"] > 0, "effect_size_defined"] == True).all()


def test_year_contrast_diff_matches_the_means():
    df = _load("empirical_year_contrast.csv")
    recomputed = df["mean_2022"] - df["mean_2002"]
    assert np.allclose(df["diff_2022_minus_2002"], recomputed, atol=1e-12)


@pytest.mark.skipif(
    not (DATA / "empirical_runs_2002.csv").exists(),
    reason="raw empirical outputs absent (data/ is git-ignored)")
def test_regeneration_reproduces_the_committed_tables():
    """Re-deriving every table from the raw outputs must reproduce the bytes.

    This is what makes the committed tables trustworthy: they are a pure
    function of the simulation output, with no manual editing in between.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_empirical_tables",
        ROOT / "analysis" / "empirical" / "make_empirical_tables.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    for name, fn in mod.TABLES.items():
        # Compare the serialized bytes, not the parsed floats: a CSV round-trip
        # can drop the last digit, so parsing both sides would compare something
        # weaker than what is actually committed.
        regenerated = fn().to_csv(index=False)
        committed = (TABLES / name).read_text()
        assert regenerated == committed, (
            f"{name} does not reproduce from the raw outputs; "
            f"re-run analysis/empirical/make_empirical_tables.py")
