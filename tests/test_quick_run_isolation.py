"""
test_quick_run_isolation.py
---------------------------
Regression tests for a data loss that already happened.

On 2026-08-19 a `--quick` smoke run of the empirical replay wrote 15 draws over
the filenames holding the 300-draw experiment.  data/ is git-ignored and the
outputs had never been committed, so the full pre-fix results are simply gone.

The fix is structural rather than procedural: a quick run writes to data/smoke/,
never to data/.  The complementary guard, refusing to replace any existing
output without --overwrite, lives in tests/test_overwrite_protection.py.

Run with:  pytest tests/test_quick_run_isolation.py
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis" / "empirical"))

import empirical_2002_2022 as runner

TEST_VOTERS = 40


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_full_run(path: Path, n_rows: int = 300) -> str:
    """Write a file shaped like a completed full run; return its checksum."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "draw": range(n_rows),
        "tau_hat": [1.5] * n_rows,
        "tau_absolute": [0.2] * n_rows,
        "K": [15] * n_rows,
        "delta_cenp": [0.01] * n_rows,
    }).to_csv(path, index=False)
    return _sha256(path)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirect both output directories; nothing touches the real data/."""
    data = tmp_path / "data"
    smoke = data / "smoke"
    data.mkdir()
    monkeypatch.setattr(runner, "DATA_DIR", data)
    monkeypatch.setattr(runner, "SMOKE_DIR", smoke)
    monkeypatch.setattr(runner, "N_VOTERS", TEST_VOTERS)
    return data, smoke


def _run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["empirical_2002_2022.py"] + argv)
    runner.main()


# --------------------------------------------------------------------------- #
#  The directories are distinct by construction                                #
# --------------------------------------------------------------------------- #

def test_smoke_dir_is_not_the_data_dir():
    assert runner.SMOKE_DIR != runner.DATA_DIR
    assert runner.SMOKE_DIR.name == "smoke"
    assert runner.SMOKE_DIR.parent == runner.DATA_DIR


# --------------------------------------------------------------------------- #
#  The regression itself                                                       #
# --------------------------------------------------------------------------- #

def test_quick_run_cannot_overwrite_a_full_run_output(sandbox, monkeypatch):
    """
    The 2026-08-19 loss, reproduced and prevented.

    A completed 300-row full run sits in data/.  A quick run then executes to
    completion.  The full run must be byte-identical afterwards, and the quick
    output must exist somewhere else.
    """
    data, smoke = sandbox
    full = data / "empirical_runs_2002.csv"
    before = _fake_full_run(full)

    _run_cli(monkeypatch, ["--quick", "--draws", "1", "--robust-draws", "1"])

    assert _sha256(full) == before, \
        "the quick run modified the full-run output"
    assert len(pd.read_csv(full)) == 300

    quick = smoke / "empirical_runs_2002.csv"
    assert quick.exists(), "the quick run wrote nothing to data/smoke/"
    assert len(pd.read_csv(quick)) == 1


def test_quick_run_writes_every_output_under_smoke(sandbox, monkeypatch):
    """No quick artefact of any kind lands in data/."""
    data, smoke = sandbox
    _run_cli(monkeypatch, ["--quick", "--draws", "1", "--robust-draws", "1"])

    stray = [p.name for p in data.glob("*.csv")]
    assert stray == [], f"quick run leaked into data/: {stray}"

    produced = {p.name for p in smoke.glob("*.csv")}
    for year in runner.YEARS:
        assert f"empirical_runs_{year}.csv" in produced
        assert f"empirical_robustness_{year}.csv" in produced


def test_full_run_still_targets_the_data_dir(sandbox, monkeypatch):
    """The redirect applies to --quick only; a real run is unaffected."""
    data, smoke = sandbox
    _run_cli(monkeypatch, ["--draws", "1", "--no-robustness"])

    assert (data / "empirical_runs_2002.csv").exists()
    assert not smoke.exists() or not list(smoke.glob("*.csv"))


def test_explicit_out_dir_overrides_the_quick_redirect(sandbox, monkeypatch,
                                                       tmp_path):
    """--out-dir is the escape hatch and beats --quick."""
    _, smoke = sandbox
    elsewhere = tmp_path / "elsewhere"
    _run_cli(monkeypatch, ["--quick", "--draws", "1", "--no-robustness",
                           "--out-dir", str(elsewhere)])

    assert (elsewhere / "empirical_runs_2002.csv").exists()
    assert not smoke.exists() or not list(smoke.glob("*.csv"))
