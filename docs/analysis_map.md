# Canonical logic vs intentionally separate analyses

An audit done immediately before the corrected empirical reruns, to answer one
question: where the same idea appears twice, is that a duplicate to remove or a
distinction to protect?

Nothing structural was changed as a result. The reruns come first, and every
entry below is marked *centralize now*, *document as separate*, or *consolidate
after the reruns*.

The delay has a specific reason rather than being general caution. Several of
these duplicates are load-bearing on RNG consumption order: the Latin-hypercube
routine draws one dimension at a time, so the *order* of the parameter list
determines the design, and the two runners declare their parameters in different
orders. Merging them without care changes which points get simulated, which
would silently invalidate the comparison the reruns exist to produce.

---

## A. Genuine duplicated model logic

### A1 · Latin-hypercube construction (*consolidate after the reruns*)

`empirical_2002_2022._latin_hypercube` and `behavioral_sweep.latin_hypercube`
have identical bodies; the sweep's docstring already says so.

The catch is that the function is shared while the *designs* are not:

| Runner | Dimension order |
|---|---|
| `empirical_2002_2022` | `tau_hat, rho_pi, alpha, [mu], [beta]` |
| `behavioral_sweep` | `tau_hat, mu, alpha, rho_pi, beta` |

`cut = (arange(n) + rng.random(n)) / n` is drawn per dimension, in order, from a
shared generator. Reordering the list therefore changes every drawn value. The
*function* can be lifted safely; the *orders* must stay exactly as they are.

Move the function to `core_model` after the reruns, keeping both call sites'
orders, and pin each design with a fixed-seed fingerprint test first.

### A2 · ENP and CENP computed in two places (*consolidate after the reruns*)

`core_model/metrics.py` defines `enp` / `cenp`. `functions.coordination_measures`
defines `_enp` / `_cenp` inline with the same formulae.

They are not quite interchangeable:

| | `metrics.enp` | `functions._enp` |
|---|---|---|
| Normalisation | normalises internally | expects a normalised input (the caller does it) |
| Zero-sum input | divides by zero | returns `nan` |

`tests/test_metrics.py` already asserts the two agree on well-formed input
(`test_metrics_enp_agrees_with_coordination_measures`), so the risk is confined
to the edge cases. Merge after the reruns, and pin the edge behaviour first.
Whichever version is kept, one of the two current callers changes behaviour on a
degenerate input.

### A3 · Behavioural parameter ranges declared twice (*consolidate after the reruns*)

`TAU_RANGE`, `MU_RANGE`, `ALPHA_RANGE`, `RHO_PI_RANGE`, `BETA_RANGE` appear with
identical values in both empirical runners. The values agree today, so the
duplication is currently harmless and the risk is drift rather than error. It is
deferred for the same reason as A1: the two designs consume them in different
orders, so the tidy-looking fix is the dangerous one.

---

## B. Shared protocol, schema or I/O infrastructure

### B1 · Predictor selection (**centralized now**)

Done, in `analysis/empirical/lhs_importance.py`. Selection by exclusion, meaning
"every numeric column is a predictor unless something rules it out", was
replaced by `SWEPT_PREDICTORS`, an explicit allowlist per design, and
`resolve_predictors()`.

This one was not deferred because it was actively wrong. Adding `tau_absolute`
and `K` for traceability would have made both predictors, and `tau_absolute` is
`tau_hat * (2 / K)`, perfectly collinear with `tau_hat` within a year.
Permutation importance would have split one parameter's importance across two
columns and changed the reported ranking. `tests/test_predictor_schema.py`
pins that arbitrary extra columns cannot reach the predictor matrix.

Verified byte-identical on a fixed-seed smoke design before and after.

### B2 · Empirical loading (**already centralized, nothing to do**)

`core_model/empirical_data.py` is the single loader. Every consumer
(`empirical_2002_2022`, `behavioral_sweep`, `behavioral_targets`) imports
`load_year` and `sample_voters` from it. No duplication found.

### B3 · Synthetic outcome extraction (*consolidate after the reruns*)

`saltelli_sensitivity`, `main_results`, `robustness_checks` and
`protocol_validation` each repeat the same few lines: call
`functions.coordination_measures(sincere, final)`, read
`diag["trigger_rate_final"]`, read the switching summary. It is a genuine shared
idiom and a natural `extract_outcomes(res)` helper. It is a pure refactor with
no RNG involvement, but it touches four scripts whose outputs are *not* being
regenerated, so it waits.

### B4 · Output-row construction and provenance (*document now, consolidate later*)

Each runner builds its output row separately: `_scalar_row` in the replay, an
inline dict in the sweep, `trajectory_outcomes` in protocol validation. The
convention is now consistent and is the thing to preserve:

> A row records the design parameters as drawn, then any derived quantity read
> back out of the object that used it, and never recomputed at write time.

That is what makes `tau_absolute` in a CSV provably the value handed to
`run_simulation` rather than a second, possibly divergent, calculation. A shared
row builder is worth having, though the convention matters more than the code
sharing.

### B5 · Diagnostic aggregation (*consolidate after the reruns, partly*)

`empirical_diagnostics._binned_stats` is a reusable 2-D binning helper.
`empirical_beta_bins` and `protocol_posthoc` do their own `groupby`
aggregations, but over different shapes and for different questions, which puts
them in category C. Only the binning helper is worth lifting.

---

## C. Intentionally separate: do not merge

### C1 · The two ΔCENP baselines

The single most important distinction in this list, and the easiest to destroy
by "removing duplication":

| Where | Baseline | Meaning |
|---|---|---|
| `functions.coordination_measures["delta_cenp"]` | the model's own iteration-0 sincere shares | how much coordination the loop produced from its own starting point |
| `metrics.delta_cenp` / `behavioral_sweep` | the exogenous opening poll s⁰ | how much coordination occurred relative to the real world's starting point |

Both are called `delta_cenp`. They answer different questions and are not
interchangeable. The sweep uses the s⁰ baseline precisely so the simulated value
is comparable with the observed poll→result value, which is what makes
`behavioral_targets` meaningful. `behavioral_sweep`'s docstring already says
this explicitly. Keep both, keep both documented, never unify.

### C2 · Seed construction

| Runner | Scheme |
|---|---|
| Empirical replay | `draw_seed = MASTER_SEED + draw`, then a purpose-specific multiplier per RNG (`×7919` electorate, `×104729` position jitter, `×999983` resampled voters), plus the year |
| Behavioural sweep | `run_seed = seed + 1000 × (draw + 1) + repeat` |

Different designs need different things. The replay needs independent streams
per *purpose* within a draw, while the sweep needs independent streams per
*repeat*.
Both are documented at their call sites. Unifying them would change every drawn
value for no benefit.

### C3 · Synthetic and empirical parameter spaces

The Saltelli problem has 8 free parameters including `c`, `theta`, `rho_s` and
`eps_F`, while the empirical designs sweep 4 or 5. That gap is deliberate:
under empirical replay the signal is exogenous, so the signal-generating
parameters have nothing to do. Keep separate.

### C4 · Tests that check the same contract from different angles

| Contract | Files | Verdict |
|---|---|---|
| ENP / CENP | `test_metrics.py` (canonical) and `test_empirical.py` (agreement with `coordination_measures`) | Intentional. The second is an *agreement* test between A2's two implementations, and is exactly what makes merging them safe later |
| tau conversion | `test_tau_units.py` (the conversion, and that runners apply it) and `test_tau_absolute_output.py` (that both units are recorded) | Adjacent rather than overlapping |
| Contender set | `test_decision_rule.py` (construction and boundary) and `test_empirical.py::test_prob_probs_sum_to_one_within_contenders` (initialisation over Ca) | Different contracts on the same object |

No test consolidation needed.

---

## Summary

| | Now | After the reruns |
|---|---|---|
| **A** duplicated model logic | none | A1 LHS function, A2 ENP/CENP, A3 ranges |
| **B** shared infrastructure | B1 predictor schema ✔ | B3 outcome extraction, B4 row builder, B5 binning helper |
| **C** intentionally separate | C1-C4 documented ✔ | none |
