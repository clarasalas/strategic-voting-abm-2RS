<h1 align="center">docs</h1>

<p align="center">
The <a href="https://clarasalas.github.io/strategic-voting-abm-2RS/">interactive page</a>, and the detailed
reference behind it.
</p>

<p align="center"><sub><a href="../README.md">← Back to the project</a></sub></p>

## Two things live here

**The interactive page.** [`index.html`](index.html) is published by GitHub Pages from this folder, which is why
the folder is called `docs/` and has to stay where it is. Its data, [`data/grid.json`](data/grid.json), is computed
by [`demo/`](../demo/README.md). Start there for a quick, visual introduction.

**The reference.** The page's cards summarise the model, the checks and the data. These pages hold what a card
leaves out: the equations, every family of checks, parameter ranges and seeds, and the exact commands.

## The reference

| Page | What it answers |
|---|---|
| **[Model](model.md)** | What the model is, what its entities are, and exactly what happens in one round. |
| **[Validation](validation.md)** | How we know the code is right: 17 families of checks, what each guarantees and what it does not. |
| **[Experiments](experiments.md)** | The synthetic and empirical protocols: parameter ranges, seeds, simulation counts, data sources. |
| **[Reproducibility](reproducibility.md)** | Install, run, and rebuild every committed number. |
| **[Code map](code_map.md)** | How the repository is laid out, and which definition wins when two seem to compute the same thing. |

## Run records

A dated record of every full empirical run: what changed, what ran, how it was checked, what it produced.

| Run | Inputs | |
|---|---|---|
| [2026-09-24](reports/empirical_rerun_2026-09-24.md) | survey-based positions and electorates, polls from fixed Wikipedia revisions | **current** |
| [2026-08-21](reports/empirical_rerun_2026-08-21.md) | expert and LLM-coded positions, hand-copied polls | superseded; its 2022 polls had two pairs of candidates swapped |

<details>
<summary><strong>Working notes</strong></summary>

<br>

Kept in [`notes/`](notes) for the record. They were written to plan and operate the August 2026 run, and parts of
them describe that moment rather than the current state.

* [Analysis map](notes/analysis_map.md): which definitions are duplicated across scripts, and which are canonical.
* [Local rerun runbook](notes/local_rerun_runbook.md) and [rerun manifest](notes/rerun_manifest.md): how the
  August run was launched and checked.
* [Documentation plan](notes/documentation_plan.md): the outline these pages were written from.

</details>

<details>
<summary><strong>Scope of the empirical mode</strong></summary>

<br>

The empirical mode is *pattern-oriented*. One behavioural setting is applied to both years, only the environment
changes, and nothing is fitted to either election. Where the model diverges from the real result, the divergence
is recorded as it stands.

</details>
