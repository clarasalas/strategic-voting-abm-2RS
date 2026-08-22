# Local rerun runbook

Standalone operating instructions for the corrected empirical rerun. Everything
here is copy-pasteable and needs no Claude session.

| | |
|---|---|
| **Repository** | `~/Desktop/strategic-voting-abm-2RS` |
| **Branch** | `pre-rerun-safety` (pushed to origin) |
| **Commit** | `0bba146cd2a1aeaedc2af1f7b84777603a80ddd9` |
| **Log directory** | `logs/rerun_20260821_launch/` |
| **Started** | 2026-08-21 13:04:02 local |
| **Expected finish** | ≈ 21:45 local (~8 h 40 min) |
| **Total simulations** | 14,000 |

Set this once per terminal — every command below assumes it:

```bash
cd ~/Desktop/strategic-voting-abm-2RS
export LOGDIR=logs/rerun_20260821_launch
```

---

## 1. Monitoring the current run

**Is it alive?**

```bash
ps -p "$(cat $LOGDIR/rerun.pid)" -o pid=,stat=,etime=,command=
```

Prints a line while running, nothing when finished or dead. The `etime` column
is the **elapsed runtime** (`HH:MM:SS`, or `D-HH:MM:SS` past a day).

Elapsed time alone:

```bash
ps -p "$(cat $LOGDIR/rerun.pid)" -o etime=
```

**Last 50 lines of the master log:**

```bash
tail -50 $LOGDIR/master.log
```

**Follow it live** (Ctrl-C stops watching, not the run):

```bash
tail -f $LOGDIR/master.log
```

**Which stages have finished:**

```bash
grep -E "^\S+ \S+  (OK|START|FAILED)" $LOGDIR/master.log
```

**Inspect a single stage log.** One file per stage, named after the stage:

```bash
ls -la $LOGDIR/                       # every stage log written so far
tail -40 $LOGDIR/01_replay_nearest.log
tail -40 $LOGDIR/02a_prob_signal.log
tail -40 $LOGDIR/03a_sweep_2002.log   # sweep progress, 25 draws at a time
tail -40 $LOGDIR/03b_sweep_2022.log
tail -40 $LOGDIR/07_lhs_importance.log
tail -60 $LOGDIR/08a_pytest.log
```

Sweep progress at a glance:

```bash
grep "draws done" $LOGDIR/03a_sweep_2002.log | tail -5
```

**Marker files** — exactly one of these appears at the end:

```bash
ls -la $LOGDIR/COMPLETE    # success
ls -la $LOGDIR/FAILED      # failure; contains the stage name and exit code
cat $LOGDIR/FAILED 2>/dev/null
```

**Run metadata** (commit, host, planned outputs):

```bash
cat $LOGDIR/run_metadata.json
```

**Stopping the pipeline** (only if you need to). This kills the whole process
group — the driver, `caffeinate`, and the running Python — so nothing is left
orphaned:

```bash
PID=$(cat $LOGDIR/rerun.pid)
kill -TERM -"$(ps -o pgid= -p "$PID" | tr -d ' ')"
```

Then confirm it is gone:

```bash
ps -p "$(cat $LOGDIR/rerun.pid)" -o pid= || echo "stopped"
```

A behavioural sweep stopped this way keeps every completed draw and can be
resumed — see §3. A replay stage stopped this way must restart from zero.

---

## 2. Stage order and expected duration

**Simulation stages: 1–3.** These are the ~8.5 hours. Stages 4–8 run no
simulation at all and take minutes in total.

### Stage 1 · `01_replay_nearest` — simulation

| | |
|---|---|
| Command | `python3 analysis/empirical/empirical_2002_2022.py --overwrite` |
| Depends on | nothing |
| Simulations | **1,200** (300 main × 2 years, + 100 draws × 3 variants × 2 years) |
| Runtime | ~17 min |

Outputs and expected rows:

| File | Rows |
|---|---|
| `data/empirical_runs_2002.csv` | 300 |
| `data/empirical_runs_2022.csv` | 300 |
| `data/empirical_robustness_2002.csv` | 300 |
| `data/empirical_robustness_2022.csv` | 300 |
| `data/empirical_candidate_draws_2002.csv` | 4500 |
| `data/empirical_candidate_draws_2022.csv` | 3600 |
| `data/empirical_candidate_shares_2002.csv` | 15 |
| `data/empirical_candidate_shares_2022.csv` | 12 |

Validation afterwards: `01_check_runs_2002`, `01_check_runs_2022`,
`01_check_robust_2002`, `01_check_robust_2022`, `01_check_draws_2002`,
`01_check_draws_2022` — each runs `tools/validate_rerun.py` (schema, K,
`tau_absolute = tau_hat × 2/K`, year ceiling, row count, finiteness, and for the
runs files, that no `tau >= 2.0` warning appears in the stage log).

### Stage 2 · `02a_prob_signal`, `02b_prob_prior`, `02c_prob_signal_mu0` — simulation

| | |
|---|---|
| Commands | `python3 analysis/empirical/empirical_2002_2022.py --sincere-init probabilistic --salience-source signal --draws 800 --overwrite` |
| | `python3 analysis/empirical/empirical_2002_2022.py --sincere-init probabilistic --salience-source prior --draws 800 --overwrite` |
| | `python3 analysis/empirical/empirical_2002_2022.py --sincere-init probabilistic --salience-source signal --mu-zero --draws 800 --overwrite` |
| Depends on | nothing (independent of stage 1) |
| Simulations | **4,800** (1,600 per variant) |
| Runtime | ~65 min total |

Outputs per variant `v ∈ {prob_signal, prob_prior, prob_signal_mu0}`:

| File | Rows |
|---|---|
| `data/empirical_runs_<v>_2002.csv` | 800 |
| `data/empirical_runs_<v>_2022.csv` | 800 |
| `data/empirical_candidate_draws_<v>_2002.csv` | 12000 |
| `data/empirical_candidate_draws_<v>_2022.csv` | 9600 |
| `data/empirical_candidate_shares_<v>_2002.csv` | 15 |
| `data/empirical_candidate_shares_<v>_2022.csv` | 12 |

Robustness is skipped automatically for these — the runner restricts it to
`--sincere-init nearest`.

Validation afterwards: `02_check_<v>_<year>`, six in total.

### Stage 3 · `03a_sweep_2002`, `03b_sweep_2022` — simulation, the long one

| | |
|---|---|
| Commands | `python3 analysis/empirical/behavioral_sweep.py --year 2002 --n_draws 1000 --n_repeats 4 --seed 20020422 --overwrite` |
| | `python3 analysis/empirical/behavioral_sweep.py --year 2022 --n_draws 1000 --n_repeats 4 --seed 20020422 --overwrite` |
| Depends on | nothing |
| Simulations | **8,000** (1000 draws × 4 repeats × 2 years) |
| Runtime | ~3 h 30 min per year, ~7 h total |

| File | Rows |
|---|---|
| `data/behavioral_sweep_2002.csv` | 1000 |
| `data/behavioral_sweep_2022.csv` | 1000 |
| `data/behavioral_sweep_<year>_design.csv` | 1000 |
| `data/behavioral_sweep_<year>_meta.json` | — (sidecar) |

Validation afterwards: `03_check_sweep_2002` runs immediately after 2002 and
before 2022 starts, so a unit error is caught after 3.5 hours rather than 7.

### Stage 4 · `04a_diag_nearest` … `04d_diag_prob_signal_mu0` — no simulation

| | |
|---|---|
| Commands | `python3 analysis/empirical/empirical_diagnostics.py` |
| | `python3 analysis/empirical/empirical_diagnostics.py --tag prob_signal` |
| | `python3 analysis/empirical/empirical_diagnostics.py --tag prob_prior` |
| | `python3 analysis/empirical/empirical_diagnostics.py --tag prob_signal_mu0` |
| Depends on | stages 1 and 2 |
| Simulations | 0 |
| Runtime | minutes |

Outputs: `data/empirical_diagnostics_<year>[_tag].csv` (300 rows for the
nearest baseline, 800 per prob variant), `data/empirical_activation_summary_*`,
`data/empirical_shared_activating_draws_*`, and the tagged `figures/fig_diag_*`
pairs.

> Note: the new tagged files are named `..._prob_signal.csv`, whereas the
> archived June ones are `..._main_prob_signal.csv`. The tag convention
> changed; compare by content, not filename.

Validation afterwards: none automated. Row counts are checked in §4.

### Stage 5 · `05_figures` — no simulation

`python3 analysis/empirical/empirical_figures.py` · depends on stages 1–2 ·
minutes · overwrites the empirical PNG/PDF pairs in `figures/`.

### Stage 6 · `06a_compare`, `06b_sweep_figure` — no simulation

`python3 analysis/empirical/behavioral_compare.py` and
`python3 analysis/empirical/behavioral_sweep_figure.py` · depend on stage 3 ·
minutes · write `data/behavioral_compare_2002_2022.csv` and
`figures/behavioral_sweep.{png,pdf}`.

### Stage 7 · `07_lhs_importance` — no simulation

`python3 analysis/empirical/lhs_importance.py` · depends on stage 3 · minutes ·
writes **`results/tables/lhs_parameter_importance.csv`** (15 rows: 5 parameters
× 3 scopes). This is the file that turns 4 currently skipped tests into passes.

### Stage 8 · `08a_pytest`, `08b_archive_intact` — no simulation

`python3 -m pytest -ra`, then the archive checksum verification. Minutes.

### Totals

| | Simulations | Runtime |
|---|---:|---:|
| Stage 1 | 1,200 | ~17 min |
| Stage 2 | 4,800 | ~65 min |
| Stage 3 | 8,000 | ~7 h 05 min |
| Stages 4–8 | 0 | ~10 min |
| **Total** | **14,000** | **~8 h 40 min** |

---

## 3. Failure recovery

The driver stops at the first failure and writes `$LOGDIR/FAILED`. Nothing
downstream runs, so later outputs are simply absent rather than wrong.

**Always start here:**

```bash
cat $LOGDIR/FAILED                    # names the stage and exit code
STAGE=$(awk '{print $3}' $LOGDIR/FAILED)
tail -40 "$LOGDIR/$STAGE.log"         # the actual error
```

Then re-run **only** the failed stage and everything after it, by hand, using
the commands in §2 in order.

### Stage 1 or 2 failed (empirical replay)

**Why:** `tail -40 "$LOGDIR/$STAGE.log"`.

**What may be partial:** the runner writes a year's files only after that year
finishes, so a mid-run failure typically leaves 2002 written and 2022 absent —
a partial set. `--overwrite` refuses nothing; the guard only blocks a run that
was *not* asked to replace.

**Restart, overwrite or resume:** there is **no resume** for the replay. Each
invocation rewrites from the start, so this stage genuinely must restart from
zero and `--overwrite` is correct here.

```bash
# stage 1
python3 analysis/empirical/empirical_2002_2022.py --overwrite \
    2>&1 | tee -a $LOGDIR/01_replay_nearest.log
test "${PIPESTATUS[0]}" -eq 0 || echo "STILL FAILING"

# stage 2, whichever variant failed
python3 analysis/empirical/empirical_2002_2022.py \
    --sincere-init probabilistic --salience-source signal \
    --draws 800 --overwrite 2>&1 | tee -a $LOGDIR/02a_prob_signal.log
test "${PIPESTATUS[0]}" -eq 0 || echo "STILL FAILING"
```

Then re-run that stage's validation commands from §4.

### Stage 3 failed or was interrupted (behavioural sweep)

**Why:** `tail -40 $LOGDIR/03a_sweep_2002.log`.

**What may be partial:** rows are flushed one draw at a time, so the CSV holds
every completed draw. Check how far it got:

```bash
echo "$(( $(wc -l < data/behavioral_sweep_2002.csv) - 1 )) / 1000 draws"
```

**Restart, overwrite or resume:** **resume.** Do *not* use `--overwrite` — it
discards up to 3.5 hours of completed draws. `--resume` validates year, seed,
`n_draws`, `n_repeats`, the schema version and a fingerprint of the design, and
cross-checks every retained row against the recomputed design before continuing.
The per-run seeds depend only on `(seed, draw, repeat)`, so the finished file is
identical to an uninterrupted run.

```bash
# 2002
python3 analysis/empirical/behavioral_sweep.py \
    --year 2002 --n_draws 1000 --n_repeats 4 --seed 20020422 --resume \
    2>&1 | tee -a $LOGDIR/03a_sweep_2002.log
test "${PIPESTATUS[0]}" -eq 0 || echo "STILL FAILING"

# 2022
python3 analysis/empirical/behavioral_sweep.py \
    --year 2022 --n_draws 1000 --n_repeats 4 --seed 20020422 --resume \
    2>&1 | tee -a $LOGDIR/03b_sweep_2022.log
test "${PIPESTATUS[0]}" -eq 0 || echo "STILL FAILING"
```

**Never pass `--resume` and `--overwrite` together** — the CLI refuses it.

If `--resume` itself refuses, it prints exactly which check failed. That means
the partial file does not belong to this experiment; do not force it. Move it
aside and start clean only then:

```bash
mkdir -p data/rejected
mv data/behavioral_sweep_2002.csv data/behavioral_sweep_2002_meta.json \
   data/behavioral_sweep_2002_design.csv data/rejected/
# then re-run WITHOUT --overwrite (nothing is in the way any more)
python3 analysis/empirical/behavioral_sweep.py \
    --year 2002 --n_draws 1000 --n_repeats 4 --seed 20020422
```

### Stage 4, 5, 6 or 7 failed (no simulation)

**Why:** `tail -40 "$LOGDIR/$STAGE.log"`. The usual cause is a missing or
short input from an earlier stage.

**What may be partial:** some CSVs or figures from that stage. These are cheap
and have no overwrite guard.

**Restart, overwrite or resume:** just re-run the command. No flag needed, no
simulation repeated.

```bash
python3 analysis/empirical/empirical_diagnostics.py --tag prob_signal
python3 analysis/empirical/empirical_figures.py
python3 analysis/empirical/behavioral_compare.py
python3 analysis/empirical/behavioral_sweep_figure.py
python3 analysis/empirical/lhs_importance.py
```

### Stage 8 failed

`08a_pytest` failing means a test broke against the regenerated outputs —
investigate, do not re-run the simulations. `08b_archive_intact` failing means
the archive was modified; see §4.

---

## 4. Verifying successful completion

Run these in order. Each is independent and safe to repeat.

**Markers:**

```bash
ls $LOGDIR/COMPLETE && echo "COMPLETE present"
test ! -e $LOGDIR/FAILED && echo "FAILED absent" || cat $LOGDIR/FAILED
cat $LOGDIR/COMPLETE
```

**Every stage completed** (expect 31 `OK` lines and no `FAILED`):

```bash
grep -c "  OK     " $LOGDIR/master.log
grep "FAILED" $LOGDIR/master.log || echo "no failures logged"
```

**14,000 simulations present**, recomputed from the files themselves:

```bash
python3 - <<'PY'
import pandas as pd, glob
rows = lambda p: len(pd.read_csv(p))
main  = sum(rows(f"data/empirical_runs_{y}.csv") for y in (2002, 2022))
rob   = sum(rows(f"data/empirical_robustness_{y}.csv") for y in (2002, 2022))
prob  = sum(rows(f"data/empirical_runs_prob_{v}_{y}.csv")
            for v in ("signal", "prior", "signal_mu0") for y in (2002, 2022))
sweep = sum(rows(f"data/behavioral_sweep_{y}.csv") * 4 for y in (2002, 2022))
total = main + rob + prob + sweep
print(f"  replay main       {main:>6}   (expect   600)")
print(f"  robustness        {rob:>6}   (expect   600)")
print(f"  prob variants     {prob:>6}   (expect  4800)")
print(f"  sweeps (x4 reps)  {sweep:>6}   (expect  8000)")
print(f"  TOTAL             {total:>6}   (expect 14000)")
print("  OK" if total == 14000 else "  MISMATCH")
PY
```

**Row counts and unique keys:**

```bash
python3 - <<'PY'
import pandas as pd
expect = {
    "data/empirical_runs_2002.csv": 300, "data/empirical_runs_2022.csv": 300,
    "data/empirical_robustness_2002.csv": 300, "data/empirical_robustness_2022.csv": 300,
    "data/empirical_candidate_draws_2002.csv": 4500,
    "data/empirical_candidate_draws_2022.csv": 3600,
    "data/behavioral_sweep_2002.csv": 1000, "data/behavioral_sweep_2022.csv": 1000,
}
for v in ("signal", "prior", "signal_mu0"):
    for y in (2002, 2022):
        expect[f"data/empirical_runs_prob_{v}_{y}.csv"] = 800
bad = 0
for path, n in sorted(expect.items()):
    df = pd.read_csv(path)
    ok_rows = len(df) == n
    # draw ids must be unique wherever a row IS a draw
    uniq = df["draw"].is_unique if "candidate_draws" not in path else True
    flag = "ok " if (ok_rows and uniq) else "BAD"
    if flag == "BAD": bad += 1
    print(f"  [{flag}] {path:<52} {len(df):>6} rows (expect {n}) unique_draw={uniq}")
print("  all good" if bad == 0 else f"  {bad} problem(s)")
PY
```

**`tau_absolute = tau_hat × 2/K`, ceilings, finiteness** — the validator, on
every regenerated file:

```bash
V=tools/validate_rerun.py
python3 $V data/empirical_runs_2002.csv --year 2002 --expect-rows 300
python3 $V data/empirical_runs_2022.csv --year 2022 --expect-rows 300
python3 $V data/empirical_robustness_2002.csv --year 2002 --expect-rows 300
python3 $V data/empirical_robustness_2022.csv --year 2022 --expect-rows 300
python3 $V data/empirical_candidate_draws_2002.csv --year 2002 --expect-rows 4500
python3 $V data/empirical_candidate_draws_2022.csv --year 2022 --expect-rows 3600
for v in signal prior signal_mu0; do
  for y in 2002 2022; do
    python3 $V "data/empirical_runs_prob_${v}_${y}.csv" --year "$y" --expect-rows 800
  done
done
python3 $V data/behavioral_sweep_2002.csv --year 2002 --expect-rows 1000
python3 $V data/behavioral_sweep_2022.csv --year 2022 --expect-rows 1000
```

Every block must end `All checks passed.` The ceiling is year-specific and
inclusive: `≤ 0.4` for 2002 (K=15), `≤ 0.5` for 2022 (K=12).

**No `tau >= 2` warning anywhere in the new logs** — this is the pre-fix bug's
direct signature, and it must appear zero times:

```bash
grep -rc ">= 2.0: every party is a contender" $LOGDIR/*.log | grep -v ":0$" \
  && echo "PROBLEM: the pre-fix warning appears above" \
  || echo "OK: zero occurrences in every stage log"
```

**Archive checksums still valid:**

```bash
( cd data/archive/pre_rerun_2026-08-21 && shasum -c SHA256SUMS --quiet \
  && echo "archive intact (153 files)" )
```

**Downstream tables and figures exist:**

```bash
ls -la data/empirical_diagnostics_*.csv
ls -la data/empirical_activation_summary_*.csv
ls -la data/behavioral_compare_2002_2022.csv
ls -la figures/behavioral_sweep.png figures/fig_sim_vs_actual.png
echo "figures: $(ls figures | wc -l) files"
```

**The importance table:**

```bash
ls -la results/tables/lhs_parameter_importance.csv
head -3 results/tables/lhs_parameter_importance.csv
python3 -c "import pandas as pd; d=pd.read_csv('results/tables/lhs_parameter_importance.csv'); print(d.shape, sorted(d['scope'].unique()), sorted(d['parameter'].unique()))"
```

Expect 15 rows × 10 columns, scopes `2002 / 2022 / pooled`, parameters
`alpha, beta, mu, rho_pi, tau_hat`. Compare regenerated copies **numerically,
not by checksum**: the surrogate is fitted in parallel and the last bit of a
double can move (~1e-16) without any ranking changing.

**Full test suite and remaining skips:**

```bash
python3 -m pytest -ra 2>&1 | tail -20
```

Expect **481 passed, 2 skipped** once the importance table exists — the 4
`lhs_parameter_importance.csv not generated yet` skips become passes. The two
that legitimately remain:

- `test_protocol_validation.py` — `eps_s plumbing now exists; this guard is obsolete`
- `test_result_tables.py` — `panel E is analytic: no repetitions`

**Final git status** — regenerated data is git-ignored, so the only tracked
change should be the new importance table:

```bash
git status --short
git log --oneline -1
```

---

## 5. Post-run commands, in order

Nothing here commits anything or touches the fiche.

**1 · Validate every regenerated output** — the full validator block from §4,
plus the warning grep and the archive check.

**2 · Generate the before/after comparison** against the archive:

```bash
python3 - <<'PY'
import pandas as pd
A = "data/archive/pre_rerun_2026-08-21/data"
pairs = [("behavioral_sweep_2002.csv", 2002), ("behavioral_sweep_2022.csv", 2022)]
for v in ("signal", "prior", "signal_mu0"):
    for y in (2002, 2022):
        pairs.append((f"empirical_runs_prob_{v}_{y}.csv", y))
for name, year in pairs:
    old = pd.read_csv(f"{A}/{name}")
    new = pd.read_csv(f"data/{name}")
    col = "mean_delta_cenp" if "sweep" in name else "delta_cenp"
    print(f"\n{name}  ({len(old)} -> {len(new)} rows)")
    for c in (col, "trigger_rate", "conditional_switching_rate"):
        if c in old.columns and c in new.columns:
            print(f"   {c:<28} before {old[c].mean():+.4f}   after {new[c].mean():+.4f}")
PY
```

> **State this in any write-up:** a direct raw before/after comparison of the
> **main replay** is impossible. Its pre-fix outputs were overwritten on
> 2026-08-19 by a `--quick` run and were never committed, so the archived
> `empirical_runs_{2002,2022}.csv` are that smoke run. For the main replay the
> archived logs, figures and fiche snapshot are **historical evidence only**.
> The comparison above is genuine only for the sweeps, the probabilistic
> variants and the diagnostics, which were never overwritten.

**3 · Produce the proposed fiche updates.** Work from
`docs/documentation_plan.md`, which marks every section ready / partial /
blocked. Draft the changes and the change log **without publishing**. The
current fiche is snapshotted at
`data/archive/pre_rerun_2026-08-21/fiche/fiche_technique_pre_rerun_2026-08-21.html`.

**4 · Review before committing anything:**

```bash
git status --short
git diff --stat
git diff results/tables/lhs_parameter_importance.csv
python3 -m pytest -ra 2>&1 | tail -5
```

Only `results/tables/lhs_parameter_importance.csv` should be a tracked change.
Everything under `data/`, `figures/` and `logs/` is git-ignored by design.

---

## 6. Warnings

- **Do not launch the pipeline twice.** A second run would fight the first for
  the same output files. Check `ps -p "$(cat $LOGDIR/rerun.pid)"` first.
- **Do not edit files, switch branches, `git pull`, or `git checkout` while it
  runs.** The driver imports the working tree on every stage; changing it
  mid-run means different stages ran different code.
- **Keep the Mac plugged in and the lid open.** `caffeinate -i -s` prevents
  idle and system sleep, but **closing the lid still sleeps the machine** on
  most configurations.
- **Closing Claude and closing the terminal will not stop it.** The driver was
  launched with `nohup` and disowned; it is not a child of any terminal.
- **Restarting or shutting down the Mac will stop it.** So will a kernel panic
  or a power loss on battery. If that happens, follow §3: the behavioural
  sweeps resume, the replay stages restart.
- **Never pass `--resume` and `--overwrite` together.** The CLI refuses it.
- **Do not use `--overwrite` to recover an interrupted sweep** — it discards
  every completed draw. Use `--resume`.
