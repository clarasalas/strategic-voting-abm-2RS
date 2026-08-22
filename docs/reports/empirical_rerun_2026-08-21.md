# Empirical rerun record — 2026-08-21

[← Experiments](../experiments.md) · **Rerun record** · [Reproducibility →](../reproducibility.md)

A dated record of the corrected empirical rerun: what was wrong, what was run,
how it was validated, and what it produced.

> **Scope.** This is a process and validation record for a **research
> prototype**, written to document a reproducible empirical stress test. It
> reports what the corrected pipeline produced. It is not a study of how well
> the model fits French elections, and it makes no recommendation about
> calibration or model design.

| | |
|---|---|
| **Commit** | `0bba146cd2a1aeaedc2af1f7b84777603a80ddd9` |
| **Branch** | `pre-rerun-safety` |
| **Window** | 2026-08-21, 13:04:02 → 17:11:13 local (4 h 07) |
| **Simulations** | 14 000 |
| **Stages** | 30 / 30 OK |

---

## 1. The defect: an unapplied tolerance conversion

The model consumes an **absolute** tolerance τ in ideology units on [−1, 1].
Every design, sweep and CSV records the **normalised** τ̂, measured in zone
lengths. They are related through the zone length ℓ = 2/*K*:

> **τ = τ̂ × (2 / K)**

On the empirical side that conversion was not applied — τ̂ was passed straight
into `run_simulation` and silently reinterpreted as an absolute distance.

| | Effective τ before | Effective τ after |
|---|---|---|
| 2002 (*K* = 15) | 0.500 – 3.000 | **0.067 – 0.400** |
| 2022 (*K* = 12) | 0.500 – 3.000 | **0.083 – 0.500** |

Too large by a factor of **7.5** (2002) and **6** (2022).

The consequence is structural, not marginal. At τ ≥ 2 every party is a
contender for every voter, so *C<sub>a</sub> ∩ T<sub>R</sub> = ∅* never holds,
the coordination indicator never fires, and no voter ever has a strategic
incentive. **40 % of the design sat at τ ≥ 2 outright**, and the remainder was
still far above the zone length.

The fix routes every empirical caller through `core_model/metrics.py::tau_absolute`,
applied exactly once, with `tau_hat`, `tau_absolute` and `K` all recorded per
output row so the relation is checkable from the CSV alone.

---

## 2. Rerun protocol

Executed by [`tools/run_empirical_rerun.sh`](../../tools/run_empirical_rerun.sh),
unattended, under `caffeinate`, with a master log, per-stage logs, a PID file and
a `COMPLETE`/`FAILED` marker.

| Stage | Runs | Wall time |
|---|---:|---:|
| 1 · Replay, `nearest` (300 draws × 2 years) + robustness | 1 200 | ~30 min |
| 2 · Replay, 3 probabilistic variants (800 × 2 each) | 4 800 | ~39 min |
| 3 · Behavioural sweeps (1 000 draws × 4 repeats × 2 years) | 8 000 | ~2 h 57 |
| 4–8 · Diagnostics, figures, comparison, importance, tables, pytest | 0 | ~3 min |
| **Total** | **14 000** | **4 h 07** |

Every simulation stage is followed by
[`tools/validate_rerun.py`](../../tools/validate_rerun.py) before the next stage
starts, so a unit error surfaces in minutes rather than after seven hours.

### Pre-run safety work

The rerun was preceded by a set of guards, all of which are now permanent:

- `tau_absolute` and `K` added to every replay and sweep output row.
- Quick runs isolated to `data/smoke/`, making overwrite of full output
  structurally impossible.
- Validated `--resume` for the sweeps, mutually exclusive with `--overwrite`.
- Refusal to overwrite any existing empirical output without `--overwrite`,
  checked before anything is written.
- Failure-safe execution (`set -o pipefail`, `PIPESTATUS`), so a failed stage
  stops the pipeline instead of being masked by `tee`.
- Year-specific validation ceilings (2002 ≤ 0.4, 2022 ≤ 0.5, inclusive).
- Evidence archived under `data/archive/pre_rerun_2026-08-21/` with a SHA-256
  manifest, verified after copying.

---

## 3. Validation status

| Check | Result |
|---|---|
| `COMPLETE` marker | present |
| `FAILED` marker | absent |
| Stages OK | **30 / 30** |
| Simulations accounted for | **14 000 / 14 000** |
| Row counts | all 14 output files at expected length |
| Unique keys | all unique |
| NaN / non-finite | none |
| `tau_absolute == tau_hat × 2/K` | holds to 1e-12 in all 14 files |
| Year ceilings | 2002 ≤ 0.4, 2022 ≤ 0.5 — respected, inclusive |
| `tau ≥ 2` warning | **zero occurrences in all 30 simulation logs** |
| Archive checksums | 153 / 153 verified |
| Test suite at run time | 481 passed, 2 skipped |

Two verification notes, both resolved:

- **Robustness `draw` is not unique alone.** The key is `(variant, draw)` —
  3 perturbation variants × 100 draws = 300 rows, verified unique on the
  composite key.
- **The `tau ≥ 2` string appears once, in `08a_pytest.log`.** It originates in
  `tests/test_empirical.py`, which passes `tau=2.0` deliberately as a synthetic
  baseline fixture. Zero occurrences in any of the 30 simulation logs, which is
  the check that matters.

---

## 4. Generated outputs

### Raw (git-ignored, regenerable)

| File group | Rows |
|---|---|
| `empirical_runs_{2002,2022}.csv` | 300 each |
| `empirical_robustness_{2002,2022}.csv` | 300 each (3 variants × 100) |
| `empirical_candidate_draws_{2002,2022}.csv` | 4 500 / 3 600 |
| `empirical_runs_prob_{signal,prior,signal_mu0}_{2002,2022}.csv` | 800 each |
| `behavioral_sweep_{2002,2022}.csv` | 1 000 each |

### Compact tables

Seven tables generated from the raw outputs and included in this branch:
`empirical_replay_summary`, `empirical_robustness_summary`,
`empirical_activation_summary`, `behavioral_sweep_quantiles`,
`empirical_year_contrast`, `empirical_candidate_fit`,
`lhs_parameter_importance`. Registry:
[`results/README.md`](../../results/README.md).

The six produced by `make_empirical_tables.py` regenerate **byte-identically**
from unchanged inputs, verified by SHA-256 and pinned by a test that compares
serialized bytes rather than parsed floats.

---

## 5. What the corrected run produced

The behavioural-sweep **design is byte-identical before and after** — all of
`draw, tau_hat, mu, alpha, rho_pi, beta` match to 1e-12. The comparison below is
therefore controlled: the same parameter draws, with only the τ interpretation
changed.

Comparisons are drawn against `data/archive/pre_rerun_2026-08-21/`.

### The mechanism activates

Fraction of draws clearing each threshold (`prob_signal`, 800 draws/year):

| | trigger > 1 % | switch > 1 % | trigger > 10 % | switch > 10 % |
|---|---|---|---|---|
| 2002 before | 11.6 % | 11.1 % | 4.6 % | 0.0 % |
| 2002 after | **100 %** | **91.3 %** | **100 %** | **66.4 %** |
| 2022 before | 30.3 % | 28.9 % | 14.3 % | 7.6 % |
| 2022 after | **100 %** | **100 %** | **100 %** | **64.3 %** |

Mean rates, same specification:

| Metric | 2002 before → after | 2022 before → after |
|---|---|---|
| trigger rate | 0.0121 → **0.4417** | 0.0317 → **0.4295** |
| switching rate | 0.0042 → **0.1135** | 0.0202 → **0.1150** |
| conditional switching | 0.0780 → **0.3197** | 0.2103 → **0.3375** |

Before the fix the strategic module was effectively inert; after it, it is
active in every draw. This is the direct, expected consequence of restoring the
tolerance scale.

### Coordination measures

ΔCENP from the behavioural sweeps, measured against the exogenous opening poll
s⁰ — the baseline the observed target uses:

| | 2002 | 2022 |
|---|---|---|
| observed | −0.1132 | +0.0587 |
| simulated mean before → after | +0.0668 → **+0.0493** | +0.1127 → **+0.0611** |
| simulated range before | −0.0011 … +0.0816 | +0.0039 … +0.1555 |
| simulated range after | **−0.0701 … +0.1243** | **−0.0730 … +0.1820** |
| draws below observed | 0.0 % → 0.0 % | 2.7 % → **41.2 %** |

ΔENP moved from ≈ 0 to clearly negative (2002 −0.005 → −0.146; 2022 −0.002 →
−0.228), consistent with coordination actually occurring.

### Error and set-recovery measures

| `prob_signal` | 2002 before → after | 2022 before → after |
|---|---|---|
| RMSE | 0.0588 → 0.0687 | 0.0725 → 0.0951 |
| MAE | 0.0427 → 0.0493 | 0.0507 → 0.0697 |
| top-2 set accuracy | 0.000 → 0.000 | 0.331 → 0.000 |

`topk_accuracy` is an **exact set match** (`core_model/empirical_outcomes.py:28`),
not a partial-credit measure, so values of exactly 0 are expected rather than
anomalous.

### Between-year contrast

| Statistic (sweeps, raw ΔCENP) | before | after |
|---|---|---|
| Cohen's *d* | −3.071 | −0.202 |
| rank-biserial | −0.924 | −0.180 |
| Mann–Whitney *p* | 4e−280 | 3e−12 |

### Parameter importance

No pre-fix importance table was archived, but the pre-fix sweep data survives,
so the pre-fix values were recomputed through the identical code path and seed.

| Scope | before (top driver) | after (top driver) |
|---|---|---|
| 2002 | beta 86.4 % | **tau_hat 69.1 %** |
| 2022 | beta 86.3 % | **tau_hat 99.0 %** |
| pooled | beta 44.2 % (CV R² +0.123) | tau_hat 94.5 % (CV R² **−0.187**) |

With τ inert, the tolerance parameter could not move the outcome, so importance
accrued to the remaining live parameter. With τ on its intended scale, τ̂ is the
dominant driver.

---

## 6. Known limitations

- **No pre-fix baseline exists for the `nearest` specification.** Its raw
  outputs were overwritten on 2026-08-19 by a 15-draw `--quick` run and had
  never been committed (`data/` is git-ignored). They are **permanently
  unrecoverable**. Direct before/after comparison is valid only for the sweeps,
  the probabilistic variants and the diagnostics; for `nearest` the archived
  logs and figures are historical evidence only.

  This also affects `empirical_candidate_shares_{2002,2022}.csv`, whose row
  count is the number of candidates and therefore matches the new file exactly
  despite being smoke output — row count alone does not detect it.

- **Pooled parameter importance is not interpretable.** Its 5-fold CV R² is
  **−0.187**, worse than predicting the mean; the script emits its
  low-performance warning below 0.1. Per-year scopes (R² 0.853 and 0.991) are
  sound. The pooled row should not be cited.

- **`perturbed_positions` moves switching volume materially.** It roughly
  doubles the switching rate (2002 +86 %, 2022 +154 %) while
  `individual_signals` and `resampled_voters` move it by under 0.006. Fit and
  coordination measures track the main replay closely across all three variants.
  This is visible only now, because pre-fix switching was near zero and had no
  room to move.

- **Stale pre-fix artefacts remain on disk.** 32 figures named `*_main_prob_*`
  and 12 correspondingly named CSVs are June outputs sitting beside the
  regenerated ones, and `lhs_importance_by_year_slide.png` still reflects the
  pre-fix ranking because it requires `--slide`, which the pipeline did not run.

  All of them are git-ignored and none is referenced from the documentation, so
  none can be mistaken for a current result by a reader of this repository. They
  are left in place deliberately rather than regenerated or deleted: see the
  figure policy in [Experiments](../experiments.md#figures).

- **The importance table is not byte-identical between runs.** Seeds and
  predictor selection are fixed; values reproduce within numerical tolerance and
  rankings are stable, but parallel floating-point reduction moves the last bit
  (~1e-16). Compare it numerically, never by checksum.

---

[← Experiments](../experiments.md) · **Rerun record** · [Reproducibility →](../reproducibility.md)
