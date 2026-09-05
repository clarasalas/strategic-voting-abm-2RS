"""
test_signals.py
---------------
Unit tests for the poll-signal machinery: the deterministic temperature
transform, the ranking helper, and the invariants of a generated signal.

    s̃_i = (δ_i + ε)^(1/θ) / Σ_j (δ_j + ε)^(1/θ)       transform_signal
    s   ~ Dirichlet(ρ · s̃)                             generate_signal

θ is the only parameter with a directional claim attached to it in the paper,
so the sharpening / flattening tests below are the ones that matter:

    θ < 1  sharpens  -> the leader gains, the tail loses
    θ = 1  faithful  -> the distribution is returned unchanged
    θ > 1  flattens  -> the leader loses, the tail gains

Everything here is deterministic or fixed-seed: no test depends on an average
over random draws.

Run with:  pytest tests/test_signals.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core_model.signals import generate_signal, rank_signal, transform_signal

# A non-uniform distribution with a distinct leader and a distinct tail, so
# "largest" and "smallest" are unambiguous.
SKEWED = np.array([0.50, 0.30, 0.15, 0.05])

# eps = 1e-12 is added before exponentiation, so theta = 1 is faithful only up
# to that floor.  1e-9 is far tighter than the floor and far looser than noise.
EPS_TOL = 1e-9


# --------------------------------------------------------------------------- #
#  transform_signal: the theta direction                                       #
# --------------------------------------------------------------------------- #

def test_theta_one_leaves_distribution_unchanged():
    """θ = 1 is the faithful signal: s̃ = δ, up to the 1e-12 epsilon floor."""
    out = transform_signal(SKEWED, theta=1.0)
    assert out == pytest.approx(SKEWED, abs=EPS_TOL)


@pytest.mark.parametrize("theta", (0.3, 0.5, 0.7, 0.9))
def test_theta_below_one_sharpens(theta):
    """θ < 1 amplifies viability gaps: the leader gains, the tail loses."""
    out = transform_signal(SKEWED, theta=theta)
    assert out[0] > SKEWED[0]          # leader gains
    assert out[-1] < SKEWED[-1]        # tail loses


@pytest.mark.parametrize("theta", (1.1, 1.5, 2.0, 3.0))
def test_theta_above_one_flattens(theta):
    """θ > 1 compresses viability gaps: the leader loses, the tail gains."""
    out = transform_signal(SKEWED, theta=theta)
    assert out[0] < SKEWED[0]          # leader loses
    assert out[-1] > SKEWED[-1]        # tail gains


def test_sharpening_is_monotone_in_theta():
    """
    Smaller θ means more sharpening, so the leader's transformed share must
    decrease monotonically as θ increases.
    """
    leaders = [transform_signal(SKEWED, theta=t)[0]
               for t in (0.3, 0.5, 1.0, 2.0, 3.0)]
    assert all(a > b for a, b in zip(leaders, leaders[1:]))


def test_transform_preserves_ordering():
    """No θ may reorder the parties: the transform is monotone in δ."""
    for theta in (0.3, 0.5, 1.0, 2.0, 3.0):
        out = transform_signal(SKEWED, theta=theta)
        assert np.all(np.diff(out) < 0)     # SKEWED is strictly decreasing


# --------------------------------------------------------------------------- #
#  transform_signal: uniform is a fixed point                                  #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("theta", (0.3, 0.5, 1.0, 2.0, 3.0))
def test_uniform_stays_uniform(theta):
    """
    A uniform distribution has no viability gaps to amplify or compress, so it
    is a fixed point of the transform for every θ.
    """
    K = 5
    uniform = np.full(K, 1.0 / K)
    out = transform_signal(uniform, theta=theta)
    assert out == pytest.approx(uniform, abs=1e-12)


# --------------------------------------------------------------------------- #
#  transform_signal: output is always a valid distribution                     #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("theta", (0.3, 0.5, 1.0, 2.0, 3.0))
@pytest.mark.parametrize("support", [
    [0.50, 0.30, 0.15, 0.05],
    [0.25, 0.25, 0.25, 0.25],
    [1.0, 0.0, 0.0, 0.0],            # zeros: the epsilon floor must hold
    [0.9, 0.05, 0.05],
    [10.0, 5.0, 5.0],                # unnormalised input
])
def test_transform_returns_valid_distribution(theta, support):
    out = transform_signal(support, theta=theta)
    assert np.all(out >= 0.0)
    assert out.sum() == pytest.approx(1.0, abs=1e-12)
    assert len(out) == len(support)


def test_transform_normalises_unnormalised_input():
    """Input need not sum to 1; the transform normalises internally."""
    a = transform_signal([0.50, 0.30, 0.15, 0.05], theta=0.7)
    b = transform_signal([50.0, 30.0, 15.0, 5.0], theta=0.7)
    assert a == pytest.approx(b, abs=1e-12)


# --------------------------------------------------------------------------- #
#  rank_signal                                                                 #
# --------------------------------------------------------------------------- #

def test_rank_signal_orders_strongest_first():
    """[0.2, 0.5, 0.3] ranks as party 1, then 2, then 0."""
    assert list(rank_signal([0.2, 0.5, 0.3])) == [1, 2, 0]


def test_rank_signal_on_already_sorted_input():
    assert list(rank_signal([0.5, 0.3, 0.2])) == [0, 1, 2]


def test_rank_signal_is_a_permutation():
    signal = [0.11, 0.42, 0.07, 0.30, 0.10]
    assert sorted(rank_signal(signal)) == list(range(len(signal)))


# --------------------------------------------------------------------------- #
#  generate_signal: reproducibility and invariants                             #
# --------------------------------------------------------------------------- #

def test_generate_signal_is_reproducible_with_a_fixed_seed():
    a = generate_signal(SKEWED, theta=1.0, rho=100.0,
                        rng=np.random.default_rng(12345))
    b = generate_signal(SKEWED, theta=1.0, rho=100.0,
                        rng=np.random.default_rng(12345))
    assert np.array_equal(a, b)


def test_generate_signal_differs_across_seeds():
    """The signal is genuinely stochastic: a different stream gives a different draw."""
    a = generate_signal(SKEWED, rng=np.random.default_rng(1))
    b = generate_signal(SKEWED, rng=np.random.default_rng(2))
    assert not np.array_equal(a, b)


@pytest.mark.parametrize("theta", (0.5, 1.0, 2.0))
@pytest.mark.parametrize("rho", (10.0, 100.0, 200.0))
def test_generate_signal_returns_valid_distribution(theta, rho):
    out = generate_signal(SKEWED, theta=theta, rho=rho,
                          rng=np.random.default_rng(7))
    assert np.all(out >= 0.0)
    assert out.sum() == pytest.approx(1.0, abs=1e-12)
    assert len(out) == len(SKEWED)


def test_generate_signal_handles_zero_support_entries():
    """A party with no support must not produce a NaN under any theta."""
    out = generate_signal([0.7, 0.3, 0.0], theta=0.5,
                          rng=np.random.default_rng(3))
    assert np.all(np.isfinite(out))
    assert out.sum() == pytest.approx(1.0, abs=1e-12)
