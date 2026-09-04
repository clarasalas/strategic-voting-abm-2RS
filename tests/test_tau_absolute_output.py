"""
test_tau_absolute_output.py
---------------------------
tau exists in two units and only one of them is meaningful to run_simulation:

    tau_hat       normalised, in zone lengths : what every design draws
    tau_absolute  on [-1, 1]                  : tau_hat * (2 / K)

tests/test_tau_units.py pins the conversion and the fact that the runners apply
it.  This file pins the other half: that both units are RECORDED, that the
recorded absolute value is the one that was actually simulated, and that the
conversion happens exactly once on the way from the design to the CSV.

The motivating failure is silent.  If a later edit converted a second time, the
CSV would hold tau_hat * (2/K)^2, still plausible-looking numbers, and no
warning anywhere.  Comparing the emitted column against the value the spy saw
enter run_simulation is what makes that detectable.

Run with:  pytest tests/test_tau_absolute_output.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(REPO / "analysis" / "empirical"))

import empirical_data as ed
from metrics import tau_absolute

# The two real candidate sets.  These are the K values every empirical result
# depends on, so they are asserted rather than merely read.
K_BY_YEAR = {2002: 15, 2022: 12}

# Small enough to run the real model a few times per test.
TEST_VOTERS = 40


@pytest.fixture(autouse=True)
def _fast_electorate(monkeypatch):
    """Shrink the electorate; nothing here measures a scientific quantity."""
    import empirical_2002_2022 as runner
    monkeypatch.setattr(runner, "N_VOTERS", TEST_VOTERS)


# --------------------------------------------------------------------------- #
#  The two candidate sets                                                      #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year,expected_K", sorted(K_BY_YEAR.items()))
def test_candidate_set_size(year, expected_K):
    """K is what the whole conversion turns on, so pin it for both years."""
    assert ed.load_year(year)["K"] == expected_K


@pytest.mark.parametrize("year,K", sorted(K_BY_YEAR.items()))
def test_conversion_at_each_real_K(year, K):
    """tau_hat = 3.0 is 0.4 in 2002 (K=15) and 0.5 in 2022 (K=12)."""
    expected = {15: 0.4, 12: 0.5}[K]
    assert tau_absolute(3.0, K) == pytest.approx(expected, abs=1e-12)


# --------------------------------------------------------------------------- #
#  Empirical replay: schema, equality, single conversion, tau_hat untouched     #
# --------------------------------------------------------------------------- #

def _run_tiny_replay(tmp_path, monkeypatch, n_draws=2):
    """
    Run the real replay on a tiny design, counting conversions.

    Returns (counter, {year: DataFrame}) where counter['n'] is the number of
    times tau_absolute was called across the whole run.
    """
    import empirical_2002_2022 as runner

    counter = {"n": 0}
    real = runner.tau_absolute

    def counting(tau_hat, K):
        counter["n"] += 1
        return real(tau_hat, K)

    monkeypatch.setattr(runner, "tau_absolute", counting)
    runner.run_main_experiment(n_draws, cfg={}, out_dir=tmp_path)

    frames = {y: pd.read_csv(tmp_path / f"empirical_runs_{y}.csv")
              for y in runner.YEARS}
    return counter, frames


def test_replay_rows_carry_both_units(tmp_path, monkeypatch):
    """The schema must name both units, plus the K they are related through."""
    _, frames = _run_tiny_replay(tmp_path, monkeypatch)
    for year, df in frames.items():
        for col in ("tau_hat", "tau_absolute", "K"):
            assert col in df.columns, f"{year}: {col} missing from empirical_runs"


@pytest.mark.parametrize("year", sorted(K_BY_YEAR))
def test_replay_absolute_equals_tau_hat_times_zone_length(tmp_path, monkeypatch,
                                                          year):
    """tau_absolute == tau_hat * (2 / K), row by row, at the recorded K."""
    _, frames = _run_tiny_replay(tmp_path, monkeypatch)
    df = frames[year]

    assert (df["K"] == K_BY_YEAR[year]).all()
    expected = df["tau_hat"].to_numpy(float) * (2.0 / K_BY_YEAR[year])
    np.testing.assert_allclose(df["tau_absolute"].to_numpy(float), expected,
                               rtol=0, atol=1e-12)


def test_replay_converts_exactly_once_per_simulation(tmp_path, monkeypatch):
    """
    One conversion per simulation and no more.

    Two draws over two years is four simulations, so four conversions.  A
    second conversion site, in the row builder say, would show up here as
    eight.
    """
    import empirical_2002_2022 as runner
    n_draws = 2
    counter, _ = _run_tiny_replay(tmp_path, monkeypatch, n_draws=n_draws)
    assert counter["n"] == n_draws * len(runner.YEARS)


def test_replay_recorded_absolute_is_the_simulated_one(monkeypatch):
    """
    The emitted column must be the exact value handed to run_simulation.

    This is the check that survives refactoring: it compares the number written
    to disk against the number the model actually received, rather than against
    a formula re-derived in the test.
    """
    import empirical_2002_2022 as runner

    seen = {}
    real_sim = runner.run_simulation

    def spy(**kwargs):
        seen["tau"] = kwargs["tau"]
        return real_sim(**kwargs)

    monkeypatch.setattr(runner, "run_simulation", spy)

    year = 2002
    bundle = ed.load_year(year, signal_mode="weekly")
    voters = ed.sample_voters(year, TEST_VOTERS, np.random.default_rng(0))
    params = {"draw": 0, "tau_hat": 1.75, "mu": 0.2, "alpha": 0.1,
              "rho_pi": 50.0, "beta": 0.0}

    outcome = runner.run_single(
        params, bundle["positions"], voters, bundle["signals"],
        bundle["results"], bundle["parties"], seed=0)
    row = runner._scalar_row(params, outcome)

    assert row["tau_absolute"] == seen["tau"]          # bit-for-bit, not approx
    assert row["K"] == K_BY_YEAR[year]


def test_replay_leaves_tau_hat_unchanged(tmp_path, monkeypatch):
    """
    tau_hat must reach the CSV exactly as the design drew it.

    Both years share one design, so the recorded tau_hat must also be identical
    across years: that shared draw is the whole point of the paired design.
    """
    import empirical_2002_2022 as runner

    n_draws = 2
    rng = np.random.default_rng(runner.MASTER_SEED)
    design = runner.sample_parameter_design(n_draws, rng)

    _, frames = _run_tiny_replay(tmp_path, monkeypatch, n_draws=n_draws)
    for year, df in frames.items():
        np.testing.assert_allclose(
            df.sort_values("draw")["tau_hat"].to_numpy(float),
            design.sort_values("draw")["tau_hat"].to_numpy(float),
            rtol=0, atol=0, err_msg=f"{year}: tau_hat was modified in flight")

    a, b = (frames[y].sort_values("draw")["tau_hat"].to_numpy(float)
            for y in sorted(frames))
    np.testing.assert_array_equal(a, b)


def test_replay_per_draw_candidate_table_carries_both_units(tmp_path,
                                                            monkeypatch):
    """The long per-candidate table records tau_hat, so it records both."""
    _run_tiny_replay(tmp_path, monkeypatch)
    for year, K in K_BY_YEAR.items():
        df = pd.read_csv(tmp_path / f"empirical_candidate_draws_{year}.csv")
        assert {"tau_hat", "tau_absolute", "K"} <= set(df.columns)
        assert (df["K"] == K).all()
        np.testing.assert_allclose(
            df["tau_absolute"].to_numpy(float),
            df["tau_hat"].to_numpy(float) * (2.0 / K), rtol=0, atol=1e-12)


# --------------------------------------------------------------------------- #
#  Behavioural sweep                                                           #
# --------------------------------------------------------------------------- #

def test_sweep_schema_names_both_units():
    """The sweep's canonical column order must carry both units and K."""
    import behavioral_sweep as sweep
    for col in ("tau_hat", "tau_absolute", "K"):
        assert col in sweep.OUTPUT_COLS
    # tau_absolute must sit beside tau_hat, so a reader cannot miss that the
    # file holds two different tolerances.
    assert sweep.OUTPUT_COLS.index("tau_absolute") == \
        sweep.OUTPUT_COLS.index("tau_hat") + 1


@pytest.mark.parametrize("year,K", sorted(K_BY_YEAR.items()))
def test_sweep_run_one_reports_the_simulated_absolute(monkeypatch, year, K):
    """run_one returns the tau it passed to the model, not a recomputation."""
    import behavioral_sweep as sweep

    seen = {}
    real_sim = sweep.run_simulation

    def spy(**kwargs):
        seen["tau"] = kwargs["tau"]
        return real_sim(**kwargs)

    monkeypatch.setattr(sweep, "run_simulation", spy)

    bundle = ed.load_year(year, signal_mode="weekly")
    voters = ed.sample_voters(year, TEST_VOTERS, np.random.default_rng(0))
    params = {"tau_hat": 2.25, "mu": 0.3, "alpha": 0.2,
              "rho_pi": 40.0, "beta": 5.0}

    out = sweep.run_one(params, bundle, voters, seed=1)

    assert out["tau_absolute"] == seen["tau"]
    assert out["K"] == K
    assert out["tau_absolute"] == pytest.approx(2.25 * (2.0 / K), abs=1e-12)


def test_sweep_converts_exactly_once_per_run(monkeypatch):
    """One conversion per run_one call."""
    import behavioral_sweep as sweep

    counter = {"n": 0}
    real = sweep.tau_absolute

    def counting(tau_hat, K):
        counter["n"] += 1
        return real(tau_hat, K)

    monkeypatch.setattr(sweep, "tau_absolute", counting)

    bundle = ed.load_year(2002, signal_mode="weekly")
    voters = ed.sample_voters(2002, TEST_VOTERS, np.random.default_rng(0))
    params = {"tau_hat": 1.0, "mu": 0.0, "alpha": 0.0,
              "rho_pi": 30.0, "beta": 1.0}

    sweep.run_one(params, bundle, voters, seed=3)
    assert counter["n"] == 1


# --------------------------------------------------------------------------- #
#  The bound is year-specific                                                  #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year,bound", [(2002, 0.4), (2022, 0.5)])
def test_absolute_tau_respects_the_year_specific_ceiling(year, bound):
    """
    The largest absolute tau a design can produce is tau_hat_max * (2 / K),
    which is 0.4 in 2002 and 0.5 in 2022, not a single shared number.

    The bound is inclusive: tau_hat = 3.0 is the top of the swept range, so
    0.4 and 0.5 are attainable values, not open limits.
    """
    K = K_BY_YEAR[year]
    tau_hat_max = 3.0
    assert tau_absolute(tau_hat_max, K) == pytest.approx(bound, abs=1e-12)
    grid = np.linspace(0.5, tau_hat_max, 501)
    assert max(tau_absolute(t, K) for t in grid) <= bound + 1e-12
