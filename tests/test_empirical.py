"""
test_empirical.py
-----------------
Sanity checks for the empirical 2002 / 2022 replay machinery.

Run with:  pytest tests/test_empirical.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))

import empirical_data as ed
from model import run_simulation

YEARS = (2002, 2022)


# --------------------------------------------------------------------------- #
#  Loaders                                                                     #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year", YEARS)
def test_positions_in_range_and_ordered(year):
    df = ed.load_party_positions(year)
    pos = df["position"].to_numpy()
    assert np.all(pos >= -1.0) and np.all(pos <= 1.0)
    assert np.all(np.diff(pos) >= 0)  # left-to-right order


@pytest.mark.parametrize("year", YEARS)
def test_party_order_consistent_across_files(year):
    bundle = ed.load_year(year)
    K = bundle["K"]
    assert len(bundle["positions"]) == K
    assert len(bundle["results"]) == K
    assert all(len(s) == K for s in bundle["signals"])


@pytest.mark.parametrize("year", YEARS)
def test_results_sum_to_one(year):
    bundle = ed.load_year(year)
    assert bundle["results"].sum() == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("year", YEARS)
@pytest.mark.parametrize("mode", ["weekly", "individual"])
def test_signals_normalised(year, mode):
    bundle = ed.load_year(year, signal_mode=mode)
    for s in bundle["signals"]:
        assert s.sum() == pytest.approx(1.0, abs=1e-9)
        assert np.all(s >= 0)


# --------------------------------------------------------------------------- #
#  Voter sampling                                                             #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year", YEARS)
def test_voter_histogram_probs_sum_to_one(year):
    pos, probs = ed.load_voter_histogram(year)
    assert probs.sum() == pytest.approx(1.0, abs=1e-9)
    assert np.all(probs >= 0)
    assert np.all(pos >= -1.0) and np.all(pos <= 1.0)


@pytest.mark.parametrize("year", YEARS)
def test_voter_sample_matches_histogram_mean(year):
    pos, probs = ed.load_voter_histogram(year)
    target_mean = float((pos * probs).sum())
    rng = np.random.default_rng(0)
    sample = ed.sample_voters(year, 50000, rng)
    assert np.all(sample >= -1.0) and np.all(sample <= 1.0)
    assert sample.mean() == pytest.approx(target_mean, abs=0.05)


def test_voter_sample_deterministic():
    a = ed.sample_voters(2002, 1000, np.random.default_rng(42))
    b = ed.sample_voters(2002, 1000, np.random.default_rng(42))
    assert np.array_equal(a, b)


# --------------------------------------------------------------------------- #
#  model.py override backward-compatibility                                    #
# --------------------------------------------------------------------------- #

def test_overrides_none_is_synthetic_baseline():
    """All overrides None -> identical output to a plain synthetic run."""
    common = dict(K=8, n_electors=200, max_iterations=5, seed=7, verbose=False)
    a = run_simulation(**common)
    b = run_simulation(party_positions_override=None,
                       voter_positions_override=None,
                       exogenous_signals=None, **common)
    assert a["final_shares"] == b["final_shares"]


def test_empirical_run_basic_invariants():
    bundle = ed.load_year(2002)
    voters = ed.sample_voters(2002, 500, np.random.default_rng(1))
    res = run_simulation(
        K=bundle["K"], party_ids=bundle["parties"],
        party_positions_override=bundle["positions"],
        voter_positions_override=voters,
        exogenous_signals=bundle["signals"],
        tau=2.0, mu=0.1, alpha_prior=0.0, rho_pi=50.0,
        n_electors=len(voters), max_iterations=len(bundle["signals"]),
        seed=3, verbose=False, collect_diagnostics=True,
    )
    final = np.asarray(res["final_shares"])
    assert final.sum() == pytest.approx(1.0, abs=1e-9)
    assert len(final) == bundle["K"]
    assert 0.0 <= res["diagnostics"]["trigger_rate_final"] <= 1.0


def test_empirical_run_deterministic():
    bundle = ed.load_year(2022)
    voters = ed.sample_voters(2022, 400, np.random.default_rng(5))
    kwargs = dict(
        K=bundle["K"], party_ids=bundle["parties"],
        party_positions_override=bundle["positions"],
        voter_positions_override=voters,
        exogenous_signals=bundle["signals"],
        tau=1.5, mu=0.2, alpha_prior=0.3, rho_pi=80.0,
        n_electors=len(voters), max_iterations=len(bundle["signals"]),
        seed=11, verbose=False,
    )
    assert run_simulation(**kwargs)["final_shares"] == \
        run_simulation(**kwargs)["final_shares"]
