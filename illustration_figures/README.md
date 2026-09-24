<h1 align="center">illustration_figures</h1>

<p align="center">
Figures that explain the model rather than report its results: what an electorate looks like, what a voter
tolerates, how a poll is distorted, and how coordination is measured.
</p>

<p align="center"><sub><a href="../README.md">← Back to the project</a></sub></p>

## What is in here

| Script | What it draws |
|---|---|
| [`distribution_figure.py`](distribution_figure.py) | An imagined electorate: candidates in equal zones along the axis, and voters spread around the centre. |
| [`preferences_figure.py`](preferences_figure.py) | One voter, the candidates they tolerate, and the ones they do not. |
| [`signal_figures.py`](signal_figures.py) | How a poll is made from true support: sharpened or flattened by a temperature, then blurred by noise. |
| [`outcome_measures_figure.py`](outcome_measures_figure.py) | A sincere vote next to the vote after switching, with the coordination measures in between. |
| [`fr_elections.py`](fr_elections.py) | For five French presidential elections, the poll next to the first- and second-round results. |
| [`fr_vote_transfers.py`](fr_vote_transfers.py) | Where each first-round electorate went in the second round, 2002 and 2022. |

The two French figures read [`data/FR-electoral_data.csv`](../data/FR-electoral_data.csv) and
[`data/FR-vote_transfers.csv`](../data/FR-vote_transfers.csv), whose sources are listed in
[Experiments → Data sources](../docs/experiments.md#data-sources). The others need only the model.

## Run them

```bash
python illustration_figures/<script>.py
```

Each script writes its own PNG and PDF. Figures are not committed: they regenerate in seconds, and a stale image is
harder to spot than a stale number.
