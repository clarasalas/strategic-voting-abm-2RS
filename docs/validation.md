<h1 align="center">Validation</h1>

<p align="center">
How we know the code does what it says, and what the checks cannot tell us.
</p>

<p align="center"><sub>
<a href="model.md">← Model</a> · <strong>Validation</strong> · <a href="experiments.md">Experiments →</a>
</sub></p>

## What the checks are for

An earlier round of empirical results was invalidated by a unit-conversion error, and every figure had looked
plausible under it. The checks exist so that a result is trusted because it was tested, not because it looks
reasonable.

They cover the implementation: whether the code does what the [model page](model.md) says, and whether every
committed number can be rebuilt. They cannot tell us whether the assumptions about voters are right. How well the
model reproduces the two elections is a separate question, recorded in the
[empirical run record](reports/empirical_rerun_2026-09-24.md).

## Where things stand

On 2026-09-25 the full suite gave **653 passed, 0 skipped, 0 warnings**, in two dependency environments and on a
fresh clone. The suite has no skipped tests, and a numerical warning counts as a failure.

That is a dated run on one machine. The continuous check is CI, which runs the same suite on a clean machine for
every push and pull request, and which once caught a defect that the local environment had hidden.

<details>
<summary><strong>The verification snapshot in full</strong></summary>

<br>

| | |
|---|---|
| **Command** | `python -m pytest -ra` |
| **Result** | **653 passed, 0 skipped, 0 warnings** |
| **Date** | 2026-09-25 |
| **Platform** | Darwin 25.5.0, Python 3.11.7 |

It was run in two dependency environments, because the previous snapshot was taken in only one and missed a defect
that CI then caught:

| Environment | numpy | pandas | Result |
|---|---|---|---|
| Development | 1.26.4 | 3.0.3 | 653 passed, 0 skipped, 0 warnings |
| CI-matched | **2.4.6** | **3.0.6** | 653 passed, 0 skipped, 0 warnings |

It was also run on a checkout of the tracked files only, with no git-ignored data present, as on a fresh clone, in
both environments and with the same result. No test depends on generated output any more.

There are no skips, neither in CI nor on a fresh clone. Four tests were removed across two passes, and none was
replaced by a weaker check: two could only ever skip once the code they guarded had changed, and two read git-ignored
generated files, so they skipped everywhere but one machine. The last two were rebuilt on fixtures they construct
themselves.

A document cannot contain its own commit hash, so the date, the command and the environments are what identify the
run. CI is the authoritative check.

</details>

<details>
<summary><strong>Which tests run</strong></summary>

<br>

`pytest.ini` sets `testpaths = tests`. All 24 `test_*.py` files in the repository are under `tests/`, and collecting
with and without the repository's `pytest.ini` returns the same test IDs, so the setting hides nothing.

</details>

<details>
<summary><strong>Warnings, and why a clean run means something</strong></summary>

<br>

The filters live in [`pytest.ini`](../pytest.ini), and no category is ignored wholesale. Every entry names a specific
message and, where possible, the module that raises it, so a *new* warning of the same category still shows.

Numerical warnings are turned into errors (`error::RuntimeWarning`). An overflow, an invalid value or a division by
zero inside the model changes results, so it should stop the suite rather than print a note. The suite raises none,
so this costs nothing and catches the next one.

**What the audit counted.** The two numbers below come from two warning configurations. They are not two totals of
the same thing:

| | Warnings | Configuration |
|---|---:|---|
| Reported by a plain `pytest` run | **5 578** | Python's default filters, which hide `ResourceWarning` entirely |
| Also exposed by `pytest -W always` | **+34** | `ResourceWarning`s from a leaked file handle, invisible by default |
| **Complete audit** | **5 612** | every occurrence, nothing suppressed |

The 34 were a real defect: `_row_count` opened a file and never closed it. They would never have appeared in ordinary
output, and auditing under `-W always` rather than trusting the visible count is what found them. All 5 612 are now
fixed, asserted, or narrowly filtered:

| Source | Count | What was done |
|---|---:|---|
| `is_sparse is deprecated`, scikit-learn calling a deprecated pandas API | 5 572 | **Filtered.** Raised inside scikit-learn's own validation during RandomForest fitting. Nothing in this repository calls `is_sparse`; upgrading scikit-learn fixes it. The filter names the message and the raising module. |
| Unclosed file in `_row_count` | 34 | **Fixed**, now a context manager. Only `-W always` revealed it. |
| τ ≥ 2 guard warnings in `test_empirical.py` | 3 | **Asserted**, not filtered. `tau=2.0` is deliberate there, so the tests use `pytest.warns` and fail if the guard stops firing. |
| pandas `numexpr` / `bottleneck` version notices | 2 | **Filtered.** Emitted once each at import. Neither optional accelerator is used, and pandas falls back to its own implementations. |
| `salib.sample.saltelli` will be removed | 1 | **Filtered.** The replacement is not a drop-in rename. `SALib.sample.sobol` scrambles the Sobol′ sequence by default and returns a *different* design: at *N* = 8, 16 and 1024 the two differ by up to ~1.6 × 10². Switching would invalidate the committed `saltelli_results_K{6,8,9}.csv`, whose 30 720 evaluations are checked row by row against `saltelli.sample`. Migrating means regenerating the design and rerunning the analysis. |

The `is_sparse` filter names the category as `DeprecationWarning` rather than its actual class,
`pandas.errors.Pandas4Warning`, which subclasses it. Naming the pandas class forces pytest to import pandas while
parsing `pytest.ini`, before any `conftest.py` runs, and pandas then raises import-time warnings of its own that can
no longer be filtered. With the message and the module both named, the base class is just as precise.

</details>

## The 17 families of checks

The tests are organized by what they guarantee rather than by source file. They fall into four groups.

| Group | Families | In plain words |
|---|---|---|
| [The model's logic](#the-models-logic) | 1, 2, 3, 5, 7 | The formulas, the decision rule and the polls behave exactly as specified. |
| [Data and numbers](#data-and-numbers) | 4, 6 | The input files line up, and published numbers cannot move silently. |
| [The pipeline](#the-pipeline) | 8, 9, 10, 15 | Runs cannot destroy each other's output, resume cleanly, and record their units. |
| [The protocol and the robustness of results](#the-protocol-and-the-robustness-of-results) | 11–14, 16, 17 | The run settings are justified, and the results survive changes to the setup. |

### The model's logic

These checks compare the code with values worked out by hand, and with properties that must hold whatever the
parameters. For example, relabelling the candidates or mirroring the left-right axis must not change any voter's
decision.

<details>
<summary><strong>1 · Values computed by hand</strong></summary>

<br>

| | |
|---|---|
| **Contract** | The metrics match closed-form values on inputs small enough to compute by hand. |
| **Implementation** | [`core_model/metrics.py`](../core_model/metrics.py), [`core_model/functions.py`](../core_model/functions.py) |
| **Tests** | [`test_metrics.py`](../tests/test_metrics.py) (38), [`test_deferred_duplicates.py`](../tests/test_deferred_duplicates.py) (69) |
| **Inputs** | Tiny share vectors with known ENP and CENP. |
| **Criterion** | Exact agreement with the closed form to 1e-12. |
| **Status** | Passing |
| **Evidence** | Test assertions only, with no generated file. |

`test_deferred_duplicates.py` also pins the duplicated ENP and CENP implementations against each other, on analytic
and generated shares. It does not assert that the two `delta_cenp` definitions are equal, because
[they start from different points](model.md#two-kinds-of-δcenp).

</details>

<details>
<summary><strong>2 · The decision rule</strong></summary>

<br>

| | |
|---|---|
| **Contract** | The trigger fires exactly when *C<sub>a</sub> ∩ T<sub>R</sub>* = ∅, and the cost of leaving the favourite flips the choice at the analytically derived value. |
| **Implementation** | [`core_model/agents.py`](../core_model/agents.py), `calcStrategicUtilities` and `_updatePartition` |
| **Tests** | [`test_decision_rule.py`](../tests/test_decision_rule.py) (24) |
| **Inputs** | Hand-built voters and candidates, with no ties. |
| **Criterion** | The trigger and the chosen candidate match the hand-derived expectation. |
| **Status** | Passing |

The tests cover the following cases. A favourite who is expected in the runoff does not trigger; a favourite who is
not, with another tolerable candidate who is, does. The trigger depends on the runoff guess and not on the voter.
With no candidate outside the tolerable set there is no incentive. The tolerable set is the ball of radius τ, with an
inclusive boundary; it is never empty and always holds the favourite. The favourite itself is never charged a cost.

The boundary case is derived rather than assumed: μ\* = (S<sub>alt</sub> − S<sub>j\*</sub>)/λ<sub>alt</sub> = 1/15
for the fixture, and the model flips there.

</details>

<details>
<summary><strong>3 · Polls and metrics</strong></summary>

<br>

| | |
|---|---|
| **Contract** | The temperature and the Dirichlet draw behave as specified; ε<sub>s</sub> only keeps the computation valid and has no effect on behaviour. |
| **Implementation** | [`core_model/signals.py`](../core_model/signals.py) |
| **Tests** | [`test_signals.py`](../tests/test_signals.py) (57), [`test_signal_epsilon.py`](../tests/test_signal_epsilon.py) (25) |
| **Criterion** | Polls are valid distributions; θ sharpens or flattens them monotonically; ε<sub>s</sub> = 1e-12 leaves outcomes unchanged. |
| **Status** | Passing |

</details>

<details>
<summary><strong>5 · Properties that hold in every round</strong></summary>

<br>

| | |
|---|---|
| **Contract** | Properties that must hold in *every* round of *any* run. |
| **Implementation** | [`core_model/model.py`](../core_model/model.py) |
| **Tests** | [`test_dynamic_invariants.py`](../tests/test_dynamic_invariants.py) (24) |
| **Criterion** | Every round allocates exactly the electorate; shares sum to 1; every recorded intention is a valid candidate index; intentions agree with the counts they produced; trigger and switching counts stay in range; each round's poll is a distribution; the projected finalists are valid and distinct. |
| **Status** | Passing |

This family includes `test_the_histories_line_up_on_the_documented_offset`, which pins the *n*+1 against *n* offset
between `history`/`intention_history` and the diagnostic series. It was written after investigating an apparent
failure. The offset is real and intended, so the test documents it rather than asserting something convenient and
false.

</details>

<details>
<summary><strong>7 · Relabelling and mirroring</strong></summary>

<br>

| | |
|---|---|
| **Contract** | Relabelling the candidates, or mirroring the left-right axis, must not change the decision. |
| **Tests** | `test_decision_is_invariant_to_party_relabelling`, `test_decision_is_symmetric_under_left_right_reflection`, `test_contender_set_does_not_depend_on_candidate_labels` |
| **Criterion** | The chosen candidate, mapped through the transformation, is the same. |
| **Status** | Passing |

These properties were derived from the equations before any test asserted them. All 120 relabellings were checked
exhaustively, and mirroring at five voter positions. Both hold with no counterexample. Had one failed, the property
itself would have been questioned before the code.

</details>

### Data and numbers

The model indexes every candidate by their position in the input files, so a silent change of order would corrupt
every candidate-level result without an error. A second set of tests remembers the exact numbers that earlier
commits produced, so that a change that moves everything at once cannot pass unnoticed.

<details>
<summary><strong>4 · Data integrity</strong></summary>

<br>

| | |
|---|---|
| **Contract** | The real-data files stay consistent with each other and aligned by position. |
| **Implementation** | [`core_model/empirical_data.py`](../core_model/empirical_data.py) |
| **Tests** | [`test_empirical.py`](../tests/test_empirical.py) (27) |
| **Inputs** | `data/party_positions_*.csv`, `polls_*.csv`, `results_*.csv`, `voters_ideology_*.csv` |
| **Criterion** | Positions inside [−1, 1] and sorted; *K* the same in every file; results sum to 1 (1e-9); polls normalized and non-negative in both `weekly` and `individual` modes. |
| **Status** | Passing, for both years |

</details>

<details>
<summary><strong>6 · Pinned numbers from earlier commits</strong></summary>

<br>

| | |
|---|---|
| **Contract** | Published numbers do not drift silently from one commit to the next. |
| **Tests** | [`test_empirical.py`](../tests/test_empirical.py), golden-value cases |
| **Criterion** | Full sincere and final share vectors match recorded values to `abs=1e-12`; switcher counts pinned. |
| **Status** | Passing |

Two configurations are pinned, both chosen so that voters actually switch:

- Synthetic: *K* = 8, *N* = 500, `width_factor` = 1.5, τ̂ = 1.75, μ = 0.1, *T* = 15, seed 42.
- Empirical 2022: favourites drawn, salience = *s*<sup>0</sup>, 350 voters, μ = 0.3, α = 0.1, ρ<sub>π</sub> = 70,
  β = 6, seed 33.

Comparing two runs of *today's* code only catches differences between two ways of calling it. A change that moves
every path equally, such as a rewrite of how favourites are chosen or a reordering of random draws, would leave such
a test green while every published number changed. Pinned values are what the suite remembers about earlier commits.

When one fails, it is either a bug, in which case the code is fixed and not the numbers, or a deliberate change to
the model, in which case the values are re-recorded with the snippet in each docstring and the commit message says
so. Every figure generated before that commit is then stale.

</details>

### The pipeline

The full empirical run takes about two and a half hours and writes files that are not committed. These checks make
sure a quick test run can never overwrite a full one, that an interrupted run resumes to exactly the same output,
and that every output records the tolerance in both units.

<details>
<summary><strong>8 · Output isolation and overwrite protection</strong></summary>

<br>

| | |
|---|---|
| **Contract** | A quick run can never overwrite a full run's output, and a full run refuses to destroy existing output without an explicit flag. |
| **Implementation** | `_refuse_existing_outputs()` in [`empirical_2002_2022.py`](../analysis/empirical/empirical_2002_2022.py); `SMOKE_DIR = data/smoke/` |
| **Tests** | [`test_quick_run_isolation.py`](../tests/test_quick_run_isolation.py) (5), [`test_overwrite_protection.py`](../tests/test_overwrite_protection.py) (13) |
| **Criterion** | The refusal happens before any output is modified, whether the existing file is smaller, equal or larger; a partial set of targets is detected; `--overwrite` cannot be combined with `--resume`. |
| **Status** | Passing |

This family exists because of a real incident. On 2026-08-19 a 15-draw `--quick` run silently overwrote the full
300-draw replay outputs, which had never been committed, since `data/` is git-ignored. Recovering them would mean
regenerating them from the commit before the fix. The protection was written so that it cannot happen again.

</details>

<details>
<summary><strong>9 · Resuming gives the same bytes</strong></summary>

<br>

| | |
|---|---|
| **Contract** | A sweep that is interrupted and resumed produces byte-identical output to one that is not. |
| **Implementation** | `load_resumable()` / `finalise_output()` in [`behavioral_sweep.py`](../analysis/empirical/behavioral_sweep.py) |
| **Tests** | [`test_sweep_resume.py`](../tests/test_sweep_resume.py) (29), [`test_canonical_csv.py`](../tests/test_canonical_csv.py) (30) |
| **Criterion** | Resuming checks the year, seed, `n_draws`, `n_repeats`, schema version and a SHA-256 fingerprint of the design; it rejects duplicate, non-integer or out-of-range draw ids, missing columns and non-finite values. |
| **Status** | Passing |

Each run's seed depends only on `(seed, draw, repeat)`, which is what makes the equivalence possible. Two mechanisms
deliver the byte-identity:

- **Canonical writing.** `finalise_output` reads with pandas' correctly rounded float parser
  (`float_precision="round_trip"`) and writes with pandas' shortest round-tripping form, atomically through a
  temporary file. The default parser is fast but not correctly rounded: it can return a double one ulp away from the
  text, so reading and rewriting never settles. CI caught exactly that on 2026-08-22, on a platform whose float
  values differ from the development machine's.
- **A true no-op for a complete file.** When `--resume` finds every draw already present, it checks the metadata,
  the design fingerprint and every row, then returns without touching the file. Its bytes, checksum and modification
  time are unchanged.

The no-op only speeds up the complete case and does not replace canonical writing. An interrupted resume still merges
new rows with old ones and rewrites the file.

Byte stability was measured rather than inferred. The same 2 000-value fixture, made of the CI failure's own values
plus signed zero, subnormals, the largest finite double, integer-like floats and 1 982 random bit patterns, was
written through `write_canonical` in both environments:

| Environment | numpy | pandas | Bytes | SHA-256 |
|---|---|---|---|---|
| Development | 1.26.4 | 3.0.3 | 400 054 | `653d8db8…45210791` |
| CI-matched | 2.4.6 | 3.0.5 | 400 054 | `653d8db8…45210791` |

The hashes are identical, and finalizing four times in a row changed nothing in either environment. So for these two
environments the output is byte-identical *across* them, not only stable within each. That is a measurement of two
configurations rather than a guarantee for every future numpy or pandas, which is what the regression tests are for.

**Why the writer is pandas' default and not `%.17g`.** Three ways of writing floats were measured on 60 000
adversarial doubles (random bit patterns, subnormals, extremes and signed zero), in both environments:

| Representation | Verdict |
|---|---|
| `repr` as a callable | **Rejected.** Under numpy 2 the callable receives a numpy scalar, so it writes `np.float64(0.1)` instead of `0.1` and corrupts the file. |
| `"%.17g"` | **Rejected.** Not lossless: it writes `-0.0` as `-0`, which reads back as `+0.0` and loses the sign of zero. |
| pandas default | **Chosen.** Bitwise exact on every value tested, including signed zero and subnormals, and stable across repeated cycles in both environments. |

pandas does not document its default float format as shortest round-trip, so
[`tests/test_canonical_csv.py`](../tests/test_canonical_csv.py) pins that property rather than assuming it. A future
release that changes it fails there.

</details>

<details>
<summary><strong>10 · Stages that agree with each other</strong></summary>

<br>

| | |
|---|---|
| **Contract** | Consecutive pipeline stages agree on file names, columns and paths. |
| **Tests** | [`test_pipeline_contract.py`](../tests/test_pipeline_contract.py) (9) |
| **Criterion** | The diagnostics find and read the replay output; every column they need is produced; the figure loaders resolve the replay file names and report a missing file clearly; the sweep output is a valid input for the importance analysis; the importance table has the documented columns. |
| **Status** | Passing |

These tests ignore what the figures look like. They catch mismatched file names, columns and paths, which is where
pipelines actually break.

</details>

<details>
<summary><strong>15 · The tolerance units in every output</strong></summary>

<br>

| | |
|---|---|
| **Contract** | Every output row records `tau_hat`, `tau_absolute` and `K`, with the conversion applied exactly once. |
| **Implementation** | [`empirical_2002_2022.py`](../analysis/empirical/empirical_2002_2022.py) |
| **Tests** | [`test_tau_absolute_output.py`](../tests/test_tau_absolute_output.py) (17), [`test_tau_units.py`](../tests/test_tau_units.py) (10), [`test_empirical_tables.py`](../tests/test_empirical_tables.py) (42), [`test_table_regeneration_check.py`](../tests/test_table_regeneration_check.py) (11) |
| **Criterion** | `tau_absolute == tau_hat × 2/K` to 1e-12; the ceiling for each year (2002 ≤ 0.4, 2022 ≤ 0.5, inclusive); `tau_hat` unchanged. |
| **Status** | Passing; checked on all 14 output files of the 2026-09-24 run, as for the 2026-08-21 one |
| **Evidence** | [`empirical_replay_summary.csv`](../results/tables/empirical_replay_summary.csv), [`empirical_activation_summary.csv`](../results/tables/empirical_activation_summary.csv) |

It is also enforced at run time by [`tools/validate_rerun.py`](../tools/validate_rerun.py), which checks as well that
the old `tau >= 2.0` warning appears zero times in the simulation logs.

</details>

<details>
<summary><strong>The committed tables must rebuild from the raw output</strong></summary>

<br>

This check needs 17 MB of git-ignored simulation output, so it cannot be a unit test, but it is still enforced:

```bash
python tools/check_tables_reproduce.py
```

It regenerates every table and exits non-zero if a tracked table changes, if an unexpected untracked table appears,
if a declared table is missing, or if the tables folder already had changes. Each case prints the files concerned. It
runs as pipeline step `08b_tables_reproduce`.

On a fresh clone it exits 3 with its own message. The raw outputs it needs are git-ignored on purpose, so they are
absent. That is not a failure of the tables, and the check says so rather than reporting a missing input as a stale
output.

The previous instruction was `make_empirical_tables.py && git status --short`, which checks nothing: `git status`
exits 0 whether or not anything changed, so a drifted table passed unless someone read the output.

[`tests/test_table_regeneration_check.py`](../tests/test_table_regeneration_check.py) tests both outcomes against
throwaway git repositories in `tmp_path`, without touching the real tables.

The generator also checks its input on the way *in*, before anything is aggregated. Every summary goes through a
pandas aggregation, and those skip NaN by default, so a corrupt input checked any later would read as a
healthy-looking mean over fewer rows.

</details>

### The protocol and the robustness of results

The run settings, such as 2 000 voters and 25 rounds, are chosen by experiment rather than by habit. These families
record those experiments, the global sensitivity analysis, and whether the empirical results survive changes to the
setup.

<details>
<summary><strong>11 · Enough rounds</strong></summary>

<br>

| | |
|---|---|
| **Question** | Do the votes settle before the last round? |
| **Implementation** | [`analysis/synthetic/protocol_validation.py`](../analysis/synthetic/protocol_validation.py) |
| **Tests** | [`test_protocol_validation.py`](../tests/test_protocol_validation.py) (28) |
| **Criterion** | The state read from a long run equals a short run at the same round; averages over the last rounds behave correctly at both ends. |
| **Status** | Passing |
| **Evidence** | [`protocol_horizon_validation.csv`](../results/tables/protocol_horizon_validation.csv), `protocol_horizon_stability_by_c.csv` |

</details>

<details>
<summary><strong>12 · Enough voters</strong></summary>

<br>

| | |
|---|---|
| **Question** | How many voters before ΔCENP is stable? |
| **Criterion** | The standard error of ΔCENP across seeds, as a function of *N*. It measures how stable the estimate is, not how means compare. |
| **Status** | Complete, and sets *N* = 2000 |
| **Evidence** | [`protocol_population_validation.csv`](../results/tables/protocol_population_validation.csv), `protocol_population_stability_by_c.csv` |

</details>

<details>
<summary><strong>13 · Robustness of the protocol (panels A–G)</strong></summary>

<br>

| | |
|---|---|
| **Implementation** | [`analysis/synthetic/robustness_checks.py`](../analysis/synthetic/robustness_checks.py) |
| **Tests** | [`test_result_tables.py`](../tests/test_result_tables.py) (49) |
| **Status** | Complete, all seven panels committed |
| **Evidence** | [`robustness_panel_{A…G}.csv`](../results/tables/) |

| Panel | Question | Sets |
|---|---|---|
| A · *N* | how many voters before ΔCENP is stable? | *N* = 2000 |
| B · *T*<sub>max</sub> | do the votes settle? | *T* = 25 |
| C · ε<sub>s</sub> | is ΔCENP unaffected by the poll floor? | ε<sub>s</sub> = **1e-12** (see below) |
| D · ξ | does the centre of the electorate matter, or only its shape? | ξ = 0 |
| E · θ | what does the temperature do mechanically? | analytic, no runs |
| F · μ | does μ reduce switching monotonically? | documents μ |
| G · truncation | does stopping at *T* = 25 change the reported outcomes? | validates *T* = 25 |

**Panel C, stated precisely.** It tries six `signal_epsilon` values on four chosen parameter settings. That
establishes robustness for those settings, not across the whole Saltelli space. The grid is
ε<sub>s</sub> ∈ {1e-12, 1e-6, 1e-4, 1e-3, 1e-2, 1e-1} × {Baseline, Sweet-spot} × {θ = 0.3, θ = 1.0}, with 10
repetitions each, giving 24 rows in [`robustness_panel_C.csv`](../results/tables/robustness_panel_C.csv). Within
those settings, 1e-12, 1e-6 and 1e-4 give identical votes.

These numbers are a regeneration. In the panel's first version ε<sub>s</sub> never reached the simulation, so every
point of the grid was bit-identical and the invariance it seemed to show was empty. Earlier copies of this panel
disagree with the committed one.

**Panel G qualifies panel B.** Panel B shows that a very spread-out electorate (*c* = 2.5) never settles, with 70% of
runs still moving at the last round. Panel G asks whether that matters for the *reported outcomes*. At high width a
single run moves by more than the spread between seeds (`drift_over_sd` ≈ 1.2–1.4), but the mean across seeds barely
moves: by 0.3% for ΔCENP and 0.04% for the final ENP. The runs oscillate around a stable centre rather than still
trending.

So the aggregate results are robust to the last round, and individual trajectories are not. A flat statement that
"the model converges by *T* = 25" is not supported and should not be made.

</details>

<details>
<summary><strong>14 · Which parameters matter (global sensitivity)</strong></summary>

<br>

| | |
|---|---|
| **Question** | Which parameters drive coordination, and how much comes from parameters acting together? |
| **Implementation** | [`analysis/synthetic/saltelli_sensitivity.py`](../analysis/synthetic/saltelli_sensitivity.py) (SALib) |
| **Design** | 8 parameters, *K* ∈ {6, 8, 9}, **10 240 evaluations per *K*** = 30 720 in total |
| **Criterion** | First- and total-order Sobol indices with bootstrap confidence intervals. |
| **Status** | Complete |
| **Evidence** | [`sobol_indices.csv`](../results/tables/sobol_indices.csv), **120 rows, committed.** The raw matrices `data/saltelli_results_K{6,8,9}.csv` are committed too, so the table rebuilds with `--analyze-existing` and no simulation. |

This is the only formal variance decomposition in the project. The empirical importance analysis is based on a Latin
hypercube and is exploratory: it ranks parameters without decomposing variance.

</details>

<details>
<summary><strong>16 · Robustness of the empirical replay</strong></summary>

<br>

| | |
|---|---|
| **Question** | Does the replay depend on arbitrary setup choices, or on the candidate positions that were imputed rather than measured? |
| **Variants** | `individual_signals` (individual polls rather than weekly means), `perturbed_positions` (±0.05 jitter), `resampled_voters` (a different draw of the electorate), `perturbed_imputed_positions` (±0.2 jitter of the LLM-coded or bridged positions only) |
| **Design** | 100 draws × 4 variants × 2 years = 800 runs |
| **Status** | Complete, all four variants (2026-09-24 run) |
| **Evidence** | [`empirical_robustness_summary.csv`](../results/tables/empirical_robustness_summary.csv) |

</details>

<details>
<summary><strong>17 · How much is seed noise</strong></summary>

<br>

| | |
|---|---|
| **Question** | How much of the variation is noise from the random seed rather than signal? |
| **Implementation** | [`analysis/synthetic/protocol_posthoc.py`](../analysis/synthetic/protocol_posthoc.py) |
| **Tests** | [`test_protocol_posthoc.py`](../tests/test_protocol_posthoc.py) (33) |
| **Criterion** | Within- and between-seed variance with a bootstrap ICC; Benjamini–Hochberg correction within each outcome × statistic × interval family. |
| **Status** | Complete |
| **Evidence** | [`protocol_seed_noise_decomposition.csv`](../results/tables/protocol_seed_noise_decomposition.csv), `protocol_horizon_drift_{by_config,summary}.csv` |

</details>

## What reproduces, and how exactly

| Output | Guarantee |
|---|---|
| Model runs | **Bit-identical** for a fixed seed. |
| `sobol_indices.csv` | Rebuilds from committed inputs with no simulation. |
| Empirical tables | **Byte-identical** when regenerated, checked by SHA-256 and by a test that compares the written bytes rather than the parsed floats. |
| `lhs_parameter_importance.csv` | Reproducible, but not byte-identical. |

The importance table is the one exception. Its predictors and every seed are fixed (`SEED = 42`), the values
reproduce within numerical tolerance and the rankings are stable. The last bit can still move (~1e-16), because the
surrogate is fitted in parallel and the order of floating-point sums is not fixed. Compare regenerated copies
numerically, never by checksum.

## Known limits

- **The pooled parameter importance cannot be interpreted.** Its 5-fold cross-validated R² is −0.187, worse than
  predicting the mean, and the script warns below 0.1. The per-year analyses (R² 0.853 and 0.991) are sound; the
  pooled row should not be cited.
- **No baseline from before the fix is archived for the nearest-candidate replay** (see family 8). One could be
  regenerated from the commit before the fix (`70e23f5`) with the fixed seed, but that has not been done.

---

<p align="center"><sub>
<a href="model.md">← Model</a> · <strong>Validation</strong> · <a href="experiments.md">Experiments →</a>
</sub></p>
