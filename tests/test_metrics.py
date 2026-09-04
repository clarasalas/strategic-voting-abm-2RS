"""
test_metrics.py
---------------
Unit tests for the coordination metrics every result in this project is stated
in: ENP, CENP, ΔCENP and the cliff statistics.

Fixtures are small and hand-calculable, so each expected value below can be
checked by eye against the definitions:

    ENP(δ)  = 1 / Σ_j δ_j²
    CENP(δ) = (K − ENP(δ)) / (K − 1)          0 under uniform, 1 under full
                                              concentration
    cliff   : sort δ descending, take consecutive drops;
              k* = index of the largest drop + 1
              d* = size of that drop
              r' = d* / (d* + mean of the remaining drops)

The formulas live in two places, core_model/metrics.py and the nested helpers
inside functions.coordination_measures, so the last test class pins that the
two agree.

Run with:  pytest tests/test_metrics.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))

import functions
from metrics import cenp, delta_cenp, enp

# Uniform over 4 parties: the ENP = K, CENP = 0 corner.
UNIFORM_4 = [0.25, 0.25, 0.25, 0.25]

# All mass on one party: the ENP = 1, CENP = 1 corner.
CONCENTRATED_4 = [1.0, 0.0, 0.0, 0.0]

# Hand-calculable cliff fixture.  Sorted descending the drops are
# [0.05, 0.20, 0.05], so the largest drop is the second one:
#     k* = 2, d* = 0.20, r' = 0.20 / (0.20 + 0.05) = 0.80
CLIFF_4 = [0.40, 0.35, 0.15, 0.10]


# --------------------------------------------------------------------------- #
#  ENP and CENP at the two corners                                             #
# --------------------------------------------------------------------------- #

def test_enp_uniform_equals_K():
    """Uniform shares over K parties give ENP = K exactly."""
    assert enp(UNIFORM_4) == pytest.approx(4.0, abs=1e-12)


def test_cenp_uniform_is_zero():
    """CENP is 0 under a uniform distribution, by construction."""
    assert cenp(UNIFORM_4, 4) == pytest.approx(0.0, abs=1e-12)


def test_enp_concentrated_is_one():
    """All mass on one party gives ENP = 1."""
    assert enp(CONCENTRATED_4) == pytest.approx(1.0, abs=1e-12)


def test_cenp_concentrated_is_one():
    """CENP is 1 under full concentration, the other end of the [0, 1] scale."""
    assert cenp(CONCENTRATED_4, 4) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("K", (2, 4, 8, 12, 15))
def test_enp_uniform_equals_K_for_any_K(K):
    assert enp([1.0 / K] * K) == pytest.approx(float(K), abs=1e-12)
    assert cenp([1.0 / K] * K, K) == pytest.approx(0.0, abs=1e-12)


# --------------------------------------------------------------------------- #
#  Normalisation invariance                                                    #
# --------------------------------------------------------------------------- #

def test_enp_is_normalisation_invariant():
    """Counts and shares of the same distribution must give the same ENP."""
    counts = [50, 25, 25, 0]
    shares = [0.50, 0.25, 0.25, 0.0]
    assert enp(counts) == pytest.approx(enp(shares), abs=1e-12)


def test_cenp_is_normalisation_invariant():
    counts = [50, 25, 25, 0]
    shares = [0.50, 0.25, 0.25, 0.0]
    assert cenp(counts, 4) == pytest.approx(cenp(shares, 4), abs=1e-12)


def test_normalisation_invariance_holds_for_arbitrary_scale():
    """Scaling every entry by the same factor cannot change ENP."""
    base = np.array([0.4, 0.3, 0.2, 0.1])
    for factor in (2.0, 17.5, 1000.0):
        assert enp(base * factor) == pytest.approx(enp(base), abs=1e-12)


# --------------------------------------------------------------------------- #
#  Delta CENP                                                                  #
# --------------------------------------------------------------------------- #

def test_delta_cenp_is_difference_of_cenps():
    """delta_cenp(poll, result) is defined as CENP(result) − CENP(poll)."""
    poll = [0.30, 0.30, 0.25, 0.15]
    result = [0.45, 0.30, 0.15, 0.10]
    K = len(poll)
    assert delta_cenp(poll, result) == pytest.approx(
        cenp(result, K) - cenp(poll, K), abs=1e-12)


def test_delta_cenp_positive_when_concentrating():
    """Uniform -> more concentrated is a coordination GAIN, so ΔCENP > 0."""
    assert delta_cenp(UNIFORM_4, CLIFF_4) > 0.0


def test_delta_cenp_negative_when_fragmenting():
    """The reverse move must flip the sign: concentrated -> uniform is a loss."""
    assert delta_cenp(CLIFF_4, UNIFORM_4) < 0.0


def test_delta_cenp_is_zero_for_identical_distributions():
    assert delta_cenp(CLIFF_4, CLIFF_4) == pytest.approx(0.0, abs=1e-12)


def test_delta_cenp_is_antisymmetric():
    """Swapping poll and result negates the gain."""
    a, b = UNIFORM_4, CLIFF_4
    assert delta_cenp(a, b) == pytest.approx(-delta_cenp(b, a), abs=1e-12)


# --------------------------------------------------------------------------- #
#  Cliff statistics, through coordination_measures                             #
# --------------------------------------------------------------------------- #

def test_cliff_location_is_two():
    """The largest drop in [0.40, 0.35, 0.15, 0.10] sits after the 2nd party."""
    cm = functions.coordination_measures(UNIFORM_4, CLIFF_4)
    assert cm["k_star_final"] == 2


def test_cliff_magnitude_is_the_largest_drop():
    """d* = 0.35 − 0.15 = 0.20, larger than either 0.05 drop."""
    cm = functions.coordination_measures(UNIFORM_4, CLIFF_4)
    assert cm["d_star_final"] == pytest.approx(0.20, abs=1e-12)


def test_cliff_ratio_is_bounded_share_of_the_drop():
    """r' = d* / (d* + mean of the other drops) = 0.20 / (0.20 + 0.05) = 0.80."""
    cm = functions.coordination_measures(UNIFORM_4, CLIFF_4)
    assert cm["r_prime_final"] == pytest.approx(0.80, abs=1e-12)


def test_uniform_has_no_cliff():
    """
    With every drop equal to zero the cliff is degenerate: the implementation
    reports k* = 1, d* = 0 and falls back to r' = 0.5 rather than dividing by
    zero.
    """
    cm = functions.coordination_measures(CLIFF_4, UNIFORM_4)
    assert cm["k_star_final"] == 1
    assert cm["d_star_final"] == pytest.approx(0.0, abs=1e-12)
    assert cm["r_prime_final"] == pytest.approx(0.5, abs=1e-12)


def test_cliff_deltas_are_final_minus_sincere():
    """
    Going from uniform (d* = 0, r' = 0.5) to the cliff fixture (0.20, 0.80)
    gives deltas of exactly +0.20 and +0.30.
    """
    cm = functions.coordination_measures(UNIFORM_4, CLIFF_4)
    assert cm["delta_d_star"] == pytest.approx(0.20, abs=1e-12)
    assert cm["delta_r_prime"] == pytest.approx(0.30, abs=1e-12)


def test_cliff_is_invariant_to_input_order():
    """Cliff statistics sort internally, so input order must not matter."""
    shuffled = [0.10, 0.40, 0.15, 0.35]
    a = functions.coordination_measures(UNIFORM_4, CLIFF_4)
    b = functions.coordination_measures(UNIFORM_4, shuffled)
    for key in ("k_star_final", "d_star_final", "r_prime_final"):
        assert a[key] == pytest.approx(b[key], abs=1e-12)


# --------------------------------------------------------------------------- #
#  The two implementations must agree                                          #
# --------------------------------------------------------------------------- #

_AGREEMENT_CASES = [
    UNIFORM_4,
    CONCENTRATED_4,
    CLIFF_4,
    [0.30, 0.30, 0.25, 0.15],
    [0.5, 0.25, 0.25, 0.0],
    [0.2] * 5,
    [0.6, 0.1, 0.1, 0.1, 0.05, 0.05],
]


@pytest.mark.parametrize("shares", _AGREEMENT_CASES)
def test_metrics_enp_agrees_with_coordination_measures(shares):
    """
    ENP is implemented twice: metrics.enp, and the nested _enp inside
    functions.coordination_measures.  They must not drift apart.
    """
    cm = functions.coordination_measures(shares, shares)
    assert cm["enp_final"] == pytest.approx(enp(shares), abs=1e-12)
    assert cm["enp_sincere"] == pytest.approx(enp(shares), abs=1e-12)


@pytest.mark.parametrize("shares", _AGREEMENT_CASES)
def test_metrics_cenp_agrees_with_coordination_measures(shares):
    """Same for CENP, which coordination_measures derives with K = len(final)."""
    K = len(shares)
    cm = functions.coordination_measures(shares, shares)
    assert cm["cenp_final"] == pytest.approx(cenp(shares, K), abs=1e-12)


def test_delta_cenp_agrees_across_implementations():
    """
    functions.coordination_measures measures the gain against the SINCERE
    shares; metrics.delta_cenp measures it against whatever baseline it is
    given.  Handed the same pair, they must produce the same number.
    """
    sincere = [0.30, 0.30, 0.25, 0.15]
    final = CLIFF_4
    cm = functions.coordination_measures(sincere, final)
    assert cm["delta_cenp"] == pytest.approx(
        delta_cenp(sincere, final), abs=1e-12)
