# Empirical rerun manifest

**Date:** 2026-08-21 · **Base:** `main` @ `9c62ed6` + branch `pre-rerun-safety`
**Status:** nothing has been executed. No simulation has run.

The corrected conversion is

```
tau_absolute = tau_hat * (2.0 / K)
```

with `K` year-specific — 15 in 2002, 12 in 2022 — so one shared `tau_hat` draw
becomes a **different absolute distance in each year**. `tau_hat = 3.0` is
`0.40` in 2002 and `0.50` in 2022.

---

## 1. Scope

### Must be rerun

| # | Work | Why |
|---|---|---|
| 1 | Empirical replay 2002 + 2022, main and robustness | Pre-fix; also only a 15-draw smoke run survives |
| 2 | Three probabilistic-initialisation variants | Pre-fix (6 June) |
| 3 | Behavioural sweeps, both years | Pre-fix (7–8 June) |
| 4–7 | Diagnostics, figures, comparison, LHS importance | Derived from 1–3 |

### Must not be rerun

Saltelli/Sobol, the main synthetic runs, robustness panels A–G, the Panel C
epsilon analysis, horizon validation, population validation, and the protocol
post-hoc analysis.

PR #6 did touch the three synthetic runners, which the original plan did not
anticipate. Line by line, that change replaced `tau_hat * (2.0 / K)` with
`tau_absolute(tau_hat, K)` — the same product, so identical outputs. The audit
found no other behavioural dependency: the `signal_epsilon` plumbing added in
PR #11 is additive and its default is still `1e-12` (`core_model/model.py:100`).

---

## 2. Preconditions

**Done.**

- `tau_absolute` and `K` are now emitted by both runners, converted exactly
  once, at the point of the `run_simulation` call.
- `--quick` writes to `data/smoke/`, so it cannot overwrite a full run.
- `behavioral_sweep.py` has a validated `--resume`.
- Evidence archived and verified: `data/archive/pre_rerun_2026-08-21/`,
  153 files.
- Both runners refuse to touch an existing output unless `--overwrite` is
  given. Existence is the whole test; size is not consulted.
- `pytest -ra` → **477 passed, 6 skipped**.

**Approved.** The probabilistic variants use `--draws 800`, matching the
archived June runs and the fiche's "800 draws each", so the before/after
comparison is like-for-like.

**Overwrite policy.** Every intentional replacement below passes `--overwrite`
explicitly, because every target already exists and is archived. No command
combines `--overwrite` with `--resume`: the sweep CLI refuses that pairing, and
the replay has no resume mechanism to conflict with.

---

## 3. Commands

Copy the preamble once, then run the steps in order.

### Preamble — failure cannot be hidden

```bash
set -o errexit
set -o nounset
set -o pipefail

cd ~/Desktop/strategic-voting-abm-2RS
mkdir -p logs

# Tee to a log while keeping Python's exit status, not tee's.
# pipefail alone would suffice; PIPESTATUS is checked as well so the failing
# step is named. Under `set -e` a non-zero return aborts before the next step.
run () {
    name="$1"; shift
    printf '\n== %s\n   %s\n' "$name" "$*"
    "$@" 2>&1 | tee "logs/${name}.log"
    status=${PIPESTATUS[0]}
    if [ "$status" -ne 0 ]; then
        printf 'FAILED (exit %s): %s -- stopping; dependent steps not run.\n' \
            "$status" "$name" >&2
        exit "$status"
    fi
}
```

### Step 1 — empirical replay, nearest-party baseline

300 main draws per year plus 100 draws × 3 robustness variants per year;
1,200 simulations; ~17 min. Seed `MASTER_SEED = 20020422`, fixed in source.
Ranges: `tau_hat [0.5, 3.0]`, `rho_pi [5, 200]`, `alpha [0.0, 0.9]`,
`mu [0.0, 1.0]`, `N = 2000` voters, LHS, one shared draw across both years.

```bash
run 01_replay_nearest \
    python analysis/empirical/empirical_2002_2022.py --overwrite
```

`--overwrite` is required: the replay refuses to touch any existing output
whatever its size. The 15-row smoke run currently on disk is being replaced
deliberately, and it is archived.

Writes `data/empirical_runs_{2002,2022}.csv`,
`data/empirical_candidate_shares_{2002,2022}.csv`,
`data/empirical_candidate_draws_{2002,2022}.csv`,
`data/empirical_robustness_{2002,2022}.csv` — replacing the 15-row smoke run.
No resume: each invocation rewrites its outputs from the start.

**Validate:**

```bash
run 01_check_runs_2002 \
    python tools/validate_rerun.py data/empirical_runs_2002.csv \
        --year 2002 --expect-rows 300 --log logs/01_replay_nearest.log

run 01_check_runs_2022 \
    python tools/validate_rerun.py data/empirical_runs_2022.csv \
        --year 2022 --expect-rows 300 --log logs/01_replay_nearest.log

run 01_check_robust_2002 \
    python tools/validate_rerun.py data/empirical_robustness_2002.csv \
        --year 2002 --expect-rows 300

run 01_check_robust_2022 \
    python tools/validate_rerun.py data/empirical_robustness_2022.csv \
        --year 2022 --expect-rows 300

run 01_check_draws_2002 \
    python tools/validate_rerun.py data/empirical_candidate_draws_2002.csv \
        --year 2002 --expect-rows 4500

run 01_check_draws_2022 \
    python tools/validate_rerun.py data/empirical_candidate_draws_2022.csv \
        --year 2022 --expect-rows 3600
```

### Step 2 — probabilistic-initialisation variants

800 draws per year per variant; 1,600 simulations each, 4,800 total; ~65 min.
`--overwrite` is required: the pre-fix June outputs hold 800 rows each and are
archived and verified.
Beta enters the design here, range `[0, 20]`. Robustness is skipped
automatically: the runner restricts it to `--sincere-init nearest`.

```bash
run 02a_prob_signal \
    python analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source signal \
        --draws 800 --overwrite

run 02b_prob_prior \
    python analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source prior \
        --draws 800 --overwrite

run 02c_prob_signal_mu0 \
    python analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source signal --mu-zero \
        --draws 800 --overwrite
```

Writes `data/empirical_runs_prob_{signal,prior,signal_mu0}_{2002,2022}.csv`
and the matching `empirical_candidate_shares_*` / `empirical_candidate_draws_*`.

**Validate:**

```bash
for v in signal prior signal_mu0; do
  for y in 2002 2022; do
    run "02_check_${v}_${y}" \
        python tools/validate_rerun.py \
            "data/empirical_runs_prob_${v}_${y}.csv" \
            --year "$y" --expect-rows 800
  done
done
```

### Step 3 — behavioural sweeps (longest stage)

1,000 draws × 4 repeats = 4,000 simulations per year, 8,000 total.
~3 h 30 min per year, ~7 h total. Per-run seed is
`seed + 1000 * (draw + 1) + repeat`; the electorate is sampled once at
`seed + 1` and held fixed. `--n_draws 1000` matches the archived files; the
script's own default is 300.

`--overwrite` is required because the June outputs are still in place; they are
already archived and verified.

```bash
run 03a_sweep_2002 \
    python analysis/empirical/behavioral_sweep.py \
        --year 2002 --n_draws 1000 --n_repeats 4 --seed 20020422 --overwrite

run 03b_sweep_2022 \
    python analysis/empirical/behavioral_sweep.py \
        --year 2022 --n_draws 1000 --n_repeats 4 --seed 20020422 --overwrite
```

Writes `data/behavioral_sweep_{year}.csv`, `_design.csv` and `_meta.json`.

**If either is interrupted**, resume with the same arguments, replacing
`--overwrite` with `--resume`. Every completed draw is kept; the per-run seeds
are unchanged, so the finished file is identical to an uninterrupted run.
Use `tee -a` so the resumed output appends to the existing log:

```bash
python analysis/empirical/behavioral_sweep.py \
    --year 2002 --n_draws 1000 --n_repeats 4 --seed 20020422 --resume \
    2>&1 | tee -a logs/03a_sweep_2002.log
test "${PIPESTATUS[0]}" -eq 0 || echo "resume failed" >&2
```

`--resume` validates year, seed, `n_draws`, `n_repeats`, the schema version and
a fingerprint of the design, and cross-checks every retained row against the
recomputed design. Anything that does not match is refused, never merged.

**Validate:**

```bash
run 03_check_sweep_2002 \
    python tools/validate_rerun.py data/behavioral_sweep_2002.csv \
        --year 2002 --expect-rows 1000 --log logs/03a_sweep_2002.log

run 03_check_sweep_2022 \
    python tools/validate_rerun.py data/behavioral_sweep_2022.csv \
        --year 2022 --expect-rows 1000 --log logs/03b_sweep_2022.log
```

### Step 4 — diagnostics

Depends on steps 1–2. No simulation; reads the CSVs. Minutes.

```bash
run 04a_diag_nearest \
    python analysis/empirical/empirical_diagnostics.py

run 04b_diag_prob_signal \
    python analysis/empirical/empirical_diagnostics.py --tag prob_signal

run 04c_diag_prob_prior \
    python analysis/empirical/empirical_diagnostics.py --tag prob_prior

run 04d_diag_prob_signal_mu0 \
    python analysis/empirical/empirical_diagnostics.py --tag prob_signal_mu0
```

Writes `data/empirical_diagnostics_{year}_*.csv`,
`data/empirical_activation_summary_*.csv`,
`data/empirical_shared_activating_draws_*.csv` and the tagged `fig_diag_*`
figures.

**Validate:** confirm each diagnostics CSV has the expected row count
(800 per year per tag) and that the activation summaries are non-empty:

```bash
run 04_check \
    bash -c 'for f in data/empirical_diagnostics_*.csv \
                      data/empirical_activation_summary_*.csv; do
                printf "%8d  %s\n" "$(($(wc -l < "$f") - 1))" "$f"
             done'
```

### Step 5 — empirical figures

Depends on steps 1–2. Minutes. Overwrites the empirical PNG/PDF pairs in
`figures/`.

```bash
run 05_figures \
    python analysis/empirical/empirical_figures.py
```

### Step 6 — behavioural comparison and sweep figure

Depends on step 3. Minutes.

```bash
run 06a_compare \
    python analysis/empirical/behavioral_compare.py

run 06b_sweep_figure \
    python analysis/empirical/behavioral_sweep_figure.py
```

Writes `data/behavioral_compare_2002_2022.csv` and
`figures/behavioral_sweep.{png,pdf}`. `behavioral_targets.csv` involves no
simulation and is unaffected.

### Step 7 — LHS parameter importance

Depends on step 3. Requires `scikit-learn`. Minutes.

```bash
run 07_lhs_importance \
    python analysis/empirical/lhs_importance.py
```

Writes `results/tables/lhs_parameter_importance.csv` — a **new committed
file**, and the one that turns 4 currently skipped tests into passes.
`tau_absolute` and `K` are excluded from the predictor set: `tau_absolute` is
perfectly collinear with `tau_hat` within a year, and `K` is constant.

**Validate:**

```bash
run 07_check \
    python -m pytest tests/test_result_tables.py -ra
```

Expected: the 4 `lhs_parameter_importance.csv not generated yet` skips are gone.

### Step 8 — full suite and comparison

```bash
run 08a_pytest \
    python -m pytest -ra

run 08b_archive_intact \
    bash -c 'cd data/archive/pre_rerun_2026-08-21 && shasum -c SHA256SUMS --quiet \
             && echo "archive intact"'
```

Then the before/after comparison, against the archive. **State explicitly in
any write-up that no archived raw before-versus-after comparison of the main
replay exists** — the pre-fix full outputs were overwritten on 2026-08-19 by a
`--quick` run and were never committed. One could be regenerated from commit
`70e23f5` under the fixed seed, but has not been.

A genuine raw comparison *is* available for the parts never overwritten:
`behavioral_sweep_{2002,2022}.csv`, `empirical_runs_prob_*.csv` and
`empirical_diagnostics_*.csv`, all from 6–8 June.

### Step 9 — fiche technique (after approval of the comparison)

Not part of the compute. Once the rerun comparison is approved, the fiche is
updated to carry the corrected conversion, the corrected empirical results, the
completed synthetic validation, and the final test and CI status.

> **What actually happened.** The standalone fiche was replaced rather than
> edited: the canonical documentation now lives in this repository under
> `docs/`, with a generated single-page mirror at
> <https://clarasalas.github.io/strategic-voting-abm-2RS/guide.html>. A snapshot of the pre-rerun fiche is preserved at
> `data/archive/pre_rerun_2026-08-21/fiche/fiche_technique_pre_rerun_2026-08-21.html`.

---

## 4. Runtime

| Step | Simulations | Estimate |
|---|---:|---:|
| 1 · replay | 1,200 | ~17 min |
| 2 · prob variants | 4,800 | ~65 min |
| 3 · sweeps | 8,000 | ~7 h 05 min |
| 4–8 · derived | 0 | ~10 min |
| **Total** | **14,000** | **~8 h 40 min** |

Estimates come from each script's own history: ~0.83 s/simulation for the
replay path, measured from the 19 Aug smoke run's timestamps, and
~3.18 s/simulation for the sweep, measured from the 7–8 June run. The sweep is
slower per simulation because it runs to `T_MAX = 25` while the replay stops at
the length of the poll sequence. Treat these as ±30%.

---

## 5. Validation reference

`tools/validate_rerun.py` checks, and exits non-zero on any failure:

| Check | Expected |
|---|---|
| schema | `tau_hat`, `tau_absolute` and `K` all present |
| K | 15 for 2002, 12 for 2022 |
| conversion | `tau_absolute == tau_hat * (2 / K)` row by row, to 1e-12 |
| ceiling | max `tau_absolute` **≤ 0.4** (2002) / **≤ 0.5** (2022) |
| tau_hat | ≤ 3.0, i.e. the design itself did not change |
| rows | the expected number of draws completed |
| finite | no NaN or inf in any numeric column |
| log | the pre-fix `tau >= 2.0` warning appears **zero** times |

The ceiling is year-specific because `K` is, and it is **inclusive**:
`tau_hat = 3.0` is the top of the swept range, so 0.4 and 0.5 are attainable
values, not open limits. A single shared `< 0.50` bound would be 25% too loose
for 2002 and would not notice a 2002 design drifting upward.
