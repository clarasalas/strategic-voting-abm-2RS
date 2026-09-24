<h1 align="center">ipsos</h1>

<p align="center">
How French voters placed the twelve 2022 candidates on the left-right axis a week before the first round.
</p>

<p align="center"><sub><a href="../README.md">← Back to data</a></sub></p>

`candidate_positions_2022_wave9.csv` is the main source of the 2022 candidate positions. It is
transcribed by hand from a published report; nothing here is computed.

| | |
|---|---|
| Survey | Enquête électorale française 2022, wave 9, Ipsos / CEVIPOF / Fondation Jean Jaurès / *Le Monde* |
| Fieldwork | 2–4 April 2022, before the first round (10 April) |
| Sample | 12,600 registered voters aged 18+, online (Ipsos Access Panel), quota method |
| Report | [Ipsos – Enquête Electorale – Vague 9 – 6 avril 2022 (PDF)](https://www.ipsos.com/sites/default/files/ct/news/documents/2022-04/Ipsos%20-%20Enque%CC%82te%20Electorale%20-%20Vague%209%20-%206%20avril%202022.pdf) |
| Table | page 48, *Le positionnement des candidats sur l'axe gauche-droite* |
| Question | « En politique, les gens parlent de la gauche et de la droite. Sur une échelle de 0 à 10, où classeriez-vous les personnalités suivantes ? » |
| Base | whole sample |

## Columns

| Column | Meaning |
|---|---|
| `pct_0_1` … `pct_9_10` | percentage of respondents in each published bin: 0–1, 2–3, 4, 5, 6, 7–8, 9–10 |
| `pct_never_heard` | « Je n'ai jamais entendu parler de cette personnalité » (`-` in the report is written as 0) |
| `pct_dont_know` | « Ne sait pas » |
| `pct_left_0_3`, `pct_centre_4_6`, `pct_right_7_10` | the report's own group totals |
| `mean_0_10` | the report's mean placement, column *Avril 2022*: **the value the model uses** |

The report publishes means and grouped bins only, not per-point shares or medians. That is why
the 2022 positions are means, and why the 2002 positions are means too (see
[`data/cses/README.md`](../cses/README.md)).

## Checks

`tests/test_cses_inputs.py` checks that each row's bins plus the two non-response columns sum to
100, that the group totals agree with the bins to within rounding, that the table covers exactly
the 12 modelled candidates, and that the means equal the published values, written out
separately in the test.

The means are rounded to one decimal in the report. Candidates who are close stay distinct:
Arthaud 1.2 and Poutou 1.4, Hidalgo 3.1 and Jadot 3.3, Le Pen 8.8 and Zemmour 9.1.
