"""
test_protocol_validation.py
---------------------------
Tests for the protocol-validation design and machinery.

Everything here is deliberately cheap: tiny populations, short horizons, few
configurations.  The expensive question -- whether Tmax = 25 and N = 2000 hold
up -- is answered by running the script, not by the test suite.  What the suite
defends is that the machinery answering it is correct:

    * the design is deterministic, in-bounds, and covers every cell;
    * config_ids are stable and unique;
    * reading iteration t out of a long trajectory gives the same state as a
      run that stopped at t -- the assumption the whole single-trajectory
      design rests on;
    * tail windows, aggregation and sorting are right;
    * resume does not duplicate work.

Run with:  pytest tests/test_protocol_validation.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(REPO / "analysis" / "synthetic"))

import parameter_space as ps
import protocol_validation as pv
from model import run_simulation


# --------------------------------------------------------------------------- #
#  Design                                                                      #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def design():
    return pv.build_design(configs_per_cell=2)


def test_design_is_deterministic(design):
    """Two builds with identical arguments must be identical, row for row."""
    again = pv.build_design(configs_per_cell=2)
    pd.testing.assert_frame_equal(design, again)


def test_design_is_independent_of_the_design_seed(design):
    """
    Selection is by evenly spaced positions, not by drawing, so the design does
    not depend on the seed.  The argument is accepted for forward compatibility;
    this test pins that it currently changes nothing.
    """
    other = pv.build_design(configs_per_cell=2, design_seed=999)
    pd.testing.assert_frame_equal(design, other)


def test_all_parameters_inside_saltelli_bounds(design):
    for name in ps.PROBLEM["names"]:
        lo, hi = ps.bounds_for(name)
        values = design[name].to_numpy(dtype=float)
        assert values.min() >= lo, f"{name} below {lo}"
        assert values.max() <= hi, f"{name} above {hi}"


def test_every_K_is_represented(design):
    assert set(design["K"]) == set(ps.K_VALUES)


def test_every_c_stratum_is_represented_for_every_K(design):
    for K in ps.K_VALUES:
        strata = set(design[design["K"] == K]["c_stratum"])
        assert strata == set(ps.C_STRATA), f"K={K} covers only {strata}"


def test_stratum_label_matches_the_c_value(design):
    for _, row in design.iterrows():
        assert ps.c_stratum(row["c"]) == row["c_stratum"]


def test_config_ids_are_unique(design):
    assert not design["config_id"].duplicated().any()


def test_config_ids_are_stable_across_design_sizes():
    """
    A configuration keeps its id when the design grows.  Ids encode K, stratum
    and source row, so the same Saltelli row is always the same configuration.
    """
    small = pv.build_design(configs_per_cell=1)
    large = pv.build_design(configs_per_cell=5)
    for _, row in small.iterrows():
        match = large[large["source_row"] == row["source_row"]]
        match = match[match["K"] == row["K"]]
        if not match.empty:
            assert match.iloc[0]["config_id"] == row["config_id"]


def test_config_id_format():
    assert pv.config_id(8, "high", 1234) == "K8-high-r01234"


def test_validate_design_rejects_an_out_of_bounds_row(design):
    broken = design.copy()
    broken.loc[0, "c"] = 99.0
    with pytest.raises(ValueError):
        pv.validate_design(broken)


def test_validate_design_rejects_a_missing_stratum(design):
    broken = design[design["c_stratum"] != "high"]
    with pytest.raises(ValueError, match="misses c strata"):
        pv.validate_design(broken)


# --------------------------------------------------------------------------- #
#  The single-trajectory assumption                                            #
# --------------------------------------------------------------------------- #

_TRAJ_KWARGS = dict(
    K=6, n_modes=1, width_factor=1.4, mode_position=0.0, floor_weight=0.1,
    theta=0.9, rho=100.0, rho_pi=50.0, n_electors=200,
    tau=1.5 * (2.0 / 6), mu=0.15, alpha_prior=0.1,
    K_runoff=2, seed=3, verbose=False, collect_diagnostics=True,
)


def test_state_read_from_a_long_run_equals_a_short_run():
    """
    The design reads T=25, 50 and 100 out of ONE trajectory.  That is only valid
    if a long run's prefix is identical to a run that stopped early -- i.e. the
    ceiling does not change the path.  Checked here at a cheap horizon.
    """
    cut = 12
    short = run_simulation(max_iterations=cut, **_TRAJ_KWARGS)
    long = run_simulation(max_iterations=30, **_TRAJ_KWARGS)

    t_short = pv.trajectory_outcomes(short, 6)
    t_long = pv.trajectory_outcomes(long, 6)

    a = pv.state_at(t_short, cut)
    b = pv.state_at(t_long, cut)
    for outcome in pv.VALIDATION_OUTCOMES:
        assert a[outcome] == pytest.approx(b[outcome], abs=1e-12), outcome

    # and the whole prefix, not just the endpoint
    pd.testing.assert_frame_equal(
        t_short[t_short["t"] <= cut].reset_index(drop=True),
        t_long[t_long["t"] <= cut].reset_index(drop=True))


def test_trajectory_outcomes_covers_every_iteration():
    res = run_simulation(max_iterations=15, **_TRAJ_KWARGS)
    traj = pv.trajectory_outcomes(res, 6)
    assert list(traj["t"]) == list(range(1, 16))
    for outcome in pv.VALIDATION_OUTCOMES:
        assert traj[outcome].notna().all(), outcome


def test_state_at_missing_horizon_is_nan():
    res = run_simulation(max_iterations=10, **_TRAJ_KWARGS)
    traj = pv.trajectory_outcomes(res, 6)
    assert all(np.isnan(v) for v in pv.state_at(traj, 999).values())


# --------------------------------------------------------------------------- #
#  Tail windows                                                                #
# --------------------------------------------------------------------------- #

def _fake_traj(n=20):
    return pd.DataFrame({
        "t": np.arange(1, n + 1),
        "delta_cenp": np.arange(1, n + 1, dtype=float),
        "enp": np.zeros(n),
        "trigger_rate": np.zeros(n),
        "switching_rate": np.zeros(n),
    })


def test_tail_mean_uses_the_window_ending_at_the_horizon():
    """Window of 3 ending at t=10 is iterations 8, 9, 10 -> mean 9."""
    traj = _fake_traj()
    assert pv.tail_mean_at(traj, 10, 3)["delta_cenp"] == pytest.approx(9.0)


def test_tail_mean_window_of_one_is_the_endpoint():
    traj = _fake_traj()
    assert (pv.tail_mean_at(traj, 7, 1)["delta_cenp"]
            == pytest.approx(pv.state_at(traj, 7)["delta_cenp"]))


def test_tail_mean_clips_at_the_start_of_the_run():
    """A window longer than the history available starts at t=1, not t<=0."""
    traj = _fake_traj()
    assert pv.tail_mean_at(traj, 3, 10)["delta_cenp"] == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
#  Aggregation                                                                 #
# --------------------------------------------------------------------------- #

def _fake_raw():
    rows = []
    for K in (6, 8):
        for stratum in ("low", "high"):
            for seed in (0, 1):
                rows.append({
                    "config_id": f"K{K}-{stratum}-r00001",
                    "K": K, "c_stratum": stratum, "seed": seed,
                    "delta_cenp_T5": 0.10, "delta_cenp_T10": 0.10 + 0.02 * seed,
                    "delta_cenp_tail_T5": 0.10,
                    "delta_cenp_tail_T10": 0.10 + 0.01 * seed,
                    "enp_T5": 4.0, "enp_T10": 4.0,
                    "enp_tail_T5": 4.0, "enp_tail_T10": 4.0,
                    "trigger_rate_T5": 0.2, "trigger_rate_T10": 0.2,
                    "trigger_rate_tail_T5": 0.2, "trigger_rate_tail_T10": 0.2,
                    "switching_rate_T5": 0.05, "switching_rate_T10": 0.05,
                    "switching_rate_tail_T5": 0.05,
                    "switching_rate_tail_T10": 0.05,
                })
    return pd.DataFrame(rows)


def test_horizon_summary_computes_the_absolute_change():
    by_k, by_c = pv.summarise_horizon(_fake_raw(), [5, 10], threshold=0.01)
    row = by_k[(by_k["K"] == 6) & (by_k["c_stratum"] == "low")
               & (by_k["outcome"] == "delta_cenp")].iloc[0]
    # seeds differ by 0.00 and 0.02 -> median 0.01
    assert row["median_endpoint_abs_change_T5_to_T10"] == pytest.approx(0.01)
    assert row["n_runs"] == 2
    assert row["reference_horizon"] == 5


def test_horizon_summary_reports_continuous_values_beside_the_flag():
    by_k, _ = pv.summarise_horizon(_fake_raw(), [5, 10], threshold=0.01)
    for col in ("median_endpoint_abs_change_T5_to_T10",
                "p95_endpoint_abs_change_T5_to_T10",
                "median_tail_abs_change_T5_to_T10",
                "prop_within_threshold_endpoint_abs_change_T5_to_T10"):
        assert col in by_k.columns
    assert "stability_threshold" in by_k.columns


def test_horizon_summary_threshold_only_moves_the_flag():
    a, _ = pv.summarise_horizon(_fake_raw(), [5, 10], threshold=0.001)
    b, _ = pv.summarise_horizon(_fake_raw(), [5, 10], threshold=0.5)
    col = "median_endpoint_abs_change_T5_to_T10"
    np.testing.assert_allclose(a[col].to_numpy(), b[col].to_numpy())
    flag = "prop_within_threshold_endpoint_abs_change_T5_to_T10"
    assert not np.allclose(a[flag].to_numpy(), b[flag].to_numpy())


def test_horizon_summary_sorting_is_stable():
    by_k, by_c = pv.summarise_horizon(_fake_raw(), [5, 10], threshold=0.01)
    assert by_k[["outcome", "K", "c_stratum"]].apply(tuple, axis=1).is_monotonic_increasing
    assert by_c[["outcome", "c_stratum"]].apply(tuple, axis=1).is_monotonic_increasing


# --------------------------------------------------------------------------- #
#  Resume                                                                      #
# --------------------------------------------------------------------------- #

def test_resume_skips_rows_already_present(tmp_path):
    design = pv.build_design(configs_per_cell=1, k_values=[6])
    seeds = [0]
    kwargs = dict(design=design, seeds=seeds, horizons=[4, 6], tail_window=2,
                  n_electors=120, out_dir=tmp_path)

    first = pv.run_horizon(**kwargs)
    n_first = len(first)
    assert n_first == len(design) * len(seeds)

    second = pv.run_horizon(**kwargs)          # resume=True by default
    assert len(second) == n_first, "resume duplicated rows"
    assert not second[pv.HORIZON_KEY].duplicated().any()


def test_no_resume_recomputes(tmp_path):
    design = pv.build_design(configs_per_cell=1, k_values=[6])
    kwargs = dict(design=design, seeds=[0], horizons=[4], tail_window=2,
                  n_electors=120, out_dir=tmp_path)
    pv.run_horizon(**kwargs)
    again = pv.run_horizon(resume=False, **kwargs)
    assert len(again) == 2 * len(design), "--no-resume should append a fresh set"


# --------------------------------------------------------------------------- #
#  CLI                                                                         #
# --------------------------------------------------------------------------- #

def test_cli_refuses_to_run_without_an_explicit_size(tmp_path, monkeypatch):
    monkeypatch.setattr(pv, "TABLES_DIR", tmp_path)
    with pytest.raises(SystemExit) as exc:
        pv.main(["--mode", "horizon"])
    assert "Refusing to run" in str(exc.value)


# The guard that used to live here asserted --signal-epsilon was REFUSED,
# because eps_s could not reach run_simulation.  That plumbing exists now, so
# the guard could only ever skip.  The positive direction is covered by
# tests/test_signal_epsilon.py, which asserts every generate_signal call
# receives the value.  History: docs/validation.md.


def test_dry_run_performs_no_simulation(tmp_path, monkeypatch):
    monkeypatch.setattr(pv, "TABLES_DIR", tmp_path)
    pv.main(["--mode", "horizon", "--dry-run", "--out-dir", str(tmp_path)])
    assert (tmp_path / "design.csv").exists()
    assert not (tmp_path / "horizon_raw.csv").exists()


def test_quick_horizon_smoke_run_completes(tmp_path, monkeypatch):
    monkeypatch.setattr(pv, "TABLES_DIR", tmp_path)
    pv.main(["--mode", "horizon", "--quick", "--out-dir", str(tmp_path),
             "--k-values", "6", "--configs-per-cell", "1", "--n-seeds", "1",
             "--horizons", "3", "5", "--tail-window", "2",
             "--n-electors", "120"])
    raw = pd.read_csv(tmp_path / "horizon_raw.csv")
    assert len(raw) == 3                              # 3 strata x 1 config x 1 seed
    summary = pd.read_csv(tmp_path / "protocol_horizon_validation.csv")
    assert len(summary) == 3 * len(pv.VALIDATION_OUTCOMES)
    assert summary["median_endpoint_abs_change_T3_to_T5"].notna().all()


def test_quick_population_smoke_run_completes(tmp_path, monkeypatch):
    monkeypatch.setattr(pv, "TABLES_DIR", tmp_path)
    pv.main(["--mode", "population", "--quick", "--out-dir", str(tmp_path),
             "--k-values", "6", "--configs-per-cell", "1", "--n-seeds", "1",
             "--populations", "100", "200", "--horizon", "4",
             "--tail-window", "2"])
    raw = pd.read_csv(tmp_path / "population_raw.csv")
    assert len(raw) == 3 * 2                          # 3 strata x 2 populations
    summary = pd.read_csv(tmp_path / "protocol_population_validation.csv")
    assert "median_abs_diff" in summary.columns
    assert "mean_seed_sd_at_reference" in summary.columns
