#!/usr/bin/env python3
"""
Build data/polls_{2002,2022}.csv from fixed revisions of the French Wikipedia
poll lists.

A Wikipedia page changes; a revision does not.  Each year is read from one
revision, named below, so anyone rerunning this gets the same file.  The
fetched HTML is cached in data/raw/wikipedia/ (git-ignored) and --offline
rebuilds from the cache alone.

Which polls
-----------
The first-round tables under these section headings, as the page itself
divides them:

    2002  "Avril", "Mars"  (1 March to 18 April 2002)
    2022  "Sondages réalisés après la publication de la liste officielle
           des candidats"  (after the official list of 7 March 2022)

Rows that are not polls (official results, notices spanning the table) are
dropped.  Rolling polls are kept, marked in the ``rolling`` column.

Which candidates
----------------
Each column is mapped to a model party code by the party code in its header,
e.g. "Arlette Laguiller (LO)", never by its position: the previous poll file
was copied positionally under a header in a different order, which swapped
LO/NPA and EELV/PS in 2022.  Candidates the model does not include are
dropped, and must be listed in EXCLUDED:

    2002  Gluckstein (POI): not in the model (0.47% of the vote)
          Pasqua (RPF): withdrew; polled in March only

A poll that did not offer every modelled candidate ("-" in that candidate's
cell) is dropped, not filled with 0: a 0 would tell the model the candidate had
no support, which the poll did not measure.  The dropped polls are printed and
written to data/polls_dropped.csv.

A share published only as below a threshold ("<1 %", "<0,5 %"; OpinionWay and
Ifop do this for Arthaud in 2022) is set to half the threshold, and the
candidate is listed in that poll's ``below_threshold`` column.  Any other
non-number stops the run.  Shares are written as published
(percent / 100), not renormalised: the loader normalises each poll.

Output columns: source, date (last fieldwork day, dd/mm/yyyy), fieldwork (as
published), rolling, below_threshold, then one column per modelled party in
the page's order.

Rebuilding needs beautifulsoup4 and lxml, which the model does not:
    pip install beautifulsoup4 lxml

Usage
-----
    python tools/build_polls_from_wikipedia.py            # refuses to overwrite
    python tools/build_polls_from_wikipedia.py --force
    python tools/build_polls_from_wikipedia.py --force --offline
"""

import argparse
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
CACHE = DATA / "raw" / "wikipedia"
API = "https://fr.wikipedia.org/w/api.php"
USER_AGENT = "strategic-voting-abm (research; reproducible poll extraction)"

SOURCES = {
    2002: dict(
        page="Liste de sondages sur l'élection présidentielle française de 2002",
        revision=236399441,            # 2026-05-21; unchanged since
        sections=["Avril", "Mars"],
        rename={"CAP21": "CAP21"},
        excluded={"POI", "RPF"},
    ),
    2022: dict(
        page="Liste de sondages sur l'élection présidentielle française de 2022",
        revision=235575713,            # 2026-04-25; live when the data were first taken
        sections=["Sondages_réalisés_après_la_publication_de_la_liste_officielle_des_candidats"],
        rename={"LREM": "RE"},
        excluded=set(),
    ),
}

MONTHS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5}
NOT_POLLS = {"résultats officiels", "résultats"}


def fetch(year: int, offline: bool) -> str:
    """The rendered HTML of the pinned revision, from the cache or the API."""
    spec = SOURCES[year]
    path = CACHE / f"polls_{year}_rev{spec['revision']}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    if offline:
        raise SystemExit(f"--offline, and no cached copy at {path}")
    query = urllib.parse.urlencode({"action": "parse", "oldid": spec["revision"],
                                    "prop": "text|revid", "format": "json",
                                    "formatversion": 2})
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        parsed = json.load(r)["parse"]
    if parsed["revid"] != spec["revision"]:
        raise ValueError(f"asked for revision {spec['revision']}, got {parsed['revid']}")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(parsed["text"], encoding="utf-8")
    return parsed["text"]


def clean(cell) -> str:
    """Cell text without footnote markers and surrounding space."""
    return re.sub(r"\[[^\]]*\]", "", str(cell)).replace("\xa0", " ").strip()


def end_date(text: str, year: int) -> pd.Timestamp:
    """Last fieldwork day: '17 et 18 avril', 'du 28 février au 2 mars', '31 mars - 4 avril'."""
    t = clean(text).replace("1er", "1")
    months = re.findall(r"(janvier|février|mars|avril|mai)", t)
    days = re.findall(r"\b(\d{1,2})\b", t)
    if not months or not days:
        raise ValueError(f"cannot read a date from {text!r}")
    return pd.Timestamp(year, MONTHS[months[-1]], int(days[-1]))


NOT_TESTED = {"-", "–", "—"}


def share(cell, where: str) -> tuple:
    """
    '8 %' -> (0.08, False), '0,5 %' -> (0.005, False),
    '<1 %' -> (0.005, True): half the published threshold.
    Anything else stops the run.
    """
    t = clean(cell).replace("%", "").replace(",", ".").replace(" ", "")
    m = re.fullmatch(r"<(\d+(\.\d+)?)", t)
    if m:
        return float(m.group(1)) / 200, True
    if not re.fullmatch(r"\d+(\.\d+)?", t):
        raise ValueError(f"{where}: {cell!r} is not a published share")
    return float(t) / 100, False


def section_table(soup, heading_id: str):
    heading = soup.find(id=heading_id)
    if heading is None:
        raise ValueError(f"no section {heading_id!r} in this revision")
    return heading.find_next("table", class_="wikitable")


def build(year: int, offline: bool) -> pd.DataFrame:
    # Imported here, not at the top: only rebuilding needs them, and the tests
    # import this module for its parsing rules without them installed.
    from bs4 import BeautifulSoup

    spec = SOURCES[year]
    soup = BeautifulSoup(fetch(year, offline), "lxml")
    modelled = pd.read_csv(DATA / f"party_positions_{year}.csv", dtype=str)["party"].tolist()

    rows, dropped, order = [], [], None
    for sec in spec["sections"]:
        table = pd.read_html(io.StringIO(str(section_table(soup, sec))))[0]
        headers = [c[-1] if isinstance(c, tuple) else c for c in table.columns]
        codes = {}
        for i, h in enumerate(headers[2:], start=2):
            m = re.search(r"\(([^)]+)\)\s*$", clean(h))
            if not m:
                continue                          # e.g. the sample-size column
            code = m.group(1).upper()
            code = spec["rename"].get(code, code)
            if code in spec["excluded"]:
                continue
            if code not in modelled:
                raise ValueError(f"{year} {sec}: column {h!r} is neither modelled nor excluded")
            codes[i] = code
        if sorted(codes.values()) != sorted(modelled):
            raise ValueError(f"{year} {sec}: columns {sorted(codes.values())} "
                             f"!= modelled {sorted(modelled)}")
        order = order or list(codes.values())

        for _, r in table.iterrows():
            src, when = clean(r.iloc[0]), clean(r.iloc[1])
            if src == when or src.lower() in NOT_POLLS or src.lower() == "sondeur":
                continue                          # notice rows span every column
            rolling = "(rolling)" in src.lower()
            src = re.sub(r"\s*\(rolling\)", "", src, flags=re.I)
            row = {"source": src,
                   "date": end_date(when, year).strftime("%d/%m/%Y"),
                   "fieldwork": when,
                   "rolling": "yes" if rolling else "no"}
            untested = [code for i, code in codes.items()
                        if clean(r.iloc[i]) in NOT_TESTED]
            if untested:
                dropped.append({"year": year, "source": src, "fieldwork": when,
                                "not_tested": " ".join(untested)})
                continue
            below = []
            for i, code in codes.items():
                row[code], censored = share(r.iloc[i], f"{year} {src} {when} {code}")
                if censored:
                    below.append(code)
            row["below_threshold"] = " ".join(below)
            rows.append(row)

    cols = ["source", "date", "fieldwork", "rolling", "below_threshold"] + order
    return pd.DataFrame(rows)[cols], dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--force", action="store_true", help="overwrite data/polls_*.csv")
    ap.add_argument("--offline", action="store_true", help="use the cached HTML only")
    args = ap.parse_args()

    all_dropped = []
    for year, spec in SOURCES.items():
        out = DATA / f"polls_{year}.csv"
        if out.exists() and not args.force:
            print(f"{out} exists; pass --force to overwrite", file=sys.stderr)
            return 1
        df, dropped = build(year, args.offline)
        df.to_csv(out, index=False, decimal=",", float_format="%.4g")
        print(f"{year}: {len(df)} polls from revision {spec['revision']} -> "
              f"{out.relative_to(REPO)}")
        for d in dropped:
            print(f"      dropped: {d['source']}, {d['fieldwork']} "
                  f"(did not offer {d['not_tested']})")
        all_dropped += dropped
    pd.DataFrame(all_dropped, columns=["year", "source", "fieldwork", "not_tested"]) \
        .to_csv(DATA / "polls_dropped.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
