"""
test_signal_epsilon.py
----------------------
Regression tests for the signal offset eps_s.

eps_s is the numerical floor added before the temperature exponentiation:

    s~_i = (delta_i + eps_s)^(1/theta) / sum_j (delta_j + eps_s)^(1/theta)

It used to be unreachable: Panel C varied eps by rebinding an attribute on the
signals module, which the simulation never consulted, so all five of its eps
values produced bit-identical output.  eps_s is now a real parameter of
run_simulation, and these tests pin that the PUBLIC argument reaches every
synthetic signal-generation call.

Spies patch ``model.generate_signal``, the binding run_simulation actually calls.

Run with:  pytest tests/test_signal_epsilon.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis" / "synthetic"))

from core_model import model
from core_model.model import run_simulation
from core_model.signals import generate_signal, transform_signal

# Small synthetic run: enough iterations that the iterative signal call fires.
BASE_KWARGS = dict(
    K=6, n_modes=1, width_factor=1.5, mode_position=0.0, floor_weight=0.1,
    theta=0.5, rho=100.0, rho_pi=100.0, n_electors=150,
    tau=1.0 * (2.0 / 6), mu=0.0, alpha_prior=0.0,
    K_runoff=2, max_iterations=4, seed=0, verbose=False,
)


class _Spy:
    """Records the eps every generate_signal call receives, then delegates."""

    def __init__(self):
        self.eps_seen = []
        self._original = model.generate_signal

    def __call__(self, true_support, theta=1.0, rho=100.0, eps=1e-12, rng=None):
        self.eps_seen.append(eps)
        return self._original(true_support, theta=theta, rho=rho,
                              eps=eps, rng=rng)


@pytest.fixture
def spy(monkeypatch):
    s = _Spy()
    monkeypatch.setattr(model, "generate_signal", s)
    return s


# --------------------------------------------------------------------------- #
#  The parameter reaches every call                                            #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("eps", [0.0, 1e-12, 1e-6, 1e-4, 1e-2, 0.1])
def test_signal_epsilon_is_passed_to_every_call(spy, eps):
    run_simulation(signal_epsilon=eps, **BASE_KWARGS)
    assert spy.eps_seen, "generate_signal was never called"
    assert set(spy.eps_seen) == {eps}


def test_both_the_initial_and_the_iterative_call_receive_it(spy):
    """
    run_simulation generates the opening signal once and then a fresh signal on
    each later iteration.  Both paths must carry eps_s, not just the first.
    """
    run_simulation(signal_epsilon=1e-3, **BASE_KWARGS)
    assert len(spy.eps_seen) >= 2, (
        f"expected an initial call plus iterative ones, saw {len(spy.eps_seen)}")
    assert spy.eps_seen[0] == 1e-3       # initial
    assert spy.eps_seen[-1] == 1e-3      # last iterative


def test_number_of_calls_tracks_the_iteration_count(spy):
    run_simulation(**{**BASE_KWARGS, "max_iterations": 6},
                   signal_epsilon=1e-9)
    assert len(spy.eps_seen) == 6
    assert set(spy.eps_seen) == {1e-9}


def test_default_is_1e_12(spy):
    """The historical value.  Changing it changes every result in the repo."""
    import inspect

    assert (inspect.signature(run_simulation)
            .parameters["signal_epsilon"].default == 1e-12)
    run_simulation(**BASE_KWARGS)
    assert set(spy.eps_seen) == {1e-12}


# --------------------------------------------------------------------------- #
#  Validation                                                                  #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("bad", [-1e-9, -1.0, float("nan"),
                                 float("inf"), float("-inf")])
def test_invalid_signal_epsilon_raises(bad):
    with pytest.raises(ValueError, match="signal_epsilon"):
        run_simulation(signal_epsilon=bad, **BASE_KWARGS)


def test_zero_is_accepted():
    """Zero is a legitimate floor: it just removes the floor."""
    res = run_simulation(signal_epsilon=0.0, **BASE_KWARGS)
    assert np.isclose(sum(res["final_shares"]), 1.0)


# --------------------------------------------------------------------------- #
#  It actually changes the signal                                              #
# --------------------------------------------------------------------------- #

def test_large_epsilon_changes_the_transformed_signal():
    """
    Controlled fixture: a distribution with a zero entry, theta < 1.  A floor of
    0.1 is comparable to the shares themselves and must visibly flatten the
    transform; 1e-12 must leave it alone.
    """
    support = np.array([0.6, 0.3, 0.1, 0.0])
    tiny = transform_signal(support, theta=0.5, eps=1e-12)
    large = transform_signal(support, theta=0.5, eps=0.1)

    assert not np.allclose(tiny, large)
    assert tiny[0] > large[0]        # the leader loses its exaggerated lead
    assert large[-1] > tiny[-1]      # the zero-support party gains mass


def test_large_epsilon_changes_the_generated_signal():
    a = generate_signal(np.array([0.6, 0.3, 0.1, 0.0]), theta=0.5, rho=200.0,
                        eps=1e-12, rng=np.random.default_rng(0))
    b = generate_signal(np.array([0.6, 0.3, 0.1, 0.0]), theta=0.5, rho=200.0,
                        eps=0.1, rng=np.random.default_rng(0))
    assert not np.allclose(a, b)


def test_large_epsilon_changes_the_run_signal():
    """End to end: the same difference survives through run_simulation."""
    a = run_simulation(signal_epsilon=1e-12, **BASE_KWARGS)
    b = run_simulation(signal_epsilon=0.1, **BASE_KWARGS)
    assert not np.allclose(a["signal"], b["signal"]), (
        "eps_s did not change the signal, so the parameter is not reaching "
        "generate_signal")


# --------------------------------------------------------------------------- #
#  Empirical mode never generates a signal                                     #
# --------------------------------------------------------------------------- #

def test_exogenous_signal_mode_does_not_generate_signals(spy):
    """
    With exogenous_signals the polls are supplied, so generate_signal must not
    be called at all and eps_s cannot matter.
    """
    from core_model import empirical_data as ed

    bundle = ed.load_year(2022)
    voters = ed.sample_voters(2022, 100, np.random.default_rng(0))
    run_simulation(
        K=bundle["K"], party_ids=bundle["parties"],
        party_positions_override=bundle["positions"],
        voter_positions_override=voters,
        exogenous_signals=bundle["signals"],
        tau=0.3, mu=0.1, alpha_prior=0.0, rho_pi=50.0,
        n_electors=len(voters), max_iterations=len(bundle["signals"]),
        seed=1, verbose=False,
    )
    assert spy.eps_seen == [], (
        "generate_signal was called in exogenous-signal mode")


def test_epsilon_does_not_affect_an_empirical_run():
    from core_model import empirical_data as ed

    bundle = ed.load_year(2022)
    voters = ed.sample_voters(2022, 100, np.random.default_rng(0))
    kwargs = dict(
        K=bundle["K"], party_ids=bundle["parties"],
        party_positions_override=bundle["positions"],
        voter_positions_override=voters,
        exogenous_signals=bundle["signals"],
        tau=0.3, mu=0.1, alpha_prior=0.0, rho_pi=50.0,
        n_electors=len(voters), max_iterations=len(bundle["signals"]),
        seed=1, verbose=False,
    )
    a = run_simulation(signal_epsilon=1e-12, **kwargs)
    b = run_simulation(signal_epsilon=0.5, **kwargs)
    assert a["final_shares"] == b["final_shares"]


# --------------------------------------------------------------------------- #
#  Panel C passes it directly                                                  #
# --------------------------------------------------------------------------- #

def test_panel_C_has_no_monkeypatching_helper():
    import robustness_checks as rc

    assert not hasattr(rc, "_run_with_eps"), (
        "_run_with_eps is the monkeypatching helper that never reached the "
        "model; Panel C must call run_simulation(signal_epsilon=...) directly")


def test_panel_C_grid_includes_the_historical_value():
    import robustness_checks as rc

    assert 1e-12 in rc.EPS_VALUES_C, (
        "the eps actually used by every committed result must be in the grid")
    assert rc.CHOSEN_EPS == 1e-12


def test_panel_C_passes_epsilon_through_run_simulation(monkeypatch):
    """
    Panel C must hand its varied eps to run_simulation as an argument.  Spying
    on robustness_checks.run_simulation shows what it actually passes.
    """
    import robustness_checks as rc

    seen = []

    def fake_run_simulation(**kwargs):
        seen.append(kwargs.get("signal_epsilon", "ABSENT"))
        raise _StopEarly

    class _StopEarly(Exception):
        pass

    monkeypatch.setattr(rc, "run_simulation", fake_run_simulation)
    monkeypatch.setattr(rc, "EPS_VALUES_C", [1e-12, 0.1])
    monkeypatch.setattr(rc, "CONFIGS_C", [("test", 1.5, 1.0)])
    monkeypatch.setattr(rc, "N_REPS_C", 1)

    with pytest.raises(_StopEarly):
        rc._simulate_epsilon()

    assert seen and seen[0] != "ABSENT", (
        "Panel C did not pass signal_epsilon to run_simulation")
    assert seen[0] == 1e-12


# --------------------------------------------------------------------------- #
#  The default preserves existing results                                      #
# --------------------------------------------------------------------------- #

def test_golden_synthetic_output_unchanged_under_the_default():
    """
    The pinned synthetic golden run, recomputed here explicitly at the default
    eps_s.  Plumbing the parameter must not have moved any committed number.
    """
    from core_model.metrics import tau_absolute

    res = run_simulation(
        K=8, n_modes=1, width_factor=1.5, theta=1.0,
        rho=100.0, rho_pi=100.0, n_electors=500,
        tau=tau_absolute(1.75, 8), mu=0.1, alpha_prior=0.0,
        K_runoff=2, max_iterations=15, seed=42,
        verbose=False, collect_diagnostics=True,
    )
    assert res["sincere_shares"] == pytest.approx(
        [0.032, 0.08, 0.168, 0.246, 0.26, 0.126, 0.056, 0.032], abs=1e-12)
    assert res["final_shares"] == pytest.approx(
        [0.032, 0.08, 0.168, 0.246, 0.26, 0.164, 0.018, 0.032], abs=1e-12)
    assert res["switching"]["strategic"] == 19


def test_explicit_default_equals_omitting_the_argument():
    a = run_simulation(**BASE_KWARGS)
    b = run_simulation(signal_epsilon=1e-12, **BASE_KWARGS)
    assert a["final_shares"] == b["final_shares"]
    assert a["sincere_shares"] == b["sincere_shares"]
