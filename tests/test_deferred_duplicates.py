"""
test_deferred_duplicates.py
---------------------------
Pins for the duplicated definitions that docs/analysis_map.md defers until
after the corrected empirical reruns.

The consolidations are deliberately NOT done here. The point of these tests is
to make the duplicates safe to leave in place: if two copies of the same
definition drift apart while they are waiting, that is caught now rather than
discovered afterwards in a result nobody can explain.

Deliberately absent: any assertion that the two delta_cenp definitions agree.
functions.coordination_measures measures the gain against the model's own
iteration-0 sincere shares; metrics.delta_cenp measures it against whatever
baseline it is handed, and the behavioural sweep hands it the exogenous opening
poll s0. They are different scientific quantities that happen to share a name,
and asserting they are equal would be asserting something false and destroying
the comparison behavioral_targets depends on. See docs/analysis_map.md C1.

(tests/test_metrics.py::test_delta_cenp_agrees_across_implementations is a
different check and is fine: it hands the SAME pair to both and asserts the
arithmetic matches. It says nothing about the baselines.)

Run with:  pytest tests/test_deferred_duplicates.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(REPO / "analysis" / "empirical"))

import functions
from metrics import enp, cenp

TOL = 1e-12


# --------------------------------------------------------------------------- #
#  A2 -- ENP and CENP exist twice                                              #
# --------------------------------------------------------------------------- #
#
#   core_model/metrics.py            enp / cenp
#   functions.coordination_measures  nested _enp / _cenp
#
# Same formulae, different edge handling: metrics normalises internally, the
# nested pair expects an already-normalised input and returns nan on a
# zero-sum vector.  On well-formed input they must agree exactly.

ANALYTIC_CASES = [
    pytest.param([0.25] * 4, 4.0, 0.0, id="uniform-K4"),
    pytest.param([0.2] * 5, 5.0, 0.0, id="uniform-K5"),
    pytest.param([1.0, 0.0, 0.0, 0.0], 1.0, 1.0, id="concentrated-K4"),
    pytest.param([0.5, 0.5], 2.0, 0.0, id="even-split-K2"),
    # 1 / (0.5^2 + 0.25^2 + 0.25^2) = 1 / 0.375 = 8/3
    pytest.param([0.5, 0.25, 0.25], 8.0 / 3.0, (3 - 8 / 3) / 2, id="half-quarter"),
    # A zero-weight candidate must not change either quantity.
    pytest.param([0.5, 0.25, 0.25, 0.0], 8.0 / 3.0, (4 - 8 / 3) / 3, id="with-zero"),
]


@pytest.mark.parametrize("shares,expected_enp,expected_cenp", ANALYTIC_CASES)
def test_analytic_enp_and_cenp_match_both_implementations(
        shares, expected_enp, expected_cenp):
    """Closed-form value first, then both implementations against it."""
    K = len(shares)
    cm = functions.coordination_measures(shares, shares)

    assert enp(shares) == pytest.approx(expected_enp, abs=TOL)
    assert cm["enp_final"] == pytest.approx(expected_enp, abs=TOL)

    assert cenp(shares, K) == pytest.approx(expected_cenp, abs=TOL)
    assert cm["cenp_final"] == pytest.approx(expected_cenp, abs=TOL)


def _generated_shares():
    """Share vectors spanning concentrated to near-uniform, across K."""
    rng = np.random.default_rng(20020422)
    out = []
    for K in (2, 3, 4, 6, 8, 9, 12, 15):
        for conc in (0.15, 1.0, 8.0):
            v = rng.dirichlet(np.full(K, conc))
            out.append(pytest.param(v, id=f"K{K}-a{conc}"))
    return out


@pytest.mark.parametrize("shares", _generated_shares())
def test_generated_shares_agree_across_both_enp_implementations(shares):
    cm = functions.coordination_measures(shares, shares)
    assert cm["enp_final"] == pytest.approx(enp(shares), abs=TOL)
    assert cm["enp_sincere"] == pytest.approx(enp(shares), abs=TOL)


@pytest.mark.parametrize("shares", _generated_shares())
def test_generated_shares_agree_across_both_cenp_implementations(shares):
    K = len(shares)
    cm = functions.coordination_measures(shares, shares)
    assert cm["cenp_final"] == pytest.approx(cenp(shares, K), abs=TOL)
    assert cm["cenp_sincere"] == pytest.approx(cenp(shares, K), abs=TOL)


def test_both_implementations_agree_on_unnormalised_input():
    """
    metrics normalises internally; coordination_measures normalises its inputs
    before using the nested pair. Handed counts rather than shares, the two
    must still land on the same number.
    """
    counts = np.array([120.0, 60.0, 60.0, 20.0])
    cm = functions.coordination_measures(counts, counts)
    assert cm["enp_final"] == pytest.approx(enp(counts), abs=TOL)
    assert cm["cenp_final"] == pytest.approx(cenp(counts, len(counts)), abs=TOL)


# --------------------------------------------------------------------------- #
#  A1 -- the Latin-hypercube routine exists twice                              #
# --------------------------------------------------------------------------- #

def test_the_two_latin_hypercube_implementations_are_interchangeable():
    """
    Same generator state and same ranges must give the same design.

    This pins the FUNCTIONS as interchangeable, which is what makes the later
    consolidation safe. It says nothing about the two runners' parameter
    ORDERS, which differ on purpose and must not be unified: the routine draws
    one dimension at a time from a shared generator, so the order determines
    the design.
    """
    import behavioral_sweep as sweep
    import empirical_2002_2022 as replay

    ranges = [(0.5, 3.0), (0.0, 1.0), (0.0, 0.9), (5.0, 200.0), (0.0, 20.0)]
    a = sweep.latin_hypercube(24, ranges, np.random.default_rng(7))
    b = replay._latin_hypercube(24, ranges, np.random.default_rng(7))
    np.testing.assert_array_equal(a, b)


def test_the_two_runners_declare_different_parameter_orders():
    """
    Documenting the trap, so a future tidy-up meets a failing test rather than
    a silently different design.
    """
    import behavioral_sweep as sweep

    sweep_order = list(sweep.PARAM_COLS)
    # The replay builds its order inline in sample_parameter_design.
    replay_order = ["tau_hat", "rho_pi", "alpha", "mu", "beta"]

    assert sweep_order == ["tau_hat", "mu", "alpha", "rho_pi", "beta"]
    assert sweep_order != replay_order
    assert set(sweep_order) == set(replay_order)


# --------------------------------------------------------------------------- #
#  A3 -- the parameter ranges are declared twice                               #
# --------------------------------------------------------------------------- #

SHARED_RANGE_NAMES = ["TAU_RANGE", "MU_RANGE", "ALPHA_RANGE",
                      "RHO_PI_RANGE", "BETA_RANGE"]


@pytest.mark.parametrize("name", SHARED_RANGE_NAMES)
def test_shared_parameter_bounds_are_equal_in_both_runners(name):
    """
    Identical values in two modules today; the risk is drift, not error.

    Only the bounds are pinned. The order in which each runner declares and
    consumes them is deliberately free, and is checked separately above.
    """
    import behavioral_sweep as sweep
    import empirical_2002_2022 as replay

    a = getattr(sweep, name)
    b = getattr(replay, name)
    assert tuple(float(x) for x in a) == tuple(float(x) for x in b), \
        f"{name} has drifted apart: sweep={a} replay={b}"


def test_the_two_runners_sweep_the_same_named_parameters():
    import behavioral_sweep as sweep
    import empirical_2002_2022 as replay

    for name in SHARED_RANGE_NAMES:
        assert hasattr(sweep, name), f"behavioral_sweep lost {name}"
        assert hasattr(replay, name), f"empirical_2002_2022 lost {name}"


@pytest.mark.parametrize("name", SHARED_RANGE_NAMES)
def test_every_shared_bound_is_a_well_formed_interval(name):
    import behavioral_sweep as sweep

    lo, hi = getattr(sweep, name)
    assert lo < hi
    assert np.isfinite([lo, hi]).all()


def test_the_two_delta_cenp_baselines_are_documented_as_different():
    """
    Not an equivalence test -- the opposite.

    Both docstrings must keep saying what their baseline is, because the names
    do not distinguish them and the next reader has only the docstring.
    """
    import behavioral_sweep as sweep
    import metrics

    assert "s⁰" in sweep.__doc__ or "s0" in sweep.__doc__ or \
        "exogenous" in sweep.run_one.__doc__
    assert "poll" in metrics.delta_cenp.__doc__
