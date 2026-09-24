"""
Checks on the committed survey-derived inputs in data/cses/ and data/ipsos/.

The raw CSES files are not in the repository, so this cannot rebuild them;
tools/build_cses_inputs.py verifies the codebook mappings when it runs.  What
this pins:

* the Ipsos wave 9 transcription is internally consistent, and its means are
  the published ones;
* the main specification takes its values from the sources the README names
  (2002: screened CSES candidate means; 2022: Ipsos means), and the bridge is
  used for exactly the candidates no survey measures;
* every specification file covers every modelled candidate on the 0-10 scale;
* the model loads the files in place of the current ones.
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import core_model.empirical_data as ed
from core_model.empirical_data import _to_float

DATA = Path(__file__).resolve().parent.parent / "data"
CSES = DATA / "cses"
IPSOS = DATA / "ipsos" / "candidate_positions_2022_wave9.csv"
PREVIOUS = DATA / "previous_inputs"      # inputs of the 2026-08-21 run
YEARS = (2002, 2022)

SPEC_FILES = {
    2002: ["party_positions_2002.csv", "party_positions_2002_unscreened_means.csv",
           "party_positions_2002_party_items.csv"],
    2022: ["party_positions_2022.csv", "party_positions_2022_cses_party_items.csv"],
}


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def num(series):
    return series.map(_to_float)


# --------------------------------------------------------------------------- #
#  Ipsos wave 9                                                               #
# --------------------------------------------------------------------------- #

# Published means, page 48 of the wave 9 report, column "Avril 2022" --
# written out here by hand, independently of the CSV, so a transcription edit
# cannot pass silently.
IPSOS_PUBLISHED = {"LO": 1.2, "NPA": 1.4, "LFI": 1.6, "PCF": 1.9, "PS": 3.1,
                   "EELV": 3.3, "RES": 4.9, "RE": 6.4, "LR": 7.4, "DLF": 7.8,
                   "RN": 8.8, "REC": 9.1}


def test_ipsos_means_are_the_published_ones():
    df = read(IPSOS).set_index("party")
    assert set(df.index) == set(IPSOS_PUBLISHED)
    for party, mean in IPSOS_PUBLISHED.items():
        assert _to_float(df.loc[party, "mean_0_10"]) == mean, party


def test_ipsos_rows_are_internally_consistent():
    df = read(IPSOS)
    bins = ["pct_0_1", "pct_2_3", "pct_4", "pct_5", "pct_6", "pct_7_8", "pct_9_10"]
    b = df[bins + ["pct_never_heard", "pct_dont_know"]].astype(int)
    assert (b.sum(axis=1) == 100).all()
    # the published group totals agree with the bins, up to rounding
    groups = {"pct_left_0_3": bins[:2], "pct_centre_4_6": bins[2:5],
              "pct_right_7_10": bins[5:]}
    for g, cols in groups.items():
        assert (abs(df[cols].astype(int).sum(axis=1) - df[g].astype(int)) <= 1).all(), g


def test_ipsos_covers_every_modelled_2022_candidate():
    modelled = read(PREVIOUS / "party_positions_2022.csv")["party"]
    assert sorted(read(IPSOS)["party"]) == sorted(modelled)


# --------------------------------------------------------------------------- #
#  Voters                                                                     #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year", YEARS)
def test_voter_shares_sum_to_one_on_0_10(year):
    df = read(CSES / f"voters_ideology_{year}.csv")
    assert df["ideological_scale"].astype(int).tolist() == list(range(11))
    assert set(df["scale"]) == {"0-10"}
    share = num(df["share"]).to_numpy()
    assert (share >= 0).all()
    assert share.sum() == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------- #
#  Main specification                                                         #
# --------------------------------------------------------------------------- #

def test_main_2002_is_the_screened_candidate_mean_where_measured():
    main = read(CSES / "party_positions_2002.csv").set_index("party")
    table = read(CSES / "candidate_positions_2002.csv").set_index("party")
    for party, row in table.iterrows():
        assert main.loc[party, "position_source"] == "cses_candidate_placement"
        assert _to_float(main.loc[party, "left_right_position"]) == pytest.approx(
            _to_float(row["candidate_weighted_mean_screened_0_10"]), abs=1e-9)


def test_main_2022_is_ipsos_for_every_candidate():
    main = read(CSES / "party_positions_2022.csv").set_index("party")
    ipsos = read(IPSOS).set_index("party")
    assert set(main["position_source"]) == {"ipsos_candidate_placement"}
    for party in main.index:
        assert main.loc[party, "left_right_position"] == ipsos.loc[party, "mean_0_10"]


def test_scale_screen_drops_only_reversed_respondents():
    sc = read(CSES / "scale_screen.csv").iloc[0]
    assert (sc["screen_left"], sc["screen_right"]) == ("LO", "FN")
    assert 0 < int(sc["n_dropped"]) < int(sc["n_placed_both"]) <= int(sc["n_study"])
    # the screen is what moves Le Pen away from Chirac
    main = read(CSES / "party_positions_2002.csv").set_index("party")
    raw = read(CSES / "party_positions_2002_unscreened_means.csv").set_index("party")
    gap = lambda d: _to_float(d.loc["FN", "left_right_position"]) - _to_float(d.loc["RPR", "left_right_position"])
    assert gap(main) > gap(raw)


# --------------------------------------------------------------------------- #
#  Every specification                                                        #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("year,name", [(y, n) for y in YEARS for n in SPEC_FILES[y]])
def test_specification_covers_every_candidate(year, name):
    new = read(CSES / name)
    cur = read(PREVIOUS / f"party_positions_{year}.csv")
    assert new.columns.tolist() == cur.columns.tolist()
    assert new["party"].tolist() == cur["party"].tolist()
    assert new["block"].tolist() == cur["block"].tolist()
    x = num(new["left_right_position"])
    assert x.notna().all() and x.between(0, 10).all()


@pytest.mark.parametrize("year,name", [(y, n) for y in YEARS for n in SPEC_FILES[y]])
def test_imputed_values_are_the_bridge_and_labelled_as_such(year, name):
    pos = read(CSES / name).set_index("party")
    imputed = pos.index[pos["position_source"].str.startswith("imputed_")]
    for p in imputed:
        assert p not in ed.MEASURED_SOURCES
        assert ed.imputed_mask([pos.loc[p, "position_source"]])[0]
    spec = "main" if name == f"party_positions_{year}.csv" else \
        name[len(f"party_positions_{year}_"):-len(".csv")]
    fits = read(CSES / "bridge_fit.csv")
    fit = fits[(fits["election_year"] == str(year)) & (fits["spec"] == spec)]
    if len(imputed) == 0:
        assert fit.empty
        return
    fit = fit.iloc[0]
    assert fit["imputed"].split() == list(imputed)
    a, b = _to_float(fit["intercept"]), _to_float(fit["slope"])
    assert b > 0
    cur = read(PREVIOUS / f"party_positions_{year}.csv").set_index("party")
    for p in imputed:
        assert pos.loc[p, "position_source"] == \
            f"imputed_bridge_from_{cur.loc[p, 'position_source']}"
        want = np.clip(a + b * _to_float(cur.loc[p, "left_right_position"]), 0, 10)
        assert _to_float(pos.loc[p, "left_right_position"]) == pytest.approx(want, abs=1e-8)


def test_which_candidates_are_imputed_in_the_main_specification():
    # pinned, so a change in coverage is a deliberate edit here
    cov = read(CSES / "coverage.csv")
    imp = cov[cov["imputed"] == "yes"]
    assert imp[imp["election_year"] == "2002"]["party"].tolist() == \
        ["LCR", "PRG", "CAP21", "CPNT", "FRS", "MNR"]
    assert imp[imp["election_year"] == "2022"].empty


@pytest.mark.parametrize("year", YEARS)
def test_coverage_lists_every_modelled_candidate(year):
    cov = read(CSES / "coverage.csv")
    cov = cov[cov["election_year"] == str(year)]
    main = read(CSES / f"party_positions_{year}.csv")
    assert cov["party"].tolist() == main["party"].tolist()
    assert cov["main_source"].tolist() == main["position_source"].tolist()


@pytest.mark.parametrize("year", YEARS)
def test_model_loads_the_main_specification(year, tmp_path):
    """Swapping the files in for the current ones is all the model needs."""
    for f in DATA.glob("*.csv"):
        shutil.copy(f, tmp_path / f.name)
    for name in (f"party_positions_{year}.csv", f"voters_ideology_{year}.csv"):
        shutil.copy(CSES / name, tmp_path / name)

    bundle = ed.load_year(year, data_dir=tmp_path)
    assert bundle["K"] == len(read(PREVIOUS / f"party_positions_{year}.csv"))
    main = read(CSES / f"party_positions_{year}.csv").set_index("party")
    assert bundle["sources"] == [main.loc[p, "position_source"] for p in bundle["parties"]]
    pos, probs = ed.load_voter_histogram(year, data_dir=tmp_path)
    np.testing.assert_allclose(pos, np.arange(11) / 5 - 1)
    assert probs.sum() == pytest.approx(1.0)


@pytest.mark.parametrize("year", YEARS)
def test_data_holds_the_main_specification(year):
    """The model's inputs in data/ are the main specification, byte for byte."""
    for name in (f"party_positions_{year}.csv", f"voters_ideology_{year}.csv"):
        assert (DATA / name).read_bytes() == (CSES / name).read_bytes(), name


@pytest.mark.parametrize("year", YEARS)
def test_previous_inputs_are_the_august_run_values(year):
    """
    data/previous_inputs/ is the input set of the 2026-08-21 run.  Only two
    metadata edits separate it from the tag: hand_coded relabelled llm_coded,
    and the voter files' declared scale column.  The values are pinned here by
    their sums, so an edit to any number fails.
    """
    pos = num(read(PREVIOUS / f"party_positions_{year}.csv")["left_right_position"])
    vot = read(PREVIOUS / f"voters_ideology_{year}.csv")
    want = {2002: (76.58, 1.001, "1-10"), 2022: (55.645455, 1.0, "0-10")}[year]
    assert pos.sum() == pytest.approx(want[0], abs=1e-6)
    assert num(vot["share"]).sum() == pytest.approx(want[1], abs=1e-9)
    assert set(vot["scale"]) == {want[2]}
    # the August polls, swap in 2022 included: row count and the total of
    # every cell, so an edit to any value fails
    polls = read(PREVIOUS / f"polls_{year}.csv")
    cells = polls.drop(columns=["source", "date"]).apply(num)
    n, total = {2002: (41, 40.96), 2022: (81, 81.076)}[year]
    assert len(polls) == n
    assert cells.to_numpy().sum() == pytest.approx(total, abs=1e-9)
