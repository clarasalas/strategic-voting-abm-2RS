"""
test_result_tables.py
---------------------
Schema and integrity tests for the committed tables under results/tables/.

These tables are the reader-facing artefact: they get cited, and unlike a figure
a wrong number in a CSV is invisible.  The tests check three things:

    * the schema and identifying columns are what results/README.md promises;
    * no unexpected NaN or infinity slipped into a numeric column;
    * the exported values are the ones the plotting code consumes, and
      regeneration from identical inputs is deterministic.

Tables that require a simulation run are skipped when absent rather than failed,
so the suite stays green on a fresh clone.  sobol_indices.csv is NOT skippable:
it is reproducible from committed inputs alone, so it must always be there.

Run with:  pytest tests/test_result_tables.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(REPO / "analysis" / "synthetic"))
sys.path.insert(0, str(REPO / "analysis" / "empirical"))

TABLES = REPO / "results" / "tables"

SOBOL_TABLE = TABLES / "sobol_indices.csv"
IMPORTANCE_TABLE = TABLES / "lhs_parameter_importance.csv"


def _panel_table(panel: str) -> Path:
    return TABLES / f"robustness_panel_{panel}.csv"


def _require(path: Path) -> pd.DataFrame:
    """Load a table, skipping the test if it needs an unrun simulation."""
    if not path.exists():
        pytest.skip(f"{path.name} not generated yet (requires its experiment run)")
    return pd.read_csv(path)


def _assert_finite(df: pd.DataFrame, name: str, exclude=()):
    """No NaN or +/-inf in any numeric column."""
    for col in df.select_dtypes(include=[np.number]).columns:
        if col in exclude:
            continue
        values = df[col].to_numpy(dtype=float)
        assert not np.isnan(values).any(), f"{name}: NaN in column {col!r}"
        assert np.isfinite(values).all(), f"{name}: non-finite in column {col!r}"


# --------------------------------------------------------------------------- #
#  results/tables/ exists and is tracked                                       #
# --------------------------------------------------------------------------- #

def test_tables_directory_exists():
    assert TABLES.is_dir(), "results/tables/ is the committed output directory"


def test_sobol_table_is_committed():
    """
    The Sobol table is reproducible from committed inputs alone, so unlike the
    others it must always be present.
    """
    assert SOBOL_TABLE.exists(), (
        "results/tables/sobol_indices.csv missing -- regenerate with "
        "python analysis/synthetic/saltelli_sensitivity.py --analyze-existing")


# --------------------------------------------------------------------------- #
#  Sobol table                                                                 #
# --------------------------------------------------------------------------- #

SOBOL_COLUMNS = ["K", "outcome", "parameter", "S1", "S1_conf",
                 "ST", "ST_conf", "n_base", "n_evaluations"]


def test_sobol_schema():
    df = _require(SOBOL_TABLE)
    assert list(df.columns) == SOBOL_COLUMNS


def test_sobol_identifying_columns_are_unique():
    """(K, outcome, parameter) identifies a row exactly once."""
    df = _require(SOBOL_TABLE)
    key = df[["K", "outcome", "parameter"]]
    assert not key.duplicated().any()
    assert len(df) == len(key.drop_duplicates())


def test_sobol_has_no_missing_values():
    _assert_finite(_require(SOBOL_TABLE), "sobol_indices.csv")


def test_sobol_row_count_is_the_full_grid():
    """3 K values x 5 outcomes x 8 parameters = 120 rows, no gaps."""
    df = _require(SOBOL_TABLE)
    n_expected = (df["K"].nunique() * df["outcome"].nunique()
                  * df["parameter"].nunique())
    assert len(df) == n_expected


def test_sobol_design_metadata_is_consistent():
    """
    n_evaluations must equal n_base * (D + 2) for the calc_second_order=False
    design -- the N*(2D+2) formula does not apply and would not satisfy this.
    """
    import saltelli_sensitivity as ss

    df = _require(SOBOL_TABLE)
    D = ss.PROBLEM["num_vars"]
    assert (df["n_evaluations"] == df["n_base"] * (D + 2)).all()
    assert (df["n_evaluations"] % (D + 2) == 0).all()


def test_sobol_parameters_match_the_problem_definition():
    import saltelli_sensitivity as ss

    df = _require(SOBOL_TABLE)
    assert set(df["parameter"]) == set(ss.PROBLEM["names"])
    assert set(df["outcome"]) == set(ss.OUTCOMES)


def test_sobol_total_order_is_not_below_first_order():
    """
    ST >= S1 up to estimator noise.  A gross violation means the indices were
    computed on a mis-ordered design.  Tolerance is the confidence half-width.
    """
    df = _require(SOBOL_TABLE)
    slack = df["S1_conf"] + df["ST_conf"]
    assert ((df["ST"] - df["S1"]) > -slack).all()


# --------------------------------------------------------------------------- #
#  Sobol: exported values agree with what the plots consume                    #
# --------------------------------------------------------------------------- #

def test_sobol_table_matches_the_analysed_objects():
    """
    Rebuild the indices from the committed results and check the table was
    written from those same Si objects.  This is the test that would catch a
    table drifting away from the figures.
    """
    import saltelli_sensitivity as ss

    df = _require(SOBOL_TABLE)
    K = int(df["K"].min())                     # one K is enough; full run is slow

    sobol_results, n_base, n_eval = ss.analyze_existing(K)
    rebuilt = ss.sobol_table({K: sobol_results}, {K: (n_base, n_eval)})
    committed = df[df["K"] == K].reset_index(drop=True)

    assert list(rebuilt.columns) == list(committed.columns)
    for col in ("S1", "S1_conf", "ST", "ST_conf"):
        np.testing.assert_allclose(
            rebuilt[col].to_numpy(), committed[col].to_numpy(),
            rtol=0, atol=1e-12,
            err_msg=f"{col} in sobol_indices.csv differs from a fresh analysis")


def test_sobol_regeneration_is_deterministic():
    """
    Two analyses of identical inputs must agree exactly.  Without the fixed
    CONF_SEED the bootstrap confidence intervals would differ every run.
    """
    import saltelli_sensitivity as ss

    K = 6
    a, _, _ = ss.analyze_existing(K, verify_design=False)
    b, _, _ = ss.analyze_existing(K, verify_design=False)
    for outcome in ss.OUTCOMES:
        for key in ("S1", "S1_conf", "ST", "ST_conf"):
            np.testing.assert_array_equal(
                a[outcome][key], b[outcome][key],
                err_msg=f"{outcome}/{key} is not reproducible")


def test_infer_base_sample_rejects_the_second_order_formula():
    """
    10240 rows is 1024 * (8 + 2).  Under the full second-order design it would
    imply 568.9 base samples, so a file built that way must be rejected.
    """
    import saltelli_sensitivity as ss

    assert ss.infer_base_sample(10240) == 1024
    with pytest.raises(ValueError, match="not a multiple"):
        ss.infer_base_sample(10241)


# --------------------------------------------------------------------------- #
#  Robustness panel tables                                                     #
# --------------------------------------------------------------------------- #

PANEL_SCHEMAS = {
    "A": (["regime", "c", "N", "n_reps", "delta_cenp_mean",
           "delta_cenp_sd", "delta_cenp_se", "n_chosen"],
          ["regime", "N"]),
    "B": (["regime", "N_electors", "n_reps", "tmax_ceiling", "median_conv",
           "p95_conv", "n_tmax_binding", "prop_tmax_binding"],
          ["regime"]),
    "C": (["config", "eps", "n_reps", "delta_cenp_mean", "delta_cenp_sd"],
          ["config", "eps"]),
    "D": (["xi", "K", "theta", "n_reps", "enp_sincere_mean", "enp_sincere_se",
           "enp_final_mean", "enp_final_se"],
          ["xi"]),
    "E": (["theta", "party", "sincere_share", "transformed_share",
           "enp_sincere", "enp_transformed", "delta_enp", "shown_in_figure"],
          ["theta", "party"]),
    "F": (["regime", "mu", "n_reps", "cond_sw_mean", "cond_sw_se"],
          ["regime", "mu"]),
}


@pytest.mark.parametrize("panel", sorted(PANEL_SCHEMAS))
def test_panel_table_has_required_columns(panel):
    required, _ = PANEL_SCHEMAS[panel]
    df = _require(_panel_table(panel))
    missing = [c for c in required if c not in df.columns]
    assert not missing, f"panel {panel}: missing columns {missing}"


@pytest.mark.parametrize("panel", sorted(PANEL_SCHEMAS))
def test_panel_table_key_is_unique(panel):
    _, key = PANEL_SCHEMAS[panel]
    df = _require(_panel_table(panel))
    assert not df[key].duplicated().any(), f"panel {panel}: duplicate {key}"


@pytest.mark.parametrize("panel", sorted(PANEL_SCHEMAS))
def test_panel_table_has_no_unexpected_nans(panel):
    df = _require(_panel_table(panel))
    # p95_conv is nan by construction when a regime never converges below the
    # ceiling; that is a documented outcome, not a defect.
    _assert_finite(df, f"robustness_panel_{panel}.csv", exclude=("p95_conv",))


@pytest.mark.parametrize("panel", sorted(PANEL_SCHEMAS))
def test_panel_table_reports_repetitions(panel):
    """Every summary row must say how many runs it came from."""
    if panel == "E":
        pytest.skip("panel E is analytic: no repetitions")
    df = _require(_panel_table(panel))
    assert (df["n_reps"] > 0).all()


# --------------------------------------------------------------------------- #
#  Panel E: analytic, so it can be regenerated and compared here              #
# --------------------------------------------------------------------------- #

def test_panel_E_is_deterministic_and_matches_the_plotted_transform():
    """
    Panel E runs no simulation, so the table must reproduce exactly -- and its
    transformed shares must equal transform_signal, which is what the figure
    draws.
    """
    import robustness_checks as rc
    from signals import transform_signal

    a = rc.table_panel_E()
    b = rc.table_panel_E()
    pd.testing.assert_frame_equal(a, b)

    delta0 = rc.BASELINE_SHARES_E / rc.BASELINE_SHARES_E.sum()
    for theta in a["theta"].unique():
        expected = transform_signal(delta0, theta=float(theta))
        got = a[a["theta"] == theta].sort_values("party")["transformed_share"]
        np.testing.assert_allclose(got.to_numpy(), expected, rtol=0, atol=1e-12)


def test_panel_E_delta_enp_sign_follows_theta():
    """theta < 1 sharpens (ENP falls); theta > 1 flattens (ENP rises)."""
    import robustness_checks as rc

    t = rc.table_panel_E().drop_duplicates("theta")
    assert (t.loc[t["theta"] < 1.0, "delta_enp"] < 0).all()
    assert (t.loc[t["theta"] > 1.0, "delta_enp"] > 0).all()
    assert t.loc[np.isclose(t["theta"], 1.0), "delta_enp"].abs().max() < 1e-9


# --------------------------------------------------------------------------- #
#  LHS importance table                                                        #
# --------------------------------------------------------------------------- #

IMPORTANCE_COLUMNS = [
    "scope", "parameter", "permutation_importance", "importance_std",
    "relative_importance_pct", "standardized_coefficient",
    "cv_r2_mean", "cv_r2_std", "n_rows", "seed",
]


def test_importance_schema_when_present():
    df = _require(IMPORTANCE_TABLE)
    assert list(df.columns) == IMPORTANCE_COLUMNS


def test_importance_key_is_unique_when_present():
    df = _require(IMPORTANCE_TABLE)
    assert not df[["scope", "parameter"]].duplicated().any()


def test_importance_scopes_when_present():
    df = _require(IMPORTANCE_TABLE)
    assert set(df["scope"]) == {"pooled", "2002", "2022"}


def test_importance_percentages_sum_to_100_per_scope_when_present():
    df = _require(IMPORTANCE_TABLE)
    for scope, sub in df.groupby("scope"):
        total = sub["relative_importance_pct"].sum()
        assert total == pytest.approx(100.0, abs=1e-6), f"scope {scope}: {total}"


def test_importance_builder_is_deterministic_on_fixed_input():
    """
    The exporter itself must be deterministic and must agree with the helper the
    slide figure uses.  Runs on a fixed in-memory frame, so it needs no sweep
    data -- deliberately, since the sweeps on disk are stale pending the
    corrected tau_hat rerun.
    """
    import lhs_importance as lhs

    frame = pd.DataFrame({
        "param": ["tau_hat", "mu", "beta"],
        "importance": [0.30, -0.01, 0.10],
        "importance_std": [0.010, 0.002, 0.005],
        "std_coef": [0.5, -0.1, 0.2],
        "cv_r2_mean": [0.42] * 3,
        "cv_r2_std": [0.03] * 3,
        "n_rows": [1000] * 3,
    })
    results = {"Pooled (2002 + 2022)": (frame, 0.42),
               "2002": (frame, 0.42),
               "2022": (frame, 0.42)}

    a = lhs.build_importance_table(results)
    b = lhs.build_importance_table(results)
    pd.testing.assert_frame_equal(a, b)

    assert list(a.columns) == IMPORTANCE_COLUMNS
    assert set(a["scope"]) == {"pooled", "2002", "2022"}

    # Percentages must come from the slide figure's own helper.
    pct = lhs._importance_pct(frame)
    got = a[a["scope"] == "pooled"].set_index("parameter")["relative_importance_pct"]
    for param, expected in pct.items():
        assert got[param] == pytest.approx(expected, abs=1e-12)

    # Negative importances are clipped to zero before scaling, not dropped.
    assert got["mu"] == pytest.approx(0.0, abs=1e-12)
