"""
Schema and regeneration contract for the committed empirical result tables.

These tables are cited, so the properties that matter are structural: the key
columns identify a row uniquely, the ordering is deterministic, nothing is
missing or infinite, and regenerating from unchanged inputs reproduces the
committed bytes.

The regeneration test is skipped when the raw empirical outputs are absent,
because ``data/`` is git-ignored and a fresh clone has no simulation output.
"""

import io
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


def _load_generator(data_dir):
    """Import the table generator with its DATA directory redirected."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_empirical_tables",
        ROOT / "analysis" / "empirical" / "make_empirical_tables.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DATA = Path(data_dir)
    # Never let a fixture-driven test write into the real results/tables.
    # Tests that want the committed tables read them directly from TABLES.
    if Path(data_dir) != DATA:
        mod.OUT = Path(data_dir).parent / "tables"
    return mod


def _write_fixture_inputs(data_dir):
    """Minimal raw outputs with the real schema, in a temporary directory.

    The real inputs are 17 MB of git-ignored simulation output, so a test that
    reads them can only skip in CI. These fixtures carry the same columns and
    the same per-year candidate counts, with values chosen to be awkward for a
    float round-trip -- so the test exercises the generator's contract, not the
    size of the data.
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    hard = [0.1, 1 / 3, 0.06933728008356, 2.145268755345708e-05,
            1e-300, 0.30000000000000004, -0.0, 123456789.123456789]

    scalar_cols = ["rmse", "mae", "top2_acc", "top3_acc", "top4_acc",
                   "enp_sincere", "enp_final", "delta_enp", "delta_cenp",
                   "cliff_magnitude", "cliff_ratio", "trigger_rate",
                   "switching_rate", "conditional_switching_rate"]

    def runs(year, K, n):
        rows = []
        for d in range(n):
            r = {"draw": d, "tau_hat": 0.5 + d, "tau_absolute": (0.5 + d) * 2 / K,
                 "K": K, "rho_pi": 5.0 + d, "alpha": 0.1 * d, "mu": 0.2 * d,
                 "beta": 1.0 * d, "cliff_location": 1 + (d % 2)}
            for i, c in enumerate(scalar_cols):
                r[c] = hard[(d + i) % len(hard)]
            rows.append(r)
        return pd.DataFrame(rows)

    def shares(K):
        return pd.DataFrame({
            "party": [f"P{i}" for i in range(K)],
            "block": ["left" if i < K // 2 else "right" for i in range(K)],
            "position": [-1 + 2 * i / (K - 1) for i in range(K)],
            "actual_share": [1 / K] * K,
            "first_signal_share": [hard[i % len(hard)] for i in range(K)],
            "mean_final_share": [hard[(i + 1) % len(hard)] for i in range(K)],
            "p05_final_share": [0.0] * K, "p25_final_share": [0.0] * K,
            "p50_final_share": [0.0] * K, "p75_final_share": [0.0] * K,
            "p95_final_share": [1.0] * K,
            "mean_change_first_to_final": [0.0] * K,
            "p05_change": [0.0] * K, "p95_change": [0.0] * K,
            "prob_top2": [0.0] * K, "prob_top3": [0.0] * K, "prob_top4": [0.0] * K,
        })

    for year, K in ((2002, 15), (2022, 12)):
        runs(year, K, 4).to_csv(data_dir / f"empirical_runs_{year}.csv", index=False)
        for v in ("prob_signal", "prob_prior", "prob_signal_mu0"):
            runs(year, K, 4).to_csv(
                data_dir / f"empirical_runs_{v}_{year}.csv", index=False)
            shares(K).to_csv(
                data_dir / f"empirical_candidate_shares_{v}_{year}.csv", index=False)
        shares(K).to_csv(
            data_dir / f"empirical_candidate_shares_{year}.csv", index=False)

        rob = pd.concat([runs(year, K, 3).assign(variant=v) for v in
                         ("individual_signals", "perturbed_positions",
                          "resampled_voters")], ignore_index=True)
        rob.to_csv(data_dir / f"empirical_robustness_{year}.csv", index=False)

        sw = pd.DataFrame({
            "draw": range(4), "tau_hat": [0.5, 1.0, 2.0, 3.0],
            "tau_absolute": [x * 2 / K for x in (0.5, 1.0, 2.0, 3.0)],
            "K": K, "mu": 0.1, "alpha": 0.2, "rho_pi": 50.0, "beta": 3.0,
            "mean_delta_cenp": hard[:4], "mean_final_enp": hard[1:5],
            "std_delta_cenp": hard[2:6], "n_repeats": 4, "seed": 20020422,
        })
        sw.to_csv(data_dir / f"behavioral_sweep_{year}.csv", index=False)

    pd.DataFrame({"year": [2002, 2022], "K": [15, 12],
                  "cenp_s0": [0.571868, 0.556685],
                  "cenp_real": [0.458633, 0.615341],
                  "delta_cenp_real": [-0.113235, 0.058656]}
                 ).to_csv(data_dir / "behavioral_targets.csv", index=False)


def test_generator_is_deterministic_on_fixture_inputs(tmp_path):
    """Two runs over identical inputs must produce identical bytes.

    This is the property that makes the committed tables trustworthy -- they
    are a pure function of the raw output, with nothing time- or
    environment-dependent in between. It runs everywhere, including CI, because
    it builds its own inputs.
    """
    _write_fixture_inputs(tmp_path / "data")
    mod = _load_generator(tmp_path / "data")
    for name, fn in mod.TABLES.items():
        first = fn().to_csv(index=False)
        second = fn().to_csv(index=False)
        assert first == second, f"{name} is not deterministic"


def test_generator_output_survives_a_csv_round_trip(tmp_path):
    """Writing a table and reading it back must not change a single value.

    The generator reads its inputs with the correctly rounded parser; this
    checks the other half, that what it writes can be recovered exactly.
    """
    _write_fixture_inputs(tmp_path / "data")
    mod = _load_generator(tmp_path / "data")
    for name, fn in mod.TABLES.items():
        df = fn()
        text = df.to_csv(index=False)
        back = pd.read_csv(io.StringIO(text), float_precision="round_trip")
        for c in df.columns:
            if df[c].dtype.kind == "f":
                assert np.array_equal(df[c].to_numpy(), back[c].to_numpy()), \
                    f"{name}: column {c} changed through a round trip"
            else:
                assert df[c].tolist() == back[c].tolist(), f"{name}: {c} changed"


def test_generator_guard_rails_reject_a_non_finite_input(tmp_path):
    """A NaN in the raw output must stop the table being written, not
    propagate into a committed artefact.

    Both DATA and OUT are redirected into tmp_path, so this can never read or
    write the real directories however it fails.
    """
    data = tmp_path / "data"
    _write_fixture_inputs(data)
    df = pd.read_csv(data / "empirical_runs_2002.csv")
    df.loc[0, "rmse"] = np.nan
    df.to_csv(data / "empirical_runs_2002.csv", index=False)

    mod = _load_generator(data)
    mod.OUT = tmp_path / "tables"
    with pytest.raises(AssertionError, match="NaN"):
        mod.main()
    assert not (TABLES / "empirical_replay_summary.csv").stat().st_size == 0


# The committed tables are also checked against the REAL raw outputs, but not
# from here: that check needs 17 MB of git-ignored simulation output, so as a
# test it could only ever skip in CI and on a fresh clone. It runs instead as
# the last step of the pipeline --
#
#     python analysis/empirical/make_empirical_tables.py && git status --short
#
# which must leave results/tables/ unchanged. The contract that makes it
# meaningful -- that the generator is a deterministic pure function of its
# inputs, exact through a CSV round trip, and refuses corrupt input -- is
# covered above by tests that build their own fixtures and therefore run
# everywhere.
