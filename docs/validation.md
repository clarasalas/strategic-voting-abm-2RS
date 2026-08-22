# Validation

[← Model](model.md) · **Validation** · [Experiments →](experiments.md)

How we know the implementation is coherent and the analytical process is
reproducible. Organised **by type of check**, not by chronology.

> **Scope of this page.** This is about *implementation correctness* — whether
> the code does what it claims and whether the process is reproducible. How well
> the model reproduces the two elections is a separate question, recorded in the
> [empirical rerun record](reports/empirical_rerun_2026-08-21.md); it is not
> evidence of a working or broken implementation either way.

---

## Verification snapshot

An **auditable local verification**. It is a record of runs on one machine, not
a standing property of the repository; CI is the continuous check.

| | |
|---|---|
| **Command** | `python -m pytest -ra` |
| **Result** | **570 passed, 0 skipped, 0 warnings** |
| **Date** | 2026-08-22 |
| **Platform** | Darwin 25.5.0, Python 3.11.7 |

Run in **two dependency environments**, because the previous snapshot was taken
in only one and missed a defect that CI then caught:

| Environment | numpy | pandas | Result |
|---|---|---|---|
| Development | 1.26.4 | 3.0.3 | 570 passed, 0 skipped, 0 warnings |
| CI-matched | **2.4.6** | **3.0.5** | 570 passed, 0 skipped, 0 warnings |

Also run against a **tracked-files-only checkout** — no git-ignored data
present, as on a fresh clone — in both environments, with the same result. No
test depends on generated output any more.

### Commit roles

| Commit | Role |
|---|---|
| `50a2bf5` | code and tables — the generator, its tests, seven summary tables |
| `3a3a215` | documentation |
| `cc5ed19` | test hygiene — removed two always-skipping tests |
| `6db9aee` | documentation — recorded the previous snapshot |
| *this change* | canonical CSV serialisation, fixture-based tests |

A document cannot contain its own commit hash, so the date, the command and the
environments are the identifying facts. CI is the authoritative check.

### Test discovery

`pytest.ini` sets `testpaths = tests`. All 20 `test_*.py` files in the
repository are under `tests/`, and collection with and without the repository's
`pytest.ini` returns the same test IDs, so the setting hides nothing.

### No skipped tests

The suite has **no skips at all** — not in CI, not on a fresh clone. Four were
removed in two passes, none replaced by a weaker check:

| Removed | Why it was meaningless | What covers it now |
|---|---|---|
| `test_cli_refuses_an_unhonourable_signal_epsilon` | Asserted `--signal-epsilon` was *refused*, because ε<sub>s</sub> could not reach `run_simulation`. That plumbing exists, so it could only skip. | [`test_signal_epsilon.py`](../tests/test_signal_epsilon.py) asserts every `generate_signal` call receives the value. |
| Panel E branch of `test_panel_table_reports_repetitions` | Panel E is analytic and declares no `n_reps` column. | Parametrization derives from `PANEL_SCHEMAS`; a guard fails if any *other* panel loses the column. |
| `test_real_horizon_raw_passes_validation` | Read a 213 KB git-ignored generated file, so it skipped everywhere but the author's machine. | Four tests build a synthetic frame with the real schema and shape (54 configurations × 8 seeds = 432 rows) and check the validator accepts it and rejects a short run, a wrong ε<sub>s</sub> and a non-finite outcome. |
| `test_regeneration_reproduces_the_committed_tables` | Needed 17 MB of git-ignored simulation output. | Three tests build their own fixture inputs and check the generator is deterministic, exact through a CSV round trip, and refuses corrupt input. The real-data check runs as a pipeline step — see below. |

> Removing the last one surfaced a real weakness. Its replacement feeds a NaN
> through the generator — and the existing guard did **not** fire, because every
> summary goes through a pandas aggregation and those skip NaN by default, so a
> corrupt input became a healthy-looking mean over fewer rows. The generator now
> validates on the way *in*, which is the only place it is visible.

### Enforcing real-table regeneration

The committed tables must reproduce from the real raw outputs. That check needs
17 MB of git-ignored simulation output, so it cannot be a unit test — but it can
still be enforced:

```bash
python tools/check_tables_reproduce.py
```

It regenerates every table and **exits non-zero** if a tracked table changes, if
an unexpected untracked table appears, if a declared table goes missing, or if
the tables directory was already dirty beforehand — printing the affected
filenames in each case. It runs as pipeline step `08b_tables_reproduce`.

On a **fresh clone** it exits **3** with its own message: the raw simulation
outputs it needs are git-ignored by design, so they are simply absent. That is
not a failure of the tables, and the check says so rather than reporting a
missing input as stale output.

> The previous instruction was `make_empirical_tables.py && git status --short`.
> That is not a check: `git status` exits 0 whether or not anything changed, so
> a drifted table passed silently unless a human read the output.

Both directions are tested in
[`tests/test_table_regeneration_check.py`](../tests/test_table_regeneration_check.py)
against throwaway git repositories in `tmp_path`, so the failure modes are
exercised without touching the real tables.

### Warning policy

The suite runs clean. Filters live in [`pytest.ini`](../pytest.ini) and no
category is ignored wholesale — every entry pins a specific message and, where
possible, the module that raises it, so a *new* warning of the same category
still surfaces.

**Numerical warnings are promoted to errors** (`error::RuntimeWarning`): an
overflow, an invalid value or a divide-by-zero inside the model is a
result-changing event, not a note. The suite emits none, so this costs nothing
and catches the next one.

#### What the audit counted

Two different numbers appear below, and they come from **two different warning
configurations**. They are not alternative totals of the same thing:

| | Warnings | Configuration |
|---|---:|---|
| Reported by a plain `pytest` run | **5 578** | Python's default filters, which **hide `ResourceWarning` entirely** |
| Additionally exposed by `pytest -W always` | **+34** | `ResourceWarning`s from a leaked file handle, invisible by default |
| **Complete audit** | **5 612** | every occurrence, nothing suppressed |

The 34 were a real defect — `_row_count` opened a file and never closed it —
and would never have appeared in ordinary output. Auditing under `-W always`
rather than trusting the visible count is what surfaced them.

All 5 612 are now fixed, asserted, or narrowly filtered.

<details>
<summary>What is filtered, and why it cannot simply be fixed</summary>

Counts below are from the complete `-W always` audit.

| Source | Count | Disposition |
|---|---:|---|
| `is_sparse is deprecated` — scikit-learn calling a deprecated pandas API | 5 572 | **Filtered.** Raised inside sklearn's own validation layer during RandomForest fitting. Nothing in this repository calls `is_sparse`; it is fixed by upgrading scikit-learn. Pinned to the message *and* the raising module. |
| Unclosed file in `_row_count` | 34 | **Fixed** — now a context manager. Hidden by default filtering; only `-W always` revealed it. |
| τ ≥ 2 guard warnings in `test_empirical.py` | 3 | **Asserted**, not filtered. `tau=2.0` is deliberate there, so the tests now use `pytest.warns` and fail if the guard stops firing. |
| pandas `numexpr` / `bottleneck` version notices | 2 | **Filtered.** Emitted once each at import. Neither optional accelerator is used here; pandas falls back to its own implementations. |
| `salib.sample.saltelli` will be removed | 1 | **Filtered — not a drop-in rename.** `SALib.sample.sobol` scrambles the Sobol′ sequence by default and returns a *different* design: comparing the two at *N* = 8, 16 and 1024 gives a maximum deviation of ~1.6 × 10², not zero. Switching would invalidate the committed `saltelli_results_K{6,8,9}.csv`, whose 30 720 evaluations are verified row-by-row against `saltelli.sample`. Migrating means regenerating the design and re-running the analysis. |

The `is_sparse` filter names the category as `DeprecationWarning` rather than
its actual class `pandas.errors.Pandas4Warning` (which subclasses it). Naming
the pandas class forces pytest to import pandas while parsing `pytest.ini` —
before any `conftest.py` runs — and pandas emits import-time warnings of its
own that then become impossible to filter. With the message and module both
pinned, the base class is equally precise.

</details>

## Validation matrix

### 1 · Analytic unit fixtures

| | |
|---|---|
| **Contract** | Metric implementations match closed-form values on hand-computable inputs. |
| **Implementation** | [`core_model/metrics.py`](../core_model/metrics.py), [`core_model/functions.py`](../core_model/functions.py) |
| **Tests** | [`test_metrics.py`](../tests/test_metrics.py) (38), [`test_deferred_duplicates.py`](../tests/test_deferred_duplicates.py) (69) |
| **Inputs** | Tiny analytic share vectors with known ENP/CENP. |
| **Criterion** | Exact agreement with the closed form to 1e-12. |
| **Status** | ✅ passing |
| **Evidence** | Test assertions only — no generated artefact. |

`test_deferred_duplicates.py` additionally pins the **duplicated** ENP/CENP
implementations against each other within strict tolerance, using both analytic
and generated-share fixtures. It deliberately does **not** assert the two
`delta_cenp` definitions are equal — [they use different
baselines](model.md#δcenp--two-baselines-that-must-never-be-mixed).

### 2 · Decision-rule tests

| | |
|---|---|
| **Contract** | The trigger fires exactly when *C<sub>a</sub> ∩ T<sub>R</sub> = ∅*, and the expressive cost flips the choice at the analytically derived boundary. |
| **Implementation** | [`core_model/agents.py`](../core_model/agents.py) — `calcStrategicUtilities`, `_updatePartition` |
| **Tests** | [`test_decision_rule.py`](../tests/test_decision_rule.py) (24) |
| **Inputs** | Hand-built fixtures with no ties. |
| **Criterion** | Trigger state and chosen party match the hand-derived expectation. |
| **Status** | ✅ passing |

Covers: viable sincere choice does not trigger; non-viable choice with a viable
contender does; the trigger depends on the projection not the voter; no
opponents means no incentive; the contender set is the tolerance ball with an
**inclusive** boundary; the set is never empty and always holds the attachment;
the cost is never charged on the attachment itself.

The boundary case is derived, not assumed: μ\* = (S<sub>alt</sub> −
S<sub>j\*</sub>)/λ<sub>alt</sub> = 1/15 for the fixture, and the model flips
there.

### 3 · Signal and metric tests

| | |
|---|---|
| **Contract** | The temperature transform and Dirichlet draw behave as specified; ε<sub>s</sub> is a numerical floor with no behavioural effect. |
| **Implementation** | [`core_model/signals.py`](../core_model/signals.py) |
| **Tests** | [`test_signals.py`](../tests/test_signals.py) (57), [`test_signal_epsilon.py`](../tests/test_signal_epsilon.py) (25) |
| **Criterion** | Signals are valid distributions; θ monotonically sharpens/compresses; ε<sub>s</sub> = 1e-12 leaves outcomes invariant. |
| **Status** | ✅ passing |

### 4 · Data integrity

| | |
|---|---|
| **Contract** | Real-data files stay mutually consistent and positionally aligned. |
| **Implementation** | [`core_model/empirical_data.py`](../core_model/empirical_data.py) |
| **Tests** | [`test_empirical.py`](../tests/test_empirical.py) (27) |
| **Inputs** | `data/party_positions_*.csv`, `polls_*.csv`, `results_*.csv`, `voters_ideology_*.csv` |
| **Criterion** | Positions inside [−1, 1] and sorted; *K* consistent across every file; results sum to 1 (1e-9); poll signals normalised and non-negative in both `weekly` and `individual` modes. |
| **Status** | ✅ passing, parametrised over both years |

This family exists because everything downstream is **indexed positionally** — a
silent re-ordering would corrupt every candidate-level result without raising.

### 5 · Dynamic invariants

| | |
|---|---|
| **Contract** | Properties that must hold at *every* iteration of *any* run. |
| **Implementation** | [`core_model/model.py`](../core_model/model.py) |
| **Tests** | [`test_dynamic_invariants.py`](../tests/test_dynamic_invariants.py) (24) |
| **Criterion** | Every iteration allocates exactly the electorate; shares sum to 1; every recorded intention is a valid party index; intentions agree with the counts they produced; trigger/switching counts stay in range; each iteration's signal is a distribution; projected finalists are valid and distinct. |
| **Status** | ✅ passing |

Includes `test_the_histories_line_up_on_the_documented_offset`, which pins the
*n+1* vs *n* offset between `history`/`intention_history` and the diagnostic
series. That test was written **after** investigating an apparent failure — the
offset is real and intended, so the test documents it rather than asserting a
convenient falsehood.

### 6 · Deterministic golden regressions

| | |
|---|---|
| **Contract** | Published numbers do not drift silently across commits. |
| **Tests** | [`test_empirical.py`](../tests/test_empirical.py) — golden-value cases |
| **Criterion** | Full sincere **and** final share vectors match recorded literals to `abs=1e-12`; switcher counts pinned. |
| **Status** | ✅ passing |

Two configurations are pinned, both chosen to exercise the strategic path:

- **Synthetic** — *K* = 8, *N* = 500, `width_factor` = 1.5, τ̂ = 1.75, μ = 0.1, *T* = 15, seed 42.
- **Empirical 2022** — probabilistic init, salience = *s*<sup>0</sup>, 350 voters, μ = 0.3, α = 0.1, ρ<sub>π</sub> = 70, β = 6, seed 33.

> Why this family exists: comparing two runs of *today's* code only catches
> divergence between argument paths. A change that moves every path equally —
> a rewrite of the sincere-init rule, a reordering of RNG draws — leaves such a
> test green while every published number changes. Golden values are the suite's
> memory of the past.
>
> A failure is either a bug (fix the code, not the numbers) or a deliberate
> model change, in which case re-record with the snippet in each docstring and
> say so in the commit message — every figure generated before that commit is
> then stale.

### 7 · Metamorphic properties

| | |
|---|---|
| **Contract** | Relabelling candidates, or reflecting the ideological axis, must not change the decision. |
| **Tests** | `test_decision_is_invariant_to_party_relabelling`, `test_decision_is_symmetric_under_left_right_reflection`, `test_contender_set_does_not_depend_on_candidate_labels` |
| **Criterion** | The chosen party, mapped through the transformation, is identical. |
| **Status** | ✅ passing |

> These properties were **derived from the equations before being asserted**, not
> assumed. All 120 relabellings were exhaustively verified, and reflection was
> checked at five voter positions. Both hold with no counterexample. Had one
> failed, the contract would have been the thing in question — not the code.

### 8 · Output isolation and overwrite protection

| | |
|---|---|
| **Contract** | A quick/smoke run can never overwrite a full-run output, and a full run refuses to destroy existing output without an explicit flag. |
| **Implementation** | `_refuse_existing_outputs()` in [`empirical_2002_2022.py`](../analysis/empirical/empirical_2002_2022.py); `SMOKE_DIR = data/smoke/` |
| **Tests** | [`test_quick_run_isolation.py`](../tests/test_quick_run_isolation.py) (5), [`test_overwrite_protection.py`](../tests/test_overwrite_protection.py) (13) |
| **Criterion** | Refusal occurs **before any output is modified**, whether the existing file is smaller, equal or larger; partial target sets are detected; `--overwrite` is incompatible with `--resume`. |
| **Status** | ✅ passing |

> This family exists because of a real incident: on 2026-08-19 a 15-draw
> `--quick` run silently overwrote the full 300-draw main-replay outputs, which
> were never committed (`data/` is git-ignored). Those pre-fix results are
> **permanently unrecoverable**. The protection was written so it cannot recur.

### 9 · Resume equivalence

| | |
|---|---|
| **Contract** | An interrupted-and-resumed sweep produces byte-identical output to an uninterrupted one. |
| **Implementation** | `load_resumable()` / `finalise_output()` in [`behavioral_sweep.py`](../analysis/empirical/behavioral_sweep.py) |
| **Tests** | [`test_sweep_resume.py`](../tests/test_sweep_resume.py) (29), [`test_canonical_csv.py`](../tests/test_canonical_csv.py) (30) |
| **Criterion** | Resume validates year, seed, `n_draws`, `n_repeats`, schema version and a SHA-256 fingerprint of the design; rejects duplicate, non-integer or out-of-range draw ids, missing columns and non-finite values. |
| **Status** | ✅ passing |

Canonical finalisation makes uninterrupted and resumed sweep outputs
byte-identical under the supported environments; this is regression-tested in
CI.

Byte stability was measured directly, not inferred. The same 2 000-value
fixture — the CI failure's own values, plus signed zero, subnormals, the
largest finite double, integer-like floats and 1 982 uniformly random bit
patterns — was written through `write_canonical` in both environments:

| Environment | numpy | pandas | Bytes | SHA-256 |
|---|---|---|---|---|
| Development | 1.26.4 | 3.0.3 | 400 054 | `653d8db8…45210791` |
| CI-matched | 2.4.6 | 3.0.5 | 400 054 | `653d8db8…45210791` |

**The hashes are identical**, and finalising four times in a row changed
nothing in either environment. So for the two environments tested the output is
byte-identical *across* them, not merely idempotent within each. That is a
measurement of those two configurations, not a guarantee for every future
numpy or pandas — which is what the regression tests exist to catch.

Per-run seeds depend only on `(seed, draw, repeat)`, which is what makes the
equivalence hold. Two mechanisms deliver the byte-identity:

- **Canonical serialisation.** `finalise_output` reads with pandas' correctly
  rounded float parser (`float_precision="round_trip"`) and writes with
  pandas' shortest round-tripping form, atomically via a temporary file. The
  default parser is fast but *not* correctly rounded — it can return a double
  one ulp from the text, so reading and rewriting never settles. That is what
  CI caught on 2026-08-22, on a platform whose float values differ from the
  development machine's.
- **A true no-op for a complete file.** When `--resume` finds every draw
  already present, it validates the sidecar metadata, the design fingerprint
  and every retained row, then returns without touching the file at all — its
  bytes, checksum and modification time are unchanged.

The no-op is an optimisation of the complete case, not a substitute for
canonical serialisation: an interrupted resume still merges new rows with old
ones and rewrites the file.

<details>
<summary>Why the writer is pandas' default and not <code>%.17g</code></summary>

Three representations were measured on 60 000 adversarial doubles — uniformly
random bit patterns, subnormals, extremes, signed zero — in both the local and
the CI dependency environments:

| Representation | Verdict |
|---|---|
| `repr` as a callable | **Rejected.** Under numpy 2 the callable receives a numpy scalar, so it emits `np.float64(0.1)` instead of `0.1` and corrupts the file. |
| `"%.17g"` | **Rejected.** Not lossless: it writes `-0.0` as `-0`, which parses back as `+0.0`, losing the sign of zero. |
| pandas default | **Chosen.** Bitwise exact on every value tested, including signed zero and subnormals, and byte-idempotent across repeated cycles in both environments. |

pandas does not document its default float format as shortest-round-trip, so
that property is pinned by
[`tests/test_canonical_csv.py`](../tests/test_canonical_csv.py) rather than
assumed — a future release that changes it fails there loudly.

</details>

### 10 · Pipeline-contract tests

| | |
|---|---|
| **Contract** | Consecutive pipeline stages agree on filenames, columns and paths. |
| **Tests** | [`test_pipeline_contract.py`](../tests/test_pipeline_contract.py) (9) |
| **Criterion** | Diagnostics finds and reads the replay output; every column diagnostics wants is actually produced; figure loaders resolve the replay filenames and report a missing file clearly; sweep output is a valid importance input; the importance table exports the documented schema. |
| **Status** | ✅ passing |

Deliberately does **not** inspect figure appearance — it catches incompatible
filenames, columns and paths, which is where pipelines actually break.

### 11 · Horizon validation

| | |
|---|---|
| **Question** | Does the loop reach a fixed point before the iteration ceiling? |
| **Implementation** | [`analysis/synthetic/protocol_validation.py`](../analysis/synthetic/protocol_validation.py) |
| **Tests** | [`test_protocol_validation.py`](../tests/test_protocol_validation.py) (28) |
| **Criterion** | State read from a long run equals a short run at the same horizon; tail-mean windows behave correctly at both ends. |
| **Status** | ✅ passing |
| **Evidence** | [`protocol_horizon_validation.csv`](../results/tables/protocol_horizon_validation.csv), `protocol_horizon_stability_by_c.csv` |

### 12 · Population validation

| | |
|---|---|
| **Question** | How many voters before ΔCENP stabilises? |
| **Criterion** | Standard error of ΔCENP across seeds as a function of *N* — an estimator-stability criterion, not a mean comparison. |
| **Status** | ✅ complete → fixes *N* = 2000 |
| **Evidence** | [`protocol_population_validation.csv`](../results/tables/protocol_population_validation.csv), `protocol_population_stability_by_c.csv` |

### 13 · Protocol robustness (panels A–G)

| | |
|---|---|
| **Implementation** | [`analysis/synthetic/robustness_checks.py`](../analysis/synthetic/robustness_checks.py) |
| **Tests** | [`test_result_tables.py`](../tests/test_result_tables.py) (49) |
| **Status** | ✅ complete, all seven panels committed |
| **Evidence** | [`robustness_panel_{A…G}.csv`](../results/tables/) |

| Panel | Question | Fixes |
|---|---|---|
| A · *N* | voters before ΔCENP stabilises | *N* = 2000 |
| B · *T*<sub>max</sub> | do vote intentions reach a fixed point? | *T* = 25 |
| C · ε<sub>s</sub> | is ΔCENP invariant to the signal offset? | ε<sub>s</sub> = **1e-12** (see caveat) |
| D · ξ | does electorate centre matter, or only geometry? | ξ = 0 |
| E · θ | what does temperature do mechanically? | analytic, no runs |
| F · μ | does μ suppress switching monotonically? | documents μ |
| G · truncation | does the *T* = 25 ceiling reach reported outcomes? | validates *T* = 25 |

> ⚠️ **Panel C was invalid and has been regenerated — read its claim narrowly.**
> In its original form the ε<sub>s</sub> value *never reached the simulation*, so
> all five grid points produced bit-identical output and the "invariance" it
> appeared to show was vacuous. ε<sub>s</sub> is now a real parameter
> (`run_simulation(signal_epsilon=…)`), the grid includes the **1e-12** actually
> in force, and the results genuinely vary.
>
> What the corrected panel establishes: **Panel C evaluates six `signal_epsilon`
> values across four selected parameter configurations. It establishes local
> robustness for those tested configurations, not invariance across the full
> Saltelli parameter space.**
>
> The grid is ε<sub>s</sub> ∈ {1e-12, 1e-6, 1e-4, 1e-3, 1e-2, 1e-1} × {Baseline,
> Sweet-spot} × {θ = 0.3, θ = 1.0}, 10 repetitions each — 24 rows in
> [`robustness_panel_C.csv`](../results/tables/robustness_panel_C.csv). Within
> those configurations, 1e-12, 1e-6 and 1e-4 return identical voting outcomes.

**Panel G qualifies Panel B.** Panel B shows the diffuse regime (*c* = 2.5) never
reaches a fixed point — 70 % of runs are still moving at the ceiling. Panel G
asks the different question of whether that truncation reaches the *reported
outcomes*: at high width a single run's outcome moves by more than the
between-seed SD (`drift_over_sd` ≈ 1.2–1.4), but the **mean across seeds** barely
moves — 0.3 % for ΔCENP, 0.04 % for final ENP. The trajectory oscillates around a
stable centre rather than still trending.

> So the defensible claim is: **aggregate results are robust to the ceiling;
> individual trajectories are not.** A flat statement that "the model converges by
> *T* = 25" is not supported and should not be made.

### 14 · Global sensitivity

| | |
|---|---|
| **Question** | Which parameters drive coordination, and how much is interaction? |
| **Implementation** | [`analysis/synthetic/saltelli_sensitivity.py`](../analysis/synthetic/saltelli_sensitivity.py) (SALib) |
| **Design** | 8 parameters, *K* ∈ {6, 8, 9}, **10 240 evaluations per K** = 30 720 total |
| **Criterion** | First- and total-order Sobol indices with bootstrap CIs. |
| **Status** | ✅ complete |
| **Evidence** | [`sobol_indices.csv`](../results/tables/sobol_indices.csv) — **120 rows, committed.** Raw matrices `data/saltelli_results_K{6,8,9}.csv` are committed too, so the table regenerates with `--analyze-existing` and **no simulation**. |

This is the **only formal variance decomposition** in the project. The empirical
importance analysis is LHS-based and exploratory — it ranks, it does not
decompose variance.

### 15 · Empirical replay

| | |
|---|---|
| **Contract** | Every output row records `tau_hat`, `tau_absolute` and `K`, with the conversion applied exactly once. |
| **Implementation** | [`empirical_2002_2022.py`](../analysis/empirical/empirical_2002_2022.py) |
| **Tests** | [`test_tau_absolute_output.py`](../tests/test_tau_absolute_output.py) (17), [`test_tau_units.py`](../tests/test_tau_units.py) (10), [`test_empirical_tables.py`](../tests/test_empirical_tables.py) (42), [`test_table_regeneration_check.py`](../tests/test_table_regeneration_check.py) (11) |
| **Criterion** | `tau_absolute == tau_hat × 2/K` to 1e-12; year-specific ceilings (2002 ≤ 0.4, 2022 ≤ 0.5, inclusive); `tau_hat` unchanged. |
| **Status** | ✅ passing; validated across all 14 output files of the 2026-08-21 rerun |
| **Evidence** | [`empirical_replay_summary.csv`](../results/tables/empirical_replay_summary.csv), [`empirical_activation_summary.csv`](../results/tables/empirical_activation_summary.csv) |

Enforced at runtime as well, by
[`tools/validate_rerun.py`](../tools/validate_rerun.py), which also asserts the
pre-fix `tau >= 2.0` warning appears **zero** times in the simulation logs.

### 16 · Empirical robustness

| | |
|---|---|
| **Question** | Does the replay depend on three arbitrary setup choices? |
| **Variants** | `individual_signals` (individual polls vs weekly means), `perturbed_positions` (±0.05 jitter), `resampled_voters` (different electorate draw) |
| **Design** | 100 draws × 3 variants × 2 years = 600 runs |
| **Status** | ✅ complete |
| **Evidence** | [`empirical_robustness_summary.csv`](../results/tables/empirical_robustness_summary.csv) |

### 17 · Stochastic-noise analysis

| | |
|---|---|
| **Question** | How much of the observed variation is seed noise rather than signal? |
| **Implementation** | [`analysis/synthetic/protocol_posthoc.py`](../analysis/synthetic/protocol_posthoc.py) |
| **Tests** | [`test_protocol_posthoc.py`](../tests/test_protocol_posthoc.py) (33) |
| **Criterion** | Within/between variance components with bootstrap ICC; Benjamini–Hochberg correction applied within each outcome × statistic × interval family. |
| **Status** | ✅ complete |
| **Evidence** | [`protocol_seed_noise_decomposition.csv`](../results/tables/protocol_seed_noise_decomposition.csv), `protocol_horizon_drift_{by_config,summary}.csv` |

---

## Reproducibility guarantees

| Artefact | Guarantee |
|---|---|
| Model runs | **Bit-identical** for a fixed seed. |
| `sobol_indices.csv` | Regenerates from committed inputs with no simulation. |
| Empirical tables | **Byte-identical** on regeneration — verified by SHA-256 and pinned by a test that compares serialized bytes, not parsed floats. |
| `lhs_parameter_importance.csv` | Reproducible **but not byte-identical** — see below. |

> ⚠️ **The importance table is not byte-identical, and any claim that it is
> would be wrong.** Predictor selection and every seed are fixed (`SEED = 42`);
> values reproduce within numerical tolerance and rankings are stable. Last-bit
> differences (~1e-16) occur because the surrogate is fitted in parallel and the
> order of floating-point reduction is not fixed. **Compare regenerated copies
> numerically, never by checksum.**

---

## Known limitations of the validation

- **Pooled parameter importance is not interpretable.** Its 5-fold CV R² is
  **−0.187** — worse than predicting the mean. The script emits its
  low-performance warning below 0.1. Per-year scopes (R² 0.853 and 0.991) are
  sound; the pooled row should not be cited.
- **No pre-fix baseline exists for the nearest-party replay.** See family 8.
  Comparisons for that specification rest on archived logs and figures as
  historical evidence only.
- **CI is not yet merged.** The workflow is pushed on the `add-ci-workflow`
  branch but has never run: it triggers only on `main`, and the branch is
  neither merged nor in an open pull request.

---

[← Model](model.md) · **Validation** · [Experiments →](experiments.md)
