#!/usr/bin/env python3
"""
Fail if the committed result tables do not reproduce from the raw outputs.

`make_empirical_tables.py && git status --short` was the previous instruction,
and it is not a check: `git status` exits 0 whether or not anything changed, so
a drifted table passes silently unless a human reads the output. This script
makes the same intent enforceable -- it exits non-zero, names the files, and is
safe to put in a pipeline.

It fails when:

  * a tracked table changes when regenerated (the committed bytes are stale, or
    the generator is not deterministic);
  * regenerating produces an untracked table nobody committed;
  * an expected table is missing after regeneration;
  * the tables directory is already dirty before regeneration, which would make
    any later diff impossible to attribute.

It exits 3, distinctly, when the raw simulation outputs are simply absent --
the normal state of a fresh clone, since data/ is git-ignored. That is not a
failure of the tables and should not be reported as one.

Usage:
    python tools/check_tables_reproduce.py
    python tools/check_tables_reproduce.py --repo /path/to/clone
"""

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_GENERATOR = Path("analysis/empirical/make_empirical_tables.py")
DEFAULT_TABLES = Path("results/tables")


def git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return its stdout."""
    res = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def dirty(repo: Path, tables: Path) -> tuple[list[str], list[str]]:
    """(modified tracked, untracked) paths under ``tables``, relative to repo."""
    out = git(repo, "status", "--porcelain", "--", str(tables))
    modified, untracked = [], []
    for line in out.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip().strip('"')
        (untracked if code.strip() == "??" else modified).append(path)
    return sorted(modified), sorted(untracked)


def _load_generator(repo: Path, generator: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_empirical_tables", repo / generator)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def expected_tables(repo: Path, generator: Path) -> list[str]:
    """The table filenames the generator declares it owns."""
    return sorted(_load_generator(repo, generator).TABLES)


def missing_inputs(repo: Path, generator: Path) -> list[str]:
    """Raw inputs the generator needs that are not present.

    Derived from the generator's own YEARS and SPECS rather than hard-coded, so
    adding a specification cannot leave this list quietly out of date.
    """
    try:
        mod = _load_generator(repo, generator)
    except (Exception, SystemExit):
        # Importing the generator failed -- possibly SystemExit, which is not an
        # Exception. Say nothing here and let running it report the real problem.
        return []
    years = tuple(getattr(mod, "YEARS", ()))
    if not years:
        # A generator that declares no years reads no per-year raw output, so
        # there is nothing to require. Keeps this honest for stubs and for any
        # future generator with different inputs.
        return []
    data = Path(getattr(mod, "DATA", repo / "data"))
    names = ["behavioral_targets.csv"]
    for year in years:
        for infix in getattr(mod, "SPECS", {}).values():
            names.append(f"empirical_runs{infix}_{year}.csv")
            names.append(f"empirical_candidate_shares{infix}_{year}.csv")
        names.append(f"empirical_robustness_{year}.csv")
        names.append(f"behavioral_sweep_{year}.csv")
    return sorted(n for n in dict.fromkeys(names) if not (data / n).exists())


def check(repo: Path, generator: Path = DEFAULT_GENERATOR,
          tables: Path = DEFAULT_TABLES, verbose: bool = True) -> int:
    """Regenerate and report. Returns a process exit status."""
    def say(*a):
        if verbose:
            print(*a)

    repo = Path(repo).resolve()

    before_mod, before_untracked = dirty(repo, tables)
    if before_mod or before_untracked:
        say("FAIL: the tables directory is already dirty before regenerating, "
            "so any change afterwards could not be attributed.")
        for p in before_mod:
            say(f"  modified  {p}")
        for p in before_untracked:
            say(f"  untracked {p}")
        say("Commit or stash these first.")
        return 2

    absent = missing_inputs(repo, generator)
    if absent:
        say("SKIPPED: the raw simulation outputs this check needs are not here.")
        say("")
        for n in absent[:6]:
            say(f"  missing  data/{n}")
        if len(absent) > 6:
            say(f"  ... and {len(absent) - 6} more")
        say("")
        say("This is expected on a fresh clone: data/ is git-ignored by design, "
            "because the raw outputs are bulky and regenerate from a seed. The "
            "committed tables cannot be re-derived without them.")
        say("Run the empirical pipeline first, or run this check on a machine "
            "that already has its output. Nothing is wrong with the tables.")
        return 3

    res = subprocess.run([sys.executable, str(repo / generator)],
                         cwd=str(repo), capture_output=True, text=True)
    if res.returncode != 0:
        say(f"FAIL: {generator} exited {res.returncode}")
        say(res.stdout.strip())
        say(res.stderr.strip())
        return res.returncode

    after_mod, after_untracked = dirty(repo, tables)

    missing = [n for n in expected_tables(repo, generator)
               if not (repo / tables / n).exists()]

    if after_mod or after_untracked or missing:
        say("FAIL: the committed tables do not reproduce from the raw outputs.")
        for p in after_mod:
            say(f"  changed on regeneration : {p}")
        for p in after_untracked:
            say(f"  unexpected new table    : {p}")
        for n in missing:
            say(f"  missing after generating: {tables / n}")
        say("")
        say("Either the committed bytes are stale -- commit the regenerated "
            "tables -- or the generator is not deterministic.")
        return 1

    n = len(expected_tables(repo, generator))
    say(f"OK: all {n} committed tables reproduce byte-for-byte.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".", type=Path,
                    help="repository root (default: current directory)")
    ap.add_argument("--generator", default=DEFAULT_GENERATOR, type=Path,
                    help="generator script, relative to --repo")
    ap.add_argument("--tables-dir", default=DEFAULT_TABLES, type=Path,
                    help="tables directory, relative to --repo")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    return check(a.repo, a.generator, a.tables_dir, verbose=not a.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
