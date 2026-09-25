<h1 align="center">Code map</h1>

<p align="center">
How the repository is laid out, and which definition wins when two seem to compute the same thing.
</p>

<p align="center"><sub>
<a href="reproducibility.md">← Reproducibility</a> · <strong>Code map</strong> · <a href="README.md">Docs →</a>
</sub></p>

## The layout

The model lives in one package, [`core_model/`](../core_model/README.md), which is the only folder that is installed.
Everything else uses it. The synthetic and empirical experiments in [`analysis/`](../analysis/README.md) import the
model and share nothing else, and [`tools/`](../tools/README.md) builds the inputs and runs the pipeline without
computing any result itself.

```
strategic-voting-abm-2RS/
├── core_model/            the model: no experiment design, no result files, no command line
│   ├── model.py             run_simulation(), the loop over rounds
│   ├── agents.py            voters and candidates; the decision rule
│   ├── environment.py       imagined electorates and candidate positions
│   ├── signals.py           generated polls: temperature and noise
│   ├── functions.py         electorate helpers, coordination_measures
│   ├── metrics.py           ENP, CENP, tau_absolute   ← the only place units are converted
│   ├── empirical_data.py    reads the real 2002 and 2022 inputs
│   └── empirical_outcomes.py compares a replay with the real election
│
├── analysis/
│   ├── synthetic/         imagined electorates
│   │   ├── parameter_space.py      the Saltelli design   ← the only place its ranges are declared
│   │   ├── saltelli_sensitivity.py Sobol indices (SALib)
│   │   ├── robustness_checks.py    protocol panels A–G
│   │   ├── protocol_validation.py  enough rounds, enough voters
│   │   ├── protocol_posthoc.py     seed noise, Benjamini–Hochberg correction
│   │   └── main_results.py         synthetic headline figures
│   │
│   └── empirical/         France 2002 and 2022
│       ├── empirical_2002_2022.py  the replay (4 ways of starting)
│       ├── behavioral_sweep.py     the 1 000-draw ΔCENP sweep, resumable
│       ├── behavioral_targets.py   the real ΔCENP of each election
│       ├── behavioral_compare.py   2002 against 2022, significance tests
│       ├── empirical_diagnostics.py who is triggered, and who switches
│       ├── empirical_figures.py    replay figures
│       ├── behavioral_sweep_figure.py
│       ├── empirical_beta_bins.py  candidate diagnostics by range of β
│       ├── lhs_importance.py       RandomForest surrogate and permutation importance
│       └── make_empirical_tables.py the 6 committed empirical tables
│
├── data/                  real inputs (committed), raw output (ignored)
├── results/tables/        23 small tables, the numbers to cite
├── tests/                 24 files, 653 tests, no skips
├── tools/                 building inputs, running and checking the pipeline
├── demo/                  the data behind the interactive page
├── illustration_figures/  figures that explain the model
└── docs/                  the interactive page and these reference pages
```

Each folder has its own short guide, listed in the [project README](../README.md).

<details>
<summary><strong>What each folder is responsible for</strong></summary>

<br>

**`core_model/`** is the model and nothing else: no experiment design, no result files, no command line. It uses
relative imports, and `pip install -e .` makes `from core_model.model import run_simulation` work from any folder.

**`analysis/synthetic/`** runs the experiments on imagined electorates, with generated polls: which parameters
matter, and whether the protocol is sound. It produces the Sobol indices and the protocol panels.

**`analysis/empirical/`** replays 2002 and 2022 with the real candidates, a real electorate and the real polls, and
asks whether the rule reproduces the contrast between them.

**`tests/`** is organized by what each test guarantees rather than by source file. See
[Validation](validation.md#the-17-families-of-checks).

**`results/tables/`** holds the only committed derived output: small, deterministic and easy to compare line by
line. Each table is described in [`results/README.md`](../results/README.md).

**`data/`** holds the real inputs (`polls_*`, `results_*`, `party_positions_*`, `voters_ideology_*`, `FR-*`) and the
raw Saltelli matrices, so that the Sobol table rebuilds without simulation. Everything the model *writes* there is
git-ignored.

**`tools/`** is operational rather than scientific. Nothing in it computes a result.

**`docs/`** holds these pages, the interactive page, the dated [run records](reports/empirical_rerun_2026-09-24.md),
and the [working notes](README.md#run-records) of the August 2026 run.

</details>

## One home for each definition

Where the same idea could be written in several places, exactly one is authoritative. When two files seem to compute
the same thing, this table says which one wins.

| Concept | Where it lives | Rule |
|---|---|---|
| **τ̂ → τ conversion** | `core_model/metrics.py::tau_absolute` | The only place the conversion may happen. Callers convert once and record both values. |
| **ENP and CENP** | `core_model/metrics.py` | |
| **Saltelli ranges** | `analysis/synthetic/parameter_space.py::PROBLEM` | Never restate the ranges by hand. |
| **Swept parameters** | `lhs_importance.py::SWEPT_PREDICTORS` | An explicit list for each design, rather than detecting columns and excluding some, so a metadata column can never become a predictor. |
| **Outcomes of a replay** | `core_model/empirical_outcomes.py` | |
| **Real ΔCENP of each election** | `analysis/empirical/behavioral_targets.py` | |

## Look alike, but must stay separate

Some code looks duplicated and is not. Merging any of these would silently change results.

<details>
<summary><strong>The two ΔCENP definitions</strong></summary>

<br>

| | Starting point |
|---|---|
| `functions.coordination_measures(sincere, final)` | the model's own sincere vote in round 0 |
| [`behavioral_sweep.py:215`](../analysis/empirical/behavioral_sweep.py#L215), `cenp(final) − cenp(s⁰)` | the real opening poll |

They are different quantities answering different questions, and only the second can be compared with the real
election ([why](model.md#two-kinds-of-δcenp)). A contract test pins each against drift and does not assert that they
are equal.

</details>

<details>
<summary><strong>The two Latin-hypercube declarations</strong></summary>

<br>

The two functions are identical; the order of their dimensions is not.

| Runner | Order |
|---|---|
| `empirical_2002_2022` | `tau_hat, rho_pi, alpha, [mu], [beta]` |
| `behavioral_sweep` | `tau_hat, mu, alpha, rho_pi, beta` |

The sampler draws one dimension at a time from a shared generator, so the order determines the design. Reordering the
list would change every drawn value and silently invalidate the comparison the reruns exist to make. The function can
be shared; the orders must not move.

</details>

<details>
<summary><strong><code>initialization_benchmarks</code> passing <code>tau=2.0</code></strong></summary>

<br>

A deliberate exception to the conversion rule, so that every candidate is tolerable and the ways of choosing a
favourite are compared on the same footing. It is commented as such at
[`empirical_2002_2022.py:554`](../analysis/empirical/empirical_2002_2022.py#L554).

</details>

<details>
<summary><strong>Merges left for later</strong></summary>

<br>

The audit before the August 2026 rerun found these, and they were left alone until the results had been safely
regenerated. The reasoning is in [`analysis_map.md`](notes/analysis_map.md).

| | Item | Action |
|---|---|---|
| A1 | Latin-hypercube function | merge; keep both orders, fingerprint first |
| A2 | Duplicated ENP and CENP | merge; their equivalence is already pinned |
| A3 | Parameter ranges | merge |
| B3 | Extraction of outcomes | merge |
| B4 | Row builder | merge |
| B5 | Binning helper | merge |

</details>

---

<p align="center"><sub>
<a href="reproducibility.md">← Reproducibility</a> · <strong>Code map</strong> · <a href="README.md">Docs →</a>
</sub></p>
