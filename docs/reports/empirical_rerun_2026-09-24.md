# Empirical rerun record: 2026-09-24, survey inputs

[← Experiments](../experiments.md) · **Rerun record** · [Reproducibility →](../reproducibility.md)

A dated record of the rerun on the survey-based inputs: what changed, what was run, how it was
validated, and what it produced. It records the process only; the results are for the analysis.

The previous run's record is [2026-08-21](empirical_rerun_2026-08-21.md). Its outputs are archived
in `data/archive/august_rerun_2026-08-21/` (234 files, SHA-256 verified before and after this run).

## What changed since the 2026-08-21 run

| Input | 2026-08-21 | This run |
|---|---|---|
| Candidate positions | CHES + LLM-coded | 2002: CSES candidate placements, screened means, 6 imputed; 2022: Ipsos–CEVIPOF wave 9 means, all 12 ([details](../../data/cses/README.md)) |
| Electorates | Ipsos histograms (2002 untraced, 1–10 scale) | CSES self-placement, 0–10, both years |
| Polls | hand-copied; **2022 had LO/NPA and EELV/PS swapped** | built from fixed Wikipedia revisions ([details](../experiments.md#data-sources)); 2002: 39 polls (2 dropped), 2022: 81 |
| Robustness | 3 variants | 4: adds `perturbed_imputed_positions` |

The code of the model is unchanged: the golden empirical regression, run on the August inputs
(`data/previous_inputs/`), passes with its pinned numbers.

## Run

| | |
|---|---|
| Name | `survey_inputs_2026-09` |
| Commit | `173d20ceb41ba913507a2ff3453c649f0f424bd8` (branch `survey-inputs`, pushed; CI passed, 648 tests) |
| Working tree | clean (`dirty_tree: false`) |
| Started / finished | 20:35:42 → 23:07:39 CEST (2 h 32) |
| Python | 3.11.7, on the author's MacBook Air |
| Stages | **33 / 33 OK** |
| Simulations | **14,200**: replay 600 + robustness 800, probabilistic variants 4,800, sweeps 8,000 |
| Seeds | replay and sweeps `20020422`; LHS importance `42` |
| Command | `RUN_NAME=survey_inputs_2026-09 RERUN_ARCHIVE=data/archive/august_rerun_2026-08-21 caffeinate -i nohup tools/run_empirical_rerun.sh` |

A smoke run of the same driver and commands (a few draws each, in a separate worktree) passed on
the same inputs beforehand. It found one driver defect, since fixed: no stage wrote
`data/behavioral_targets.csv`, which earlier runs had only found because an older copy was in
`data/`.

| Stage | Wall time | 2026-08-21 |
|---|---|---|
| Replay, `nearest`, with robustness | 11 min 40 | ~30 min (200 fewer runs) |
| Three probabilistic variants | 20 min 21 | ~39 min |
| Sweep 2002 | 61 min 15 | 2 h 57 for both years |
| Sweep 2022 | 57 min 04 | |
| Derived outputs, demo preset, tests, tables | 1 min 29 | ~3 min |

The run was faster than August's throughout. Every validation passed (row counts, τ relation), so
no work was skipped; the machine's load in August is the likely difference, but it was not measured.

## Validation

* `tools/validate_rerun.py` after every simulation stage: expected row counts; `tau_absolute =
  tau_hat × 2/K`, with both units and *K* recorded, in every file; ceilings 0.400 (2002) and
  0.500 (2022) respected; zero occurrences of the pre-fix `tau >= 2.0` warning.
* Test suite at the end of the run: **648 passed**.
* Archive of the August outputs: intact.
* The demo's France 2022 preset was regenerated; it is identical to the committed one (only the
  recorded commit changes).

## Outputs

The seven summary tables in `results/tables/` were regenerated and are committed with this record.
`empirical_robustness_summary.csv` grows from 84 to 112 rows (the fourth variant); the others keep
their shapes. `tools/check_tables_reproduce.py` passes on the committed state.

Raw outputs stay in `data/` (git-ignored). Their SHA-256 manifest, also in
`logs/survey_inputs_2026-09/outputs.sha256`:

<details>
<summary>50 files</summary>

```
d752ee5b09e8e323cea85e7f378547faa717e66474061786fef89e08187e7ab9  data/behavioral_compare_2002_2022.csv
86925959164284567cf3defec02b356a74a4e949333b51c265b0a719067a1865  data/behavioral_sweep_2002.csv
db2dcb016e0633263446065809e45aa567ce5a0e24d160ca93282e1306dbf62a  data/behavioral_sweep_2002_design.csv
009638d807ab29002e80b43cb165685531bd7eba38cafcdb7f5f499f45c25878  data/behavioral_sweep_2002_meta.json
75cc94618bee74ddbcea3159b8e0e99125c627f3c91b660c1b2699c73fa35b80  data/behavioral_sweep_2022.csv
db2dcb016e0633263446065809e45aa567ce5a0e24d160ca93282e1306dbf62a  data/behavioral_sweep_2022_design.csv
283e6e097ea34466e7b81f98e351ad9b4389ee2bf0b766e6a006cd9d8283de97  data/behavioral_sweep_2022_meta.json
f011a8068f8ff8e0adec57373e54d0dd3b446e3af09de26a0be145a0123357cc  data/behavioral_targets.csv
b8f7bcd058dd69497dd395ebfa2e8ccbff3120b1b9a4eb0cbfdfb95c315b8a17  data/empirical_activation_summary.csv
4b678e6d4c0a3c1b0829759f7d03c67bd28f9eb98fadffd83b860a37f60ea7be  data/empirical_activation_summary_prob_prior.csv
ce6477e678d21e80eed988d9b5f302def06d17a17ff2c20b543e16d19cbde455  data/empirical_activation_summary_prob_signal.csv
f80bce025c44b5dca6d98b131c09f35dba36f301aa625aeb66f9bb9ad9cce7c4  data/empirical_activation_summary_prob_signal_mu0.csv
eacdb206d1ea05793a5d4f12d9ffa9f2cd2d05b6b5f5400e0732b54539fe2e4b  data/empirical_candidate_draws_2002.csv
d71ef66b827d3efaa955b73f84f16f74406727d0bf3bea22e0d8f6894eaab3d2  data/empirical_candidate_draws_2022.csv
8bd179bb854127d1b19546d2d27e8e35a215808ae9178c3e39be58da607c56fe  data/empirical_candidate_draws_prob_prior_2002.csv
5f78cea886ac0d1aa6ab1f9ce63ed1df6806eabfe09b1bf0d25063f65d421881  data/empirical_candidate_draws_prob_prior_2022.csv
ce69e2decad71b50f8ac4e6c9e906657b2b13d1901a5c32c3ebfe51aa58f8830  data/empirical_candidate_draws_prob_signal_2002.csv
76b4d19fdd4a9dbdb732b01c8f5de78f26e479b8b9b00ae17b6fd0f7d8f54940  data/empirical_candidate_draws_prob_signal_2022.csv
991c222ac3e818fcfa19cad982406a6039ec1b02453ec17be0353b673c28d603  data/empirical_candidate_draws_prob_signal_mu0_2002.csv
639705ae68964dedebdbd5a51f96a29aeecb145acaeea3446c3a08dc106a5523  data/empirical_candidate_draws_prob_signal_mu0_2022.csv
d3ff08462614b7dd47a7c4d5d435a8a452149163c3ee1586a622cb0153a86d92  data/empirical_candidate_shares_2002.csv
73820cced7af8dcc23bc5727f42229a1b62416a0346abd2626ea7bc68a25a4a7  data/empirical_candidate_shares_2022.csv
55c29815acd1f142ed3265719b6018fa435504d4491eb63a429eac9e554e1d61  data/empirical_candidate_shares_prob_prior_2002.csv
f08c5f501a8aff446d42abc2836673309124ea717c55ad242efb7577e932d6ef  data/empirical_candidate_shares_prob_prior_2022.csv
9c74164449bdaa2c2f9831363291c91777c34d63765e9ac421625f1d57f1461f  data/empirical_candidate_shares_prob_signal_2002.csv
341cbd220ad6afd69259c44b1becc89b3e4281f072eb69cb031b818f455fb995  data/empirical_candidate_shares_prob_signal_2022.csv
739757ab8a6b94e30b1ac51234e6c821ffd12e2bbd03c135590aff085c54f2fc  data/empirical_candidate_shares_prob_signal_mu0_2002.csv
38ca19467c1fcbb580f0a6ff8dcc7b5fca8b6a390648ddef97e75a71b3a21a7c  data/empirical_candidate_shares_prob_signal_mu0_2022.csv
236e93bf6c835aa455a8bddfd5fb3f1084db12fdd67656bf679463b7586bb7e2  data/empirical_diagnostics_2002.csv
40f0805f01ddd571973594dbd8ea1fff055c2aeb9d09c07b1438cbfa66fc55fc  data/empirical_diagnostics_2002_prob_prior.csv
a410f6fbc7c57c3ab23b293c0fba3b7b62da3d02cfee0edb01ec9d9119b1b943  data/empirical_diagnostics_2002_prob_signal.csv
bd4e830a6aa8ae99ecf36bde9349cfdc5893ddd6f9e17b86a2340effbc615029  data/empirical_diagnostics_2002_prob_signal_mu0.csv
9dda68c6dcfd8175405b91ac752b6dc4d5f6c3fdc02e6f03e6416f0a47822769  data/empirical_diagnostics_2022.csv
7d611c4c635f0243a35c83bffe16a4025d66a9f059b8ad95260c70088972f400  data/empirical_diagnostics_2022_prob_prior.csv
30fe7250ca14e62b927ed6e31d4ced5a270f7ffffe5d9bac634e589ea730ecd3  data/empirical_diagnostics_2022_prob_signal.csv
18f31430e6f74761f3d13958a1220df1d756506fea0cdd21fc09b0253e1e411d  data/empirical_diagnostics_2022_prob_signal_mu0.csv
8a8091c24df4ff1c77ab3f582fa212c72ef99c71eac7e837f9c44c126088e4c3  data/empirical_robustness_2002.csv
2036747aa28bdfa9cd087b429664b94c6d69d6a36b2a5bfb8e6cff7f6085b2ec  data/empirical_robustness_2022.csv
ac84cea0f24f5194d634ddcfece4d799a7d395f4a50320eee3c7eeebf472ae25  data/empirical_runs_2002.csv
ecf2480d3d9d11f9054c2e1ff4461ad9bd3c3a439c9fcdc4de7f9b1f0abb8149  data/empirical_runs_2022.csv
a8999ef0b547448a79b894c8f242aa83bfa9a70a10eb1ab838529d92e3c8858f  data/empirical_runs_prob_prior_2002.csv
b6668f33b02c2716a0c167643e500c9f036a29ca4138683cb7763d400ec8b565  data/empirical_runs_prob_prior_2022.csv
a271871f77abdb8f1a5105e3224378f299a6ad4e526bda3ee4695aa462377521  data/empirical_runs_prob_signal_2002.csv
1a5ae59a20a91e3a616c6a998e2e294f765eec8ee73e40ff44de3aab94447100  data/empirical_runs_prob_signal_2022.csv
715ab48914094ff147509a9e80ad0fb72cb158088f0605ea276d051837741e6b  data/empirical_runs_prob_signal_mu0_2002.csv
c69e88b9c5d16c47f23941539d27cdabeea1071f8a9816044cd86a7637281fb8  data/empirical_runs_prob_signal_mu0_2022.csv
9991d7837858e201c7f97394a9f6e88a0d498dbe515c7a76f5a4407b80b1dcab  data/empirical_shared_activating_draws.csv
a7981f6c3cb9a8844b53a9107c07e660d6b07ad501505d6f4c326e55879da09a  data/empirical_shared_activating_draws_prob_prior.csv
d7f0fb2b582c2e26620a94a30260f6f7cc6c1d76ab8baa4d102012c03b9c28b8  data/empirical_shared_activating_draws_prob_signal.csv
795de0c334221ec83629eb577587c97c49034e5b7bed0ff168dbea57ea54bb7b  data/empirical_shared_activating_draws_prob_signal_mu0.csv
```

</details>

Inputs, as recorded by the driver:

```
9ca9350b0e4c301cd651cc5276ef6d4b49c9f009a8b8c7c44fdc4eb2d0f26f52  data/party_positions_2002.csv
6e7ffa22ca2bf112275b139e813895829260115a216d35d04882db2ad94b361c  data/party_positions_2022.csv
6a403b69f743751eff20fa32392e48e5deb8941c1e6d9d4ba1b92b6d3dbbf431  data/voters_ideology_2002.csv
21d35fe6b6a135d363bbf9aecf91af866fb1e080a9da4bfcd1a4193b22a2eaa1  data/voters_ideology_2022.csv
4542adf6aa19cf3ff63f965d51277aa800a8b83c9882b280a43e918483fcef59  data/polls_2002.csv
626d3a6ae747cb43df59e0ec7e6f7e5702728a4fb85dbe45359dfc508894b62e  data/polls_2022.csv
d6e795946f2e341e11d234cf302dbb10c552a97e6aa207dc6f37a327027ef78c  data/results_2002.csv
5ebba0fe404d84ede60f957b00487f7912ff6ec9c45b4b752cd6c42fa5a8b74a  data/results_2022.csv
```

Files in `data/` that this run did **not** write, and that nothing in the pipeline reads:
`empirical_*_main_prob_*.csv` (leftovers from before 2026-08-21) and
`empirical_init_benchmarks_{2002,2022}.csv` (written only by `--init-benchmarks`, not part of the
pipeline). They are from earlier inputs; do not use them.

## Known issues for the analysis

These are properties of the outputs to keep in mind, not failures of the run.

* **Starting from the nearest candidate gives centrist minor candidates large shares.** Under
  `nearest`, the largest mean final shares are Lepage (CAP21) 12.8% in 2002 and Lassalle (RES)
  21.6% in 2022, against actual results of 1.9% and 3.1%. The probabilistic starts put Chirac
  (2002) and Macron (2022) first, with mean absolute errors of 3.0–3.6 points (2002) and 4.2–6.0
  (2022), against 6.2 and 9.4 under `nearest`. `top2_acc` is 0 in every variant and both years,
  as it was in August.
* **2002 depends on the imputed positions.** Moving only the six imputed 2002 positions by up to
  ±1 point lowers the mean switching rate to 0.118, against 0.159–0.164 in the other variants,
  and mean ΔCENP to −0.010, against −0.014 to −0.023. In 2022 nothing is imputed, so that variant
  is an unperturbed run.
* **Pooled parameter importance is still not interpretable**: 5-fold CV R² −0.067 (−0.187 in
  August). Per year it is 0.819 (2002) and 0.956 (2022).
* **Every 2022 result from earlier runs used swapped polls** (see the erratum on the
  [2026-08-21 record](empirical_rerun_2026-08-21.md)); compare with them only with that in mind.

---

[← Experiments](../experiments.md) · **Rerun record** · [Reproducibility →](../reproducibility.md)
