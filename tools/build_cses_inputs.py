#!/usr/bin/env python3
"""
Build survey-based ideology inputs for 2002 and 2022.

Reads the CSES Module 2 (France 2002) and Module 6 (France 2022) files straight
from the downloaded zips in ``data/raw/cses/`` (git-ignored; see
``data/cses/README.md`` for where to get them), the transcribed Ipsos-CEVIPOF
2022 table in ``data/ipsos/``, and the inputs of the 2026-08-21 run in
``data/previous_inputs/``.  Writes to ``data/cses/``:

    voters_ideology_{year}.csv     weighted left-right self-placement histogram,
                                   raw 0-10 bins, with a declared ``scale``
    party_positions_{year}.csv     MAIN specification, model-ready, in the
                                   schema of data/party_positions_{year}.csv
    party_positions_{year}_{spec}.csv
                                   comparison specifications, same schema
    candidate_positions_{year}.csv every summary of every survey item
    coverage.csv                   candidate by candidate: main position and
                                   source, imputed or not, previous value,
                                   value under every comparison specification
    bridge.csv, bridge_fit.csv     the bridge, per candidate and per fit
    scale_screen.csv               the 2002 scale-direction screen
    sample_sizes.csv               unweighted / weighted / effective n per item

Main specification
------------------
* 2002: CSES candidate (leader) placements, weighted mean, after dropping
  respondents who place Laguiller strictly to the right of Le Pen -- a
  scale read backwards.
* 2022: the published Ipsos-CEVIPOF wave 9 means, all 12 candidates.
* Voters, both years: CSES self-placement.

Means, because Ipsos publishes means only and both years should use the same
statistic.  Comparison specifications: 2002 unscreened means and CSES party
items; 2022 CSES party items (interpolated medians).

Candidates no survey measures are placed by a **bridge**: an OLS fit, per year
and specification, of the survey position on the previous position (CHES or
LLM-coded, ``data/previous_inputs/``) over the candidates that have both,
applied to the previous position of each unmeasured candidate.  The value is
labelled ``imputed_bridge_from_<previous source>``, so the robustness run can
perturb exactly those.  Its R^2 and RMSE are in-sample fit, not validation.

This script never writes to ``data/`` outside ``data/cses/``.  Switching the
model to its output is a copy (see data/cses/README.md).

Usage
-----
    python tools/build_cses_inputs.py            # refuses to overwrite
    python tools/build_cses_inputs.py --force
"""

import argparse
import hashlib
import io
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "cses"
OUT = REPO / "data" / "cses"
# The inputs of the 2026-08-21 run (CHES + LLM-coded positions): the party
# list, the blocks, and the base the bridge carries onto the survey scale.
# Read from a fixed copy, not from data/, so that data/ can hold this script's
# own output without the bridge reading it back.
PREVIOUS = REPO / "data" / "previous_inputs"
IPSOS_2022 = REPO / "data" / "ipsos" / "candidate_positions_2022_wave9.csv"

VALID = range(0, 11)            # CSES left-right scale, 0 = left, 10 = right
SCALE_MIN, SCALE_MAX = 0, 10


def to_model_scale(x):
    """CSES 0-10 -> model [-1, 1]; same map the loader applies to raw positions."""
    return np.asarray(x, dtype=float) / 5.0 - 1.0


# --------------------------------------------------------------------------- #
#  Study specifications.  Every letter mapping carries the codebook text that #
#  confirms it; build() refuses to run if that text is not found.            #
# --------------------------------------------------------------------------- #

STUDIES = {
    2002: dict(
        module="CSES Module 2 Full Release",
        csv_zip="cses2_csv.zip", csv_member="cses2.csv",
        codebook_zip="cses2_codebook.zip",
        release_var="B1002_VER", release="VER2015-DEC-15",
        doi_var="B1002_DOI", doi="doi:10.7804/cses.module2.2015-12-15",
        study_var="B1004", study="FRA_2002",
        election_type_var="B1015", election_type="20",       # 20 = presidential
        # France (2002) deposited only a demographic weight (codebook B1010
        # table).  B1012_2 is that weight rescaled by CSES to mean 1 within the
        # study; the original B1010_2 already has mean 1, so they coincide.
        weight_var="B1012_2",
        weight_note=("B1012_2 (polity weight: demographic); the only weight "
                     "France 2002 deposited. Matches education and "
                     "public/private sector employment."),
        self_var="B3045",
        missing_codes={95, 96, 97, 98, 99},
        candidate_prefix="B3039_",     # LEFT-RIGHT - LEADER (main)
        party_prefix="B3038_",         # LEFT-RIGHT - PARTY (comparison)
        # Scale-direction screen: a respondent who places Laguiller (E) to the
        # right of Le Pen (B) has almost certainly read the scale backwards.
        screen=("E", "B"),
        section=r">>> PARTIES AND LEADERS: FRANCE \(2002\)",
        # letter -> (model code, regex).  verify_mapping() prefixes the regex
        # with this letter's own label, so it must match "Party X  <party>
        # <leader>" for this X inside the France section of Appendix I.
        label=r"Party {L}\s+",
        letters={
            "A": ("RPR", r"Rally For The Republic\s+J\. Chirac"),
            "B": ("FN", r"National Front\s+J\. Le Pen"),
            "C": ("PS", r"Socialist Party\s+L\. Jospin"),
            "D": ("UDF", r"Union For French Democracy\s+F\. Bayrou"),
            "E": ("LO", r"Workers' Struggle\s+A\. Laguiller"),
            "F": ("MDC", r"Republican And Civic Movement\s+J\. Chevenment"),
            "G": ("LV", r"Greens\s+N\. Mamere"),
            "H": ("DL", r"Liberal Democracy\s+A\. Madelin"),
            "I": ("PCF", r"French Communist Party\s+R\. Hue"),
        },
    ),
    2022: dict(
        module="CSES Module 6 Second Advance Release",
        csv_zip="cses6_csv.zip", csv_member="cses6.csv",
        codebook_zip="cses6_codebook.zip",
        release_var="F1002_VER", release="VER2025-DEC-16",
        doi_var="F1002_DOI", doi="doi:10.7804/cses.module6.2025-12-16",
        study_var="F1004", study="FRA_2022",
        election_type_var="F1014", election_type="20",
        # Codebook F1101 and Part 5: "Weights are unavailable for FRANCE
        # (2022)"; all weight variables are coded 1.  F1103_2 is used so the
        # code path is the same as 2002, and the run asserts it is constant.
        weight_var="F1103_2",
        weight_note=("None available (codebook F1101, Part 5: 'No weights "
                     "provided'); F1103_2 is identically 1, so weighted = "
                     "unweighted."),
        self_var="F3020_R",
        missing_codes={95, 96, 97, 98, 99},
        candidate_prefix=None,         # no leader left-right item in Module 6
        party_prefix="F3020_",         # IDEOLOGY: LEFT-RIGHT - PARTY (comparison)
        screen=None,
        section=r">>> PARTIES/COALITIONS & LEADERS: FRANCE \(2022\)",
        label=r"PARTY {L}\s+",
        letters={
            "A": ("RE", r"La Republique En Marche! \(LREM\)[\s\S]*?LEADER {L}\s+Emmanuel Macron"),
            "B": ("RN", r"Rassemblement National \(RN\)[\s\S]*?LEADER {L}\s+Marine Le Pen"),
            "C": ("LFI", r"La France Insoumise \(FI\)[\s\S]*?LEADER {L}\s+Jean-Luc Melenchon"),
            "D": ("REC", r"Reconquete \(REC\)[\s\S]*?LEADER {L}\s+Eric Zemmour"),
            "E": ("LR", r"Les Republicains \(LR\)[\s\S]*?LEADER {L}\s+Valerie Pecresse"),
            "F": ("EELV", r"Europe Ecologie - Les Verts \(EELV\)[\s\S]*?LEADER {L}\s+Yannick Jadot"),
            "G": ("PS", r"Parti Socialiste \(PS\)"),
        },
    ),
}

# Candidate behind each modelled party code.  For measured candidates the name
# is also in the codebook regex above; the rest are listed for the coverage
# table only and carry no survey value.
CANDIDATES = {
    2002: {
        "LO": "Arlette Laguiller", "LCR": "Olivier Besancenot",
        "PCF": "Robert Hue", "PS": "Lionel Jospin",
        "PRG": "Christiane Taubira", "LV": "Noel Mamere",
        "MDC": "Jean-Pierre Chevenement", "CAP21": "Corinne Lepage",
        "CPNT": "Jean Saint-Josse", "UDF": "Francois Bayrou",
        "DL": "Alain Madelin", "RPR": "Jacques Chirac",
        "FRS": "Christine Boutin", "FN": "Jean-Marie Le Pen",
        "MNR": "Bruno Megret",
    },
    2022: {
        "NPA": "Philippe Poutou", "LO": "Nathalie Arthaud",
        "PCF": "Fabien Roussel", "LFI": "Jean-Luc Melenchon",
        "EELV": "Yannick Jadot", "PS": "Anne Hidalgo",
        "RE": "Emmanuel Macron", "LR": "Valerie Pecresse",
        "RES": "Jean Lassalle", "DLF": "Nicolas Dupont-Aignan",
        "RN": "Marine Le Pen", "REC": "Eric Zemmour",
    },
}


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_codebook(zip_name: str) -> str:
    """All codebook parts in one string, CP1252-decoded, LF line endings."""
    with zipfile.ZipFile(RAW / zip_name) as z:
        return "\n".join(
            z.read(n).decode("cp1252").replace("\r\n", "\n")
            for n in sorted(z.namelist())
        )


def codebook_section(text: str, header: str) -> str:
    """The text of one Appendix/Part-3 block, up to the next '>>>' header."""
    m = re.search(r"^" + header + r"\s*$", text, flags=re.M)
    if not m:
        raise ValueError(f"codebook section not found: {header}")
    rest = text[m.end():]
    nxt = re.search(r"^>>> ", rest, flags=re.M)
    return rest[: nxt.start()] if nxt else rest


def verify_mapping(spec: dict, model_parties: list) -> None:
    section = codebook_section(read_codebook(spec["codebook_zip"]), spec["section"])
    for letter, (code, tail) in spec["letters"].items():
        # The letter comes from the dict key, not from the pattern, so a
        # pattern filed under the wrong letter cannot match.
        pattern = (spec["label"] + tail).replace("{L}", letter)
        if not re.search(pattern, section):
            raise ValueError(f"{spec['study']}: codebook does not confirm "
                             f"letter {letter} -> {code} ({pattern!r})")
        if code not in model_parties:
            raise ValueError(f"{spec['study']}: {code} is not a modelled party")


def load_study(spec: dict) -> pd.DataFrame:
    letters = list(spec["letters"])
    cols = [spec["release_var"], spec["doi_var"], spec["study_var"],
            spec["election_type_var"], spec["weight_var"], spec["self_var"]]
    for prefix in (spec["party_prefix"], spec["candidate_prefix"]):
        if prefix:
            cols += [prefix + x for x in letters]
    with zipfile.ZipFile(RAW / spec["csv_zip"]) as z:
        with z.open(spec["csv_member"]) as f:
            df = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig"),
                             usecols=cols, dtype=str)
    df = df[df[spec["study_var"]] == spec["study"]].copy()
    if df.empty:
        raise ValueError(f"no rows for {spec['study']}")
    for var, want in [(spec["release_var"], spec["release"]),
                      (spec["doi_var"], spec["doi"]),
                      (spec["election_type_var"], spec["election_type"])]:
        got = set(df[var].str.strip())
        if got != {want}:
            raise ValueError(f"{spec['study']}: {var} is {got}, expected {want}")
    return df


def clean(values: pd.Series, missing: set, name: str) -> pd.Series:
    """Integer placements with documented missing codes set to NaN."""
    v = values.astype(int)
    bad = set(v.unique()) - set(VALID) - missing
    if bad:
        raise ValueError(f"{name}: undocumented values {sorted(bad)}")
    return v.where(v.isin(VALID))


def weighted_median(x: np.ndarray, w: np.ndarray) -> float:
    """
    Smallest value whose cumulative weight share reaches 1/2; if the share is
    exactly 1/2 there, the midpoint with the next value.  With unit weights
    this is the ordinary sample median.
    """
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    cum = np.cumsum(w) / w.sum()
    i = int(np.searchsorted(cum, 0.5 - 1e-12))
    if abs(cum[i] - 0.5) < 1e-12 and i + 1 < len(x):
        return float((x[i] + x[i + 1]) / 2)
    return float(x[i])


def interpolated_median(x: np.ndarray, w: np.ndarray) -> float:
    """
    Grouped-data median treating each integer k as the interval
    [k - 0.5, k + 0.5], clipped to the 0-10 scale.  This is the position the
    model uses: it separates items that share an integer median.
    """
    cats = np.arange(SCALE_MIN, SCALE_MAX + 1)
    wk = np.array([w[x == k].sum() for k in cats])
    half = wk.sum() / 2
    below = np.concatenate([[0.0], np.cumsum(wk)[:-1]])
    j = int(np.argmax(below + wk >= half))
    m = cats[j] - 0.5 + (half - below[j]) / wk[j]
    return float(np.clip(m, SCALE_MIN, SCALE_MAX))


def summarise(x: pd.Series, w: pd.Series) -> dict:
    ok = x.notna()
    xv, wv = x[ok].to_numpy(float), w[ok].to_numpy(float)
    return dict(
        n_unweighted=int(ok.sum()),
        n_weighted=float(wv.sum()),
        n_effective=float(wv.sum() ** 2 / (wv ** 2).sum()),
        n_excluded=int((~ok).sum()),
        weighted_median=weighted_median(xv, wv),
        interpolated_median=interpolated_median(xv, wv),
        weighted_mean=float(np.average(xv, weights=wv)),
    )


def write_csv(df: pd.DataFrame, path: Path) -> None:
    # European decimals, like every other input in data/.
    df.to_csv(path, index=False, decimal=",", float_format="%.10g")


# --------------------------------------------------------------------------- #
#  Build                                                                       #
# --------------------------------------------------------------------------- #

def item_stats(df, w, spec, year, prefix, sizes, keep=None) -> pd.DataFrame:
    """
    Every summary of every item under ``prefix``, one row per modelled party.
    With ``keep`` (bool per respondent), also the weighted mean over the kept
    respondents only.
    """
    rows = []
    for letter, (code, _) in spec["letters"].items():
        var = prefix + letter
        raw = df[var].astype(int)
        x = clean(df[var], spec["missing_codes"], var)
        s = summarise(x, w)
        row = dict(party=code, item=var, n_unweighted=s["n_unweighted"],
                   n_weighted=s["n_weighted"],
                   weighted_median_0_10=s["weighted_median"],
                   interpolated_median_0_10=s["interpolated_median"],
                   weighted_mean_0_10=s["weighted_mean"])
        if keep is not None:
            k = x.notna() & keep
            row["n_screened"] = int(k.sum())
            row["weighted_mean_screened_0_10"] = float(
                np.average(x[k].to_numpy(float), weights=w[k].to_numpy(float)))
        rows.append(row)
        sizes.append(dict(year=year, item=var, measures=code, n_study=len(df), **s,
                          excluded_codes=";".join(f"{c}:{n}" for c, n in
                                                  raw[x.isna()].value_counts().sort_index().items())))
    return pd.DataFrame(rows).set_index("party")


def scale_screen(df, spec):
    """
    Respondents kept by the scale-direction screen, and how many were dropped.

    A respondent is dropped when they placed both screen candidates and put
    the left one strictly to the right of the right one.  Respondents who did
    not place both are kept: the screen has no evidence about them.
    """
    left, right = spec["screen"]
    pre = spec["candidate_prefix"]
    xl = clean(df[pre + left], spec["missing_codes"], pre + left)
    xr = clean(df[pre + right], spec["missing_codes"], pre + right)
    both = xl.notna() & xr.notna()
    reversed_ = both & (xl > xr)
    return ~reversed_, dict(screen_left=spec["letters"][left][0],
                            screen_right=spec["letters"][right][0],
                            n_study=len(df), n_placed_both=int(both.sum()),
                            n_dropped=int(reversed_.sum()))


def assemble(name, values: pd.Series, source: str, current: pd.DataFrame, year: int):
    """
    One specification: every modelled candidate gets a 0-10 position.

    ``values`` holds the measured ones.  Any other candidate is placed by the
    bridge -- an OLS fit, over the candidates that have both, of the measured
    position on the previous position in data/previous_inputs/ -- and
    labelled ``imputed_bridge_from_<previous source>``.  R^2 and RMSE are
    in-sample fit on the anchors, not a validation of the imputed values.

    Returns (model-ready positions, per-candidate bridge rows, fit row or None).
    """
    cur = current.set_index("party")
    missing = [p for p in cur.index if p not in values.index]
    fit, a, b = None, np.nan, np.nan
    if missing:
        anchors = [p for p in cur.index if p in values.index]
        x = cur.loc[anchors, "raw"].to_numpy(float)
        y = values.loc[anchors].to_numpy(float)
        b, a = np.polyfit(x, y, 1)
        resid = y - (a + b * x)
        if b <= 0:
            raise ValueError(f"{year} {name}: bridge slope {b:.3f} is not positive")
        fit = dict(election_year=year, spec=name, n_anchors=len(anchors),
                   anchors=" ".join(anchors),
                   anchor_previous_sources=" ".join(sorted(set(cur.loc[anchors, "position_source"]))),
                   imputed=" ".join(missing),
                   intercept=a, slope=b,
                   in_sample_r2=1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum(),
                   in_sample_rmse_0_10=float(np.sqrt((resid ** 2).mean())),
                   in_sample_max_abs_residual_0_10=float(np.abs(resid).max()))

    out, per = [], []
    for p in cur.index:
        if p in values.index:
            value, src, pred = float(values[p]), source, np.nan
        else:
            pred = float(a + b * cur.loc[p, "raw"])
            value = float(np.clip(pred, SCALE_MIN, SCALE_MAX))
            src = f"imputed_bridge_from_{cur.loc[p, 'position_source']}"
        out.append(dict(election_year=year, party=p, left_right_position=value,
                        position_source=src, block=cur.loc[p, "block"]))
        per.append(dict(election_year=year, spec=name, party=p,
                        previous_position_0_10=cur.loc[p, "raw"],
                        previous_source=cur.loc[p, "position_source"],
                        measured_0_10=values.get(p, np.nan),
                        bridge_prediction_0_10=pred,
                        clipped="yes" if not np.isnan(pred) and
                                not SCALE_MIN <= pred <= SCALE_MAX else "no",
                        final_position_0_10=value, final_source=src))
    return pd.DataFrame(out), pd.DataFrame(per), fit


def read_previous_positions(year: int) -> pd.DataFrame:
    cur = pd.read_csv(PREVIOUS / f"party_positions_{year}.csv", dtype=str)
    cur["raw"] = cur["left_right_position"].str.replace(",", ".").astype(float)
    return cur


def read_ipsos_2022(model_parties: list) -> pd.Series:
    """Published mean placements, Ipsos-CEVIPOF wave 9 (see data/ipsos/README.md)."""
    df = pd.read_csv(IPSOS_2022, dtype=str)
    if sorted(df["party"]) != sorted(model_parties):
        raise ValueError("Ipsos wave 9 table does not cover exactly the modelled candidates")
    return df.set_index("party")["mean_0_10"].str.replace(",", ".").astype(float)


def build(year: int):
    spec = STUDIES[year]
    current = read_previous_positions(year)
    model_parties = current["party"].tolist()
    verify_mapping(spec, model_parties)
    df = load_study(spec)

    w = df[spec["weight_var"]].astype(float)
    if (w <= 0).any() or w.isna().any():
        raise ValueError(f"{spec['study']}: non-positive or missing weights")
    if year == 2022 and not np.allclose(w, 1.0):
        raise ValueError("France 2022 is documented as unweighted but "
                         f"{spec['weight_var']} is not constant")

    sizes, n_total = [], len(df)

    # ---- voters ---------------------------------------------------------- #
    self_raw = df[spec["self_var"]].astype(int)
    self_x = clean(df[spec["self_var"]], spec["missing_codes"], spec["self_var"])
    ok = self_x.notna()
    hist = (pd.DataFrame({"k": self_x[ok].astype(int), "w": w[ok]})
            .groupby("k")["w"].sum()
            .reindex(VALID, fill_value=0.0))
    voters = pd.DataFrame({"ideological_scale": list(VALID),
                           "share": (hist / hist.sum()).to_numpy(),
                           "scale": "0-10"})
    s = summarise(self_x, w)
    sizes.append(dict(year=year, item=spec["self_var"], measures="self-placement",
                      n_study=n_total, **s,
                      excluded_codes=";".join(f"{c}:{n}" for c, n in
                                              self_raw[~ok].value_counts().sort_index().items())))

    # ---- candidate positions, every specification ------------------------ #
    party = item_stats(df, w, spec, year, spec["party_prefix"], sizes)
    specs, screen = {}, None
    if year == 2002:
        keep, screen = scale_screen(df, spec)
        cand = item_stats(df, w, spec, year, spec["candidate_prefix"], sizes, keep=keep)
        specs["main"] = (cand["weighted_mean_screened_0_10"], "cses_candidate_placement")
        specs["unscreened_means"] = (cand["weighted_mean_0_10"], "cses_candidate_placement")
        specs["party_items"] = (party["interpolated_median_0_10"], "cses_party_placement")
        table = cand.add_prefix("candidate_").join(party.add_prefix("party_"))
        table["candidate_minus_party_mean_0_10"] = (table["candidate_weighted_mean_0_10"]
                                                    - table["party_weighted_mean_0_10"])
    else:
        ipsos = read_ipsos_2022(model_parties)
        specs["main"] = (ipsos, "ipsos_candidate_placement")
        specs["cses_party_items"] = (party["interpolated_median_0_10"], "cses_party_placement")
        table = party.add_prefix("party_").reindex(model_parties)
        table["ipsos_mean_0_10"] = ipsos
    table = table.reset_index().rename(columns={"index": "party"})
    table.insert(0, "election_year", year)
    table.insert(2, "candidate", table["party"].map(CANDIDATES[year]))

    positions, bridges, fits = {}, [], []
    for name, (values, source) in specs.items():
        positions[name], br, fit = assemble(name, values, source, current, year)
        bridges.append(br)
        if fit:
            fits.append(fit)

    # ---- candidate-by-candidate coverage --------------------------------- #
    main = positions["main"].set_index("party")
    cov = pd.DataFrame([dict(
        election_year=year, party=p, candidate=CANDIDATES[year][p],
        main_position_0_10=main.loc[p, "left_right_position"],
        main_model_position=float(to_model_scale(main.loc[p, "left_right_position"])),
        main_source=main.loc[p, "position_source"],
        imputed="yes" if main.loc[p, "position_source"].startswith("imputed_") else "no",
        previous_position_0_10=current.set_index("party").loc[p, "raw"],
        previous_source=current.set_index("party").loc[p, "position_source"],
        **{f"{n}_0_10": positions[n].set_index("party").loc[p, "left_right_position"]
           for n in positions if n != "main"},
    ) for p in model_parties])

    check(year, voters, positions, cov, model_parties)
    return (voters, table, positions, pd.concat(bridges), fits, screen,
            cov, pd.DataFrame(sizes))


def check(year, voters, positions, cov, model_parties):
    assert abs(voters["share"].sum() - 1.0) < 1e-12, "voter shares do not sum to 1"
    assert (voters["share"] >= 0).all()
    assert voters["ideological_scale"].tolist() == list(VALID)
    assert cov["party"].tolist() == model_parties, "coverage must list every modelled party"
    for name, p in positions.items():
        assert p["party"].tolist() == model_parties, f"{name}: party list differs"
        assert p["left_right_position"].between(SCALE_MIN, SCALE_MAX).all()
        assert p["left_right_position"].notna().all()
    # every specification must put the two candidates everyone agrees on at
    # opposite ends
    left, right = {2002: ("LO", "FN"), 2022: ("LO", "REC")}[year]
    for name, p in positions.items():
        pos = p.set_index("party")["left_right_position"]
        assert pos[left] < 5 < pos[right], f"{name}: left/right anchors are reversed"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--force", action="store_true", help="overwrite data/cses/")
    args = ap.parse_args()

    missing = [z for s in STUDIES.values() for z in (s["csv_zip"], s["codebook_zip"])
               if not (RAW / z).is_file()]
    if missing:
        print(f"missing raw files in {RAW}: {missing}", file=sys.stderr)
        return 1
    if OUT.exists() and any(OUT.glob("*.csv")) and not args.force:
        print(f"{OUT} already has output; pass --force to overwrite", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    # Remove this script's earlier outputs first, so a file from a
    # specification that no longer exists cannot linger beside the new ones.
    for old in OUT.glob("*.csv"):
        old.unlink()

    all_bridge, all_fit, all_screen, all_cov, all_sizes = [], [], [], [], []
    for year in STUDIES:
        voters, table, positions, br, fits, screen, cov, sizes = build(year)
        write_csv(voters, OUT / f"voters_ideology_{year}.csv")
        write_csv(table, OUT / f"candidate_positions_{year}.csv")
        for name, pos in positions.items():
            suffix = "" if name == "main" else f"_{name}"
            write_csv(pos, OUT / f"party_positions_{year}{suffix}.csv")
        all_bridge.append(br)
        all_fit.extend(fits)
        if screen:
            all_screen.append(dict(election_year=year, **screen))
        all_cov.append(cov)
        all_sizes.append(sizes)
    write_csv(pd.concat(all_bridge), OUT / "bridge.csv")
    write_csv(pd.DataFrame(all_fit), OUT / "bridge_fit.csv")
    write_csv(pd.DataFrame(all_screen), OUT / "scale_screen.csv")
    write_csv(pd.concat(all_cov), OUT / "coverage.csv")
    write_csv(pd.concat(all_sizes), OUT / "sample_sizes.csv")

    for s in STUDIES.values():
        for z in (s["csv_zip"], s["codebook_zip"]):
            print(f"sha256  {sha256(RAW / z)}  {z}")
    print(f"wrote {OUT.relative_to(REPO)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
