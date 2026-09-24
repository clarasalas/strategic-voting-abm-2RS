<h1 align="center">previous_inputs</h1>

<p align="center">
The inputs the model used until September 2026, kept so the August run stays reproducible, and the reasons they were replaced.
</p>

<p align="center"><sub><a href="../README.md">← Back to data</a></sub></p>

The party positions and electorates the empirical model used up to the 2026-08-21 rerun, kept as
files because the survey-based inputs replaced them in `data/` (see
[`data/cses/README.md`](../cses/README.md)).

| File | Contents | Source |
|---|---|---|
| `party_positions_{2002,2022}.csv` | candidate positions, 0–10 | `CHES` (Chapel Hill Expert Survey) or `llm_coded` |
| `voters_ideology_2002.csv` | self-placement histogram, **1–10** | an Ipsos survey that could not be traced |
| `voters_ideology_2022.csv` | self-placement histogram, 0–10 | Ipsos–CEVIPOF wave 8 (21–24 March 2022), p. 81, per-point values read off the chart |
| `polls_{2002,2022}.csv` | poll timelines | French Wikipedia poll lists, copied by hand |

The values are those at the tag `empirical-rerun-2026-08-21`. Two metadata edits were made
since, and neither changes a number: `hand_coded` is relabelled `llm_coded`, its actual origin,
and each voter file declares its scale in a `scale` column. `tests/test_cses_inputs.py` pins the
values.

They are used in two places:

* **The bridge.** `tools/build_cses_inputs.py` places the candidates no survey measures by
  carrying these positions onto the survey scale.
* **The code regression.** `test_golden_empirical_probabilistic` runs on these inputs, polls
  included, so it pins the code and does not move when the empirical inputs change.

Known problems, and the reasons they were replaced: the 2002 voter file has no traceable source
and uses a different scale from 2022. The 2022 voter file does not match the grouped totals Ipsos
publishes; it has too few voters at 9–10. Expert and voter positions are on different scales.
Seven positions in 2002 (four in 2022) were LLM-coded. And **`polls_2022.csv` has two pairs of
candidates swapped in every poll, LO/NPA and EELV/PS**: the values were copied in the page's
column order under a header in a different order, so the model saw Hidalgo polling ahead of Jadot.
The 2002 file has the right columns but differs from the page by up to a few tenths of a point, and
kept two polls that did not offer every candidate. Both files were rebuilt from fixed Wikipedia
revisions by `tools/build_polls_from_wikipedia.py`.
