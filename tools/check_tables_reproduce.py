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


def expected_tables(repo: Path, generator: Path) -> list[str]:
    """The table filenames the generator declares it owns."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_empirical_tables", repo / generator)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return sorted(mod.TABLES)


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
