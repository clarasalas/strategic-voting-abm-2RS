"""
Canonical CSV serialisation: lossless, byte-idempotent, atomic.

`finalise_output` reads a sweep CSV and writes it back, so it must be a
fixed point: finalising twice has to produce the same bytes as finalising
once. Otherwise a resumed run and an uninterrupted run yield different files
from identical numbers -- which is exactly what CI caught on 2026-08-22, on a
platform whose float values differ from the development machine's.

The cause was the reader, not the writer: pandas' default float parser is fast
but not correctly rounded, so it can return a double one ulp from the text.
These tests pin both halves of the contract, and they pin the *properties*
rather than a particular pandas version, so a future release that changes the
default float format fails here loudly.
"""

import hashlib
import io
import math
import os
import random
import struct
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis" / "empirical"))
sys.path.insert(0, str(REPO / "core_model"))

import behavioral_sweep as bs  # noqa: E402


# --------------------------------------------------------------------------- #
#  Difficult values
# --------------------------------------------------------------------------- #

# The value shape that failed in CI, plus the classes most likely to break a
# text round trip.
NASTY = [
    0.06933728008356,          # from the CI failure diff
    2.145268755345708e-05,     # neighbouring column in the same row
    6.0933728008356,
    0.1, 1 / 3, 0.30000000000000004,
    0.0, -0.0,                 # signed zero: "%.17g" loses the sign here
    5e-324,                    # smallest subnormal
    1e-300, 1e300,
    1.7976931348623157e308,    # largest finite double
    2.0, -1.5, 1e16, 1e17,     # integer-like floats
    123456789.123456789,
    -2.2250738585072014e-308,  # smallest normal, negative
]


def _random_doubles(n, seed=20020422):
    """Uniformly random *bit patterns*, which is far harsher than random
    numbers: it samples the whole exponent range including subnormals."""
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        f = struct.unpack("<d", struct.pack("<Q", rng.getrandbits(64)))[0]
        if math.isfinite(f):
            out.append(f)
    return out


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _frame(values):
    """A frame with the sweep's real column set, so column order and the
    integer/string columns are exercised alongside the floats."""
    n = len(values)
    return pd.DataFrame({
        "draw": list(range(n)),
        "tau_hat": values,
        "tau_absolute": [v / 7 for v in values],
        "K": [15] * n,
        "mu": values,
        "alpha": [abs(v) % 1 for v in values],
        "rho_pi": [50.0] * n,
        "beta": values,
        "mean_delta_cenp": values,
        "mean_final_enp": [abs(v) for v in values],
        "std_delta_cenp": [abs(v) / 3 for v in values],
        "n_repeats": [4] * n,
        "seed": [20020422] * n,
    })[bs.OUTPUT_COLS]


# --------------------------------------------------------------------------- #
#  Round-trip exactness
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("value", NASTY)
def test_each_difficult_value_survives_a_round_trip_bitwise(tmp_path, value):
    """Not "close to" -- the identical double, including the sign of zero."""
    out = tmp_path / "s.csv"
    bs.write_canonical(pd.DataFrame({"x": [value]}), out)
    back = bs.read_canonical(out)["x"].to_numpy()[0]
    assert np.float64(back).tobytes() == np.float64(value).tobytes()


def test_random_bit_patterns_survive_a_round_trip_bitwise(tmp_path):
    values = _random_doubles(5000)
    out = tmp_path / "s.csv"
    bs.write_canonical(pd.DataFrame({"x": values}), out)
    back = bs.read_canonical(out)["x"].to_numpy()
    assert back.tobytes() == np.asarray(values, dtype=np.float64).tobytes()


def test_negative_zero_keeps_its_sign(tmp_path):
    """`%.17g` writes -0.0 as "-0", which reads back as +0.0. That is why the
    writer is pandas' shortest round-trip form and not a fixed precision."""
    out = tmp_path / "s.csv"
    bs.write_canonical(pd.DataFrame({"x": [-0.0, 0.0]}), out)
    back = bs.read_canonical(out)["x"].to_numpy()
    assert bool(np.signbit(back[0])) is True
    assert bool(np.signbit(back[1])) is False


# --------------------------------------------------------------------------- #
#  Idempotency
# --------------------------------------------------------------------------- #

def test_finalising_three_times_gives_the_same_sha256(tmp_path):
    out = tmp_path / "s.csv"
    bs.write_canonical(_frame(NASTY + _random_doubles(500)), out)
    digests = []
    for _ in range(3):
        bs.finalise_output(out)
        digests.append(_sha(out))
    assert len(set(digests)) == 1, f"finalisation is not a fixed point: {digests}"


def test_finalisation_preserves_parsed_values_exactly(tmp_path):
    out = tmp_path / "s.csv"
    original = _frame(NASTY + _random_doubles(500))
    bs.write_canonical(original, out)
    bs.finalise_output(out)
    back = bs.read_canonical(out)
    for c in bs.OUTPUT_COLS:
        if original[c].dtype.kind == "f":
            assert back[c].to_numpy().tobytes() == original[c].to_numpy().tobytes(), c
        else:
            assert back[c].tolist() == original[c].tolist(), c


def test_finalisation_preserves_column_order_and_identifier_columns(tmp_path):
    out = tmp_path / "s.csv"
    df = _frame(NASTY)
    shuffled = df[list(reversed(bs.OUTPUT_COLS))]
    bs.write_canonical(shuffled, out)
    result = bs.finalise_output(out)
    assert list(result.columns) == bs.OUTPUT_COLS
    back = bs.read_canonical(out)
    assert list(back.columns) == bs.OUTPUT_COLS
    for c in ("draw", "K", "n_repeats", "seed"):
        assert back[c].dtype.kind in "iu", f"{c} stopped being an integer column"
        assert back[c].tolist() == df[c].tolist()


def test_finalisation_sorts_by_draw_without_disturbing_values(tmp_path):
    out = tmp_path / "s.csv"
    df = _frame(NASTY).sample(frac=1.0, random_state=7).reset_index(drop=True)
    bs.write_canonical(df, out)
    result = bs.finalise_output(out)
    assert result["draw"].tolist() == sorted(df["draw"].tolist())
    by_draw = df.set_index("draw")["tau_hat"]
    for d, v in zip(result["draw"], result["tau_hat"]):
        assert np.float64(v).tobytes() == np.float64(by_draw.loc[d]).tobytes()


# --------------------------------------------------------------------------- #
#  Text form
# --------------------------------------------------------------------------- #

def test_written_files_use_unix_line_endings_and_utf8(tmp_path):
    out = tmp_path / "s.csv"
    bs.write_canonical(_frame(NASTY), out)
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    raw.decode("utf-8")


def test_string_columns_are_preserved(tmp_path):
    """The sweep has no string column, but the writer is shared; a label must
    survive unchanged."""
    out = tmp_path / "s.csv"
    df = pd.DataFrame({"variant": ["perturbed_positions", "resampled_voters"],
                       "x": [0.1, -0.0]})
    bs.write_canonical(df, out)
    back = bs.read_canonical(out)
    assert back["variant"].tolist() == df["variant"].tolist()


# --------------------------------------------------------------------------- #
#  Guard rails and atomicity
# --------------------------------------------------------------------------- #

def test_finalise_refuses_a_non_finite_value(tmp_path):
    out = tmp_path / "s.csv"
    df = _frame(NASTY)
    df.loc[0, "mean_delta_cenp"] = np.nan
    bs.write_canonical(df, out)
    with pytest.raises(SystemExit, match="non-finite"):
        bs.finalise_output(out)


def test_a_failed_write_leaves_the_previous_file_intact(tmp_path, monkeypatch):
    """Atomic replace: a crash mid-write must not truncate the destination."""
    out = tmp_path / "s.csv"
    bs.write_canonical(_frame(NASTY), out)
    before_bytes, before_sha = out.read_bytes(), _sha(out)

    def boom(self, *a, **k):
        raise RuntimeError("simulated failure mid-write")

    monkeypatch.setattr(pd.DataFrame, "to_csv", boom)
    with pytest.raises(RuntimeError, match="simulated failure"):
        bs.write_canonical(_frame(NASTY), out)

    assert out.read_bytes() == before_bytes
    assert _sha(out) == before_sha


def test_a_failed_write_leaves_no_temporary_file_behind(tmp_path, monkeypatch):
    out = tmp_path / "s.csv"
    bs.write_canonical(_frame(NASTY), out)

    def boom(self, *a, **k):
        raise RuntimeError("simulated failure mid-write")

    monkeypatch.setattr(pd.DataFrame, "to_csv", boom)
    with pytest.raises(RuntimeError):
        bs.write_canonical(_frame(NASTY), out)

    leftovers = [p.name for p in tmp_path.iterdir() if p.name != out.name]
    assert leftovers == [], f"temporary files left behind: {leftovers}"


# --------------------------------------------------------------------------- #
#  The property the writer choice rests on
# --------------------------------------------------------------------------- #

def test_the_default_float_format_is_shortest_round_trip(tmp_path):
    """pandas does not document its default float format as shortest
    round-trip. The canonical writer depends on it, so it is pinned here: if a
    future pandas changes it, this fails rather than the sweep quietly
    producing files that never settle."""
    values = NASTY + _random_doubles(2000)
    out = tmp_path / "s.csv"
    bs.write_canonical(pd.DataFrame({"x": values}), out)
    text = out.read_text(encoding="utf-8")
    for line, want in zip(text.splitlines()[1:], values):
        assert float(line) == want
        assert len(line) <= len(f"{want!r}"), (
            f"{line} is longer than the shortest round-tripping form {want!r}")
