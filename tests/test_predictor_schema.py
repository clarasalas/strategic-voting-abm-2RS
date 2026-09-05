"""
test_predictor_schema.py
------------------------
The predictor set is declared, and nothing a runner adds to its output can
change it.

Selection used to work by exclusion: every numeric column was a predictor
unless a name pattern ruled it out. That inverts the burden: a new column is
a parameter by default, and only becomes metadata if somebody remembers to
exclude it. Adding tau_absolute and K for traceability would have quietly added
two predictors, and tau_absolute is exactly tau_hat * (2 / K), so within a year
it is perfectly collinear with tau_hat: permutation importance would have split
one parameter's importance across two columns and changed the ranking.

These tests pin the inverted rule: the allowlist decides, and arbitrary extra
columns are inert.

Run with:  pytest tests/test_predictor_schema.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis" / "empirical"))

import lhs_importance as lhs

N = 30


def _sweep_frame(K=15, seed=0):
    """A minimal frame carrying exactly the behavioural sweep's parameters."""
    rng = np.random.default_rng(seed)
    tau = rng.uniform(0.5, 3.0, N)
    return pd.DataFrame({
        "draw": np.arange(N),
        "tau_hat": tau,
        "tau_absolute": tau * (2.0 / K),
        "K": np.full(N, K),
        "mu": rng.uniform(0, 1, N),
        "alpha": rng.uniform(0, 0.9, N),
        "rho_pi": rng.uniform(5, 200, N),
        "beta": rng.uniform(0, 20, N),
        "n_repeats": np.full(N, 4),
        "seed": np.full(N, 20020422),
        "mean_delta_cenp": rng.normal(0, 0.05, N),
    })


# --------------------------------------------------------------------------- #
#  The allowlist decides                                                       #
# --------------------------------------------------------------------------- #

def test_behavioural_sweep_predictors_are_the_five_swept_parameters():
    df = _sweep_frame()
    assert lhs.resolve_predictors(df, "behavioral_sweep") == \
        ["tau_hat", "mu", "alpha", "rho_pi", "beta"]


def test_traceability_columns_are_not_predictors():
    """The two columns that motivated the change."""
    got = lhs.resolve_predictors(_sweep_frame(), "behavioral_sweep")
    assert "tau_absolute" not in got
    assert "K" not in got


def test_no_declared_set_contains_a_metadata_name():
    for design, cols in lhs.SWEPT_PREDICTORS.items():
        clash = sorted({c.lower() for c in cols} & lhs.NEVER_PREDICTORS)
        assert not clash, f"{design} declares metadata as predictors: {clash}"


def test_declared_sets_have_no_duplicates():
    for design, cols in lhs.SWEPT_PREDICTORS.items():
        assert len(cols) == len(set(cols)), f"{design} repeats a column"


def test_the_designs_really_do_differ():
    """
    If they were all the same set there would be no reason to name them
    separately, and a single list would be clearer. They are not.
    """
    sets = {d: tuple(c) for d, c in lhs.SWEPT_PREDICTORS.items()}
    assert len(set(sets.values())) == len(sets)

    # The specific differences that matter, each traceable to a runner flag:
    assert "beta" not in lhs.SWEPT_PREDICTORS["replay_nearest"]
    assert "beta" in lhs.SWEPT_PREDICTORS["replay_probabilistic"]
    assert "mu" in lhs.SWEPT_PREDICTORS["replay_probabilistic"]
    assert "mu" not in lhs.SWEPT_PREDICTORS["replay_prob_mu0"]


# --------------------------------------------------------------------------- #
#  Arbitrary metadata cannot change the predictor matrix                       #
# --------------------------------------------------------------------------- #

EXTRA_COLUMNS = [
    "K", "tau_absolute", "seed", "year", "draw", "n_repeats", "repeat",
    "run_id", "config_id", "git_commit_ordinal", "wall_clock_seconds",
    "hostname_hash", "schema_version", "tau_hat_absolute", "beta_bin",
    "some_new_metric", "zzz", "x", "importance",
]


@pytest.mark.parametrize("extra", EXTRA_COLUMNS)
def test_one_extra_column_changes_nothing(extra):
    base = _sweep_frame()
    expected = lhs.resolve_predictors(base, "behavioral_sweep")
    X_expected = base[expected].to_numpy(dtype=float)

    polluted = base.copy()
    polluted[extra] = np.linspace(1.0, 2.0, N)

    got = lhs.resolve_predictors(polluted, "behavioral_sweep")
    assert got == expected, f"adding {extra!r} changed the predictor list"
    np.testing.assert_array_equal(polluted[got].to_numpy(dtype=float),
                                  X_expected)


def test_all_extra_columns_at_once_change_nothing():
    base = _sweep_frame()
    expected = lhs.resolve_predictors(base, "behavioral_sweep")
    X_expected = base[expected].to_numpy(dtype=float)

    polluted = base.copy()
    for i, extra in enumerate(EXTRA_COLUMNS):
        polluted[extra] = np.linspace(i, i + 1, N)

    got = lhs.resolve_predictors(polluted, "behavioral_sweep")
    assert got == expected
    np.testing.assert_array_equal(polluted[got].to_numpy(dtype=float),
                                  X_expected)


def test_column_order_in_the_file_does_not_matter():
    """
    The declared order is the contract, not the file's order. The surrogate's
    feature subsampling is seeded, so a reordering that reached X would change
    the fitted forest.
    """
    base = _sweep_frame()
    shuffled = base[list(reversed(base.columns))]

    assert lhs.resolve_predictors(shuffled, "behavioral_sweep") == \
        lhs.resolve_predictors(base, "behavioral_sweep")
    np.testing.assert_array_equal(
        shuffled[lhs.resolve_predictors(shuffled, "behavioral_sweep")].to_numpy(float),
        base[lhs.resolve_predictors(base, "behavioral_sweep")].to_numpy(float))


def test_exclusion_detection_would_have_been_fooled():
    """
    The reason the rule was inverted, stated as a test.

    Exclusion-based detection picks up a plausible-looking new column; the
    allowlist does not. If this ever stops being true the old mechanism has
    become safe, and this test is the place to record that.
    """
    df = _sweep_frame()
    df["shiny_new_column"] = np.linspace(0, 1, N)

    detected = lhs.find_predictor_columns(df, "mean_delta_cenp")
    declared = lhs.resolve_predictors(df, "behavioral_sweep")

    assert "shiny_new_column" in detected
    assert "shiny_new_column" not in declared


# --------------------------------------------------------------------------- #
#  Refusals                                                                    #
# --------------------------------------------------------------------------- #

def test_a_missing_swept_parameter_is_an_error_not_a_smaller_model():
    """
    Dropping a parameter silently would fit a plausible surrogate on the wrong
    design and report a ranking for it.
    """
    df = _sweep_frame().drop(columns=["beta"])
    with pytest.raises(ValueError, match="missing"):
        lhs.resolve_predictors(df, "behavioral_sweep")


def test_a_non_numeric_predictor_is_an_error():
    df = _sweep_frame()
    df["mu"] = "not a number"
    with pytest.raises(ValueError, match="not numeric"):
        lhs.resolve_predictors(df, "behavioral_sweep")


def test_an_unknown_design_is_an_error():
    with pytest.raises(ValueError, match="Unknown design"):
        lhs.resolve_predictors(_sweep_frame(), "no_such_design")


def test_the_module_declares_which_design_it_analyses():
    """lhs_importance reads the behavioural-sweep outputs, so that is its set."""
    assert lhs.DESIGN == "behavioral_sweep"
    assert lhs.DESIGN in lhs.SWEPT_PREDICTORS
