# Reproducibility

[← Experiments](experiments.md) · **Reproducibility** · [Code map →](code_map.md)

---

## Installation

Requires **Python 3.10 or later**; every committed result was produced under
**3.11**.

```bash
git clone https://github.com/clarasalas/strategic-voting-abm-2RS.git
cd strategic-voting-abm-2RS
python -m pip install -r requirements.txt
```

`requirements.txt` lists what the *model* needs:

```
numpy>=1.24   scipy>=1.10   matplotlib>=3.7   pandas>=2.0   SALib>=1.4
```

Two more are needed to run the **test suite** and are installed separately —
they are not model dependencies:

```bash
pip install pytest scikit-learn
```

> `scikit-learn` is imported by `lhs_importance.py` (the RandomForest surrogate).
> Whether it belongs in `requirements.txt` is a genuine question about the
> model's declared dependencies, deliberately left open rather than settled by
> convenience.

---

## Smoke example (~10 seconds)

The fastest way to see the model do something real:

```bash
python -c "
import sys; sys.path.insert(0, 'core_model')
from model import run_simulation
from metrics import tau_absolute, enp

K = 8
res = run_simulation(
    K=K, n_modes=1, width_factor=1.5, theta=1.0, rho=100.0, rho_pi=100.0,
    n_electors=500,
    tau=tau_absolute(1.75, K),      # NEVER pass tau_hat straight in
    mu=0.1, alpha_prior=0.0, K_runoff=2,
    max_iterations=15, seed=42, verbose=False, collect_diagnostics=True,
)
print(f\"ENP  sincere {enp(res['sincere_shares']):.3f}  ->  final {enp(res['final_shares']):.3f}\")
print(f\"winner   party {res['winner_id']}\")
print(f\"switchers {res['switching']['strategic']} of 500\")
"
```

Expected output:

```
ENP  sincere 5.441  ->  final 5.208
winner   party 4
switchers 19 of 500
```

> `core_model` uses flat imports internally, so it must be on `sys.path` — that
> is how every script in `analysis/` loads it. This exact configuration is the
> one pinned by `test_golden_synthetic_baseline`, so if these three numbers ever
> change, that test fails first.

A quick empirical run, isolated under `data/smoke/`:

```bash
python analysis/empirical/empirical_2002_2022.py --quick
```

---

## Running the tests

```bash
python -m pytest -ra                                 # full suite
python -m pytest -ra tests/test_decision_rule.py     # one family
python -m pytest -ra -k tau                          # by keyword
```

`-ra` shows skip reasons; the suite currently has none. For the most recent
recorded result, the environment it was taken in, and the warning policy, see
[Validation → Verification snapshot](validation.md#verification-snapshot).

---

## Regenerating committed artefacts

### Needs no simulation

```bash
python analysis/synthetic/saltelli_sensitivity.py --analyze-existing
```

Recomputes `sobol_indices.csv` from the committed raw matrices — all 30 720
evaluations are already on disk.

Once raw empirical output exists in `data/`:

```bash
python analysis/empirical/make_empirical_tables.py   # 6 empirical tables
python analysis/empirical/lhs_importance.py          # importance table
```

### Needs simulation

```bash
python analysis/synthetic/robustness_checks.py       # panels A–G, ~2–4 min
python analysis/synthetic/protocol_validation.py     # horizon + population
python analysis/empirical/empirical_2002_2022.py     # replay
python analysis/empirical/behavioral_sweep.py --year 2002 --n_draws 1000 --n_repeats 4 --seed 20020422
```

### The whole empirical pipeline

```bash
bash tools/run_empirical_rerun.sh
```

Unattended driver: writes `run_metadata.json` (commit, host, PID, planned
outputs), a master log, per-stage logs, a PID file, and a `COMPLETE` or `FAILED`
marker. Uses `caffeinate` on macOS. **~4 hours, 14 000 simulations.** Full
operating instructions — monitoring, recovery, verification — are in
[`local_rerun_runbook.md`](local_rerun_runbook.md), and the most recent
execution is recorded in the
[empirical rerun record](reports/empirical_rerun_2026-08-21.md).

---

## Determinism guarantees

| Artefact | Guarantee | How to compare |
|---|---|---|
| Model runs | **bit-identical** for a fixed seed | direct equality |
| `sobol_indices.csv` | regenerates exactly from committed inputs | checksum |
| The 6 empirical tables | **byte-identical** on regeneration | checksum |
| `lhs_parameter_importance.csv` | reproducible, **not** byte-identical | **numerically** |

> ⚠️ The importance table is fitted in parallel, so the order of floating-point
> reduction is not fixed and the last bit of a double can move (~1e-16).
> Predictor selection and all seeds are fixed; values reproduce within tolerance
> and rankings are stable. **Never compare it by checksum.**

---

## What is committed and what is not

| Committed | Ignored |
|---|---|
| `results/tables/*.csv` (22) | `data/empirical_*`, `data/behavioral_*` |
| Real input data (`polls_*`, `results_*`, `party_positions_*`, `voters_ideology_*`) | `data/smoke/`, `data/archive/` |
| `data/saltelli_results_K{6,8,9}.csv` | `figures/` (108 files) |
| All source, tests and docs | `logs/`, `analysis/**/outputs/` |

The principle: **commit the numbers a reader needs to cite; regenerate the rest.**
Raw simulation output is bulky and reproducible from a seed; derived tables are
small and diff-readable.

---

## Continuous integration

> ⚠️ **There is no active CI for this repository.** No GitHub Actions workflow
> is running, so no build or test badge would be meaningful. Every test result
> quoted in this documentation is a **local run on a single machine**, recorded
> with its date and commit.

A workflow is drafted on the `add-ci-workflow` branch — Python 3.11, pip caching
keyed on `requirements.txt`, `pytest -ra` with no suppressed failures.

> **Not yet pushed.** It needs a token with `workflow` scope:
> ```bash
> gh auth refresh -h github.com -s workflow
> git push -u origin add-ci-workflow
> ```
> Until a workflow is actually running, no CI badge belongs in the README.

---

## Verifying a completed rerun

```bash
export LOGDIR=logs/rerun_20260821_launch

ls $LOGDIR/COMPLETE && grep -c "  OK     " $LOGDIR/master.log   # expect 30

# tau relation, ceilings, row counts, finiteness — per file
python3 tools/validate_rerun.py data/empirical_runs_2002.csv --year 2002 --expect-rows 300

# the pre-fix defect signature must not appear in ANY simulation log
grep -l ">= 2.0: every party is a contender" $LOGDIR/0[1-7]*.log || echo "clean"

python -m pytest -ra | tail -3
```

The full twelve-check verification block is in
[`local_rerun_runbook.md`](local_rerun_runbook.md#4-verifying-successful-completion).

---

[← Experiments](experiments.md) · **Reproducibility** · [Code map →](code_map.md)
