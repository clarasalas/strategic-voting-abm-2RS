"""
test_diagnostics_are_observational.py
-------------------------------------
collect_diagnostics must observe the run without changing it.

The flag exists so that a caller can read the trajectory: per-iteration trigger
rates, the projected runoff set, and the poll signal at each step. Everything
it records is a value the run already computed. Nothing it does may feed back
into the run.

Two things could break that quietly. A diagnostic could draw from signal_rng,
which would shift every later draw and change the result for a given seed. Or a
recorded array could be stored by reference rather than copied, so that a
caller reading diagnostics sees a later state than the one at that iteration,
which is a silent corruption of the record rather than of the run.

The check is exact equality, not closeness. The two runs use the same seed and
must execute the same arithmetic in the same order, so any difference at all is
a defect.

This matters beyond tidiness: anything built on the recorded trajectory --
the demo under demo/, any figure of the signal path -- is only showing the
model if the recording is free.

Run with:  pytest tests/test_diagnostics_are_observational.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core_model.model import run_simulation
from core_model.metrics import tau_absolute
from core_model import empirical_data as ed

SEED = 20260905

# Synthetic configs spanning a run that triggers heavily and one that barely
# does, since the diagnostics block sits inside the branch that depends on
# whether voters are triggered at all.
CONFIGS = [
    pytest.param({"K": 6, "width_factor": 0.5, "mu": 0.1}, id="narrow-K6"),
    pytest.param({"K": 8, "width_factor": 2.5, "mu": 0.4}, id="wide-K8"),
    pytest.param({"K": 9, "width_factor": 1.25, "mu": 0.0}, id="mid-K9"),
]

# Everything run_simulation returns except the diagnostics themselves, which
# are absent when the flag is off and so cannot be compared.
COMPARED = [
    "final_counts", "final_shares", "history", "intention_history",
    "iterations", "party_positions", "pi_priors", "signal", "sincere_counts",
    "sincere_shares", "sw_history", "switching", "voter_dist", "winner_id",
]


def _assert_identical(off, on):
    """Every non-diagnostic output must be exactly equal."""
    assert set(off) | {"diagnostics", "mu_calibration"} >= set(COMPARED)
    for key in COMPARED:
        a, b = off[key], on[key]
        if isinstance(a, np.ndarray) or isinstance(a, list):
            assert np.array_equal(np.asarray(a, dtype=object).tolist(),
                                  np.asarray(b, dtype=object).tolist()), (
                f"{key} differs with collect_diagnostics on")
        else:
            assert a == b, f"{key} differs with collect_diagnostics on"


@pytest.mark.parametrize("cfg", CONFIGS)
def test_synthetic_run_is_identical_with_and_without_diagnostics(cfg):
    kwargs = dict(
        K=cfg["K"], n_electors=150, width_factor=cfg["width_factor"],
        mu=cfg["mu"], tau=tau_absolute(1.5, cfg["K"]), max_iterations=12,
        seed=SEED, verbose=False,
    )
    off = run_simulation(**kwargs, collect_diagnostics=False)
    on = run_simulation(**kwargs, collect_diagnostics=True)
    _assert_identical(off, on)


@pytest.mark.parametrize("year", [2002, 2022])
def test_empirical_run_is_identical_with_and_without_diagnostics(year):
    """Exogenous signals take a different branch through the loop."""
    env = ed.load_year(year)
    rng = np.random.default_rng(SEED)
    K = env["K"]
    kwargs = dict(
        K=K,
        party_ids=env["parties"],
        party_positions_override=env["positions"],
        voter_positions_override=ed.sample_voters(year, 300, rng),
        exogenous_signals=env["signals"],
        tau=tau_absolute(1.5, K), mu=0.3, alpha_prior=0.3, rho_pi=50.0,
        n_electors=300, max_iterations=10, seed=SEED, verbose=False,
    )
    off = run_simulation(**kwargs, collect_diagnostics=False)
    on = run_simulation(**kwargs, collect_diagnostics=True)
    _assert_identical(off, on)


def test_diagnostics_absent_when_flag_is_off():
    """The flag defaults to off, and off means nothing is recorded."""
    r = run_simulation(K=8, n_electors=100, tau=tau_absolute(1.5, 8),
                       max_iterations=5, seed=SEED, verbose=False)
    assert r["diagnostics"] is None or r["diagnostics"] == {}


def test_recorded_signal_is_a_copy_not_a_reference():
    """
    Each iteration's recorded signal must be the signal AT that iteration.

    Storing the live array by reference would make every record show the final
    signal, which reads as a converged run no matter what actually happened.
    """
    r = run_simulation(K=8, n_electors=200, width_factor=2.0,
                       tau=tau_absolute(1.5, 8), mu=0.2, max_iterations=15,
                       seed=SEED, verbose=False, collect_diagnostics=True)
    signals = [rec["signal"] for rec in r["diagnostics"]["iterations"]]
    assert len(signals) == 15
    assert not all(np.array_equal(signals[0], s) for s in signals), (
        "every recorded signal is identical; they are likely the same array")
    assert np.array_equal(signals[-1], r["signal"])
