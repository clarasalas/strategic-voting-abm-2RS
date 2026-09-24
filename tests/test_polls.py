"""
Checks on data/polls_{2002,2022}.csv, built by tools/build_polls_from_wikipedia.py
from fixed revisions of the French Wikipedia poll lists.

The earlier 2022 file had LO/NPA and EELV/PS swapped: its values were copied in
the page's column order under a header in a different order.  These tests pin
the columns by name against values read off the page by hand, so a column that
moves to the wrong candidate fails here.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import build_polls_from_wikipedia as bp                         # noqa: E402
from core_model.empirical_data import _to_float                  # noqa: E402

DATA = REPO / "data"


def polls(year):
    return pd.read_csv(DATA / f"polls_{year}.csv", dtype=str, keep_default_na=False)


def test_sources_are_pinned_revisions():
    assert bp.SOURCES[2002]["revision"] == 236399441
    assert bp.SOURCES[2022]["revision"] == 235575713


@pytest.mark.parametrize("year,n", [(2002, 39), (2022, 81)])
def test_poll_counts(year, n):
    assert len(polls(year)) == n


@pytest.mark.parametrize("year", [2002, 2022])
def test_columns_are_exactly_the_modelled_candidates(year):
    df = polls(year)
    fixed = ["source", "date", "fieldwork", "rolling", "below_threshold"]
    assert df.columns[:5].tolist() == fixed
    modelled = pd.read_csv(DATA / f"party_positions_{year}.csv")["party"]
    assert sorted(df.columns[5:]) == sorted(modelled)


# Values read off the pinned revisions by hand, by candidate name.
HAND_CHECKED = {
    # Ipsos, 8 avril 2022: Arthaud 0,5 %, Poutou 1 %, Hidalgo 2 %, Jadot 5 %
    (2022, "Ipsos", "08/04/2022"): {"LO": 0.005, "NPA": 0.01, "PS": 0.02,
                                    "EELV": 0.05, "RE": 0.265, "RN": 0.225},
    # BVA, 18 avril 2002: Jospin 18 %, Chirac 19 %, Le Pen 14 %
    (2002, "BVA", "18/04/2002"): {"PS": 0.18, "RPR": 0.19, "FN": 0.14,
                                  "LO": 0.08, "LCR": 0.035},
}


@pytest.mark.parametrize("key", sorted(HAND_CHECKED))
def test_hand_checked_values(key):
    year, source, date = key
    df = polls(year)
    row = df[(df["source"] == source) & (df["date"] == date)]
    assert len(row) == 1
    for party, value in HAND_CHECKED[key].items():
        assert _to_float(row.iloc[0][party]) == pytest.approx(value, abs=1e-12), party


def test_jadot_ahead_of_hidalgo_in_the_last_week():
    # every poll of the final week, 2-8 April 2022, had Jadot ahead
    df = polls(2022)
    last = df[pd.to_datetime(df["date"], dayfirst=True) >= "2022-04-02"]
    assert len(last) > 5
    assert (last["EELV"].map(_to_float) > last["PS"].map(_to_float)).all()


@pytest.mark.parametrize("year,low", [(2002, 0.93), (2022, 0.97)])
def test_each_poll_sums_to_about_one(year, low):
    # 2002 excludes Gluckstein (up to 0.5 %) and, in March, Pasqua (up to
    # 3.5 %); the loader renormalises each poll.  Rounding moves the rest.
    df = polls(year)
    parties = df.columns[5:]
    total = df[parties].apply(lambda c: c.map(_to_float)).sum(axis=1)
    assert total.between(low, 1.02).all()


def test_below_threshold_cells_are_the_known_four():
    df = polls(2022)
    flagged = df[df["below_threshold"] != ""]
    assert flagged["below_threshold"].tolist() == ["LO"] * 4
    # half the published threshold: 0,5 % for "<1 %", 0,25 % for "<0,5 %"
    assert sorted(flagged["LO"].map(_to_float)) == [0.0025, 0.005, 0.005, 0.005]
    assert (polls(2002)["below_threshold"] == "").all()


def test_dropped_polls_are_recorded():
    d = pd.read_csv(DATA / "polls_dropped.csv", dtype=str)
    assert d[["year", "source", "fieldwork", "not_tested"]].values.tolist() == [
        ["2002", "Ifop", "23 et 24 mars", "MNR"],
        ["2002", "Ifop", "21 et 22 mars", "PRG"],
    ]


@pytest.mark.parametrize("cell,want", [("8 %", (0.08, False)), ("0,5 %", (0.005, False)),
                                       ("<1\xa0%", (0.005, True)), ("<0,5 %", (0.0025, True)),
                                       ("12,5 %[3]", (0.125, False))])
def test_share_parsing(cell, want):
    got = bp.share(cell, "test")
    assert got[0] == pytest.approx(want[0]) and got[1] == want[1]


@pytest.mark.parametrize("cell", ["-", "", "n.c.", "~2 %"])
def test_share_refuses_anything_else(cell):
    with pytest.raises(ValueError):
        bp.share(cell, "test")


@pytest.mark.parametrize("text,want", [("18 avril", "2002-04-18"),
                                       ("17 et 18 avril", "2002-04-18"),
                                       ("du 28 février au 1er mars", "2002-03-01"),
                                       ("31 mars - 4 avril", "2002-04-04")])
def test_end_date(text, want):
    assert bp.end_date(text, 2002) == pd.Timestamp(want)
