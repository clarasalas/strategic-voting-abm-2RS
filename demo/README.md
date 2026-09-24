<h1 align="center">demo</h1>

<p align="center">
Computes the data behind the <a href="https://clarasalas.github.io/strategic-voting-abm-2RS/">interactive page</a>.
The page draws; it never simulates.
</p>

<p align="center"><sub><a href="../README.md">← Back to the project</a></sub></p>

## What is in here

[`precompute.py`](precompute.py) runs the real model over the grid of settings the page's sliders can reach, with
8 seeds each, and writes every trajectory to [`docs/data/grid.json`](../docs/data/grid.json). It also runs the
*France 2022* preset: one behavioural setting replayed on the real 2022 candidates, electorate and polls.

Because the page only replays these trajectories, it cannot drift away from the model: when the model changes,
the data has to be recomputed.

## Run it

```bash
python demo/precompute.py --force                 # the full grid, about 40 minutes
python demo/precompute.py --preset-only --force   # only the France 2022 preset, seconds
python demo/precompute.py --smoke                 # 8 cells, to docs/data/smoke.json
python -m http.server -d docs                     # preview at http://localhost:8000
```

`--preset-only` is enough when the empirical inputs change but the model does not. The rerun driver does this
automatically.

<details>
<summary><strong>How the page is kept honest</strong></summary>

<br>

[`tests/test_demo_data_matches_model.py`](../tests/test_demo_data_matches_model.py) reruns the model on a few
cells, at the parameters the file says it used, and fails if the stored numbers differ. It also recomputes the
France 2022 preset in full and compares it with the stored one, so the preset cannot go stale when the inputs
change.

</details>
