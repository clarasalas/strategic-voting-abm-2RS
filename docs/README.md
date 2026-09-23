# Documentation

The detailed reference for the model, how it is checked, and how to reproduce
every number in the repository. For a quick, visual introduction, start with the
[interactive page](https://clarasalas.github.io/strategic-voting-abm-2RS/)
instead; its source is [`index.html`](index.html) in this folder.

## Read in order

| # | Page | What it answers |
|---|---|---|
| 1 | **[Model](model.md)** | What the model is, what its entities are, and exactly what happens in one iteration. |
| 2 | **[Validation](validation.md)** | How we know the implementation is coherent: 17 families of checks. |
| 3 | **[Experiments](experiments.md)** | The synthetic and empirical protocols, with parameter spaces, seeds and simulation counts. |
| 4 | **[Reproducibility](reproducibility.md)** | Install, run, and regenerate every committed artefact. |
| 5 | **[Code map](code_map.md)** | Repository architecture and which definition is canonical. |

Working notes, kept for the record: [analysis map](analysis_map.md),
[local rerun runbook](local_rerun_runbook.md), [rerun manifest](rerun_manifest.md),
[2026-08-21 rerun report](reports/empirical_rerun_2026-08-21.md),
[documentation plan](documentation_plan.md).

## Status

| | |
|---|---|
| Test suite | runs in [CI](https://github.com/clarasalas/strategic-voting-abm-2RS/actions) on every push and pull request |
| Last empirical rerun | 2026-08-21, commit `0bba146`, **14 000 simulations**, 30/30 stages OK |
| Compact result tables | 22 under [`results/tables/`](../results/README.md) |
| Raw simulation output | git-ignored on purpose; regenerate from the scripts |

The empirical replay was re-run in full on 2026-08-21 after a tolerance-unit
defect was corrected. See [the τ̂ conversion](model.md#tolerance-the-two-units)
for the mechanism, and the
[rerun record](reports/empirical_rerun_2026-08-21.md) for the protocol,
validation status and outputs.

## Scope

The empirical mode is *pattern-oriented*. One behavioural draw is applied to
both years, only the environment changes, and nothing is fitted to either
election. Where the model diverges from the real result, the divergence is
recorded as it stands.

---

Next → **[Model](model.md)**
