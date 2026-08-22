"""
The regeneration check must actually fail.

`make_empirical_tables.py && git status --short` exits 0 whether or not a table
changed, so it only works if a human reads the output. tools/check_tables_reproduce.py
replaces it with something a pipeline can enforce, and these tests pin both
directions: it passes on a clean regeneration and fails, with the filenames, on
each way it can go wrong.

Every case runs against a throwaway git repository built in tmp_path, so none
of this touches the real results/tables.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import check_tables_reproduce as ctr  # noqa: E402


# --------------------------------------------------------------------------- #
#  A throwaway repository whose "generator" we control
# --------------------------------------------------------------------------- #

GENERATOR = '''\
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results" / "tables"
TABLES = {{"alpha.csv": None, "beta.csv": None}}
CONTENT = {content!r}
EXTRA = {extra!r}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        (OUT / name).write_text(CONTENT.get(name, "x\\n1\\n"))
    for name, text in EXTRA.items():
        (OUT / name).write_text(text)


if __name__ == "__main__":
    main()
'''

BASELINE = {"alpha.csv": "x\n1\n", "beta.csv": "x\n2\n"}


def _make_repo(tmp_path, content=None, extra=None, commit_tables=True):
    repo = tmp_path / "repo"
    (repo / "results" / "tables").mkdir(parents=True)
    # The real repository ignores these; without it, running the generator
    # leaves __pycache__ behind and the fixture stops resembling the real case.
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    (repo / "gen.py").write_text(GENERATOR.format(
        content=content if content is not None else BASELINE,
        extra=extra or {}))

    for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"],
                ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True,
                       capture_output=True)

    # Commit the baseline tables, so "changed" means changed against them.
    for name, text in BASELINE.items():
        (repo / "results" / "tables" / name).write_text(text)
    if commit_tables:
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"],
                       check=True, capture_output=True)
    return repo


def _check(repo, capsys):
    code = ctr.check(repo, Path("gen.py"), Path("results/tables"))
    return code, capsys.readouterr().out


# --------------------------------------------------------------------------- #
#  Passing
# --------------------------------------------------------------------------- #

def test_passes_when_regeneration_is_clean(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    code, out = _check(repo, capsys)
    assert code == 0
    assert "reproduce byte-for-byte" in out


def test_passing_case_leaves_the_repository_clean(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    _check(repo, capsys)
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                            capture_output=True, text=True).stdout
    assert status.strip() == ""


# --------------------------------------------------------------------------- #
#  Failing
# --------------------------------------------------------------------------- #

def test_fails_when_a_tracked_table_changes(tmp_path, capsys):
    """The committed bytes are stale, or the generator is not deterministic."""
    repo = _make_repo(tmp_path, content={"alpha.csv": "x\n999\n",
                                         "beta.csv": "x\n2\n"})
    code, out = _check(repo, capsys)
    assert code == 1
    assert "alpha.csv" in out
    assert "changed on regeneration" in out
    assert "beta.csv" not in out.split("changed on regeneration")[1]


def test_fails_when_an_unexpected_untracked_table_appears(tmp_path, capsys):
    repo = _make_repo(tmp_path, extra={"gamma.csv": "x\n3\n"})
    code, out = _check(repo, capsys)
    assert code == 1
    assert "gamma.csv" in out
    assert "unexpected new table" in out


def test_names_every_affected_file(tmp_path, capsys):
    repo = _make_repo(tmp_path,
                      content={"alpha.csv": "x\n9\n", "beta.csv": "x\n9\n"},
                      extra={"gamma.csv": "x\n3\n"})
    code, out = _check(repo, capsys)
    assert code == 1
    for name in ("alpha.csv", "beta.csv", "gamma.csv"):
        assert name in out


def test_fails_when_the_tables_directory_is_already_dirty(tmp_path, capsys):
    """A pre-existing edit would make any later diff unattributable."""
    repo = _make_repo(tmp_path)
    (repo / "results" / "tables" / "alpha.csv").write_text("x\ntampered\n")
    code, out = _check(repo, capsys)
    assert code == 2
    assert "already dirty" in out
    assert "alpha.csv" in out


def test_fails_when_the_generator_itself_fails(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    (repo / "gen.py").write_text("raise SystemExit(3)\n")
    code, out = _check(repo, capsys)
    assert code == 3
    assert "exited 3" in out


def test_fails_when_an_expected_table_is_not_produced(tmp_path, capsys):
    """Declared in TABLES but never written: silent loss of an artefact."""
    repo = _make_repo(tmp_path)
    (repo / "gen.py").write_text(textwrap.dedent('''\
        from pathlib import Path
        OUT = Path(__file__).resolve().parent / "results" / "tables"
        TABLES = {"alpha.csv": None, "beta.csv": None}
        def main():
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "alpha.csv").write_text("x\\n1\\n")
            (OUT / "beta.csv").unlink(missing_ok=True)
        if __name__ == "__main__":
            main()
        '''))
    code, out = _check(repo, capsys)
    assert code == 1
    assert "beta.csv" in out


# --------------------------------------------------------------------------- #
#  The real repository
# --------------------------------------------------------------------------- #

def test_the_real_checker_defaults_point_at_the_real_generator():
    assert (REPO / ctr.DEFAULT_GENERATOR).exists()
    assert (REPO / ctr.DEFAULT_TABLES).is_dir()
