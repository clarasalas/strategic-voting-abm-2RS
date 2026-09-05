"""
test_overwrite_protection.py
----------------------------
The empirical replay refuses to overwrite existing outputs unless told to.

behavioral_sweep.py already worked this way. The replay did not: it only
refused to replace a file with a SMALLER one, which left the ordinary case
unguarded: re-running the same command overwrote a completed 300-draw
experiment without a word, because 300 is not smaller than 300.

Existence is now the whole test. Size is not consulted, because "the new file
has at least as many rows" is not a reason to destroy twenty minutes of compute
silently.

Run with:  pytest tests/test_overwrite_protection.py
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

MAIN_STEMS = ("runs", "candidate_shares", "candidate_draws")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _write(path: Path, n_rows: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "draw": range(n_rows),
        "tau_hat": [1.5] * n_rows,
        "tau_absolute": [0.2] * n_rows,
        "K": [15] * n_rows,
        "delta_cenp": [0.01] * n_rows,
    }).to_csv(path, index=False)
    return _sha(path)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
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


def _seed_main_outputs(data: Path, n_rows: int) -> dict:
    """Write a complete set of main-experiment outputs; return their digests."""
    return {p: _write(p, n_rows)
            for year in runner.YEARS
            for p in [data / f"empirical_{stem}_{year}.csv"
                      for stem in MAIN_STEMS]}


# --------------------------------------------------------------------------- #
#  The two cases from the loss and from the upcoming rerun                     #
# --------------------------------------------------------------------------- #

def test_15_existing_rows_and_300_requested_is_refused(sandbox, monkeypatch):
    """
    The state the repository is actually in: a 15-row smoke run on disk, a
    300-draw experiment about to be launched. The old shrink guard allowed
    this, because growing a file looked safe.
    """
    data, _ = sandbox
    before = _seed_main_outputs(data, 15)

    with pytest.raises(SystemExit, match="Refusing to run"):
        _run_cli(monkeypatch, ["--draws", "300", "--no-robustness"])

    for path, digest in before.items():
        assert _sha(path) == digest


def test_800_existing_rows_and_800_requested_is_refused(sandbox, monkeypatch):
    """
    Equal sizes: the probabilistic-variant case. Identical row counts are
    exactly when the old guard was silent and the loss is total.
    """
    data, _ = sandbox
    before = _seed_main_outputs(data, 800)

    with pytest.raises(SystemExit, match="Refusing to run"):
        _run_cli(monkeypatch, ["--draws", "800", "--no-robustness"])

    for path, digest in before.items():
        assert _sha(path) == digest


def test_a_larger_existing_file_is_refused_too(sandbox, monkeypatch):
    data, _ = sandbox
    before = _seed_main_outputs(data, 1200)
    with pytest.raises(SystemExit, match="Refusing to run"):
        _run_cli(monkeypatch, ["--draws", "300", "--no-robustness"])
    for path, digest in before.items():
        assert _sha(path) == digest


# --------------------------------------------------------------------------- #
#  --overwrite permits the intentional replacement                             #
# --------------------------------------------------------------------------- #

def test_overwrite_permits_the_intentional_replacement(sandbox, monkeypatch):
    data, _ = sandbox
    before = _seed_main_outputs(data, 800)

    _run_cli(monkeypatch, ["--draws", "2", "--no-robustness", "--overwrite"])

    for year in runner.YEARS:
        runs = data / f"empirical_runs_{year}.csv"
        assert _sha(runs) != before[runs]
        assert len(pd.read_csv(runs)) == 2


def test_a_clean_directory_needs_no_flag(sandbox, monkeypatch):
    data, _ = sandbox
    _run_cli(monkeypatch, ["--draws", "2", "--no-robustness"])
    assert (data / "empirical_runs_2002.csv").exists()


# --------------------------------------------------------------------------- #
#  Partial sets, and refusing before anything is written                       #
# --------------------------------------------------------------------------- #

def test_a_partial_target_set_is_detected_and_named(sandbox, monkeypatch):
    """
    One stray file from a run that died. Filling the gaps around it would leave
    a directory whose files came from two different runs.
    """
    data, _ = sandbox
    stray = data / "empirical_runs_2022.csv"
    before = _write(stray, 300)

    with pytest.raises(SystemExit, match="partial set"):
        _run_cli(monkeypatch, ["--draws", "300", "--no-robustness"])

    assert _sha(stray) == before


def test_refusal_happens_before_anything_is_written(sandbox, monkeypatch):
    """
    The refusal must precede the first write, not abort halfway through.

    Only the 2022 file exists here. 2002 is processed first, so a guard applied
    per-file at write time would have written both 2002 outputs before noticing.
    """
    data, _ = sandbox
    stray = data / "empirical_candidate_draws_2022.csv"
    _write(stray, 300)

    with pytest.raises(SystemExit):
        _run_cli(monkeypatch, ["--draws", "2", "--no-robustness"])

    produced = sorted(p.name for p in data.glob("*.csv"))
    assert produced == ["empirical_candidate_draws_2022.csv"], \
        f"the refusal wrote something first: {produced}"


def test_robustness_outputs_are_guarded_too(sandbox, monkeypatch):
    data, _ = sandbox
    rob = data / "empirical_robustness_2002.csv"
    before = _write(rob, 300)

    with pytest.raises(SystemExit, match="Refusing to run"):
        _run_cli(monkeypatch, ["--draws", "2", "--robust-draws", "2"])

    assert _sha(rob) == before


def test_probabilistic_variants_are_guarded_under_their_own_names(sandbox,
                                                                  monkeypatch):
    """The suffixed outputs get the same protection as the baseline."""
    data, _ = sandbox
    p = data / "empirical_runs_prob_signal_2002.csv"
    before = _write(p, 800)

    with pytest.raises(SystemExit, match="Refusing to run"):
        _run_cli(monkeypatch, ["--sincere-init", "probabilistic",
                               "--salience-source", "signal", "--draws", "800"])
    assert _sha(p) == before


# --------------------------------------------------------------------------- #
#  --quick stays isolated                                                      #
# --------------------------------------------------------------------------- #

def test_quick_is_unaffected_by_a_full_directory(sandbox, monkeypatch):
    """
    A quick run targets data/smoke/, so a full data/ cannot block it and it
    cannot touch anything there.
    """
    data, smoke = sandbox
    before = _seed_main_outputs(data, 300)

    _run_cli(monkeypatch, ["--quick", "--draws", "1", "--no-robustness"])

    for path, digest in before.items():
        assert _sha(path) == digest
    assert (smoke / "empirical_runs_2002.csv").exists()


def test_a_second_quick_run_is_refused_in_the_smoke_dir(sandbox, monkeypatch):
    """The policy applies wherever the outputs land, smoke included."""
    _, smoke = sandbox
    _run_cli(monkeypatch, ["--quick", "--draws", "1", "--no-robustness"])
    with pytest.raises(SystemExit, match="Refusing to run"):
        _run_cli(monkeypatch, ["--quick", "--draws", "1", "--no-robustness"])
    _run_cli(monkeypatch, ["--quick", "--draws", "1", "--no-robustness",
                           "--overwrite"])


# --------------------------------------------------------------------------- #
#  The message has to be actionable                                            #
# --------------------------------------------------------------------------- #

def test_the_refusal_names_the_files_and_the_way_out(sandbox, monkeypatch):
    data, _ = sandbox
    _seed_main_outputs(data, 42)

    with pytest.raises(SystemExit) as exc:
        _run_cli(monkeypatch, ["--draws", "300", "--no-robustness"])

    msg = str(exc.value)
    assert "empirical_runs_2002.csv" in msg
    assert "42 rows" in msg
    assert "--overwrite" in msg
    assert "nothing has been touched" in msg


def test_the_replay_has_no_resume_flag_to_conflict_with():
    """
    --overwrite must be incompatible with any resume mechanism. The replay has
    none (each invocation rewrites from the start), so there is nothing to
    conflict with, and this pins that fact: if a resume is ever added, this
    test fails and the mutual exclusion has to be written.
    """
    import argparse
    parser_flags = []

    real_add = argparse.ArgumentParser.add_argument

    def spy(self, *args, **kwargs):
        parser_flags.extend(a for a in args if isinstance(a, str))
        return real_add(self, *args, **kwargs)

    argparse.ArgumentParser.add_argument = spy
    try:
        try:
            sys.argv = ["empirical_2002_2022.py", "--help"]
            runner.main()
        except SystemExit:
            pass
    finally:
        argparse.ArgumentParser.add_argument = real_add

    assert "--overwrite" in parser_flags
    assert "--resume" not in parser_flags
