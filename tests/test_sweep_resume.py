"""
test_sweep_resume.py
--------------------
The behavioural sweep is roughly 3.5 hours per year, so an interruption must
cost one draw, not the whole run.  These tests cover --resume: that it keeps
completed work, that it refuses anything it cannot prove compatible, and, the
property that matters most, that a resumed sweep and an uninterrupted one
produce the same file.

No simulation runs here.  run_one is replaced by an analytic stand-in that is a
pure function of the per-run seed, which is what makes "same output" a
meaningful assertion: if resuming perturbed the seed schedule, the stand-in
would return different numbers and the comparison would fail.

Run with:  pytest tests/test_sweep_resume.py
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "core_model"))
sys.path.insert(0, str(REPO / "analysis" / "empirical"))

import behavioral_sweep as sweep

YEAR = 2002
SEED = 20020422
N_DRAWS = 6
N_REPEATS = 3


# --------------------------------------------------------------------------- #
#  Fixtures                                                                    #
# --------------------------------------------------------------------------- #

class _Interrupt(RuntimeError):
    """Stands in for a Ctrl+C or a killed session."""


@pytest.fixture
def harness(monkeypatch):
    """
    Replace the simulation with an analytic function of the run seed.

    Returns a dict with 'seeds' (every seed the sweep asked for, in order) and
    'stop_after', which can be set to make the stand-in raise partway through.
    """
    state = {"seeds": [], "stop_after": None}

    def fake_run_one(params, bundle, voters, seed):
        if state["stop_after"] is not None and \
                len(state["seeds"]) >= state["stop_after"]:
            raise _Interrupt("interrupted")
        state["seeds"].append(seed)
        K = len(bundle["positions"])
        return {
            # Pure in (seed, tau_hat): no RNG, so any change in the seed
            # schedule shows up as a changed number.
            "delta_cenp": math.sin(seed * 1e-4) * params["tau_hat"],
            "final_enp": 2.0 + math.cos(seed * 1e-4),
            "tau_absolute": sweep.tau_absolute(params["tau_hat"], K),
            "K": K,
        }

    monkeypatch.setattr(sweep, "run_one", fake_run_one)
    monkeypatch.setattr(sweep, "N_VOTERS", 20)
    return state


def _sweep(out, **kw):
    kw.setdefault("year", YEAR)
    kw.setdefault("n_draws", N_DRAWS)
    kw.setdefault("n_repeats", N_REPEATS)
    kw.setdefault("seed", SEED)
    return sweep.run_sweep(out=Path(out), **kw)


# --------------------------------------------------------------------------- #
#  Resume reproduces an uninterrupted run                                      #
# --------------------------------------------------------------------------- #

def test_resumed_sweep_matches_an_uninterrupted_one(tmp_path, harness):
    """The whole point: interrupting and resuming changes nothing."""
    whole = tmp_path / "whole.csv"
    _sweep(whole)
    reference = whole.read_text()
    reference_seeds = list(harness["seeds"])

    # Now the same sweep, killed after two draws' worth of runs.
    part = tmp_path / "part.csv"
    harness["seeds"].clear()
    harness["stop_after"] = 2 * N_REPEATS
    with pytest.raises(_Interrupt):
        _sweep(part)

    partial = pd.read_csv(part)
    assert len(partial) == 2, "row-by-row flushing did not keep completed draws"

    harness["stop_after"] = None
    _sweep(part, resume=True)

    assert part.read_text() == reference, \
        "resumed output differs from the uninterrupted run"
    assert harness["seeds"] == reference_seeds, \
        "resuming changed the per-run seed schedule"


def test_resume_does_not_recompute_completed_draws(tmp_path, harness):
    """Completed work is kept, not redone."""
    out = tmp_path / "s.csv"
    harness["stop_after"] = 3 * N_REPEATS
    with pytest.raises(_Interrupt):
        _sweep(out)

    harness["seeds"].clear()
    harness["stop_after"] = None
    _sweep(out, resume=True)

    # Only the remaining three draws should have been simulated.
    assert len(harness["seeds"]) == (N_DRAWS - 3) * N_REPEATS
    redone = {s for s in harness["seeds"]
              if s < SEED + 1000 * (3 + 1)}
    assert not redone, f"resume recomputed completed draws: {sorted(redone)}"


def test_seed_schedule_is_the_documented_formula(tmp_path, harness):
    """seed + 1000 * (draw + 1) + repeat, unchanged by any of this."""
    out = tmp_path / "s.csv"
    _sweep(out)
    expected = [SEED + 1000 * (d + 1) + r
                for d in range(N_DRAWS) for r in range(N_REPEATS)]
    assert harness["seeds"] == expected


def test_output_is_sorted_by_draw(tmp_path, harness):
    """Append order stops mattering once the run is finalised."""
    out = tmp_path / "s.csv"
    harness["stop_after"] = 2 * N_REPEATS
    with pytest.raises(_Interrupt):
        _sweep(out)
    harness["stop_after"] = None
    _sweep(out, resume=True)

    df = pd.read_csv(out)
    assert df["draw"].tolist() == sorted(df["draw"].tolist())
    assert df["draw"].tolist() == list(range(N_DRAWS))
    assert list(df.columns) == sweep.OUTPUT_COLS


def test_resume_of_a_complete_file_is_a_no_op(tmp_path, harness):
    out = tmp_path / "s.csv"
    _sweep(out)
    before = out.read_text()
    harness["seeds"].clear()
    _sweep(out, resume=True)
    assert out.read_text() == before
    assert harness["seeds"] == []


def test_resume_of_a_complete_file_leaves_bytes_and_mtime_untouched(tmp_path,
                                                                   harness):
    """A complete resume must not rewrite the file at all.

    Byte equality alone would still pass if the file were rewritten with
    identical content, so the modification time is checked too: the correct
    behaviour for an already-complete run is to touch nothing.
    """
    import hashlib
    import os
    import time

    out = tmp_path / "s.csv"
    _sweep(out)
    before_bytes = out.read_bytes()
    before_sha = hashlib.sha256(before_bytes).hexdigest()
    before_mtime = os.stat(out).st_mtime_ns

    time.sleep(0.01)          # so a rewrite would be visible in st_mtime_ns
    harness["seeds"].clear()
    _sweep(out, resume=True)

    assert out.read_bytes() == before_bytes
    assert hashlib.sha256(out.read_bytes()).hexdigest() == before_sha
    assert os.stat(out).st_mtime_ns == before_mtime, \
        "the file was rewritten even though every draw was already complete"
    assert harness["seeds"] == []


def test_interrupted_then_resumed_is_byte_identical_to_uninterrupted(tmp_path,
                                                                     harness):
    """The property the canonical serialisation exists to guarantee.

    Unlike the complete-file no-op, this path really does merge new rows with
    old ones and rewrite the file, so it depends on finalisation being a fixed
    point rather than on skipping the write.
    """
    import hashlib

    clean = tmp_path / "clean.csv"
    _sweep(clean)
    clean_sha = hashlib.sha256(clean.read_bytes()).hexdigest()

    broken = tmp_path / "broken.csv"
    harness["seeds"].clear()
    harness["stop_after"] = N_REPEATS * 2          # die partway through
    with pytest.raises(_Interrupt):
        _sweep(broken)
    harness["stop_after"] = None
    assert broken.exists() and len(pd.read_csv(broken)) < N_DRAWS

    harness["seeds"].clear()
    _sweep(broken, resume=True)

    assert hashlib.sha256(broken.read_bytes()).hexdigest() == clean_sha
    assert broken.read_bytes() == clean.read_bytes()


def test_resume_without_an_existing_file_starts_fresh(tmp_path, harness):
    out = tmp_path / "s.csv"
    _sweep(out, resume=True)
    assert len(pd.read_csv(out)) == N_DRAWS


# --------------------------------------------------------------------------- #
#  Refusals: incompatible runs must never be merged                            #
# --------------------------------------------------------------------------- #

def _partial(tmp_path, harness, n_done=2):
    out = tmp_path / "s.csv"
    harness["stop_after"] = n_done * N_REPEATS
    with pytest.raises(_Interrupt):
        _sweep(out)
    harness["stop_after"] = None
    return out


@pytest.mark.parametrize("field,value", [
    ("year", 2022),
    ("seed", 999),
    ("n_draws", N_DRAWS + 1),
    ("n_repeats", N_REPEATS + 1),
])
def test_resume_refuses_an_incompatible_run(tmp_path, harness, field, value):
    """year, seed, n_draws and n_repeats each have to match."""
    out = _partial(tmp_path, harness)
    with pytest.raises(SystemExit, match="Refusing to resume"):
        _sweep(out, resume=True, **{field: value})


def test_resume_refuses_when_the_design_fingerprint_differs(tmp_path, harness):
    """
    The last line of defence: matching metadata but a different design.

    Only the sidecar's fingerprint is corrupted here, so every scalar check
    passes and the design comparison is what has to catch it.
    """
    out = _partial(tmp_path, harness)
    meta_path = sweep.meta_path(out)
    meta = json.loads(meta_path.read_text())
    meta["design_sha256"] = "0" * 64
    meta_path.write_text(json.dumps(meta))

    with pytest.raises(SystemExit, match="does not match"):
        _sweep(out, resume=True)


def test_resume_refuses_rows_that_contradict_the_design(tmp_path, harness):
    """A row whose parameters are not the design's parameters for that draw."""
    out = _partial(tmp_path, harness)
    df = pd.read_csv(out)
    df.loc[0, "mu"] = df.loc[0, "mu"] + 0.25
    df.to_csv(out, index=False)

    with pytest.raises(SystemExit, match="the design says"):
        _sweep(out, resume=True)


def test_resume_refuses_without_the_sidecar(tmp_path, harness):
    out = _partial(tmp_path, harness)
    sweep.meta_path(out).unlink()
    with pytest.raises(SystemExit, match="cannot be identified"):
        _sweep(out, resume=True)


def test_resume_refuses_an_unreadable_sidecar(tmp_path, harness):
    out = _partial(tmp_path, harness)
    sweep.meta_path(out).write_text("{not json")
    with pytest.raises(SystemExit, match="not readable JSON"):
        _sweep(out, resume=True)


def test_resume_refuses_a_stale_schema(tmp_path, harness):
    """A partial file from before tau_absolute existed must not be extended."""
    out = _partial(tmp_path, harness)
    meta_path = sweep.meta_path(out)
    meta = json.loads(meta_path.read_text())
    meta["schema_version"] = 1
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(SystemExit, match="schema_version differs"):
        _sweep(out, resume=True)


# --------------------------------------------------------------------------- #
#  Malformed and duplicate keys                                                #
# --------------------------------------------------------------------------- #

def test_resume_detects_duplicate_draws(tmp_path, harness):
    out = _partial(tmp_path, harness)
    df = pd.read_csv(out)
    pd.concat([df, df.iloc[[0]]]).to_csv(out, index=False)
    with pytest.raises(SystemExit, match="duplicate draw id"):
        _sweep(out, resume=True)


def test_resume_detects_a_missing_draw_id(tmp_path, harness):
    out = _partial(tmp_path, harness)
    df = pd.read_csv(out)
    df.loc[0, "draw"] = np.nan
    df.to_csv(out, index=False)
    with pytest.raises(SystemExit, match="missing or non-numeric draw id"):
        _sweep(out, resume=True)


def test_resume_detects_a_non_integer_draw_id(tmp_path, harness):
    out = _partial(tmp_path, harness)
    df = pd.read_csv(out)
    df["draw"] = df["draw"].astype(float)
    df.loc[0, "draw"] = 0.5
    df.to_csv(out, index=False)
    with pytest.raises(SystemExit, match="non-integer draw ids"):
        _sweep(out, resume=True)


def test_resume_detects_an_out_of_range_draw_id(tmp_path, harness):
    out = _partial(tmp_path, harness)
    df = pd.read_csv(out)
    df.loc[0, "draw"] = N_DRAWS + 5
    df.to_csv(out, index=False)
    with pytest.raises(SystemExit, match="outside"):
        _sweep(out, resume=True)


def test_resume_detects_a_missing_column(tmp_path, harness):
    out = _partial(tmp_path, harness)
    df = pd.read_csv(out).drop(columns=["tau_absolute"])
    df.to_csv(out, index=False)
    with pytest.raises(SystemExit, match="missing column"):
        _sweep(out, resume=True)


def test_resume_detects_a_truncated_final_row(tmp_path, harness):
    """A kill mid-write leaves a row with a missing value, not a missing line."""
    out = _partial(tmp_path, harness)
    df = pd.read_csv(out)
    df.loc[len(df) - 1, "mean_delta_cenp"] = np.nan
    df.to_csv(out, index=False)
    with pytest.raises(SystemExit, match="non-finite"):
        _sweep(out, resume=True)


def test_resume_detects_mismatched_row_bookkeeping(tmp_path, harness):
    """The rows' own n_repeats/seed columns must agree with the sidecar."""
    out = _partial(tmp_path, harness)
    df = pd.read_csv(out)
    df.loc[0, "n_repeats"] = N_REPEATS + 7
    df.to_csv(out, index=False)
    with pytest.raises(SystemExit, match="n_repeats values"):
        _sweep(out, resume=True)


# --------------------------------------------------------------------------- #
#  Overwrite semantics                                                         #
# --------------------------------------------------------------------------- #

def test_existing_output_is_not_silently_destroyed(tmp_path, harness):
    """
    Without a flag, a second launch must stop.

    The old behaviour was an unconditional unlink, which is how a seven-hour
    run could be thrown away by re-running the same command.
    """
    out = tmp_path / "s.csv"
    _sweep(out)
    before = out.read_text()

    with pytest.raises(SystemExit, match="already exists"):
        _sweep(out)
    assert out.read_text() == before


def test_overwrite_starts_again(tmp_path, harness):
    out = tmp_path / "s.csv"
    harness["stop_after"] = 2 * N_REPEATS
    with pytest.raises(_Interrupt):
        _sweep(out)
    harness["stop_after"] = None

    _sweep(out, overwrite=True)
    assert len(pd.read_csv(out)) == N_DRAWS


def test_resume_and_overwrite_are_mutually_exclusive(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", [
        "behavioral_sweep.py", "--resume", "--overwrite",
        "--out", str(tmp_path / "s.csv")])
    with pytest.raises(SystemExit, match="mutually exclusive"):
        sweep.main()


# --------------------------------------------------------------------------- #
#  Sidecar contents                                                            #
# --------------------------------------------------------------------------- #

def test_sidecar_records_what_resume_validates(tmp_path, harness):
    out = tmp_path / "s.csv"
    _sweep(out)
    meta = json.loads(sweep.meta_path(out).read_text())
    assert meta["year"] == YEAR
    assert meta["seed"] == SEED
    assert meta["n_draws"] == N_DRAWS
    assert meta["n_repeats"] == N_REPEATS
    assert len(meta["design_sha256"]) == 64
    assert meta["schema_version"] == sweep.SCHEMA_VERSION


def test_design_fingerprint_is_sensitive_to_the_design(tmp_path):
    a = sweep.build_design(N_DRAWS, np.random.default_rng(SEED))
    b = sweep.build_design(N_DRAWS, np.random.default_rng(SEED))
    c = sweep.build_design(N_DRAWS, np.random.default_rng(SEED + 1))
    assert sweep.design_fingerprint(a) == sweep.design_fingerprint(b)
    assert sweep.design_fingerprint(a) != sweep.design_fingerprint(c)
