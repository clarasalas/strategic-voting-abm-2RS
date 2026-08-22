# Code map

[← Reproducibility](reproducibility.md) · **Code map** · [Index →](index.md)

---

## Tree

```
strategic-voting-abm-2RS/
├── core_model/            the model itself — no analysis, no I/O of results
│   ├── agents.py            Elector and Party; the decision rule
│   ├── model.py             run_simulation() — the iteration loop
│   ├── functions.py         electorate construction, coordination_measures
│   ├── metrics.py           ENP, CENP, ΔCENP, tau_absolute   ← CANONICAL units
│   ├── signals.py           temperature transform + Dirichlet draw
│   ├── empirical_data.py    loaders for the real 2002/2022 bundles
│   └── empirical_outcomes.py per-run outcome extraction, topk, benchmarks
│
├── analysis/
│   ├── synthetic/         abstract-model experiments
│   │   ├── parameter_space.py     the Saltelli PROBLEM  ← CANONICAL bounds
│   │   ├── saltelli_sensitivity.py  Sobol indices (SALib)
│   │   ├── robustness_checks.py     protocol panels A–G
│   │   ├── protocol_validation.py   horizon + population validation
│   │   ├── protocol_posthoc.py      seed-noise decomposition, BH correction
│   │   └── main_results.py          synthetic headline figures
│   │
│   └── empirical/         real-election replay
│       ├── empirical_2002_2022.py   the replay runner (4 specifications)
│       ├── behavioral_sweep.py      1000-draw ΔCENP sweep, resumable
│       ├── behavioral_targets.py    observed ΔCENP from real results
│       ├── behavioral_compare.py    2002 vs 2022 significance tests
│       ├── empirical_diagnostics.py activation diagnostics (post-hoc)
│       ├── empirical_figures.py     replay figures
│       ├── behavioral_sweep_figure.py
│       ├── empirical_beta_bins.py   β-bin candidate diagnostics
│       ├── lhs_importance.py        RandomForest surrogate + permutation
│       └── make_empirical_tables.py the 6 committed empirical tables
│
├── tests/                 18 files, 523 tests
├── results/tables/        22 compact CSVs — the citable artefacts
├── data/                  real inputs (committed) + raw output (ignored)
├── docs/                  this guide
└── tools/                 operational scripts, not analysis
    ├── run_empirical_rerun.sh   unattended pipeline driver
    ├── validate_rerun.py        per-file output validator
    └── archive_pre_rerun.sh     evidence snapshot + SHA-256 manifest
```

---

## Responsibilities

### `core_model/`

The model, and nothing else. No experiment design, no result files, no CLI. Both
analysis trees import from here and share nothing else.

> Uses **flat internal imports** (`from agents import …`), so `core_model` must
> be on `sys.path`. Every script in `analysis/` does
> `sys.path.insert(0, str(REPO / "core_model"))`.

### `analysis/synthetic/`

Experiments on the abstract model: which parameters matter, and is the protocol
sound? Generated electorates and generated signals. Outputs the Sobol indices and
the protocol panels.

### `analysis/empirical/`

Replay against the real 2002/2022 structure. Real positions, real electorate,
**exogenous** real poll timelines. Answers whether the rule reproduces the
observed contrast.

### `tests/`

See the [validation matrix](validation.md#validation-matrix). Organised by
contract, not by source file.

### `results/tables/`

The only committed derived output. Compact, deterministic, diff-readable —
documented in [`results/README.md`](../results/README.md).

### `data/`

Real inputs are **committed** (`polls_*`, `results_*`, `party_positions_*`,
`voters_ideology_*`, `FR-*`), plus the raw Saltelli matrices so the Sobol table
regenerates without simulation. Everything the model *writes* is ignored.

### `docs/`

This guide, plus the operational records: [`rerun_manifest.md`](rerun_manifest.md),
[`local_rerun_runbook.md`](local_rerun_runbook.md),
[`analysis_map.md`](analysis_map.md), and dated run records under
[`docs/reports/`](reports/empirical_rerun_2026-08-21.md).

### `tools/`

Operational, not scientific. Nothing here computes a result.

---

## Canonical definitions

Where the same idea could live in several places, exactly one is authoritative.

| Concept | Canonical home | Rule |
|---|---|---|
| **τ̂ → τ conversion** | `core_model/metrics.py::tau_absolute` | The **only** place the conversion may happen. Callers convert once and record both values. |
| **ENP / CENP** | `core_model/metrics.py` | |
| **Saltelli bounds** | `analysis/synthetic/parameter_space.py::PROBLEM` | Never re-declare bounds by hand. |
| **Swept predictors** | `lhs_importance.py::SWEPT_PREDICTORS` | An explicit **allowlist** per design, never auto-detection plus exclusions. Metadata columns can never become predictors. |
| **Outcome extraction** | `core_model/empirical_outcomes.py` | |
| **Observed ΔCENP targets** | `analysis/empirical/behavioral_targets.py` | |

---

## Intentionally separate — do not merge

These look like duplicates and are not.

### The two ΔCENP definitions

| | Baseline |
|---|---|
| `functions.coordination_measures(sincere, final)` | the model's **own iteration-0 sincere shares** |
| `behavioral_sweep.py:199` — `cenp(final) − cenp(s⁰)` | the **exogenous opening poll** |

**Different quantities answering different questions.** Only the second is
comparable to observation. A contract test pins both against drift and
deliberately does **not** assert they are equal.

### The two Latin-hypercube declarations

The *function* bodies are identical; the *dimension orders* are not:

| Runner | Order |
|---|---|
| `empirical_2002_2022` | `tau_hat, rho_pi, alpha, [mu], [beta]` |
| `behavioral_sweep` | `tau_hat, mu, alpha, rho_pi, beta` |

> The LHS routine draws one dimension at a time from a shared generator, so
> **the order determines the design.** Reordering the list changes every drawn
> value and would silently invalidate the comparison the reruns exist to
> produce. The function may be lifted; the orders must not move.

### `initialization_benchmarks` passing `tau=2.0`

A deliberate exception to the conversion rule, so every party is a contender and
the three attachment rules are compared on identical footing. Commented as such
at [`empirical_2002_2022.py:511`](../analysis/empirical/empirical_2002_2022.py).

---

## Deferred consolidations

Identified by the pre-rerun audit and left alone until the numerical results were
safely regenerated. Full reasoning in [`analysis_map.md`](analysis_map.md).

| | Item | Action |
|---|---|---|
| A1 | LHS function | consolidate — keep both call orders, fingerprint first |
| A2 | ENP/CENP duplicates | consolidate — equivalence already pinned |
| A3 | Parameter ranges | consolidate |
| B3 | Outcome extraction | consolidate |
| B4 | Row builder | consolidate |
| B5 | Binning helper | consolidate |

---

[← Reproducibility](reproducibility.md) · **Code map** · [Index →](index.md)
