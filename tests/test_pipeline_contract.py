"""
test_pipeline_contract.py
-------------------------
One tiny end-to-end pass over the empirical pipeline, checking that the stages
still fit together:

    empirical replay  ->  diagnostics  ->  importance input  ->  exported table
                      \\-> figure loaders

Nothing here checks a scientific conclusion or what a figure looks like. It
checks the seams: filenames, column names and paths. Those are what break when
a runner gains a column, a stem is renamed, or an output moves directory, and
they break silently, hours into a rerun, because each stage is a separate
process and the failure only appears at the next one.

Everything runs on a 3-draw design with a small electorate, in a tmp directory.

Run with:  pytest tests/test_pipeline_contract.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis" / "empirical"))

import empirical_2002_2022 as runner
import empirical_diagnostics as diagnostics
import empirical_figures as figures
import lhs_importance as lhs

N_DRAWS = 3
TEST_VOTERS = 60


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    """Run the replay once and point every downstream stage at its output."""
    out = tmp_path_factory.mktemp("pipeline")
    old_voters = runner.N_VOTERS
    runner.N_VOTERS = TEST_VOTERS
    try:
        runner.run_main_experiment(N_DRAWS, cfg={}, out_dir=out)
    finally:
        runner.N_VOTERS = old_voters
    return out


# --------------------------------------------------------------------------- #
#  Stage 1 -> 2: the replay writes what diagnostics reads                      #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year", runner.YEARS)
def test_diagnostics_finds_and_reads_the_replay_output(pipeline, monkeypatch,
                                                       year):
    monkeypatch.setattr(diagnostics, "DATA_DIR", pipeline)
    tidy = diagnostics.tidy_diagnostics(year)

    assert len(tidy) == N_DRAWS
    assert list(tidy.columns[:2]) == ["draw", "year"]
    assert (tidy["year"] == year).all()
    for col in diagnostics._DIAG_MAP:
        assert col in tidy.columns


def test_every_column_diagnostics_wants_is_actually_produced(pipeline):
    """
    _DIAG_MAP names source columns in the runner's output. A rename on either
    side is a KeyError deep in a rerun; here it is one assertion.
    """
    runs = pd.read_csv(pipeline / "empirical_runs_2002.csv")
    missing = [src for src in diagnostics._DIAG_MAP.values()
               if src not in runs.columns]
    assert not missing, f"empirical_runs is missing {missing}"


def test_activation_summary_builds_from_the_diagnostics_frame(pipeline,
                                                              monkeypatch):
    monkeypatch.setattr(diagnostics, "DATA_DIR", pipeline)
    diags = {y: diagnostics.tidy_diagnostics(y) for y in runner.YEARS}
    summary = diagnostics.activation_summary(diags)

    assert len(summary) > 0
    assert "group" in summary.columns and "n_draws" in summary.columns
    num = summary.select_dtypes(include=[np.number])
    assert np.isfinite(num.to_numpy(dtype=float)).all()


# --------------------------------------------------------------------------- #
#  Stage 1 -> figures: the loaders resolve the filenames the runner wrote      #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year", runner.YEARS)
def test_figure_loaders_resolve_the_replay_filenames(pipeline, monkeypatch,
                                                     year):
    """
    Filename convention only: the suffix goes before the year, and the figure
    module has its own resolver that has to agree with the runner's writer.
    """
    monkeypatch.setattr(figures, "DATA_DIR", pipeline)

    runs = figures.load_runs(year)
    shares = figures.load_candidates(year)

    assert len(runs) == N_DRAWS
    assert {"tau_hat", "tau_absolute", "K"} <= set(runs.columns)
    assert "mean_final_share" in shares.columns
    assert "actual_share" in shares.columns


def test_figure_loader_reports_a_missing_file_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(figures, "DATA_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        figures.load_runs(2002)


# --------------------------------------------------------------------------- #
#  Stage 3: the sweep output is a valid importance input                       #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def sweep_frames():
    """
    Sweep-shaped frames built from the real schema.

    behavioral_sweep.OUTPUT_COLS is the contract; building the fixture from it
    means a column added there without updating the predictor sets shows up
    here rather than after a seven-hour run.
    """
    import behavioral_sweep as sweep

    rng = np.random.default_rng(11)
    frames = {}
    for year, K in (("2002", 15), ("2022", 12)):
        n = 40
        tau = rng.uniform(0.5, 3.0, n)
        df = pd.DataFrame({c: np.zeros(n) for c in sweep.OUTPUT_COLS})
        df["draw"] = np.arange(n)
        df["tau_hat"] = tau
        df["tau_absolute"] = tau * (2.0 / K)
        df["K"] = K
        df["mu"] = rng.uniform(0, 1, n)
        df["alpha"] = rng.uniform(0, 0.9, n)
        df["rho_pi"] = rng.uniform(5, 200, n)
        df["beta"] = rng.uniform(0, 20, n)
        df["mean_delta_cenp"] = 0.03 * df.tau_hat - 0.02 * df.mu
        df["mean_final_enp"] = 5.0
        df["std_delta_cenp"] = 0.001
        df["n_repeats"] = 4
        df["seed"] = 20020422
        frames[year] = df
    return frames


def test_sweep_output_is_a_valid_importance_input(sweep_frames):
    all_df = pd.concat([f.assign(year=y) for y, f in sweep_frames.items()],
                       ignore_index=True)
    outcome = lhs.find_outcome_column(all_df)
    predictors = lhs.resolve_predictors(all_df, lhs.DESIGN)

    assert outcome == "mean_delta_cenp"
    assert predictors == lhs.SWEPT_PREDICTORS["behavioral_sweep"]
    assert all_df[predictors].notna().all().all()


@pytest.fixture
def small_forest(monkeypatch):
    """
    Shrink the surrogate for the schema test: 20 trees, single process.

    fit_and_importance hardcodes 500 trees and n_jobs=-1, which together cost
    ~20 s on a fixture this small, almost all of it joblib spinning up worker
    processes for a few milliseconds of arithmetic. This test asserts column
    names and finiteness, not importances, so neither the tree count nor the
    worker count matters to what it checks. The real code path is unchanged.
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.inspection import permutation_importance

    def small(*args, **kwargs):
        kwargs["n_estimators"] = 20
        kwargs["n_jobs"] = 1
        return RandomForestRegressor(*args, **kwargs)

    def serial_perm(*args, **kwargs):
        kwargs["n_jobs"] = 1
        return permutation_importance(*args, **kwargs)

    monkeypatch.setattr(lhs, "RandomForestRegressor", small)
    monkeypatch.setattr(lhs, "permutation_importance", serial_perm)


def test_importance_table_exports_the_documented_schema(sweep_frames,
                                                       small_forest):
    """The final seam: surrogate output -> the committed table's columns."""
    all_df = pd.concat([f.assign(year=y) for y, f in sweep_frames.items()],
                       ignore_index=True)
    outcome = lhs.find_outcome_column(all_df)
    predictors = lhs.resolve_predictors(all_df, lhs.DESIGN)

    results = {}
    for label, subset in [("Pooled (2002 + 2022)", all_df),
                          ("2002", all_df[all_df["year"] == "2002"])]:
        results[label] = lhs.fit_and_importance(subset[predictors],
                                                subset[outcome], label)

    table = lhs.build_importance_table(results)

    assert list(table.columns) == lhs.IMPORTANCE_TABLE_COLUMNS
    assert set(table["parameter"]) == set(predictors)
    assert set(table["scope"]) == {"pooled", "2002"}
    assert len(table) == len(predictors) * 2
    num = table.select_dtypes(include=[np.number])
    assert np.isfinite(num.to_numpy(dtype=float)).all()
