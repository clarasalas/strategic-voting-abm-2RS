<h1 align="center">tests</h1>

<p align="center">
The checks that run on every push. They exist because an earlier round of results was wrong in a way that every
figure looked plausible under.
</p>

<p align="center"><sub><a href="../README.md">← Back to the project</a></sub></p>

## Run them

```bash
pip install pytest && pip install -e ".[analysis]"
python -m pytest -ra
```

About 650 tests, in under a minute. Numerical warnings count as failures, and `-ra` prints the reason for every
skipped test, so a check that silently stops running shows up. The same command runs in
[CI](https://github.com/clarasalas/strategic-voting-abm-2RS/actions) on every push and pull request.

## What they check

| Question | Files |
|---|---|
| **Does the code do what the equations say?** Hand-computed values, the decision rule, polls and metrics | `test_metrics.py`, `test_decision_rule.py`, `test_signals.py`, `test_signal_epsilon.py`, `test_deferred_duplicates.py` |
| **Does a run behave at every step?** Invariants that must hold each round, and diagnostics that must not change the run | `test_dynamic_invariants.py`, `test_diagnostics_are_observational.py` |
| **Are the inputs right?** Candidate positions, electorates and polls, pinned by candidate name against their sources | `test_cses_inputs.py`, `test_polls.py`, `test_empirical.py` |
| **Has anything moved?** Full output vectors pinned from fixed seeds | `test_empirical.py` (golden regressions) |
| **Are the tolerance units right?** The conversion behind the error that invalidated the earlier results | `test_tau_units.py`, `test_tau_absolute_output.py` |
| **Do the stages still fit together?** A small end-to-end pass, and the outputs each stage hands to the next | `test_pipeline_contract.py`, `test_predictor_schema.py`, `test_protocol_validation.py`, `test_protocol_posthoc.py` |
| **Can a run lose or corrupt data?** Overwrite refusal, smoke runs kept apart, interrupted sweeps resuming to identical results | `test_overwrite_protection.py`, `test_quick_run_isolation.py`, `test_sweep_resume.py`, `test_canonical_csv.py` |
| **Are the committed numbers the real ones?** Table schemas, regeneration, and the page's data against the model | `test_result_tables.py`, `test_empirical_tables.py`, `test_table_regeneration_check.py`, `test_demo_data_matches_model.py` |

`conftest.py` only silences two notices pandas prints at import time about optional packages this project does
not use.

<details>
<summary><strong>Where to read more</strong></summary>

<br>

The full record, [`docs/validation.md`](../docs/validation.md), groups the checks into 17 families and says for
each one what it guarantees and what it does not. The docstring at the top of each test file says why the file
exists; several record the bug that prompted it.

</details>
