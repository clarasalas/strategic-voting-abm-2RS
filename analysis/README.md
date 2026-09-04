# analysis/

Two independent lanes over one shared model. Neither imports the other; both
import `core_model/` and nothing else from this repository.

| Lane | Question | Environment |
|---|---|---|
| [`synthetic/`](synthetic) | Which parameters drive coordination at all? | generated candidates, electorate and poll |
| [`empirical/`](empirical) | Does the rule reproduce the 2002 vs 2022 contrast? | real candidates, electorate and poll timeline |

**These files are not numbered on purpose.** The scripts form a graph, not a
sequence: each lane has several roots that do not depend on each other, and one
file in `synthetic/` is a library rather than a stage at all. The tables below
say what each script *needs*, which is the thing a number cannot express.

The authoritative, executable version of the empirical order is
[`tools/run_empirical_rerun.sh`](../tools/run_empirical_rerun.sh), which
validates each stage before running the stages that consume it. The same order
in prose is [Experiments → Pipeline order](../docs/experiments.md#pipeline-order).

---

## empirical/

```
                        ┌─→ empirical_diagnostics.py
empirical_2002_2022.py ─┼─→ empirical_figures.py
      (simulates)       └─→ empirical_beta_bins.py      ┐
                                                        │
                        ┌─→ behavioral_compare.py ←─┐   ├─→ make_empirical_tables.py
behavioral_sweep.py ────┼─→ behavioral_sweep_figure.py  │        (committed tables)
      (simulates)       └─→ lhs_importance.py       │   │
                                                    │   │
behavioral_targets.py ──────────────────────────────┘ ──┘
      (no simulation)
```

### Roots: these run the model, and everything else waits on them

| Script | Needs | Writes |
|---|---|---|
| `empirical_2002_2022.py` | real data only | `data/empirical_runs{tag}_{year}.csv`, `empirical_candidate_shares{tag}_{year}.csv`, `empirical_candidate_draws{tag}_{year}.csv`, `empirical_robustness_{year}.csv`, `empirical_init_benchmarks_{year}.csv` |
| `behavioral_sweep.py` | real data only | `data/behavioral_sweep_{year}.csv` + `_design.csv` + `_meta.json` |
| `behavioral_targets.py` | real data only | `data/behavioral_targets.csv` |

`behavioral_targets.py` runs no simulation and takes seconds; its output is
committed, so it rarely needs re-running. The other two are the expensive
stages: the sweep is roughly 3.5 hours per year, and resumes with `--resume`.

### Consumers: read the CSVs above, run no simulation

| Script | Needs | Writes |
|---|---|---|
| `empirical_diagnostics.py` | `empirical_2002_2022` | `data/empirical_diagnostics_{year}.csv`, `empirical_activation_summary*.csv`, `empirical_shared_activating_draws*.csv` |
| `empirical_figures.py` | `empirical_2002_2022` | `figures/fig_*` |
| `empirical_beta_bins.py` | `empirical_2002_2022` (the `_draws` table) | `data/empirical_beta_bins_*`, `figures/` |
| `behavioral_compare.py` | `behavioral_sweep` + `behavioral_targets` | `data/behavioral_compare_2002_2022.csv` |
| `behavioral_sweep_figure.py` | `behavioral_sweep` + `behavioral_targets` | `figures/behavioral_sweep.*` |
| `lhs_importance.py` | `behavioral_sweep` | `results/tables/lhs_parameter_importance.csv`, `figures/` |
| `make_empirical_tables.py` | everything above | the 6 committed `results/tables/empirical_*` + `behavioral_sweep_quantiles.csv` |

`make_empirical_tables.py` is the terminal stage: it derives every committed
empirical table from raw `data/` output. `tools/check_tables_reproduce.py`
re-runs it and fails if any committed table changes.

---

## synthetic/

```
parameter_space.py   (library, imported, never run)
        │
        ├─→ saltelli_sensitivity.py ──→ main_results.py
        │        (simulates)
        └─→ protocol_validation.py ──→ protocol_posthoc.py
                 (simulates)

robustness_checks.py   (simulates; standalone, needs no input CSV)
```

| Script | Needs | Writes |
|---|---|---|
| `parameter_space.py` | nothing | nothing. Side-effect-free definition of `PROBLEM`, imported by the three scripts above it. Not a stage; it has no place in any run order. |
| `saltelli_sensitivity.py` | real data only | `data/saltelli_results_K{6,8,9}.csv`, `results/tables/sobol_indices.csv`. `--analyze-existing` recomputes the indices from the committed matrices without simulating. |
| `robustness_checks.py` | nothing | `results/tables/robustness_panel_{A..G}.csv`, `analysis/synthetic/outputs/robustness_checks/`. ~2-4 min. |
| `protocol_validation.py` | real data only | `analysis/synthetic/outputs/protocol_validation/{design,horizon_raw,population_raw}.csv`, `results/tables/protocol_*.csv` |
| `protocol_posthoc.py` | `protocol_validation` (`horizon_raw.csv`) | `results/tables/protocol_horizon_drift_summary.csv`, `protocol_seed_noise_decomposition.csv`. Launches no simulations. |
| `main_results.py` | `saltelli_sensitivity` (optional, omits the model band if absent) | the four main figures + their raw CSVs |

---

## Conventions

- Every script is run from the repository root: `python analysis/<lane>/<script>.py`.
- Raw simulation output in `data/` is git-ignored; only derived tables under
  `results/tables/` are committed. See
  [results/README.md](../results/README.md) for which script generates each one.
- Runs refuse to overwrite existing output without `--overwrite`, and `--quick`
  writes to `data/smoke/` so a smoke run cannot clobber a full experiment.
- Each script's module docstring carries its own `Reads` / `Writes` block; this
  file is the summary, the docstring is the detail.
