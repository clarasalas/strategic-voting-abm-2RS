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
from agents import Elector, Party

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


# --------------------------------------------------------------------------- #
#  Probabilistic sincere initialization                                        #
# --------------------------------------------------------------------------- #

# A small fixed environment: 5 parties spread on [-1, 1], one voter at -0.55.
_PARTY_POS = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
_VOTER_X = -0.55


def _make_elector(tau=2.0):
    parties = [Party(j, _PARTY_POS[j]) for j in range(len(_PARTY_POS))]
    e = Elector(0, _VOTER_X, len(_PARTY_POS), tau=tau)
    e.calcSincereUtilities(parties)
    return e, parties


def test_nearest_mode_reproduces_old_behaviour():
    """Default kwargs (nearest) must match an explicit sincere_init_mode call."""
    bundle = ed.load_year(2002)
    voters = ed.sample_voters(2002, 300, np.random.default_rng(2))
    common = dict(
        K=bundle["K"], party_ids=bundle["parties"],
        party_positions_override=bundle["positions"],
        voter_positions_override=voters,
        exogenous_signals=bundle["signals"],
        tau=1.5, mu=0.3, alpha_prior=0.2, rho_pi=60.0,
        n_electors=len(voters), max_iterations=len(bundle["signals"]),
        seed=9, verbose=False,
    )
    a = run_simulation(**common)
    b = run_simulation(sincere_init_mode="nearest", beta=7.0,
                       salience_source="prior", **common)
    assert a["final_shares"] == b["final_shares"]
    assert a["sincere_shares"] == b["sincere_shares"]


def test_prob_probs_sum_to_one_within_contenders():
    e, _ = _make_elector(tau=1.2)
    salience = np.array([0.1, 0.3, 0.2, 0.3, 0.1])
    C, probs = e.initialAttachmentProbs(_PARTY_POS, salience, beta=4.0)
    assert set(C) == set(e.contenders)
    assert probs.sum() == pytest.approx(1.0, abs=1e-12)
    assert np.all(probs >= 0)


def test_beta_zero_depends_only_on_salience():
    """beta=0 => P_a(j) proportional to salience restricted to Ca."""
    e, _ = _make_elector(tau=3.0)  # all parties are contenders
    salience = np.array([0.05, 0.4, 0.25, 0.2, 0.1])
    C, probs = e.initialAttachmentProbs(_PARTY_POS, salience, beta=0.0)
    expected = salience[C] / salience[C].sum()
    assert np.allclose(probs, expected)


def test_large_beta_approaches_nearest_within_contenders():
    """As beta grows, mass collapses onto the nearest contender."""
    e, _ = _make_elector(tau=3.0)
    salience = np.ones(len(_PARTY_POS))  # flat salience isolates the beta effect
    C, probs = e.initialAttachmentProbs(_PARTY_POS, salience, beta=500.0)
    nearest_in_C = C[int(np.argmax(probs))]
    assert nearest_in_C == e.nearestChoice
    assert probs.max() == pytest.approx(1.0, abs=1e-6)


def test_salience_source_signal_uses_s0():
    """salience_source='signal' must use s^0, not the priors."""
    bundle = ed.load_year(2002)
    voters = ed.sample_voters(2002, 400, np.random.default_rng(3))
    common = dict(
        K=bundle["K"], party_ids=bundle["parties"],
        party_positions_override=bundle["positions"],
        voter_positions_override=voters,
        exogenous_signals=bundle["signals"],
        tau=1.5, mu=0.0, alpha_prior=0.0, rho_pi=50.0,
        sincere_init_mode="probabilistic", beta=3.0,
        n_electors=len(voters), max_iterations=len(bundle["signals"]),
        seed=21, verbose=False,
    )
    # signal vs prior salience generally give different initial shares.
    sig = run_simulation(salience_source="signal", **common)["sincere_shares"]
    pri = run_simulation(salience_source="prior", **common)["sincere_shares"]
    assert sig != pri


def test_prob_init_reproducible_with_seed():
    bundle = ed.load_year(2022)
    voters = ed.sample_voters(2022, 350, np.random.default_rng(8))
    kwargs = dict(
        K=bundle["K"], party_ids=bundle["parties"],
        party_positions_override=bundle["positions"],
        voter_positions_override=voters,
        exogenous_signals=bundle["signals"],
        tau=1.4, mu=0.2, alpha_prior=0.1, rho_pi=70.0,
        sincere_init_mode="probabilistic", beta=6.0,
        salience_source="signal",
        n_electors=len(voters), max_iterations=len(bundle["signals"]),
        seed=33, verbose=False,
    )
    a = run_simulation(**kwargs)
    b = run_simulation(**kwargs)
    assert a["sincere_shares"] == b["sincere_shares"]
    assert a["final_shares"] == b["final_shares"]


def test_invalid_init_options_raise():
    with pytest.raises(ValueError):
        run_simulation(K=5, sincere_init_mode="bogus", verbose=False,
                       max_iterations=2, n_electors=50, seed=1)
    with pytest.raises(ValueError):
        run_simulation(K=5, salience_source="bogus", verbose=False,
                       max_iterations=2, n_electors=50, seed=1)
