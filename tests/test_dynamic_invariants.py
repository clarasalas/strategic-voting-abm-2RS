"""
test_dynamic_invariants.py
--------------------------
Invariants that must hold at EVERY iteration, not only at the end.

tests/test_empirical.py checks the final state: shares sum to one, the run is
reproducible. That leaves the trajectory unchecked. A loop that produced a
malformed intermediate state (a vote for a party index that does not exist, a
share vector that stops summing to one halfway through, a trigger count above
the electorate) can still land on a well-formed final state, and every
published number is a function of that trajectory.

These run the real model on small electorates with fixed seeds.

Run with:  pytest tests/test_dynamic_invariants.py
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core_model.model import run_simulation
from core_model.metrics import tau_absolute

N_ELECTORS = 120

# Contrasting electorate widths (width_factor is the model's c: mode width as a
# fraction of the zone length), so the invariants are checked on a run that
# triggers heavily and one that mostly does not.
CONFIGS = [
    pytest.param({"K": 6, "width_factor": 0.5, "mu": 0.1}, id="narrow-K6"),
    pytest.param({"K": 8, "width_factor": 2.5, "mu": 0.4}, id="wide-K8"),
    pytest.param({"K": 9, "width_factor": 1.25, "mu": 0.0}, id="mid-K9"),
]


@pytest.fixture(scope="module")
def runs():
    """One diagnostic run per config, computed once."""
    out = {}
    for cfg in [p.values[0] for p in CONFIGS]:
        K = cfg["K"]
        key = (K, cfg["width_factor"], cfg["mu"])
        out[key] = run_simulation(
            K=K, n_electors=N_ELECTORS,
            width_factor=cfg["width_factor"], mu=cfg["mu"],
            tau=tau_absolute(1.5, K), max_iterations=12, seed=4242,
            verbose=False, collect_diagnostics=True,
        )
    return out


def _res(runs, cfg):
    return runs[(cfg["K"], cfg["width_factor"], cfg["mu"])]


@pytest.mark.parametrize("cfg", CONFIGS)
def test_every_iteration_allocates_exactly_the_electorate(runs, cfg):
    res = _res(runs, cfg)
    for t, counts in enumerate(res["history"]):
        counts = np.asarray(counts, dtype=float)
        assert counts.sum() == pytest.approx(N_ELECTORS), \
            f"iteration {t}: {counts.sum()} votes for {N_ELECTORS} electors"
        assert (counts >= 0).all(), f"iteration {t}: negative count"
        assert len(counts) == cfg["K"]


@pytest.mark.parametrize("cfg", CONFIGS)
def test_every_iteration_yields_shares_summing_to_one(runs, cfg):
    res = _res(runs, cfg)
    for t, counts in enumerate(res["history"]):
        shares = np.asarray(counts, dtype=float) / N_ELECTORS
        assert shares.sum() == pytest.approx(1.0, abs=1e-12), f"iteration {t}"
        assert np.isfinite(shares).all(), f"iteration {t}"


@pytest.mark.parametrize("cfg", CONFIGS)
def test_every_recorded_intention_is_a_valid_party(runs, cfg):
    res = _res(runs, cfg)
    K = cfg["K"]
    for t, intentions in enumerate(res["intention_history"]):
        arr = np.asarray(intentions)
        assert arr.shape == (N_ELECTORS,), f"iteration {t}"
        assert np.issubdtype(arr.dtype, np.integer), f"iteration {t}"
        assert arr.min() >= 0 and arr.max() < K, \
            f"iteration {t}: intentions outside [0, {K})"


@pytest.mark.parametrize("cfg", CONFIGS)
def test_intentions_agree_with_the_counts_they_produced(runs, cfg):
    """The two histories are recorded separately; they must not drift apart."""
    res = _res(runs, cfg)
    for t, (counts, intentions) in enumerate(
            zip(res["history"], res["intention_history"])):
        rebuilt = np.bincount(np.asarray(intentions), minlength=cfg["K"])
        np.testing.assert_array_equal(
            rebuilt, np.asarray(counts),
            err_msg=f"iteration {t}: counts and intentions disagree")


@pytest.mark.parametrize("cfg", CONFIGS)
def test_trigger_and_switching_counts_stay_in_range(runs, cfg):
    res = _res(runs, cfg)
    for d in res["diagnostics"]["iterations"]:
        t = d["t"]
        assert 0.0 <= d["trigger_rate"] <= 1.0, f"iteration {t}"
        assert 0 <= d["n_triggered"] <= N_ELECTORS, f"iteration {t}"
        assert d["n_triggered"] == pytest.approx(
            d["trigger_rate"] * N_ELECTORS, abs=1e-9), f"iteration {t}"

    for t, pct in enumerate(res["sw_history"]):
        assert 0.0 <= pct <= 100.0, f"iteration {t}: switching {pct}%"


@pytest.mark.parametrize("cfg", CONFIGS)
def test_every_iteration_signal_is_a_distribution(runs, cfg):
    res = _res(runs, cfg)
    for d in res["diagnostics"]["iterations"]:
        s = np.asarray(d["signal"], dtype=float)
        assert np.isfinite(s).all(), f"iteration {d['t']}"
        assert (s >= 0).all(), f"iteration {d['t']}"
        assert s.sum() == pytest.approx(1.0, abs=1e-9), f"iteration {d['t']}"
        assert len(s) == cfg["K"]


@pytest.mark.parametrize("cfg", CONFIGS)
def test_projected_finalists_are_valid_and_distinct(runs, cfg):
    res = _res(runs, cfg)
    for d in res["diagnostics"]["iterations"]:
        top = d["top_M_set"]
        assert len(set(top)) == len(top), f"iteration {d['t']}: duplicate"
        assert all(0 <= i < cfg["K"] for i in top), f"iteration {d['t']}"


@pytest.mark.parametrize("cfg", CONFIGS)
def test_the_histories_line_up_on_the_documented_offset(runs, cfg):
    """
    The recorded series are not all the same length, and should not be.

    history and intention_history include iteration 0, the sincere vote before
    any strategic reasoning, so they hold n + 1 entries. Switching and
    the per-iteration diagnostics are undefined at t = 0 and start at t = 1, so
    they hold n. Any per-iteration analysis that zips them together depends on
    exactly this offset, so it is pinned here rather than left to be
    rediscovered: a change that made history start at t = 1, or diagnostics at
    t = 0, would silently shift every trajectory by one step.
    """
    res = _res(runs, cfg)
    n = res["iterations"]
    assert n >= 1

    assert len(res["history"]) == n + 1
    assert len(res["intention_history"]) == n + 1
    assert len(res["sw_history"]) == n
    assert len(res["diagnostics"]["iterations"]) == n

    ts = [d["t"] for d in res["diagnostics"]["iterations"]]
    assert ts == list(range(1, n + 1))
