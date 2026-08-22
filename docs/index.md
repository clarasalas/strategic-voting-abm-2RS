# Strategic Voting ABM — Model & Validation Guide

An agent-based model of strategic voting in two-round presidential elections,
replayed against the French first rounds of **2002** and **2022**.

This guide is the single canonical description of the model, how it is
verified, and how to reproduce every number in the repository. It replaces the
earlier standalone "fiche technique".

> **Audience.** Written to be readable by a software engineer who has never
> studied voting models. Political-science terms are defined where they first
> appear.

## This documentation is canonical

**The Markdown files in this repository are the authoritative documentation.**
They read directly on GitHub with previous/next links, need no documentation
site or build step, and depend on no external service.

An [interactive rendering](https://claude.ai/code/artifact/af7c9e81-51ed-4411-9e8f-79dd4482aad2)
of the same material is published as an **optional convenience mirror**. It is
synchronized *from* these files and is not authoritative. Understanding or
reproducing this repository must not require access to it. Where the two
disagree, the repository is correct.

---

## Read in order

| # | Page | What it answers |
|---|---|---|
| 1 | **[Model](model.md)** | What the model is, what its entities are, and exactly what happens in one iteration. |
| 2 | **[Validation](validation.md)** | How we know the implementation is coherent — 17 families of checks, 523 tests. |
| 3 | **[Experiments](experiments.md)** | The synthetic and empirical protocols: parameter spaces, seeds, simulation counts. |
| 4 | **[Reproducibility](reproducibility.md)** | Install, run, and regenerate every committed artefact. |
| 5 | **[Code map](code_map.md)** | Repository architecture and which definition is canonical. |

---

## In one paragraph

Voters sit on a left–right axis. Each holds a sincere preference, watches a
public poll signal, and forms beliefs about who will reach the two-candidate
runoff. A voter votes **strategically** only when no candidate they can tolerate
is projected to qualify — otherwise they vote sincerely. The model asks what
aggregate coordination that rule produces, and whether it matches the two real
French elections. **2002** is the fragmentation case (the left split and its
front-runner missed the runoff); **2022** is the coordination case.

---

## Status

| | |
|---|---|
| Test suite | **521 passed, 2 skipped** — a [dated local run](validation.md#verification-snapshot), not a CI result |
| Last empirical rerun | 2026-08-21, commit `0bba146`, **14 000 simulations**, 30/30 stages OK |
| Compact result tables | 22 under [`results/tables/`](../results/README.md); 7 generated and included in this branch |
| Raw simulation output | git-ignored by design — regenerate from the scripts |

The empirical replay was re-run in full on 2026-08-21 after a tolerance-unit
defect was corrected. See [the τ̂ conversion](model.md#tolerance-the-two-units)
for the mechanism, and the
[rerun record](reports/empirical_rerun_2026-08-21.md) for the protocol,
validation status and outputs.

---

## What this project does and does not claim

**It does claim** to be a coherent, tested, reproducible implementation of a
specific strategic-voting rule, with its behaviour under both abstract and real
electoral structures characterised and documented.

**It does not claim** to be a predictive model of French elections, a fitted
model, or a parameter-recovery exercise. The empirical mode is
*pattern-oriented*: one behavioural draw is applied to both years, and only the
environment changes. Where the model fails to reproduce reality, that failure is
documented rather than tuned away.

---

Next → **[Model](model.md)**
