# Survey-based ideology inputs, France 2002 and 2022

Replacements for `data/voters_ideology_*.csv` and `data/party_positions_*.csv`, built by
[`tools/build_cses_inputs.py`](../../tools/build_cses_inputs.py) from the CSES and from the
Ipsos–CEVIPOF 2022 table in [`data/ipsos/`](../ipsos/README.md). For how and when the model
switches to them, see [Switching the model to these inputs](#switching-the-model-to-these-inputs).

The principle: positions are **perceived** positions. Voters in the model act on how they see the
field, so candidates are placed by survey respondents, on the same 0–10 left-right question voters
use to place themselves.

## Main specification

| | 2002 | 2022 |
|---|---|---|
| Voters | CSES self-placement, weighted | CSES self-placement, unweighted |
| Candidates measured | 9 of 15: CSES **candidate** placements, weighted **mean**, after the scale-direction screen | all 12: Ipsos–CEVIPOF wave 9 published **means** |
| Candidates imputed | 6 of 15, by the bridge: LCR, PRG, CAP21, CPNT, FRS, MNR | none |
| File | `party_positions_2002.csv` | `party_positions_2022.csv` |

**Why candidate placements.** Voters choose between candidates. 2002 CSES asked respondents to
place the presidential candidates themselves (one of three Module 2 studies to do so), and the
Ipsos 2022 wave did the same for all 12 candidates. Party placements are kept as comparison
files.

**Why means.** Ipsos publishes means and grouped bins only, so the 2022 values are means. 2002
uses the same statistic so the two years are measured the same way.

**Why the 2002 scale-direction screen.** In the 2002 CSES, 16% of respondents place Le Pen at 0–2,
on the far left. That is not projection: FN voters do not place him there. It is consistent with
respondents reading the scale backwards on a telephone interview. The screen drops a respondent's
candidate placements when they put Laguiller (LO) strictly to the right of Le Pen (FN): 118 of the
922 who placed both (`scale_screen.csv`). Respondents who did not place both are kept. Their
self-placements are kept too: the screen is about candidate placements only. Without the screen,
Le Pen's mean is 7.63 against Chirac's 7.29; with it, 8.63 against 7.39. Ipsos 2022, an online
survey, shows no such pattern: 2% or fewer place Le Pen, Zemmour or Pécresse at 0–1.

## Every candidate

The candidate-by-candidate record is `coverage.csv`: main position, its source, whether it is
imputed, the current position and source in `data/`, and the value under every comparison
specification.

**2002.** CSES candidate items, then CSES party items for comparison.

| | n | mean | mean, screened (**main**) | interp. median | party mean | party interp. median | candidate − party mean |
|---|---|---|---|---|---|---|---|
| LO Laguiller | 949 | 2.28 | **1.94** | 1.85 | 2.28 | 1.68 | 0.00 |
| PCF Hue | 947 | 2.41 | **2.17** | 2.21 | 2.41 | 2.03 | 0.00 |
| PS Jospin | 970 | 3.58 | **3.33** | 3.73 | 3.62 | 3.81 | −0.04 |
| LV Mamère | 935 | 3.59 | **3.46** | 3.67 | 3.58 | 3.67 | +0.01 |
| MDC Chevènement | 922 | 4.54 | **4.55** | 4.72 | 4.57 | 4.76 | −0.03 |
| UDF Bayrou | 907 | 5.81 | **5.91** | 5.87 | 6.36 | 6.52 | −0.54 |
| DL Madelin | 894 | 6.16 | **6.40** | 6.34 | 5.86 | 5.88 | +0.30 |
| RPR Chirac | 970 | 7.29 | **7.39** | 7.61 | 6.67 | 6.99 | +0.62 |
| FN Le Pen | 945 | 7.63 | **8.63** | 9.66 | 7.74 | 9.69 | −0.10 |

Candidate and party placements agree to within 0.05 for the left and for MDC. They differ for
the three main right-wing candidates: Chirac is placed 0.6 to the right of the RPR, Bayrou 0.5 to
the left of the UDF, and Madelin 0.3 to the right of DL. The party items rank DL to the left of
the UDF; the candidate items rank Madelin to the right of Bayrou.

Imputed in 2002, from the current positions through the bridge below: LCR 1.76, PRG 4.00,
CAP21 5.06, CPNT 6.83, FRS 6.99, MNR 8.76. One consequence to be aware of: the bridged MNR
(Mégret, 8.76) lands slightly to the right of the measured FN (Le Pen, 8.63), because Le Pen's
survey mean sits well below his current expert position (9.92).

**2022.** Ipsos means (main), CSES party items for comparison where they exist.

| | Ipsos mean (**main**) | CSES party mean | CSES party interp. median |
|---|---|---|---|
| LO Arthaud | **1.2** | – | – |
| NPA Poutou | **1.4** | – | – |
| LFI Mélenchon | **1.6** | 1.60 | 1.12 |
| PCF Roussel | **1.9** | – | – |
| PS Hidalgo | **3.1** | 2.95 | 2.91 |
| EELV Jadot | **3.3** | 3.19 | 3.17 |
| RES Lassalle | **4.9** | – | – |
| RE Macron | **6.4** | 6.37 | 6.32 |
| LR Pécresse | **7.4** | 7.46 | 7.75 |
| DLF Dupont-Aignan | **7.8** | – | – |
| RN Le Pen | **8.8** | 8.69 | 9.63 |
| REC Zemmour | **9.1** | 8.01 | 9.59 |

Two different surveys, weeks apart, one about candidates and one about parties, agree to within
0.15 for six of the seven candidates they share. The exception is Zemmour/REC (9.1 vs 8.0): the
party was created in December 2021.

The largest change from the current inputs is Lassalle: 5.8 (LLM-coded) to 4.9 (measured).

## The bridge

Used only where no survey measures a candidate: the six 2002 candidates above in the main
specification, and in the comparison specifications as listed in `bridge_fit.csv`. Per year and
specification, an OLS fit of the survey position on the candidate's current position in
`data/party_positions_{year}.csv`, over the candidates that have both, applied to the current
position of each unmeasured candidate and clipped to 0–10 (no clipping occurs). The value is
labelled `imputed_bridge_from_<current source>`: `imputed_bridge_from_CHES` for PRG,
`imputed_bridge_from_llm_coded` for the other five.

| Specification | anchors | slope | in-sample R² | in-sample RMSE (0–10) | largest in-sample residual |
|---|---|---|---|---|---|
| 2002 main | 9 | 0.77 | 0.961 | 0.44 | 0.85 |
| 2002 unscreened means | 9 | 0.65 | 0.936 | 0.48 | 1.02 |
| 2002 party items | 9 | 0.83 | 0.957 | 0.50 | 1.06 |
| 2022 CSES party items | 7 | 0.99 | 0.978 | 0.47 | 0.77 |

These describe how well the line fits the candidates it was fitted on. They are **not** a
validation of the imputed values: no imputed candidate has a survey value to check against. Two of
the 2002 anchors (LO, MDC) have LLM-coded current positions; the rest are CHES.

The LLM-coded positions (`llm_coded` in `data/party_positions_*.csv`) were produced with a
language model and checked against the order of parties in reports and party websites. **Still to
document:** the model, the prompt, the date, and the checks. They enter the main specification
only through the bridge, for five 2002 candidates.

## Robustness and comparison

| Specification | File |
|---|---|
| **2002 main** | `party_positions_2002.csv` |
| 2002, candidate means without the screen | `party_positions_2002_unscreened_means.csv` |
| 2002, CSES party items, interpolated median | `party_positions_2002_party_items.csv` |
| **2022 main** | `party_positions_2022.csv` |
| 2022, CSES party items, interpolated median | `party_positions_2022_cses_party_items.csv` |

Every summary of every item (plain weighted median, interpolated median, mean, screened mean) is in
`candidate_positions_{year}.csv`.

The replay's robustness stage has a variant, `perturbed_imputed_positions`, that moves only the
imputed positions by up to ±0.2 on the model scale (±1 point on 0–10, about twice the bridge's
in-sample RMSE) and leaves the measured ones fixed. `core_model.empirical_data.MEASURED_SOURCES`
lists what counts as measured; anything else, including an unknown label, is perturbed. Under the
main specification it moves the six 2002 candidates and **nothing in 2022**, where every candidate
is measured.

The imputed candidates matter most in 2002: they took 16.3% of the first-round vote, and LCR and
PRG alone took 6.6% on the left, where Jospin missed the runoff by 0.68 points.

## Sources

| Year | Release | DOI | Study | Fieldwork | n |
|---|---|---|---|---|---|
| 2002 | CSES Module 2 Full Release, 15 Dec 2015 (`VER2015-DEC-15`) | [10.7804/cses.module2.2015-12-15](https://doi.org/10.7804/cses.module2.2015-12-15) | `B1004 = FRA_2002` (presidential, `B1015 = 20`) | 23–24 May 2002, CATI, quota sample | 1,000 |
| 2022 | CSES Module 6 Second Advance Release, 16 Dec 2025 (`VER2025-DEC-16`) | [10.7804/cses.module6.2025-12-16](https://doi.org/10.7804/cses.module6.2025-12-16) | `F1004 = FRA_2022` (presidential, `F1014 = 20`) | 28 Apr–26 May 2022, web, ELIPSS panel | 1,575 |
| 2022 | Ipsos–CEVIPOF Enquête électorale, wave 9 | see [`data/ipsos/`](../ipsos/README.md) | | 2–4 April 2022, online | 12,600 |

Download pages: <https://cses.org/data-download/cses-module-2-2001-2006/> and
<https://cses.org/data-download/cses-module-6-2021-2026/>. Module 6 is an *advance* release, and
CSES says values may change in later releases. The script checks the release and DOI strings in
the data and stops if they differ.

The raw files go in `data/raw/cses/`. That directory is git-ignored because CSES data may be
downloaded but not redistributed. The script reads the zips in place:

```
7c31a255b17b49a8ca279165d0a77164ac2ef21817533128d4662486642fe504  cses2_csv.zip
6cefba64b5288fc377b4d7d4d905efa8a63c2c33c5b8a7b859ce23c49841919b  cses2_codebook.zip
af6eaf176f03b3ff461a6cd0cb702ae93ce696cbd1db4cd59c3be467c16cdf2e  cses6_csv.zip
33e6ea35d8ba4aa897c39f555ed1abb532f05abd111dcd6dbbedee30da1313d4  cses6_codebook.zip
```

## CSES variables

| | 2002 (Module 2) | 2022 (Module 6) |
|---|---|---|
| Self-placement | `B3045` LEFT-RIGHT - SELF | `F3020_R` IDEOLOGY: LEFT-RIGHT - SELF |
| Candidate placement | `B3039_A`–`I` LEFT-RIGHT - LEADER (**main**) | none |
| Party placement | `B3038_A`–`I` LEFT-RIGHT - PARTY (comparison) | `F3020_A`–`G` LEFT-RIGHT - PARTY (comparison) |
| Scale | 0 = left … 10 = right | 0 = left … 10 = right |
| Missing codes excluded | 95–99 (only 98 DK and 99 missing occur) | 95–99 (only 99 occurs) |
| Weight | `B1012_2`, demographic (education, public/private sector) | none: every weight variable is 1 |

The letter-to-party mappings come from the codebook: Appendix I, *Parties and Leaders: France
(2002)*, for Module 2, and Part 3, *Parties/Coalitions & Leaders: France (2022)*, for Module 6.
The script re-checks each one against that codebook text before computing anything:

| 2002 | A | B | C | D | E | F | G | H | I |
|---|---|---|---|---|---|---|---|---|---|
| Model code | RPR | FN | PS | UDF | LO | MDC | LV | DL | PCF |
| Candidate | Chirac | Le Pen | Jospin | Bayrou | Laguiller | Chevènement | Mamère | Madelin | Hue |

| 2022 | A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|---|
| Model code | RE (as LREM) | RN | LFI (as FI) | REC | LR | EELV | PS |
| Candidate | Macron | Le Pen | Mélenchon | Zemmour | Pécresse | Jadot | Hidalgo |

## Transformation

* **Voters.** Respondents with a valid 0–10 self-placement are kept. The share in each bin is its
  sum of weights divided by the total. Each `voters_ideology_{year}.csv` declares its scale in a
  `scale` column (`0-10`); the loader maps by that declaration and refuses a file without one.
* **Candidates.** Weighted means of valid placements; 2002 after the screen above. Positions are
  written on 0–10; the loader maps them with `x / 5 − 1`.
* **Exclusions.** Responses are excluded per item, not per respondent. All respondents are kept,
  whether or not they report having voted. `sample_sizes.csv` lists, for every item, the
  unweighted, weighted and effective (Kish) *n*, and the count for each excluded code.

## Files

| File | Contents |
|---|---|
| `voters_ideology_{year}.csv` | weighted self-placement histogram, bins 0–10, with declared scale |
| `party_positions_{year}.csv` | **model-ready, main specification**: every modelled candidate, same schema as `data/party_positions_{year}.csv` |
| `party_positions_{year}_{spec}.csv` | model-ready comparison specifications (table above) |
| `candidate_positions_{year}.csv` | every summary of every survey item; 2022 also the Ipsos mean |
| `coverage.csv` | candidate-by-candidate: main position and source, imputed or not, current value, comparison values |
| `bridge.csv`, `bridge_fit.csv` | the bridge, per candidate and per fit |
| `scale_screen.csv` | the 2002 screen: who was compared, how many were dropped |
| `sample_sizes.csv` | n per item and the codes excluded from it |

## Limitations

* **Timing.** The CSES surveys ran after the election, while the model describes beliefs before
  the first round. This now affects the 2002 candidates and both years' voters; the 2022
  candidates come from a pre-election wave. The 2002 fieldwork (23–24 May) follows Le Pen's
  qualification and the left's call to vote for Chirac, which may have moved placements of Chirac
  and of the left. The 2022 fieldwork overlaps the formation of the NUPES alliance.
* **2022 voters and candidates come from different respondents** (CSES and Ipsos). The Ipsos
  wave has no self-placement item; wave 8 has one, but publishes grouped bins only.
* **Means are sensitive to projection**, where supporters place their own candidate nearer
  themselves. The Ipsos detail table (page 49) shows it: Le Pen is placed at 7.9 by Zemmour's
  voters and 9.3 by Mélenchon's.
* **2022 CSES is unweighted**, and comes from an online panel covering mainland France without
  Corsica.
* **Module 6 is an advance release**; values may change in the full release.

## Switching the model to these inputs

The model reads `data/party_positions_{year}.csv` and `data/voters_ideology_{year}.csv`. Copying
the main-specification files over them is the whole switch, and `tests/test_cses_inputs.py`
checks that the model loads the swapped files:

```bash
cp data/cses/party_positions_{2002,2022}.csv data/cses/voters_ideology_{2002,2022}.csv data/
```

Do it as part of a rerun, so the committed result tables never describe inputs other than the ones
in `data/`. The inputs of the August run stay in git history, at the tag
`empirical-rerun-2026-08-21`.
