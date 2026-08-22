#!/usr/bin/env python3
"""
validate_rerun.py -- check one regenerated empirical output before trusting it.

Run this after every stage of the rerun.  It fails loudly (exit 1) rather than
printing a warning, so it can be chained after the producing command.

    python tools/validate_rerun.py data/empirical_runs_2002.csv \
        --year 2002 --expect-rows 300 --log logs/step1_replay.log

Checks
------
  schema        tau_hat, tau_absolute and K are all present
  K             matches the year's candidate set (15 in 2002, 12 in 2022)
  conversion    tau_absolute == tau_hat * (2 / K), row by row
  ceiling       max tau_absolute <= the year's bound: 0.4 in 2002, 0.5 in 2022.
                The bound is year-specific because K is, and it is inclusive --
                tau_hat = 3.0 is the top of the swept range, so the ceiling is
                attained rather than approached.  A single shared "< 0.5" test
                would be 25% too loose for 2002.
  rows          the expected number of draws actually completed
  finite        no NaN or inf anywhere numeric
  log           the pre-fix signature "tau >= 2.0" does not appear
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

K_BY_YEAR = {2002: 15, 2022: 12}
MAX_ABSOLUTE_TAU = {2002: 0.4, 2022: 0.5}
TAU_HAT_MAX = 3.0

# The UserWarning the pre-fix runs emitted throughout.  Its absence is the
# clearest single sign that the corrected conversion is in force.
BUG_SIGNATURE = ">= 2.0: every party is a contender"


class Report:
    def __init__(self):
        self.failures = []

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {label}" + (f"  -- {detail}" if detail else ""))
        if not ok:
            self.failures.append(label)


def validate(path: Path, year: int, expect_rows, log: Path, rep: Report):
    print(f"\n{path}")
    if not path.exists():
        rep.check(False, "file exists", str(path))
        return

    df = pd.read_csv(path)

    required = ["tau_hat", "tau_absolute", "K"]
    missing = [c for c in required if c not in df.columns]
    rep.check(not missing, "schema records both tau units and K",
              f"missing {missing}" if missing else ", ".join(required))
    if missing:
        return

    K = K_BY_YEAR[year]
    rep.check(bool((df["K"] == K).all()), f"K == {K} for {year}",
              f"found {sorted(df['K'].unique().tolist())}")

    expected = df["tau_hat"].to_numpy(float) * (2.0 / K)
    got = df["tau_absolute"].to_numpy(float)
    worst = float(np.max(np.abs(expected - got))) if len(df) else 0.0
    rep.check(worst <= 1e-12, "tau_absolute == tau_hat * (2 / K)",
              f"max |diff| = {worst:.3e}")

    bound = MAX_ABSOLUTE_TAU[year]
    hi = float(got.max()) if len(df) else 0.0
    rep.check(hi <= bound + 1e-12, f"tau_absolute <= {bound} ({year} ceiling)",
              f"max = {hi:.6f}")

    # A tau_hat above the swept range would mean the design changed, not just
    # the units.
    th = float(df["tau_hat"].max()) if len(df) else 0.0
    rep.check(th <= TAU_HAT_MAX + 1e-12, f"tau_hat <= {TAU_HAT_MAX}",
              f"max = {th:.6f}")

    if expect_rows is not None:
        rep.check(len(df) == expect_rows, f"row count == {expect_rows}",
                  f"found {len(df)}")

    num = df.select_dtypes(include=[np.number])
    bad = [c for c in num.columns if not np.isfinite(num[c].to_numpy(float)).all()]
    rep.check(not bad, "all numeric values finite",
              f"non-finite in {bad}" if bad else f"{len(num.columns)} columns")

    if log is not None:
        if not log.exists():
            rep.check(False, "log present", str(log))
        else:
            text = log.read_text(errors="replace")
            n = text.count(BUG_SIGNATURE)
            rep.check(n == 0, "log free of the pre-fix 'tau >= 2.0' warning",
                      f"{n} occurrence(s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--year", type=int, required=True, choices=sorted(K_BY_YEAR))
    ap.add_argument("--expect-rows", type=int, default=None)
    ap.add_argument("--log", type=Path, default=None)
    args = ap.parse_args(argv)

    rep = Report()
    for p in args.paths:
        validate(p, args.year, args.expect_rows, args.log, rep)

    print()
    if rep.failures:
        print(f"FAILED: {len(rep.failures)} check(s): {', '.join(rep.failures)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
