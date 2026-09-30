<h1 align="center">Modelling decisions</h1>

<p align="center">
Every modelling choice, what else was possible, and why this one: the working log behind the paper's
ODD+D description and parameter table.
</p>

<p align="center"><sub><a href="README.md">← Docs</a></sub></p>

## How to use this log

One row per decision. The IDs are stable: when a decision changes, edit its row and note it under **Status**
rather than renumbering, so the paper and the commit history can keep referring to it.

| Column | What goes in it |
|---|---|
| **ID** | stable identifier, prefixed by block (S, V, C, I, B, F, D, T, O) |
| **Model component** | the part of the model the decision is about |
| **Choice made** | what the model does now, in one sentence |
| **Alternatives considered** | the other options that were on the table |
| **Justification** | why this choice: theory, data, tractability, or comparability |
| **References** | BibTeX keys (e.g. `cox1997`), so the table moves into LaTeX unchanged |
| **Where in code** | file and function, e.g. `core_model/agents.py` → `calcStrategicUtilities` |
| **Sensitivity tested?** | yes (which experiment) / no / not applicable |
| **Status** | settled / provisional / under revision |

## S · Scope and structure

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| S1 | Electoral stage modelled (first round only, runoff not simulated) | | | | | | | |
| S2 | Turnout and abstention | | | | | | | |
| S3 | Candidate set and candidate behaviour (fixed, no campaign, no entry or exit) | | | | | | | |
| S4 | Dimensionality of the ideological space | | | | | | | |
| S5 | Bounds of the ideological space | | | | | | | |
| S6 | Update scheduling (all voters decide simultaneously each round) | | | | | | | |
| S7 | Two modes: synthetic and empirical | | | | | | | |

## V · Voters

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| V1 | Sincere utility function | | | | | | | |
| V2 | Electorate size *N* | | | | | | | |
| V3 | Synthetic electorate distribution (shape) | | | | | | | |
| V4 | Synthetic electorate width *c* (in zone units) | | | | | | | |
| V5 | Synthetic electorate skew ξ | | | | | | | |
| V6 | Uniform floor weight ε<sub>F</sub> | | | | | | | |
| V7 | Empirical electorate source (survey self-placements) | | | | | | | |
| V8 | Empirical electorate sampling and survey weights | | | | | | | |
| V9 | Voter homogeneity (same behavioural parameters for all voters) | | | | | | | |

## C · Candidates

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| C1 | Synthetic candidate positions (equally spaced zone midpoints) | | | | | | | |
| C2 | Number of candidates *K* in the synthetic experiments | | | | | | | |
| C3 | Empirical candidate positions: source | | | | | | | |
| C4 | Mapping of survey scales (0–10) onto [−1, 1] | | | | | | | |
| C5 | Imputation of the six unmeasured 2002 candidates | | | | | | | |
| C6 | Voters and candidates from different surveys (2022) | | | | | | | |
| C7 | Timing of the 2002 placements (post-election survey) | | | | | | | |

## I · Information and polls

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| I1 | Information structure (one public poll, no private information) | | | | | | | |
| I2 | Poll generation from current support (synthetic) | | | | | | | |
| I3 | Poll temperature θ | | | | | | | |
| I4 | Poll noise: Dirichlet precision ρ<sub>s</sub> | | | | | | | |
| I5 | Poll floor ε<sub>s</sub> | | | | | | | |
| I6 | Exogenous real polls in the empirical mode | | | | | | | |
| I7 | Poll aggregation (weekly means vs individual polls) | | | | | | | |
| I8 | Poll source and time window | | | | | | | |

## B · Beliefs

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| B1 | Prior beliefs: Dirichlet around the opening poll | | | | | | | |
| B2 | Prior precision ρ<sub>π</sub> | | | | | | | |
| B3 | Belief update rule (linear mix of fixed prior and current poll) | | | | | | | |
| B4 | Anchor of the update (fixed prior, not last round's belief) | | | | | | | |
| B5 | Weight on the prior α | | | | | | | |
| B6 | Belief at *t* = 0 equals the prior (no double counting of *s*<sup>0</sup>) | | | | | | | |

## F · Favourite (initial vote)

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| F1 | Nearest-candidate rule (baseline) | | | | | | | |
| F2 | Probabilistic draw of the favourite | | | | | | | |
| F3 | Weight of ideology against salience β | | | | | | | |
| F4 | Source of salience (opening poll vs own prior) | | | | | | | |
| F5 | Favourite fixed across rounds (reference point for switching) | | | | | | | |

## D · Decision rule

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| D1 | Tolerable set (distance threshold, inclusive boundary) | | | | | | | |
| D2 | Tolerance expressed in zones (τ̂) rather than raw distance | | | | | | | |
| D3 | Tolerance range | | | | | | | |
| D4 | Runoff expectation (top two by own belief) | | | | | | | |
| D5 | Switching trigger (no tolerable candidate in the expected runoff) | | | | | | | |
| D6 | Binary trigger (vs a smooth, probabilistic one) | | | | | | | |
| D7 | Strategic score: local viability × runoff viability − cost | | | | | | | |
| D8 | Local viability (belief renormalized over the tolerable set) | | | | | | | |
| D9 | Runoff viability (projected share against the strongest non-tolerated candidate) | | | | | | | |
| D10 | Expressive cost of leaving the favourite (quadratic, normalized by ℓ²) | | | | | | | |
| D11 | Weight of the expressive cost μ | | | | | | | |
| D12 | Deterministic choice (argmax, no choice noise) | | | | | | | |

## T · Dynamics and runs

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| T1 | Number of rounds (25 synthetic; number of polls empirical) | | | | | | | |
| T2 | Round 0 as the sincere vote | | | | | | | |
| T3 | Stopping rule (fixed horizon, no convergence stop) | | | | | | | |
| T4 | Random seeds and seed derivation | | | | | | | |

## O · Outcome measures

| ID | Model component | Choice made | Alternatives considered | Justification | References | Where in code | Sensitivity tested? | Status |
|---|---|---|---|---|---|---|---|---|
| O1 | Effective number of parties (Laakso–Taagepera ENP) | | | | | | | |
| O2 | Normalized measure CENP | | | | | | | |
| O3 | ΔCENP baseline (real opening poll vs model's sincere vote) | | | | | | | |
| O4 | Trigger, switching and conditional switching rates | | | | | | | |
| O5 | Top-*k* accuracy as an exact set match | | | | | | | |
| O6 | The cliff (largest gap in sorted shares) | | | | | | | |
| O7 | Candidate-level fit (mean share, band, change from first poll) | | | | | | | |

## E · Experimental design and validation

**Deferred.** The protocol will be designed once the model is frozen. The experiments run so far (Sobol on the
synthetic mode, the 2002 and 2022 replays, the behavioural sweeps, the robustness panels) were exploratory: they
show how the model behaves, but they are not the final protocol, and they are not logged here as decisions.

Candidate components for the final protocol, to be decided then:

- [ ] Verification (unit and invariant tests, analytic limits)
- [ ] Number of replications per setting (convergence of the output variance)
- [ ] Time horizon and convergence of the dynamics
- [ ] Global sensitivity analysis (Saltelli sampling, Sobol indices) in **both** modes
- [ ] Calibration or estimation method (e.g. likelihood-based, simulated likelihood, approximate Bayesian computation, method of simulated moments)
- [ ] Goodness of fit against the real elections (which targets, which metric)
- [ ] Pattern-oriented validation (which stylized facts the model must reproduce)
- [ ] Out-of-sample validation (e.g. other French elections)
- [ ] Case selection (2002 and 2022, and why)

---

<p align="center"><sub><a href="README.md">← Docs</a></sub></p>
