# Numerical result tables

Small, committed, reproducible tables carrying the numbers behind the thesis
figures. Everything here is **derived output**: compact enough to read in a diff,
stable enough to cite.

Raw simulation output (`data/empirical_*`, `data/behavioral_*`,
`analysis/**/outputs/`) and all figures (`figures/`, `analysis/**/*.png`) stay
**intentionally uncommitted**. They are bulky, they regenerate from the scripts,
and none of them is the artefact a reader needs. Only `results/tables/` is
tracked.

---

## Formal vs exploratory

This distinction matters and is easy to lose:

| Table | Status | What it licenses |
|---|---|---|
| `sobol_indices.csv` | **Formal variance decomposition.** Saltelli design, Sobol estimator, bootstrap confidence intervals. | "Parameter *x* accounts for *n* % of the variance in outcome *y*." |
| `robustness_panel_*.csv` | Descriptive summaries of designed experiments. | "Under condition *x*, the statistic is *y*." |
| `lhs_parameter_importance.csv` | **Exploratory surrogate importance.** Latin-hypercube design, RandomForest surrogate, permutation importance. **Not** a Sobol analysis. | "Parameter *x* ranks above *y* for this outcome." Not a variance share. |

The LHS design is not a Saltelli sequence, so the importances there rank
parameters — they do not decompose variance. The distinction is preserved in the
script, in the figure captions and here.

---

## `sobol_indices.csv`

First- and total-order Sobol indices with bootstrap confidence intervals, for
every (K, outcome, parameter) triple of the synthetic model.

| | |
|---|---|
| **Columns** | `K, outcome, parameter, S1, S1_conf, ST, ST_conf, n_base, n_evaluations` |
| **Rows** | 120 = 3 *K* × 5 outcomes × 8 parameters |
| **Inputs** | `data/saltelli_results_K{6,8,9}.csv` (committed, ~2 MB each) |
| **Reproduce** | `python analysis/synthetic/saltelli_sensitivity.py --analyze-existing` |

```bash
python analysis/synthetic/saltelli_sensitivity.py --analyze-existing
```

This **runs no simulations**. It recomputes the indices from the committed
result files, which already hold all 30 720 model evaluations.

**Design.** `calc_second_order=False`, so the Saltelli sample is
*N* × (*D* + 2) = 1024 × 10 = **10 240 evaluations per K**, 30 720 in total. The
full second-order formula *N* × (2*D* + 2) does **not** apply here — it would
imply a base sample of 568.9, which is not an integer, and that is the check the
loader performs before analysing anything.

**Validation on load.** Every parameter and outcome column must be present; the
row count must imply an integer base sample; and the parameter columns must
reproduce `saltelli.sample(PROBLEM, N, calc_second_order=False)` to within
1e-9. That last check matters because the Sobol estimator reads the rows
positionally — a re-sorted file would produce plausible-looking nonsense.

**Determinism.** Confidence intervals come from a bootstrap seeded with
`CONF_SEED = 20020422`, so repeated runs are byte-identical.

The plots and this table are built from the same `Si` objects, so their numbers
cannot diverge.

---

## `robustness_panel_{A,B,C,D,E,F}.csv`

Appendix-facing summaries of the protocol robustness checks. One table per
panel rather than a shared schema — the panels report genuinely different
quantities, and a common schema would obscure all of them.

| Panel | Varied condition | Fixed regime | Reps | Central statistic |
|---|---|---|---|---|
| A | *N* ∈ {250, 500, 1000, 2000, 5000} | *K* = 6, 4 width regimes | 30 | SE of ΔCENP |
| B | — (convergence timing) | *K* = 6, 4 width regimes, *N* = 500 | 20 | median / p95 convergence iteration, count hitting the ceiling |
| C | ε<sub>s</sub> ∈ {10⁻⁶ … 10⁻¹} | 4 configs | 10 | mean ΔCENP ± SD |
| D | ξ ∈ [−0.75, 0.75], 9 values | *K* = 6, θ = 1 | 20 | mean sincere and final ENP ± SE |
| E | θ ∈ {0.3 … 3.0} | analytic, *K* = 8 | — | transformed share per party, ΔENP |
| F | μ ∈ {0 … 1}, 8 values | *K* = 8, τ̂ = 1.75, 2 width regimes | 30 | mean conditional switching ± SE |
| G | ceiling *T* = 25 vs 60 | *K* = 6, 3 width regimes, *N* = 500 | 20 | outcome drift ÷ between-seed SD |

**Panel G** exists because panel B shows the diffuse regime (*c* = 2.5) never
reaches a fixed point: 70 % of runs are still moving at the ceiling. Since the
main analyses and the Saltelli design both cap at *T*<sub>max</sub> = 25 and both
sweep *c* up to 3.0, panel G measures whether that truncation reaches the
*reported outcomes* — a different question from whether individual vote
intentions have settled. `drift_over_sd` is the headline: mean absolute drift
between *T* = 25 and *T* = 60, divided by the between-seed SD, which is the
dispersion the Sobol analysis already integrates over.

Result, in short: at high width a **single run's** outcome moves by more than the
seed-to-seed SD (`drift_over_sd` ≈ 1.2–1.4 at *c* = 2.5), but the **mean across
seeds** barely moves — 0.3 % for ΔCENP, 0.04 % for final ENP. The trajectory
oscillates around a stable centre rather than still trending toward one. So
aggregate results are robust to the ceiling; individual trajectories are not.

Each table carries the varied condition, the fixed regime, the repetition count
and the dispersion statistic, so every plotted point can be reconstructed from
its row.

```bash
python analysis/synthetic/robustness_checks.py              # all panels
python analysis/synthetic/robustness_checks.py --panels A B # selected panels
```

Panel E is analytic and runs no simulation; panels A–D and F require roughly
1 540 model runs (~2–4 minutes). The detailed `panel_*_raw.csv` files are
written to `analysis/synthetic/outputs/robustness_checks/` and stay ignored.

The tables call the same aggregation functions as the plots
(`_agg_N_robustness`, `_build_tmax_summary`, `_agg_xi`), so a table row and its
plotted point are computed once, not twice.

---

## `lhs_parameter_importance.csv`

Exploratory parameter importance for ΔCENP under the empirical structure,
from a RandomForest surrogate fitted to the behavioural sweeps.

| | |
|---|---|
| **Columns** | `scope, parameter, permutation_importance, importance_std, relative_importance_pct, standardized_coefficient, cv_r2_mean, cv_r2_std, n_rows, seed` |
| **Scopes** | `pooled`, `2002`, `2022` |
| **Inputs** | `data/behavioral_sweep_{2002,2022}.csv` (generated, ignored) |
| **Reproduce** | `python analysis/empirical/lhs_importance.py` |

`cv_r2_mean` qualifies everything else in the row: a surrogate that cannot
predict the outcome produces importances that mean nothing. The script warns
below 0.1. `standardized_coefficient` is an independent linear-model check on the
forest's ranking. `relative_importance_pct` uses the same helper as the slide
figure (negatives clipped to zero, then scaled to 100 within each scope).

> ⚠️ **Not yet generated.** The behavioural sweeps currently on disk were
> produced before the τ̂ unit fix (#6), so any importance table built from them
> would be stale. The export is implemented and tested; the table will be
> generated once the corrected sweeps have been run.

---

## Regenerating everything that does not need a simulation

```bash
python analysis/synthetic/saltelli_sensitivity.py --analyze-existing
```

That is the only table reproducible from committed inputs alone. The others need
their experiments run first.
