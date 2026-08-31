# Experiments

[← Validation](validation.md) · **Experiments** · [Reproducibility →](reproducibility.md)

- [Experiment map](#experiment-map)
- [Parameter spaces](#parameter-spaces)
- [Fixed vs swept](#fixed-versus-swept)
- [Seeds](#seeds)
- [Simulation counts](#simulation-counts)
- [Figures](#figures)
- [Data sources](#data-sources)
- [The 2026-08-21 rerun](#the-2026-08-21-empirical-rerun)

---

## Experiment map

| | Experiment | Mode | Script | Simulations |
|---|---|---|---|---|
| **B** | Global sensitivity (Sobol) | synthetic | `saltelli_sensitivity.py` | 30 720 |
| **C** | Protocol robustness, panels A-G | synthetic | `robustness_checks.py` | ~1 540 |
| n/a | Horizon / population validation | synthetic | `protocol_validation.py` | varies |
| n/a | Stochastic-noise decomposition | synthetic | `protocol_posthoc.py` | post-hoc |
| **D** | Empirical replay, 4 specifications | empirical | `empirical_2002_2022.py` | 6 000 |
| **E** | Empirical robustness, 3 variants | empirical | `empirical_2002_2022.py` | 600 |
| **G** | Activation diagnostics | empirical | `empirical_diagnostics.py` | 0 (post-hoc) |
| **H** | Behavioural ΔCENP sweep | empirical | `behavioral_sweep.py` | 8 000 |
| **I** | 2002 vs 2022 significance test | empirical | `behavioral_compare.py` | 0 (post-hoc) |
| **J** | LHS parameter importance | empirical | `lhs_importance.py` | 0 (post-hoc) |

Synthetic experiments answer *which parameters drive coordination*. Empirical
experiments answer *does the rule reproduce the 2002/2022 contrast*. They share
`core_model/` and nothing else.

---

## Parameter spaces

### Synthetic: Saltelli design (8 parameters)

| Parameter | Bounds | Meaning |
|---|---|---|
| `tau_hat` | [0.5, 3.0] | normalised tolerance |
| `c` | [0.25, 3.0] | electorate width factor |
| `theta` | [0.3, 3.0] | signal temperature |
| `rho_s` | [10, 200] | signal precision |
| `rho_pi` | [5, 200] | prior precision |
| `alpha` | [0, 0.9] | prior weight |
| `mu` | [0, 1.0] | expressive cost |
| `epsilon` | [0.05, 0.5] | electorate **floor weight** ε<sub>F</sub> |

> ⚠️ `epsilon` here is the electorate floor weight ε<sub>F</sub>, and not the
> signal offset ε<sub>s</sub>. They are different parameters with similar names.
> ε<sub>s</sub> is fixed at 1e-12 and is not in the Saltelli problem.

Run separately for *K* ∈ {6, 8, 9} to separate odd/even geometry.

### Empirical: replay design

| Parameter | Bounds | Notes |
|---|---|---|
| `tau_hat` | [0.5, 3.0] | → τ = τ̂·(2/K), so **≤ 0.400** in 2002 and **≤ 0.500** in 2022 |
| `rho_pi` | [5, 200] | |
| `alpha` | [0, 0.9] | |
| `mu` | [0, 1.0] | |
| `beta` | [0, 20] | probabilistic initialization only |

### Empirical: behavioural sweep

Same five parameters (`tau_hat, mu, alpha, rho_pi, beta`), Latin-hypercube
sampled, 1 000 draws × 4 repeats per year.

> **ρ<sub>s</sub> is deliberately excluded as a placebo dimension.** The
> empirical signal is exogenous, so signal precision has nothing to do.
> Including it would manufacture a null result rather than measure one.

---

## Fixed versus swept

| Held fixed in empirical mode | Value |
|---|---|
| Party positions | real, coded on [−1, 1] |
| Electorate | *N* = 2000 sampled from the real ideology histogram |
| Signal timeline | real weekly-mean polls (exogenous) |
| *K*<sub>runoff</sub> | 2 |
| *T*<sub>max</sub> | length of the poll sequence |
| θ, ρ<sub>s</sub>, ε<sub>s</sub>, ξ, *c*, ε<sub>F</sub> | inert; see [why](model.md#which-parameters-are-inactive-in-empirical-replay) |

| Fixed by the protocol panels | Value | Justified by |
|---|---|---|
| *N* | 2000 | Panel A |
| *T*<sub>max</sub> | 25 (synthetic) | Panels B + G |
| ε<sub>s</sub> | 1e-12 | Panel C (locally) + `test_signal_epsilon.py` |
| ξ | 0 | Panel D |

The defining design decision of the empirical mode is *pattern-oriented
calibration rather than parameter recovery*. One behavioural draw is applied to
both years, only the environment changes between them, and no parameter is
fitted.

---

## Seeds

| Purpose | Seed |
|---|---|
| Empirical design master seed | `20020422` |
| Behavioural sweep | `20020422` |
| Surrogate / importance (`lhs_importance.py`) | `42` |
| Voter sampling | `MASTER_SEED * 7919 + year` |
| Per-run in sweeps | `seed + 1000 * (draw + 1) + repeat` |

> The importance seed is 42, not `20020422`. The latter is the *design* seed and
> belongs to the sweep rather than to the surrogate.

The per-run formula depends only on `(seed, draw, repeat)`, which is what makes
[resume equivalence](validation.md#9--resume-equivalence) hold.

---

## Simulation counts

### Empirical rerun (2026-08-21)

| Stage | Runs | Wall time |
|---|---|---|
| Replay, `nearest` (300 draws × 2 years + robustness) | 1 200 | ~30 min |
| Replay, 3 probabilistic variants (800 × 2 each) | 4 800 | ~39 min |
| Behavioural sweeps (1 000 × 4 × 2 years) | 8 000 | ~2 h 57 |
| Downstream tables and figures | 0 | ~3 min |
| **Total** | **14 000** | **4 h 07** |

### Synthetic

| Experiment | Evaluations |
|---|---|
| Saltelli, per *K* | 10 240 |
| Saltelli, total | 30 720 |
| Robustness panels A-D, F | ~1 540 |
| Panel E | 0 (analytic) |

---

## Quick versus full mode

| | Quick / smoke | Full |
|---|---|---|
| Flag | `--quick` | default |
| Draws | 15 | 300 / 800 |
| Output directory | **`data/smoke/`** | `data/` |
| Can overwrite full output? | **No, structurally impossible** | only with `--overwrite` |

> Quick mode writes to a *separate directory* rather than to differently-named
> files in the same one. That is deliberate, because it makes the dangerous case
> unrepresentable instead of merely discouraged. See
> [family 8](validation.md#8--output-isolation-and-overwrite-protection) for the
> incident that motivated it.

---

## Output locations

| Path | Committed? | Contents |
|---|---|---|
| `results/tables/` | ✅ yes, 22 CSVs (7 new in this branch) | compact derived tables, the citable artefacts |
| `data/*.csv` (inputs) | ✅ yes | real election data, party positions, polls |
| `data/saltelli_results_K*.csv` | ✅ yes | raw Sobol matrices, so indices regenerate |
| `data/empirical_*`, `data/behavioral_*` | ❌ ignored | raw simulation output, bulky and regenerable |
| `data/smoke/`, `data/archive/` | ❌ ignored | smoke runs and point-in-time evidence archives |
| `figures/` | ❌ ignored | 108 generated PNG/PDF files |
| `logs/` | ❌ ignored | per-run driver logs |
| `analysis/**/outputs/` | ❌ ignored | intermediate panel CSVs |

---

## Pipeline order

Stages 1 to 3 are the simulation; 4 to 8 run no simulation at all.

```
1  empirical_2002_2022.py --overwrite                    ← replay, nearest
2  empirical_2002_2022.py --sincere-init probabilistic … ← 3 variants
3  behavioral_sweep.py --year {2002,2022} …              ← the long one
   ── validation after each stage: tools/validate_rerun.py
4  empirical_diagnostics.py [--tag …]                    ← needs 1, 2
5  empirical_figures.py                                  ← needs 1, 2
6  behavioral_compare.py ; behavioral_sweep_figure.py    ← needs 3
7  lhs_importance.py                                     ← needs 3
8  make_empirical_tables.py ; pytest -ra                 ← needs all
```

---

## Resume and overwrite rules

| Situation | Correct action |
|---|---|
| Replay stage failed | restart with `--overwrite`. It has no resume, and each invocation rewrites from the start. |
| Sweep interrupted | use `--resume`. Never `--overwrite`, which discards every completed draw. |
| Target files already exist | the run refuses unless `--overwrite` is passed |
| Both flags passed | the CLI refuses, because they are mutually exclusive |

`--resume` validates year, seed, `n_draws`, `n_repeats`, schema version and a
SHA-256 fingerprint of the design before continuing. If it refuses, the partial
file does not belong to that experiment; move it aside rather than forcing it.

---

## Figures

No figure is committed to this repository, and none is linked from the
documentation. `figures/` is git-ignored in full (108 files at last count).

The reasoning is the same as for raw simulation output: figures are bulky, they
regenerate from the scripts, and a stale image is harder to detect than a stale
number. Every quantity a reader needs is in a
[result table](../results/README.md) instead, where it can be diffed.

This has a practical consequence worth stating. `figures/` currently holds a
mixture of current and pre-fix images: 32 files named `*_main_prob_*` from
before the tolerance correction, plus `lhs_importance_by_year_slide.png`, which
requires `--slide` and was therefore not regenerated by the rerun. They are
harmless precisely because nothing references them. Regenerate what you need
locally, and do not treat anything in `figures/` as authoritative.

---

## Data sources

### `FR-electoral_data.csv`

Party-level pre-electoral poll shares and first-round results for five French
presidential elections. Parties are ordered ideologically following the
classification used in Ipsos post-election reports.

| Year | Poll source | Electoral results |
|------|-------------|-------------------|
| 2002 | Ipsos barometer wave 5 (Ipsos for *Le Figaro* / Europe 1), 15-16 March 2002, *n* = 919 | Ministère de l'Intérieur (2002) |
| 2007 | Ipsos survey (Ipsos for Dell / SFR / *Le Point*), 22-24 March 2007, *n* = 1 245 | Ministère de l'Intérieur (2007) |
| 2012 | n/a | Ministère de l'Intérieur (2012) |
| 2017 | n/a | Ministère de l'Intérieur (2017) |
| 2022 | Ipsos / CEVIPOF / *Le Monde* / Fondation Jean Jaurès wave 5, 3-7 February 2022, *n* = 12 499 | Ministère de l'Intérieur (2022) |

Note: candidate Gluckstein (POI, 2002) is excluded from the 2002 data as he
had not announced his candidacy at the time of the pre-electoral survey and
obtained a negligible first-round score (0.47 %).

### `FR-vote_transfers.csv`

Estimated second-round vote transfer rates for 2002 and 2022. Left-side node
sizes are based on official first-round shares; right-side node sizes on
official second-round shares (both from *Ministère de l'Intérieur*). Flows are
constructed from Ipsos post-election transfer estimates, renormalised over the
two second-round finalists (abstention, blank, and null votes excluded).

| Year | Transfer estimates | Notes |
|------|-------------------|-------|
| 2002 | Ipsos post-election telephone survey, 5 May 2002, *n* = 2 886 (Ipsos for Vizzavi / *Le Figaro* / France 2 / Europe 1 / *Le Point*) | All first-round electorates included |
| 2022 | Ipsos / Sopra Steria post-election survey, 21-23 April 2022, *n* = 4 000, combining survey data with transfer analysis across 500 polling stations | Available for six electorates only: Mélenchon, Jadot, Macron, Pécresse, Le Pen, Zemmour |

---

## The 2026-08-21 empirical rerun

| | |
|---|---|
| Commit | `0bba146cd2a1aeaedc2af1f7b84777603a80ddd9` |
| Branch | `pre-rerun-safety` |
| Started / finished | 13:04:02 → 17:11:13 local (4 h 07) |
| Stages | **30 / 30 OK**, no failures |
| Simulations | **14 000**, all accounted for |
| Validation | `tau_absolute = tau_hat × 2/K` to 1e-12 in all 14 files; zero `tau ≥ 2` warnings in 30 simulation logs |
| Test suite at run time | 481 passed, 2 skipped |

Why it was needed: the τ̂ to τ conversion was missing on the empirical side, so
the effective tolerance was up to 7.5× too large and the strategic module was
largely inert. See [Tolerance](model.md#tolerance-the-two-units).

> **Pre-fix raw outputs for the `nearest` specification were not archived.**
> They were overwritten on 2026-08-19 by a 15-draw `--quick` run and had never
> been committed. Before/after comparison is therefore direct for the sweeps,
> the probabilistic variants and the diagnostics. For `nearest` a baseline would
> have to be regenerated from the pre-fix commit (`70e23f5`), which the fixed
> seed makes possible but which has not been done.

The full record, covering protocol, validation status, generated outputs and
known limitations, is in **[Empirical rerun record,
2026-08-21](reports/empirical_rerun_2026-08-21.md)**. Operating instructions are
in [`local_rerun_runbook.md`](local_rerun_runbook.md).

---

[← Validation](validation.md) · **Experiments** · [Reproducibility →](reproducibility.md)
