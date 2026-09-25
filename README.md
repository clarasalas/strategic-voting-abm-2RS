<h1 align="center">Strategic voting in two-round elections</h1>

<p align="center">
An agent-based model of voters who abandon their favourite candidate when nobody they can tolerate
looks likely to reach the runoff, replayed against the French presidential first rounds of 2002 and 2022.
</p>

<p align="center">
  <a href="https://clarasalas.github.io/strategic-voting-abm-2RS/">
    <img src="https://img.shields.io/badge/Open%20the%20interactive%20page-1a1a1a?style=for-the-badge" alt="Open the interactive page">
  </a>
</p>

<p align="center">
  <a href="https://clarasalas.github.io/strategic-voting-abm-2RS/">
    <img src="docs/preview.png" width="760"
         alt="The interactive page: sliders for the electorate, one voter's tolerance on the left-right axis, vote shares before and after strategic switching, and the poll and votes round by round">
  </a>
</p>

<p align="center"><sub>
Move three sliders and watch the poll and the votes pull on each other, then open the cards below it for the model,
how it is checked, and how to reproduce it. Every trajectory on the page was computed by the Python model.
</sub></p>

<p align="center">
  <a href="https://github.com/clarasalas/strategic-voting-abm-2RS/actions/workflows/tests.yml"><img src="https://github.com/clarasalas/strategic-voting-abm-2RS/actions/workflows/tests.yml/badge.svg" alt="tests"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python 3.10+">
</p>

## About

In a two-round election, a voter whose favourite cannot reach the runoff can vote sincerely and risk having
nobody they like in round two, or switch to a compromise candidate who can qualify. This model follows that choice
for thousands of voters at once.

Voters sit on a left-right axis. Each one reads a public poll, works out which candidates they can tolerate, and
guesses which two will reach the runoff. They switch only when none of their tolerable candidates is among those
two, and only when the gain outweighs the cost of leaving their favourite. The new vote intentions feed the next
poll, so the polls and the votes evolve together.

The model runs in two modes. The synthetic mode generates the electorate and the polls, and asks which parameters
drive coordination. The empirical mode uses the real candidates, voters and poll timeline of 2002 and 2022. 2002 is
the textbook coordination failure, when the left split and its front-runner missed the runoff; 2022 is the
contrasting case. One behavioural setting is applied to both years, and nothing is fitted to either election.

The analysis is in progress toward an article. The results below are preliminary: the mechanism is under revision
and the numbers will move.

## Preliminary results

### In imagined electorates

Across 30,720 synthetic elections with 6, 8 and 9 candidates, what decides whether voters coordinate is mostly
**how attached they are to their favourite**. The expressive cost μ, the price of leaving the candidate you prefer,
matters most for both switching and coordination. Next comes **how many candidates a voter can tolerate** (τ̂),
then **how spread out the electorate is** (*c*). How noisy the polls are, and how voters update their beliefs,
matter less.

No parameter acts alone. Taken one at a time, the eight parameters explain between 13% (6 candidates) and 64%
(9 candidates) of the variation in coordination; the rest comes from parameters acting together.

| Parameter | In plain words | Share of the variation in coordination it is involved in |
|---|---|---|
| μ | cost of leaving your favourite | 73% |
| τ̂ | how many candidates you tolerate | 48% |
| *c* | how spread out the electorate is | 42% |
| the other five | poll noise, beliefs, electorate shape | 26–33% each |

<sub>Total-order Sobol indices for ΔCENP, averaged over 6, 8 and 9 candidates. They overlap, because of the
interactions, so they do not add up to 100%. Source: <a href="results/tables/sobol_indices.csv"><code>sobol_indices.csv</code></a>.</sub>

### France, 2002 and 2022

The replay measures coordination as ΔCENP: how much the vote concentrates on fewer candidates between the first
poll and the election. Positive means it concentrates. In reality it fell in 2002 (−0.113), when the left split,
and rose in 2022 (+0.059).

The model's number has two parts: where its voters start, before anyone switches, and what switching then does.
The second part is the mechanism, and **it concentrates the vote in 7 of 8 settings**:

| How voters start | 2002: switching | 2002: total | 2022: switching | 2022: total |
|---|---|---|---|---|
| nearest candidate | −0.029 | −0.064 | +0.051 | −0.133 |
| in proportion to the polls | +0.045 | −0.036 | +0.029 | −0.010 |
| in proportion to their prior | +0.047 | −0.034 | +0.029 | −0.009 |
| in proportion to the polls, no attachment cost | +0.066 | −0.016 | +0.091 | +0.053 |
| **the real election** | | **−0.113** | | **+0.059** |

<sub>Means over 300–800 behavioural draws per setting. Source:
<a href="results/tables/empirical_delta_cenp_decomposition.csv"><code>empirical_delta_cenp_decomposition.csv</code></a>.</sub>

**On track.** Switching consolidates the vote, as the mechanism intends. When voters start in proportion to the
polls, 2002 ends more fragmented than 2022, the direction of the real contrast, and without an attachment cost 2022
lands close to the real value (+0.053 against +0.059). One behavioural setting is used for both years, and
nothing is fitted.

**Not there yet.** Where voters start weighs more than what they do. Starting everyone at their nearest candidate
spreads the vote across centrist minor candidates: Lassalle ends near 22% in 2022, against 3% in reality. So the
totals mostly reflect the starting point, and no setting yet reproduces the real top two. The 2002 results also
depend on six minor candidates whose positions had to be imputed.

## Next steps

<details>
<summary><strong>1 · Electoral data for the setup</strong></summary>

<br>

The model's inputs now come from surveys, but three gaps remain, and each one touches the results:

* **Six minor 2002 candidates have no measured position** (Besancenot, Taubira, Lepage, Saint-Josse, Boutin,
  Mégret). They took 16% of the vote, and moving them by one point changes the 2002 switching rate by a quarter.
  An expert or voter survey that places them would replace the current imputation.
* **2002 placements come from a survey taken after the election**, when Le Pen's qualification may have shaped
  how people saw the candidates. A pre-election source, such as the first wave of the 2002 French Electoral Panel,
  would match the moment the model describes.
* **In 2022, voters and candidates come from two different surveys.** A single survey with both self-placement
  and candidate placement would put them on exactly the same scale.

Details: [`data/cses/README.md`](data/cses/README.md).

</details>

<details>
<summary><strong>2 · A smooth switching condition</strong></summary>

<br>

Today the trigger is all or nothing: a voter considers switching only when none of their tolerable candidates is
among the two they expect in the runoff. One step inside that line and they may switch; one step outside and they
never do. Small changes in polls or tolerance can therefore flip many voters at once.

The next version replaces the line with a gradient: the pull to switch grows with how unlikely the voter's
tolerable candidates are to qualify. Voters near the edge become partly tempted instead of all-in or all-out. The
aim is a mechanism that responds in proportion to the polls, with the current rule kept as a special case to
compare against.

</details>

## Quick start

```bash
git clone https://github.com/clarasalas/strategic-voting-abm-2RS.git
cd strategic-voting-abm-2RS
pip install -e .
```

```python
from core_model.model import run_simulation
from core_model.metrics import tau_absolute, enp

K = 8
r = run_simulation(K=K, n_modes=1, width_factor=1.5, theta=1.0, rho=100.0,
                   rho_pi=100.0, n_electors=500, tau=tau_absolute(1.75, K),
                   mu=0.1, alpha_prior=0.0, K_runoff=2, max_iterations=15,
                   seed=42, verbose=False, collect_diagnostics=True)
print(f"ENP {enp(r['sincere_shares']):.3f} -> {enp(r['final_shares']):.3f}")   # ENP 5.441 -> 5.208
```

Those exact numbers are pinned by a regression test. To run the full test suite:

```bash
pip install pytest && pip install -e ".[analysis]"
python -m pytest -ra
```

<details>
<summary><strong>How it is checked</strong></summary>

<br>

The test suite runs in CI on every push and pull request, and numerical warnings count as failures. It exists
because an earlier round of empirical results was invalidated by a unit-conversion error that every figure had
looked plausible under. The checks fall into 17 families, among them:

* **Hand-computed values**: metrics match closed-form results to 1e-12.
* **The decision rule**: hand-built voters check that the trigger fires exactly when it should, and that the
  choice flips at the analytically derived cost.
* **Symmetry**: relabelling the candidates or mirroring the axis must not change any decision.
* **Golden regressions**: full output vectors are pinned, so a change that moves every number fails.
* **Reproducibility**: fixed seeds throughout; derived tables regenerate byte-for-byte; runs refuse to overwrite
  output without a flag; interrupted sweeps resume to identical results.
* **The interactive page**: its data are re-checked against the model, so the page cannot drift from the code.

Full record: [docs/validation.md](docs/validation.md).

</details>

<details>
<summary><strong>Repository layout</strong></summary>

<br>

Every folder has a short guide.

| Folder | What is in it |
|---|---|
| [`core_model/`](core_model/README.md) | The model: voters, candidates, polls, one iteration, the metrics. The only installed package. |
| [`analysis/`](analysis/README.md) | The experiments: synthetic (which parameters matter) and empirical (France 2002 and 2022). |
| [`data/`](data/README.md) | Inputs for 2002 and 2022: candidate positions, electorates, polls, results, and where each comes from. |
| [`results/`](results/README.md) | 23 small tables holding every number the analysis cites. |
| [`tests/`](tests/README.md) | The test suite, run on every push. |
| [`tools/`](tools/README.md) | Building the inputs, running the full pipeline, checking and archiving its outputs. |
| [`demo/`](demo/README.md) | Computes the data behind the interactive page. |
| [`docs/`](docs/README.md) | The interactive page, and the detailed reference behind it. |
| [`illustration_figures/`](illustration_figures/README.md) | Explanatory figures: electorates, polls, preferences, outcome measures. |

Raw simulation output and figures are git-ignored on purpose: they are bulky and regenerate from a seed. Only the
derived tables are committed.

</details>

<details>
<summary><strong>Documentation</strong></summary>

<br>

| | |
|---|---|
| **[Model](docs/model.md)** | One round in a diagram, where voters start, what they tolerate and believe, when they switch, how coordination is measured. |
| **[Validation](docs/validation.md)** | The 17 check families, what each guarantees, current status. |
| **[Experiments](docs/experiments.md)** | Parameter spaces, seeds, simulation counts, data provenance. |
| **[Reproducibility](docs/reproducibility.md)** | Install, run, regenerate, verify. |
| **[Code map](docs/code_map.md)** | Repository architecture, and which definitions are canonical. |
| **[Result tables](results/README.md)** | All 23 tables: contents, generating script, inputs, regeneration command. |

</details>

<details>
<summary><strong>The interactive page</strong></summary>

<br>

[`docs/index.html`](docs/index.html) is a static page published with GitHub Pages from the `docs/` folder of `main`.
It computes nothing itself: it replays trajectories that
[`demo/precompute.py`](demo/precompute.py) computed with the real model over 660 settings × 8 seeds (about 40
minutes), stored in `docs/data/grid.json`.

```bash
python demo/precompute.py --force       # regenerate the data after a model change
python -m http.server -d docs           # preview at http://localhost:8000
```

`tests/test_demo_data_matches_model.py` re-runs the model on a few cells and fails if the stored data no longer
match it.

</details>

<details>
<summary><strong>Data sources</strong></summary>

<br>

* **Polls**: the French Wikipedia lists of polls, at fixed revisions for
  [2002](https://fr.wikipedia.org/w/index.php?oldid=236399441) and
  [2022](https://fr.wikipedia.org/w/index.php?oldid=235575713), extracted by `tools/build_polls_from_wikipedia.py`.
* **Voter ideology**: left-right self-placement in the CSES, Module 2 (France 2002) and Module 6 (France 2022).
* **Candidate positions**: respondents' placements of the candidates: CSES 2002, and the Ipsos–CEVIPOF
  Enquête électorale 2022, wave 9. Six minor 2002 candidates are imputed.
* **Election results**: Ministère de l'Intérieur.

Provenance and processing: [docs/experiments.md → Data sources](docs/experiments.md#data-sources).

</details>

---

<sub>Master's thesis project, ENS-PSL / Centre Borelli. Companion project on the geography of coordination:
[strategic-voting-geo-2RS](https://github.com/clarasalas/strategic-voting-geo-2RS).</sub>
