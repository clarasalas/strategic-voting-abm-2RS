"""
test_tau_units.py
-----------------
The tolerance threshold exists in two units, and mixing them up is silent:

    tau_hat   normalised, in zone lengths  -- what every design/sweep draws
    tau       absolute, on [-1, 1]         -- what run_simulation expects

These tests pin the conversion and, more importantly, pin the fact that the
empirical runners actually apply it.  Before this was fixed, both empirical
runners passed tau_hat straight through, so a swept tau_hat of 3.0 became an
absolute tau of 3.0 -- past the tau >= 2 threshold at which every party is a
contender for every voter and the Ca/Oa distinction is disabled.

Run with:  pytest tests/test_tau_units.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(REPO / "analysis" / "empirical"))

import empirical_data as ed
from metrics import tau_absolute, zone_length

# The swept range, mirrored from both empirical runners.
TAU_HAT_RANGE = (0.5, 3.0)

# The threshold at which model.py warns that Ca == every party.
DEGENERATE_TAU = 2.0

# The largest absolute tau each year's design can produce: tau_hat_max * (2/K)
# at K = 15 and K = 12.  Year-specific, because K is.
MAX_ABSOLUTE_TAU = {2002: 0.4, 2022: 0.5}


# --------------------------------------------------------------------------- #
#  The conversion itself                                                       #
# --------------------------------------------------------------------------- #

def test_conversion_2002_top_of_range():
    """tau_hat = 3 with the 2002 candidate set (K = 15) is tau = 0.4."""
    assert tau_absolute(3.0, 15) == pytest.approx(0.4, abs=1e-12)


def test_conversion_2022_top_of_range():
    """tau_hat = 3 with the 2022 candidate set (K = 12) is tau = 0.5."""
    assert tau_absolute(3.0, 12) == pytest.approx(0.5, abs=1e-12)


def test_conversion_is_zone_length_scaling():
    assert zone_length(15) == pytest.approx(2.0 / 15, abs=1e-12)
    for K in (6, 8, 9, 12, 15):
        assert tau_absolute(1.0, K) == pytest.approx(zone_length(K), abs=1e-12)


# --------------------------------------------------------------------------- #
#  No swept draw can reach the degenerate regime                               #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year", (2002, 2022))
def test_no_empirical_sweep_draw_reaches_degenerate_tau(year):
    """
    Across the whole swept tau_hat range, the converted tau must stay below the
    tau >= 2 threshold for both real candidate sets.  The binding case is the
    top of the range on the smaller candidate set.
    """
    K = ed.load_year(year)["K"]
    lo, hi = TAU_HAT_RANGE
    grid = np.linspace(lo, hi, 501)
    tau_values = np.array([tau_absolute(t, K) for t in grid])

    assert tau_values.max() < DEGENERATE_TAU
    # And by a wide margin.  The ceiling is year-specific, because K is:
    # tau_hat_max * (2 / K) is 0.4 for 2002 and 0.5 for 2022.  A single shared
    # "< 0.5" bound would pass for 2002 while being 25% too loose, so it would
    # not notice a 2002 design drifting upward.  The bound is inclusive:
    # tau_hat = 3.0 is the top of the swept range, so the ceiling is attained,
    # not approached.
    assert tau_values.max() <= MAX_ABSOLUTE_TAU[year] + 1e-12


# --------------------------------------------------------------------------- #
#  The runners actually apply it                                               #
# --------------------------------------------------------------------------- #

class _Captured(Exception):
    """Raised by the spy once it has recorded the kwargs it was called with."""

    def __init__(self, kwargs):
        self.kwargs = kwargs


def _spy(**kwargs):
    raise _Captured(kwargs)


def _capture_run_simulation_kwargs(monkeypatch, module, call):
    """Call ``call()`` with ``module.run_simulation`` replaced by a spy."""
    monkeypatch.setattr(module, "run_simulation", _spy)
    with pytest.raises(_Captured) as excinfo:
        call()
    return excinfo.value.kwargs


@pytest.mark.parametrize("year", (2002, 2022))
def test_empirical_runner_converts_tau(monkeypatch, year):
    """empirical_2002_2022.run_single must convert tau_hat, not forward it."""
    import empirical_2002_2022 as runner

    bundle = ed.load_year(year)
    voters = ed.sample_voters(year, 50, np.random.default_rng(0))
    tau_hat = 3.0
    params = {"tau_hat": tau_hat, "mu": 0.1, "alpha": 0.0,
              "rho_pi": 50.0, "beta": 0.0}

    kwargs = _capture_run_simulation_kwargs(
        monkeypatch, runner,
        lambda: runner.run_single(
            params, bundle["positions"], voters, bundle["signals"],
            bundle["results"], bundle["parties"], seed=0),
    )

    K = bundle["K"]
    assert kwargs["K"] == K
    assert kwargs["tau"] == pytest.approx(tau_absolute(tau_hat, K), abs=1e-12)
    assert kwargs["tau"] != pytest.approx(tau_hat, abs=1e-12)
    assert kwargs["tau"] < DEGENERATE_TAU


@pytest.mark.parametrize("year", (2002, 2022))
def test_behavioral_sweep_converts_tau(monkeypatch, year):
    """behavioral_sweep.run_one must convert tau_hat, not forward it."""
    import behavioral_sweep as sweep

    bundle = ed.load_year(year, signal_mode="weekly")
    voters = ed.sample_voters(year, 50, np.random.default_rng(0))
    tau_hat = 3.0
    params = {"tau_hat": tau_hat, "mu": 0.1, "alpha": 0.0,
              "rho_pi": 50.0, "beta": 5.0}

    kwargs = _capture_run_simulation_kwargs(
        monkeypatch, sweep,
        lambda: sweep.run_one(params, bundle, voters, seed=0),
    )

    K = bundle["K"]
    assert kwargs["tau"] == pytest.approx(tau_absolute(tau_hat, K), abs=1e-12)
    assert kwargs["tau"] != pytest.approx(tau_hat, abs=1e-12)
    assert kwargs["tau"] < DEGENERATE_TAU


def test_shared_tau_hat_differs_by_year_in_absolute_units():
    """
    The point of the conversion: one shared behavioural draw is a different
    absolute distance in each year, because the candidate sets differ.
    """
    K_2002 = ed.load_year(2002)["K"]
    K_2022 = ed.load_year(2022)["K"]
    assert K_2002 != K_2022

    tau_hat = 1.75
    assert tau_absolute(tau_hat, K_2002) != pytest.approx(
        tau_absolute(tau_hat, K_2022), abs=1e-12)
