# Strategic Voting in Two-Round Elections — Agent-Based Model

An agent-based model of strategic coordination in two-round elections,
using the French presidential system as its main empirical reference.

> Clara Salas — M2 Thesis, ENS-PSL / Centre Borelli (CHArtS), 2025-2026.

---

## Overview

The model represents an electoral campaign as a feedback loop between public
signals and vote intentions. Voters are boundedly cognitive agents who rely on
poll-like signals to assess candidate viability and decide whether to vote
sincerely or strategically. Coordination (i.e., the concentration of votes around
fewer candidates) emerges from individual responses to perceived viability
rather than being imposed at the aggregate level.

The framework is applied to the French two-round presidential system (M = 2
qualifiers) and uses the Effective Number of Parties (ENP) and cliff statistics
to measure coordination gains (ΔCENP).

**Main findings from the baseline characterisation:**

- Strategic pressure is governed by electorate width *c* and tolerance
  threshold *τ̂* — not by the informational environment.
- Among triggered voters, the expressive cost parameter *μ* is the dominant
  driver of behavioural switching.
- The signal–vote feedback loop produces path-dependent dynamics rather than
  monotonic convergence; coordination becomes more volatile at high electorate
  width.

---

## Requirements

Python 3.10 or later. Install all dependencies with:

```bash
pip install -r requirements.txt
```

| Package | Purpose |
|---------|---------|
| `numpy >= 1.24` | Core numerics |
| `scipy >= 1.10` | Skew-normal sampling, sensitivity helpers |
| `matplotlib >= 3.7` | All figures |
| `pandas >= 2.0` | Data loading and aggregation |
| `SALib >= 1.4` | Saltelli sampling and Sobol analysis |
| `Pillow >= 9.0` | *(optional)* combined 2×2 figure grids |

---

## Quick start

```python
from model import run_simulation

result = run_simulation(
    K=8,                         # number of parties
    n_modes=1,                   # unimodal electorate
    width_factor=1.5,            # c: electorate width
    theta=1.0,                   # signal temperature (neutral)
    rho=100.0,                   # signal precision
    rho_pi=100.0,                # prior precision
    n_electors=2000,
    tau=1.75 * (2.0 / 8),       # τ̂ = 1.75, converted to absolute units
    mu=0.1,                      # expressive cost weight
    alpha_prior=0.0,             # full signal reliance
    K_runoff=2,                  # French two-round rule
    max_iterations=25,
    seed=42,
    verbose=True,
)

sincere = result["sincere_shares"]
final   = result["final_shares"]
print(f"Switching rate : {result['switching']['pct_strategic']:.1%}")
print(f"Winner (R1)   : Party {result['winner_id']}")
```

Diagnostics and per-voter calibration data are available via
`collect_diagnostics=True` and `collect_mu_calibration=True`; see the
`run_simulation` docstring for the full return-dict specification.

---

## Repository structure

```
strategic-voting-abm-2RS/
│
├── core_model/
│   ├── agents.py               Party and Elector agent classes;
│   │                           four-step decision pipeline
│   ├── environment.py          Equal-zone ideological space;
│   │                           unimodal voter distributions
│   ├── functions.py            Voter placement, vote counting,
│   │                           coordination outcome measures
│   ├── signals.py              Temperature-transformed Dirichlet
│   │                           poll signal generation
│   ├── model.py                Main simulation loop (run_simulation)
│   ├── metrics.py              Shared coordination metrics (ENP, CENP, ΔCENP)
│   ├── empirical_data.py       Loaders for the fixed 2002/2022 inputs
│   │                           (party positions, electorate, poll timeline)
│   └── empirical_outcomes.py   Per-run outcome and initialization benchmarks
│                               for the empirical replay
│
├── analysis/
│   ├── synthetic/              Abstract model on random inputs
│   │   ├── saltelli_sensitivity.py Global Sobol sensitivity across
│   │   │                           K ∈ {6, 8, 9}  (~55 000 runs)
│   │   ├── robustness_checks.py    Protocol checks: N, Tmax, εs, ξ (A–D);
│   │   │                           signal mechanism (E); μ sweep (F)
│   │   └── main_results.py         Four main paper figures: heatmap, c-sweep,
│   │                               trajectory, empirical comparison
│   └── empirical/             Real party positions, electorate & polls held fixed
│       ├── empirical_2002_2022.py  2002/2022 replay pipeline (runs + robustness)
│       ├── empirical_diagnostics.py Diagnostic tables per year
│       ├── empirical_figures.py     Figures from the replay outputs
│       ├── empirical_beta_bins.py   Outcome by β bin
│       ├── behavioral_targets.py    Observed ΔCENP target per year
│       ├── behavioral_sweep.py      Behavioral-parameter sweep (fixed structure)
│       ├── behavioral_sweep_figure.py  Sweep summary figures
│       └── lhs_importance.py        LHS parameter-importance (use --slide for slides)
│
├── illustration_figures/
│   ├── distribution_figure.py      Voter distribution on ideological interval
│   ├── outcome_measures_figure.py  Sincere vs final shares with ΔCENP, k*, Δd*, Δr'
│   ├── preferences_figure.py       Contender (Ca) and opponent (Oa) sets
│   ├── signal_figures.py           Signal distortion (θ) and noise (ρs) figures
│   ├── fr_elections.py             French election poll-vs-result bar charts
│   └── fr_vote_transfers.py        Second-round vote transfer alluvial diagrams
│
├── tests/                     pytest suite (test_empirical.py, …)
│
├── data/
│   ├── FR-electoral_data.csv       Poll and result shares by year and party
│   ├── FR-vote_transfers.csv       Second-round transfer rates (2002, 2022)
│   ├── party_positions_{2002,2022}.csv  Candidate ideological positions
│   ├── polls_{2002,2022}.csv            Pre-electoral poll timeline
│   ├── results_{2002,2022}.csv          First-round results
│   ├── voters_ideology_{2002,2022}.csv  Empirical electorate distribution
│   └── saltelli_results_K{6,8,9}.csv    Pre-computed Saltelli output
│
└── requirements.txt
```

> Generated outputs (`data/empirical_*`, `data/behavioral_*`, `data/sweep_*`,
> and everything under `figures/`) are git-ignored — regenerate them by running
> the analysis scripts below.

---

## Reproducing the results

Pre-computed Saltelli CSVs are included so the main figures can be reproduced
without re-running the full sensitivity analysis.

Scripts are organised by data regime: `analysis/synthetic/` runs the abstract
model on random inputs, while `analysis/empirical/` holds the real 2002/2022
party positions, electorate, and polls fixed. Run each from the repo root.

**Main paper figures** (heatmap, c-sweep, trajectory, empirical range):
```bash
python analysis/synthetic/main_results.py
```
Outputs: `fig1_heatmap_trigger.png`, `fig2_trigger_condswitch_c.png`,
`fig3_trajectory_deltacenp.png`, `fig4_empirical_range_cenp.png`.

**Robustness checks** (Appendices B–D):
```bash
python analysis/synthetic/robustness_checks.py               # all six panels
python analysis/synthetic/robustness_checks.py --panels A B  # specific panels only
```
Outputs written to `outputs/robustness_checks/`.

**Empirical 2002/2022 replay** (real structure fixed):
```bash
python analysis/empirical/empirical_2002_2022.py            # runs + robustness
python analysis/empirical/empirical_2002_2022.py --quick    # few draws, smoke run
python analysis/empirical/empirical_figures.py              # figures from the outputs
python analysis/empirical/empirical_diagnostics.py          # diagnostic tables
```

**Behavioral sweep & parameter importance** (fixed empirical structure):
```bash
python analysis/empirical/behavioral_targets.py        # observed ΔCENP targets
python analysis/empirical/behavioral_sweep.py          # run the sweep
python analysis/empirical/behavioral_sweep_figure.py   # sweep figures
python analysis/empirical/lhs_importance.py            # paper figures
python analysis/empirical/lhs_importance.py --slide    # slide figure
```

**Illustration figures**:
```bash
python illustration_figures/distribution_figure.py
python illustration_figures/outcome_measures_figure.py
python illustration_figures/preferences_figure.py
python illustration_figures/signal_figures.py
python illustration_figures/fr_elections.py --save     # one PNG per election year
python illustration_figures/fr_vote_transfers.py       # PNG + PDF per year
```

**Re-run the full Saltelli analysis** (overwrites included CSVs; ~1.5 hours):
```bash
python analysis/synthetic/saltelli_sensitivity.py
# Edit K_VALUES or set N_SALTELLI = 64 for a quick test run (1152 runs per K).
```

**Tests**:
```bash
pytest
```

---

## Data sources

### `FR-electoral_data.csv`

Party-level pre-electoral poll shares and first-round results for five French
presidential elections. Parties are ordered ideologically following the
classification used in Ipsos post-election reports.

| Year | Poll source | Electoral results |
|------|-------------|-------------------|
| 2002 | Ipsos barometer wave 5 (Ipsos for *Le Figaro* / Europe 1), 15–16 March 2002, *n* = 919 | Ministère de l'Intérieur (2002) |
| 2007 | Ipsos survey (Ipsos for Dell / SFR / *Le Point*), 22–24 March 2007, *n* = 1 245 | Ministère de l'Intérieur (2007) |
| 2012 | — | Ministère de l'Intérieur (2012) |
| 2017 | — | Ministère de l'Intérieur (2017) |
| 2022 | Ipsos / CEVIPOF / *Le Monde* / Fondation Jean Jaurès wave 5, 3–7 February 2022, *n* = 12 499 | Ministère de l'Intérieur (2022) |

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
| 2022 | Ipsos / Sopra Steria post-election survey, 21–23 April 2022, *n* = 4 000, combining survey data with transfer analysis across 500 polling stations | Available for six electorates only: Mélenchon, Jadot, Macron, Pécresse, Le Pen, Zemmour |

---

## Model parameters

| Symbol | Meaning | Range | Status |
|--------|---------|-------|--------|
| *K* | Number of parties | {6, 8, 9} | Structural |
| *M* | Runoff qualifiers | 2 | Fixed |
| *τ̂* | Normalised tolerance threshold | [0.5, 3.0] | Free |
| *c* | Electorate width factor | [0.25, 3.0] | Free |
| *θ* | Signal temperature | [0.3, 3.0] | Free |
| *ρs* | Signal precision | [10, 200] | Free |
| *ρπ* | Prior precision | [5, 200] | Free |
| *α* | Prior weight in belief update | [0.0, 0.9] | Free |
| *μ* | Expressive cost weight | [0.0, 1.0] | Free |
| *εF* | Uniform floor weight | [0.05, 0.5] | Free |
| *N* | Number of voters | 2000 | Fixed |
| *Tmax* | Maximum iterations | 25 | Fixed |
| *ξ* | Electorate mode position | 0.0 | Fixed |
| *εs* | Signal offset | 10⁻⁴ | Fixed |

Party positions are equally spaced on [−1, 1]:
*xⱼ* = −1 + (2*j* + 1)/*K*, *j* = 0, …, *K* − 1.  
Voter tolerance is normalised by zone spacing: *τ* = *τ̂* · (2/*K*).
