<h1 align="center">core_model</h1>

<p align="center">
The model itself: voters, candidates, polls, one round of decisions, and the measures applied to the result.
</p>

<p align="center"><sub><a href="../README.md">← Back to the project</a></sub></p>

## What is in here

| File | What it does |
|---|---|
| [`model.py`](model.py) | **The entry point.** `run_simulation` runs one election for one set of parameters and returns everything it did. |
| [`agents.py`](agents.py) | The two kinds of agent: candidates (fixed on the axis) and voters, who read the poll, list who they tolerate, guess the runoff, and stay or switch. |
| [`signals.py`](signals.py) | How a poll is generated from current support, with a temperature and noise. Synthetic mode only. |
| [`environment.py`](environment.py) | Builds imagined electorates: where candidates sit and how voters are spread. Synthetic mode only. |
| [`functions.py`](functions.py) | Shared helpers: drawing voters, generating prior beliefs, the coordination measures. |
| [`metrics.py`](metrics.py) | ENP and CENP, the two coordination measures both analyses use. |
| [`empirical_data.py`](empirical_data.py) | Reads the 2002 and 2022 inputs in [`data/`](../data/README.md) and turns them into what the model takes. |
| [`empirical_outcomes.py`](empirical_outcomes.py) | Compares a replay with the real election: errors, top-*k* accuracy, switching rates. |

## How it fits together

```
run_simulation (model.py)
  ├─ candidates and electorate   environment.py   or   empirical_data.py  (France)
  ├─ each round:
  │    poll                       signals.py        or   the real poll timeline
  │    every voter decides        agents.py
  │    votes are counted, and feed the next poll
  └─ results                      metrics.py, empirical_outcomes.py
```

The same loop runs both modes. In the synthetic mode the model draws the electorate and makes its own polls; in
the empirical mode it takes real candidates, real voters' self-placements and the real poll timeline, and the poll
no longer depends on what the simulated voters do.

## Use

```bash
pip install -e .          # from the repository root
```

```python
from core_model.model import run_simulation
```

This is the only folder that is installed as a package. The scripts in [`analysis/`](../analysis/README.md) and
[`tools/`](../tools/README.md) import it and nothing else from the repository.

<details>
<summary><strong>Where to read more</strong></summary>

<br>

* [The model, step by step](../docs/model.md): entities, one full iteration, the decision rule, the tolerance units,
  the outcome measures.
* [Code map](../docs/code_map.md): which definition is canonical when two files seem to compute the same thing.
* The docstring of `run_simulation` lists every parameter and every key of the result.

</details>
