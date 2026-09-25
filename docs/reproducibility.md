<h1 align="center">Reproducibility</h1>

<p align="center">
How to install the model, run it, and rebuild every committed number.
</p>

<p align="center"><sub>
<a href="experiments.md">← Experiments</a> · <strong>Reproducibility</strong> · <a href="code_map.md">Code map →</a>
</sub></p>

## Install

Python 3.10 or later. Every committed result was produced under 3.11.

```bash
git clone https://github.com/clarasalas/strategic-voting-abm-2RS.git
cd strategic-voting-abm-2RS
pip install -e .                  # the model
pip install -e ".[analysis]"      # plus SALib and scikit-learn, for the analysis scripts
pip install pytest                # for the tests
```

The first line installs only what the model imports: numpy, scipy, matplotlib and pandas. The analysis scripts need
two more packages, SALib for the sensitivity analysis and scikit-learn for the importance analysis, and they come
with the `[analysis]` extra.

<details>
<summary><strong>Which file to install from</strong></summary>

<br>

[`requirements.txt`](../requirements.txt) and [`pyproject.toml`](../pyproject.toml) give minimum versions, and are
the right files for running the code. [`requirements-lock.txt`](../requirements-lock.txt) gives the exact versions
that produced the committed tables, and is the right file when the question is why a number came out as it did.

</details>

## See it run

About ten seconds:

```python
from core_model.model import run_simulation
from core_model.metrics import tau_absolute, enp

K = 8
res = run_simulation(
    K=K, n_modes=1, width_factor=1.5, theta=1.0, rho=100.0, rho_pi=100.0,
    n_electors=500,
    tau=tau_absolute(1.75, K),      # convert the tolerance first; never pass tau_hat directly
    mu=0.1, alpha_prior=0.0, K_runoff=2,
    max_iterations=15, seed=42, verbose=False, collect_diagnostics=True,
)
print(f"ENP  sincere {enp(res['sincere_shares']):.3f}  ->  final {enp(res['final_shares']):.3f}")
print(f"winner   party {res['winner_id']}")
print(f"switchers {res['switching']['strategic']} of 500")
```

```
ENP  sincere 5.441  ->  final 5.208
winner   party 4
switchers 19 of 500
```

This is the configuration pinned by `test_golden_synthetic_baseline`, so if these three numbers ever change, that
test fails first. A quick empirical run, written to `data/smoke/` so that it cannot touch real output:

```bash
python analysis/empirical/empirical_2002_2022.py --quick
```

## Run the tests

```bash
python -m pytest -ra                                 # everything
python -m pytest -ra tests/test_decision_rule.py     # one family
python -m pytest -ra -k tau                          # by keyword
```

`-ra` prints the reason for any skipped test; there are none at the moment. The latest recorded result and the
warning policy are in [Validation → Where things stand](validation.md#where-things-stand).

CI runs the same suite on every push and on every pull request to `main`, on a clean machine with a fresh install.
It is the authoritative check. Results quoted elsewhere in the documentation are dated runs on one machine, and CI
has already caught a defect that such a run missed.

<details>
<summary><strong>What CI does exactly</strong></summary>

<br>

[`.github/workflows/tests.yml`](../.github/workflows/tests.yml) sets up Python 3.11, installs `requirements.txt`,
pytest and `pip install -e ".[analysis]"`, imports every analysis script with
`tools/check_analysis_imports.py`, then runs `pytest -ra` with no suppressed failures. It installs minimum versions
rather than the lock file on purpose, so that it checks the code still works as its dependencies move. It was merged
in [#13](https://github.com/clarasalas/strategic-voting-abm-2RS/pull/13), and its
[run history](https://github.com/clarasalas/strategic-voting-abm-2RS/actions) is public.

</details>

## Rebuild the committed numbers

Some tables rebuild in seconds from files already in the repository; others need the raw simulation output, which is
not committed and has to be regenerated first.

**No simulation needed.** The Sobol indices rebuild from the raw matrices, whose 30 720 evaluations are committed:

```bash
python analysis/synthetic/saltelli_sensitivity.py --analyze-existing
```

**Once the raw empirical output exists in `data/`:**

```bash
python analysis/empirical/make_empirical_tables.py   # the 6 empirical tables
python analysis/empirical/lhs_importance.py          # the importance table
python tools/check_tables_reproduce.py               # fails, naming the files, if a committed table changed
```

**Simulations:**

```bash
python analysis/synthetic/robustness_checks.py       # panels A–G, 2 to 4 minutes
python analysis/synthetic/protocol_validation.py     # enough rounds, enough voters
python analysis/empirical/empirical_2002_2022.py     # the replay
python analysis/empirical/behavioral_sweep.py --year 2002 --n_draws 1000 --n_repeats 4 --seed 20020422
```

<details>
<summary><strong>The whole empirical pipeline, unattended</strong></summary>

<br>

```bash
tools/archive_pre_rerun.sh <archive-name> "" <note.md>
RUN_NAME=<run-name> RERUN_ARCHIVE=data/archive/<archive-name> \
  caffeinate -i nohup tools/run_empirical_rerun.sh > /dev/null 2>&1 &
```

The driver refuses to start without an archive of the current outputs, and refuses to reuse a run name. It writes
`logs/<run-name>/`: the run metadata (commit, settings, seeds), the hashes of every input, a master log, a log per
stage, a PID file, and a `COMPLETE` or `FAILED` marker. The last run was 14 200 simulations in about 2 h 30.
`RERUN_SMOKE=1` runs the same commands at a few draws each, in a separate worktree.

How to run and check it: [`tools/README.md`](../tools/README.md). The latest run is recorded in the
[run record](reports/empirical_rerun_2026-09-24.md). The August 2026 runbook,
[`local_rerun_runbook.md`](notes/local_rerun_runbook.md), has more on monitoring and recovery.

</details>

<details>
<summary><strong>Checking a finished run</strong></summary>

<br>

```bash
export LOGDIR=logs/<run-name>

ls $LOGDIR/COMPLETE && grep -c "  OK     " $LOGDIR/master.log   # one per stage: 33 in the 2026-09-24 run

# tolerance units, ceilings, row counts and finite values, file by file
python3 tools/validate_rerun.py data/empirical_runs_2002.csv --year 2002 --expect-rows 300

# the sign of the old unit error must not appear in any simulation log
grep -l ">= 2.0: every party is a contender" $LOGDIR/0[1-7]*.log || echo "clean"

python -m pytest -ra | tail -3
```

The full list of twelve checks is in
[`local_rerun_runbook.md`](notes/local_rerun_runbook.md#4-verifying-successful-completion).

</details>

## How exactly things reproduce

| Output | Guarantee | How to compare |
|---|---|---|
| Model runs | bit-identical for a fixed seed | direct equality |
| `sobol_indices.csv` | rebuilds exactly from committed inputs | checksum |
| The 6 empirical tables | byte-identical when regenerated | checksum |
| `lhs_parameter_importance.csv` | reproducible, but not byte-identical | numerically |

The importance table is fitted in parallel, so the order of floating-point sums is not fixed and the last bit of a
number can move (~1e-16). Its predictors and all seeds are fixed, the values reproduce within tolerance and the
rankings are stable, but it should never be compared by checksum.

## What is committed, and what is not

The rule is to commit the numbers a reader needs to cite, and to regenerate the rest. Raw simulation output is bulky
and comes back from a seed, while the derived tables are small and easy to compare line by line.

| Committed | Not committed |
|---|---|
| `results/tables/*.csv` (23) | `data/empirical_*`, `data/behavioral_*` |
| Real inputs (`polls_*`, `results_*`, `party_positions_*`, `voters_ideology_*`) | `data/smoke/`, `data/archive/` |
| `data/saltelli_results_K{6,8,9}.csv` | `figures/` (108 files) |
| All code, tests and documentation | `logs/`, `analysis/**/outputs/` |

---

<p align="center"><sub>
<a href="experiments.md">← Experiments</a> · <strong>Reproducibility</strong> · <a href="code_map.md">Code map →</a>
</sub></p>
