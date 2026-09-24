<h1 align="center">tools</h1>

<p align="center">
Scripts around the model: building its inputs, running the whole empirical pipeline, and checking and archiving
what it produces.
</p>

<p align="center"><sub><a href="../README.md">← Back to the project</a></sub></p>

## What is in here

| Script | What it does |
|---|---|
| [`build_polls_from_wikipedia.py`](build_polls_from_wikipedia.py) | Builds `data/polls_{2002,2022}.csv` from fixed revisions of the French Wikipedia poll lists, matching each column to a candidate by name. |
| [`build_cses_inputs.py`](build_cses_inputs.py) | Builds candidate positions and electorates from the CSES surveys and the Ipsos 2022 table, into `data/cses/`. |
| [`run_empirical_rerun.sh`](run_empirical_rerun.sh) | Runs the whole empirical pipeline unattended, checks each stage before the next, and stops at the first failure. |
| [`validate_rerun.py`](validate_rerun.py) | Checks one output file: row count, tolerance units, ceilings, and the warnings the old unit error left in the logs. |
| [`archive_pre_rerun.sh`](archive_pre_rerun.sh) | Takes a checksummed copy of the current outputs before a rerun replaces them. |
| [`check_tables_reproduce.py`](check_tables_reproduce.py) | Rebuilds the committed tables and fails if any of them changes. |
| [`check_analysis_imports.py`](check_analysis_imports.py) | Imports every analysis script, so a broken import fails loudly. Runs in CI before the tests. |

## A full rerun

```bash
tools/archive_pre_rerun.sh <archive-name> "" <note.md>          # keep what is there now
RUN_NAME=<run-name> RERUN_ARCHIVE=data/archive/<archive-name> \
  caffeinate -i nohup tools/run_empirical_rerun.sh > /dev/null 2>&1 &
tail -f logs/<run-name>/master.log
```

The driver refuses to start without an archive, and refuses to reuse a run name. It records the commit, the input
hashes and the settings in `logs/<run-name>/`, and writes `COMPLETE` or `FAILED` there when it stops. A full run
is 14,200 simulations and took about 2.5 hours on the last run.

`RERUN_SMOKE=1` runs the same commands at a few draws each. Use it in a separate worktree, never in the folder
that holds the real outputs.

<details>
<summary><strong>After a run</strong></summary>

<br>

1. Read `logs/<run-name>/master.log`: every stage should say `OK`.
2. Review the regenerated tables in `results/tables/` and commit them.
3. Run `python tools/check_tables_reproduce.py` on the committed state. It fails by design while regenerated
   tables are still uncommitted.
4. Write a record in `docs/reports/`, like
   [the 2026-09-24 one](../docs/reports/empirical_rerun_2026-09-24.md), and tag the run's commit.

If a sweep is interrupted, rerun that one command with `--resume` in place of `--overwrite`, never both.

</details>

<details>
<summary><strong>Where to read more</strong></summary>

<br>

* [Reproducibility](../docs/reproducibility.md): install, run, regenerate, verify.
* [Rerun runbook](../docs/notes/local_rerun_runbook.md) and [rerun manifest](../docs/notes/rerun_manifest.md):
  the operating notes written for the August 2026 run.

</details>
