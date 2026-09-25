<h1 align="center">Experiments</h1>

<p align="center">
What was run, with which parameters and seeds, and where the data come from.
</p>

<p align="center"><sub>
<a href="validation.md">← Validation</a> · <strong>Experiments</strong> · <a href="reproducibility.md">Reproducibility →</a>
</sub></p>

## Two sets of experiments

The **synthetic** experiments ask which parameters drive coordination, on imagined electorates. The **empirical**
experiments ask whether the same decision rule reproduces the contrast between France 2002 and 2022. The two share
the model in [`core_model/`](../core_model/README.md) and nothing else.

| Experiment | Mode | Script | Simulations |
|---|---|---|---|
| Global sensitivity (Sobol) | synthetic | `saltelli_sensitivity.py` | 30 720 |
| Protocol robustness, panels A–G | synthetic | `robustness_checks.py` | ~1 540 |
| Horizon and population checks | synthetic | `protocol_validation.py` | varies |
| Seed-noise decomposition | synthetic | `protocol_posthoc.py` | none, uses earlier runs |
| Replay of 2002 and 2022, 4 ways of starting | empirical | `empirical_2002_2022.py` | 6 000 |
| Robustness of the replay, 4 variants | empirical | `empirical_2002_2022.py` | 800 |
| Who is triggered, and who switches | empirical | `empirical_diagnostics.py` | none, uses earlier runs |
| Behavioural ΔCENP sweep | empirical | `behavioral_sweep.py` | 8 000 |
| 2002 against 2022, significance test | empirical | `behavioral_compare.py` | none, uses earlier runs |
| Which parameters matter in the replay | empirical | `lhs_importance.py` | none, uses earlier runs |

## What is varied

The synthetic experiments vary eight parameters at once, across electorates of 6, 8 and 9 candidates, so that each
parameter's effect can be separated from the others'. The empirical experiments vary only the five parameters that
describe voters: how many candidates they tolerate (τ̂), how attached they are to their favourite (μ), how much they
trust their own beliefs over the poll (α and ρ<sub>π</sub>), and, when favourites are drawn, how much closeness
counts (β). The candidates, the voters and the polls stay those of the real election.

<details>
<summary><strong>Synthetic: the 8 parameters of the Saltelli design</strong></summary>

<br>

| Parameter | Range | Meaning |
|---|---|---|
| `tau_hat` | [0.5, 3.0] | tolerance, in zones |
| `c` | [0.25, 3.0] | how spread out the electorate is |
| `theta` | [0.3, 3.0] | poll temperature |
| `rho_s` | [10, 200] | poll precision |
| `rho_pi` | [5, 200] | prior precision |
| `alpha` | [0, 0.9] | weight on the prior |
| `mu` | [0, 1.0] | cost of leaving the favourite |
| `epsilon` | [0.05, 0.5] | electorate **floor weight** ε<sub>F</sub> |

`epsilon` here is the floor weight of the electorate, ε<sub>F</sub>, not the poll floor ε<sub>s</sub>. They are
different parameters with similar names. ε<sub>s</sub> is fixed at 1e-12 and is not part of the design.

The design is run separately for *K* ∈ {6, 8, 9}, to separate the effect of an odd or even number of candidates.

</details>

<details>
<summary><strong>Empirical: the replay and the behavioural sweep</strong></summary>

<br>

**Replay.**

| Parameter | Range | Notes |
|---|---|---|
| `tau_hat` | [0.5, 3.0] | τ = τ̂·(2/*K*), so **at most 0.400** in 2002 and **0.500** in 2022 |
| `rho_pi` | [5, 200] | |
| `alpha` | [0, 0.9] | |
| `mu` | [0, 1.0] | |
| `beta` | [0, 20] | only when favourites are drawn |

**Behavioural sweep.** The same five parameters (`tau_hat, mu, alpha, rho_pi, beta`), sampled by Latin hypercube,
1 000 draws × 4 repeats per year.

The poll precision ρ<sub>s</sub> is left out on purpose. The empirical poll is read rather than generated, so its
precision has no effect, and including it would only manufacture a null result.

</details>

## What is held fixed

In the empirical mode, one setting of the voter parameters is applied to both years. Only the environment changes
between them, and nothing is fitted to either election. The aim is to see whether the rule produces the pattern of
2002 against 2022, rather than to recover parameter values.

<details>
<summary><strong>Fixed values, and what justifies them</strong></summary>

<br>

| Held fixed in the empirical mode | Value |
|---|---|
| Candidate positions | survey placements of the real candidates (0–10), mapped to [−1, 1] |
| Electorate | *N* = 2000, sampled from the survey self-placements |
| Polls | the real weekly means, read as they are |
| *K*<sub>runoff</sub> | 2 |
| *T*<sub>max</sub> | the number of polls |
| θ, ρ<sub>s</sub>, ε<sub>s</sub>, ξ, *c*, ε<sub>F</sub> | no effect; see [why](model.md#which-parameters-do-nothing-in-the-empirical-mode) |

| Set by the protocol panels | Value | Justified by |
|---|---|---|
| *N* | 2000 | panel A |
| *T*<sub>max</sub> | 25 (synthetic) | panels B and G |
| ε<sub>s</sub> | 1e-12 | panel C (locally) and `test_signal_epsilon.py` |
| ξ | 0 | panel D |

</details>

<details>
<summary><strong>Seeds</strong></summary>

<br>

| Purpose | Seed |
|---|---|
| Empirical design | `20020422` |
| Behavioural sweep | `20020422` |
| Surrogate and importance (`lhs_importance.py`) | `42` |
| Voter sampling | `MASTER_SEED * 7919 + year` |
| Each run in a sweep | `seed + 1000 * (draw + 1) + repeat` |

The importance seed is 42, not `20020422`. The latter belongs to the design of the sweep, not to the surrogate fitted
on it.

Each run's seed depends only on `(seed, draw, repeat)`, which is what lets an interrupted sweep
[resume to identical output](validation.md#the-pipeline).

</details>

## How much was run

The current empirical results come from the run of 2026-09-24:

| Stage | Runs | Time |
|---|---|---|
| Replay, nearest candidate (300 draws × 2 years, plus 100 × 4 robustness variants × 2 years) | 1 400 | 11 min 40 |
| Replay, 3 ways of drawing favourites (800 × 2 each) | 4 800 | 20 min 21 |
| Behavioural sweeps (1 000 × 4 × 2 years) | 8 000 | 1 h 58 |
| Tables, figures, tests | 0 | ~1 min 30 |
| **Total** | **14 200** | **2 h 32** |

The run of 2026-08-21 did 14 000 simulations (three robustness variants) in 4 h 07. Every stage of the later run
passed its row-count checks, so no work was skipped; why it ran faster was not measured. Full record:
[2026-09-24](reports/empirical_rerun_2026-09-24.md).

<details>
<summary><strong>Synthetic counts</strong></summary>

<br>

| Experiment | Evaluations |
|---|---|
| Saltelli, per *K* | 10 240 |
| Saltelli, total | 30 720 |
| Robustness panels A–D, F | ~1 540 |
| Panel E | 0 (analytic) |

</details>

## Pipeline order

Stages 1 to 3 run the simulations; stages 4 to 8 only read their output.

```
1  empirical_2002_2022.py --overwrite                    ← replay, nearest candidate
2  empirical_2002_2022.py --sincere-init probabilistic … ← 3 ways of drawing favourites
3  behavioral_sweep.py --year {2002,2022} …              ← the long one
   ── checked after each stage: tools/validate_rerun.py
4  empirical_diagnostics.py [--tag …]                    ← needs 1, 2
5  empirical_figures.py                                  ← needs 1, 2
6  behavioral_compare.py ; behavioral_sweep_figure.py    ← needs 3
7  lhs_importance.py                                     ← needs 3
8  make_empirical_tables.py ; pytest -ra                 ← needs all
```

<details>
<summary><strong>Quick runs and full runs</strong></summary>

<br>

| | Quick | Full |
|---|---|---|
| Flag | `--quick` | default |
| Draws | 15 | 300 / 800 |
| Output folder | **`data/smoke/`** | `data/` |
| Can it overwrite a full run? | **No, by construction** | only with `--overwrite` |

Quick runs write to a *separate folder* rather than to differently named files in the same one. That makes the
dangerous case impossible rather than merely discouraged.
[Validation → The pipeline](validation.md#the-pipeline) records the incident that led to it.

</details>

<details>
<summary><strong>Resuming and overwriting</strong></summary>

<br>

| Situation | What to do |
|---|---|
| A replay stage failed | restart it with `--overwrite`. It cannot resume, and each call rewrites from the start. |
| A sweep was interrupted | use `--resume`, never `--overwrite`, which discards every completed draw |
| The target files already exist | the run refuses unless `--overwrite` is passed |
| Both flags are passed | the command refuses, because they exclude each other |

`--resume` checks the year, seed, `n_draws`, `n_repeats`, schema version and a SHA-256 fingerprint of the design
before continuing. If it refuses, the partial file does not belong to that experiment; move it aside rather than
forcing it.

</details>

<details>
<summary><strong>Where the outputs go</strong></summary>

<br>

| Path | Committed? | Contents |
|---|---|---|
| `results/tables/` | yes, 23 CSVs | small derived tables, the numbers to cite |
| `data/*.csv` (inputs) | yes | real election data, candidate positions, polls |
| `data/saltelli_results_K*.csv` | yes | raw Sobol matrices, so the indices rebuild |
| `data/empirical_*`, `data/behavioral_*` | no | raw simulation output, bulky and regenerable |
| `data/smoke/`, `data/archive/` | no | quick runs and dated archives |
| `figures/` | no | 108 generated PNG and PDF files |
| `logs/` | no | the logs of each run |
| `analysis/**/outputs/` | no | intermediate panel CSVs |

</details>

## Figures

No results figure is committed, and none is linked from the documentation. `figures/` is git-ignored in full (108
files at last count). Figures are bulky, they regenerate from the scripts, and a stale image is harder to notice than
a stale number, so every quantity a reader needs is in a [result table](../results/README.md) instead, where it can be
compared line by line. The one committed image in these pages, the diagram of a round on the
[model page](model.md#one-round), explains the model rather than reporting a result.

<details>
<summary><strong>What is in <code>figures/</code> today</strong></summary>

<br>

`figures/` currently holds a mix of current images and images from before the tolerance fix: 32 files named
`*_main_prob_*`, plus `lhs_importance_by_year_slide.png`, which needs `--slide` and so was not regenerated by the
rerun. They do no harm because nothing refers to them. Regenerate what you need locally, and do not treat anything
in `figures/` as authoritative.

</details>

## Data sources

| Input | 2002 | 2022 |
|---|---|---|
| Polls, `polls_{year}.csv` | Wikipedia poll list, [revision 236399441](https://fr.wikipedia.org/w/index.php?oldid=236399441): sections *Avril* and *Mars*, 39 polls, 1 March–18 April | Wikipedia poll list, [revision 235575713](https://fr.wikipedia.org/w/index.php?oldid=235575713): section *Sondages réalisés après la publication de la liste officielle des candidats*, 81 polls, 8 March–8 April |
| Voters, `voters_ideology_{year}.csv` | CSES Module 2 self-placement, weighted | CSES Module 6 self-placement |
| Candidates, `party_positions_{year}.csv` | CSES candidate placements, screened means; 6 imputed | Ipsos–CEVIPOF wave 9 means, all 12 |
| Results, `results_{year}.csv` | Ministère de l'Intérieur | Ministère de l'Intérieur |

How the positions and electorates were built, and their limits: [`data/cses/README.md`](../data/cses/README.md) and
[`data/ipsos/README.md`](../data/ipsos/README.md). The inputs they replaced are described in
[`data/previous_inputs/README.md`](../data/previous_inputs/README.md).

<details>
<summary><strong>How the poll files are built</strong></summary>

<br>

Both files are built by `tools/build_polls_from_wikipedia.py` from the fixed revisions above, which it caches and
checks, so rerunning it gives the same files. Each column is matched to a candidate by the party code in its header,
never by position.

The window is the one the page defines: in 2022, the polls after the official list of candidates (7 March); in 2002,
the March and April tables. Candidates not in the model are dropped: Gluckstein (POI) in 2002, and Pasqua (RPF), who
withdrew and appears in the March polls only. Each poll is renormalized by the loader.

Two 2002 Ifop polls that did not offer every modelled candidate are dropped rather than given a 0
(`data/polls_dropped.csv`). Four 2022 values published only as below a threshold ("<1 %") are set to half the
threshold and flagged in `below_threshold`. `tests/test_polls.py` checks values against the page, by candidate name.

The hand-copied files these replaced had LO/NPA and EELV/PS swapped in every 2022 poll. They are kept in
`data/previous_inputs/`, and every empirical result up to the 2026-08-21 run used them.

</details>

<details>
<summary><strong>The files behind the explanatory figures</strong></summary>

<br>

**`FR-electoral_data.csv`** holds party-level poll shares before the election and first-round results for five
French presidential elections. Parties are ordered on the left-right axis following the classification in Ipsos
post-election reports.

| Year | Poll source | Results |
|------|-------------|---------|
| 2002 | Ipsos barometer wave 5 (Ipsos for *Le Figaro* / Europe 1), 15–16 March 2002, *n* = 919 | Ministère de l'Intérieur (2002) |
| 2007 | Ipsos survey (Ipsos for Dell / SFR / *Le Point*), 22–24 March 2007, *n* = 1 245 | Ministère de l'Intérieur (2007) |
| 2012 | n/a | Ministère de l'Intérieur (2012) |
| 2017 | n/a | Ministère de l'Intérieur (2017) |
| 2022 | Ipsos / CEVIPOF / *Le Monde* / Fondation Jean Jaurès wave 5, 3–7 February 2022, *n* = 12 499 | Ministère de l'Intérieur (2022) |

Gluckstein (POI, 2002) is left out of the 2002 data: he had not announced his candidacy at the time of the survey,
and obtained 0.47% in the first round.

**`FR-vote_transfers.csv`** holds estimated second-round vote transfers for 2002 and 2022. The left-hand nodes are
sized by the official first-round shares, and the right-hand nodes by the official second-round shares, both from
the Ministère de l'Intérieur. The flows come from Ipsos post-election transfer estimates, renormalized over the two
finalists, with abstention, blank and null votes left out.

| Year | Transfer estimates | Notes |
|------|-------------------|-------|
| 2002 | Ipsos post-election telephone survey, 5 May 2002, *n* = 2 886 (Ipsos for Vizzavi / *Le Figaro* / France 2 / Europe 1 / *Le Point*) | All first-round electorates included |
| 2022 | Ipsos / Sopra Steria post-election survey, 21–23 April 2022, *n* = 4 000, combining survey data with transfer analysis across 500 polling stations | Six electorates only: Mélenchon, Jadot, Macron, Pécresse, Le Pen, Zemmour |

</details>

## Run history

**2026-09-24, current.** Survey-based positions and electorates, polls rebuilt from fixed Wikipedia revisions, and
four robustness variants: 14 200 simulations, 33 of 33 stages OK, 648 tests passed. Record:
[2026-09-24](reports/empirical_rerun_2026-09-24.md).

**2026-08-21, superseded.** The first run after the tolerance fix. Before it, the conversion from τ̂ to τ was missing
on the empirical side, so the tolerance was up to 7.5 times too large and voters almost never switched (see
[the model](model.md#how-much-a-voter-tolerates)). Its 2022 polls had two pairs of candidates swapped. Record:
[2026-08-21](reports/empirical_rerun_2026-08-21.md).

<details>
<summary><strong>The 2026-08-21 run in detail</strong></summary>

<br>

| | |
|---|---|
| Commit | `0bba146cd2a1aeaedc2af1f7b84777603a80ddd9` |
| Branch | `pre-rerun-safety` |
| Started / finished | 13:04:02 → 17:11:13 local (4 h 07) |
| Stages | **30 / 30 OK**, no failures |
| Simulations | **14 000**, all accounted for |
| Checks | `tau_absolute = tau_hat × 2/K` to 1e-12 in all 14 files; zero `tau ≥ 2` warnings in 30 simulation logs |
| Test suite at the time | 481 passed, 2 skipped |

The raw outputs from before the fix were not archived for the nearest-candidate replay. A 15-draw `--quick` run
overwrote them on 2026-08-19, and they had never been committed. The comparison before and after the fix is
therefore direct for the sweeps, the ways of drawing favourites and the diagnostics. For the nearest-candidate replay,
a baseline would have to be regenerated from the commit before the fix (`70e23f5`); the fixed seed makes that
possible, but it has not been done.

Operating instructions for that run are in [`local_rerun_runbook.md`](notes/local_rerun_runbook.md).

</details>

---

<p align="center"><sub>
<a href="validation.md">← Validation</a> · <strong>Experiments</strong> · <a href="reproducibility.md">Reproducibility →</a>
</sub></p>
