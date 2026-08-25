# Documentation plan — outline only

Three documents to write. This file is the **structure**, not the content: no
empirical value appears here, and none should be filled in until the corrected
2002/2022 runs finish and their comparison is approved.

Status of each section is marked:

- **ready** — can be written now from committed code and tables
- **blocked** — waits on the corrected empirical reruns
- **partial** — the synthetic half is ready, the empirical half is blocked

---

## 1. ODD-style model description

Overview–Design concepts–Details, the ABM convention, so the model can be
reimplemented from the description alone.

### Overview

1.1 **Purpose and question** — ready
  Two-round strategic voting; whether the fragmentation→coordination contrast
  between 2002 and 2022 is reproducible under plausible behavioural parameters.
  State the framing explicitly: pattern-oriented calibration, not parameter
  recovery.

1.2 **Entities, state variables, scales** — ready
  Parties (ID, position on [−1, 1]); Electors (position, τ, sincere utilities,
  posterior beliefs, contender set Ca, opponent set Oa, expressive attachment
  j*, triggered flag). Scales: K candidates, N = 2000 electors, T = 25
  iterations.

1.3 **Process overview and scheduling** — ready
  Per iteration: signal → belief update → partition → strategic utilities →
  choice → tally. Record the t = 0 asymmetry explicitly: iteration 0 is the
  sincere vote, and switching and per-iteration diagnostics are only defined
  from t = 1 (pinned by `tests/test_dynamic_invariants.py`).

### Design concepts

1.4 **Basic principles** — ready. Expressive vs instrumental motivation; the
    coordination indicator G_a.
1.5 **Emergence** — ready. Coordination is not imposed; ΔCENP is the emergent
    quantity.
1.6 **Adaptation and objectives** — ready. φ_a(j) = LV·NV − μ·λ̂; the
    boundary is now pinned by a hand-calculated test.
1.7 **Sensing** — ready. Voters sense polls, not each other.
1.8 **Stochasticity** — ready. Enumerate every RNG: electorate sampling, prior
    generation, signal generation, probabilistic initialisation. Cross-reference
    the seed schemes in `analysis_map.md` §C2.
1.9 **Observation** — ready. ENP, CENP, and **the two ΔCENP baselines** — the
    distinction in `analysis_map.md` §C1 belongs here, prominently.

### Details

1.10 **Initialisation** — ready. `nearest` vs `probabilistic`; salience from
     s⁰ or from the prior; the β limits.
1.11 **Input data** — ready. Party positions, voter-ideology histograms, poll
     timelines, first-round results, per year.
1.12 **Submodels** — ready. Signal transform and θ; Dirichlet prior and ρ_π;
     belief update and α; the contender set and **the units of τ**
     (`tau_absolute = tau_hat × (2/K)`, K-dependent, so the same normalised
     tolerance is a different absolute distance per year); the perceived runoff
     share R_a(j|k); the expressive cost normalised by ℓ².

---

## 2. Verification and validation record

Verification = the code does what the equations say. Validation = the model
says something about the world. The current fiche mixes the two; this
separation should survive into the rewrite.

### 2.1 Verification — ready

| Layer | Evidence |
|---|---|
| Unit and analytic limits | `test_empirical.py`, `test_metrics.py`, `test_signals.py` |
| Decision rule and contender set | `test_decision_rule.py` — G_a, the μ boundary at 1/15, tolerance-boundary inclusion, Ca never empty |
| Metamorphic properties | `test_decision_rule.py` — relabelling invariance (all 120 permutations) and left–right reflection symmetry, both **derived from the equations, then verified**, not assumed |
| Dynamic invariants | `test_dynamic_invariants.py` — per-iteration share, index, count and alignment invariants |
| Units | `test_tau_units.py`, `test_tau_absolute_output.py` |
| Regression against past behaviour | golden-value tests in `test_empirical.py` |
| Pipeline seams | `test_pipeline_contract.py` |
| Output-schema integrity | `test_predictor_schema.py`, `test_result_tables.py` |
| Operational safety | `test_quick_run_isolation.py`, `test_sweep_resume.py` |

### 2.2 Protocol validation (synthetic) — ready

The fixed constants and what justifies each: N = 2000, T = 25, ε_s, ξ = 0.
Cite the committed tables in `results/tables/`. Carry forward the limitations
already established: configuration-specific drift, seed noise, one stochastic
realisation per Saltelli row, and caution about exact Sobol magnitudes and
close rankings.

### 2.3 Sensitivity analysis (synthetic) — ready
  Saltelli/Sobol design, its outputs, and the stated caveats. **Not** rerun —
  §2.5 records why.

### 2.4 Empirical validation — **blocked**
  Replay results, robustness variants, activation diagnostics, the ΔCENP sweep
  against the observed target, parameter importance. Every number waits.

### 2.5 Change and rerun record — partial
  The τ unit error, its scope, and the audit showing the synthetic path was a
  pure refactor. Include the standing caveat: **no archived raw
  before-versus-after comparison of the main replay exists**, because the
  pre-fix full outputs were overwritten on 2026-08-19 and were never committed.
  One could be regenerated from commit `70e23f5` under the fixed seed, but has
  not been. Ready to write now except for the after-side numbers.

### 2.6 Reproducibility — ready
  Python version, `requirements.txt`, seeds, the exact commands
  (`docs/rerun_manifest.md`), CI status, and the archive's SHA-256 manifest.
  Note honestly that the LHS importance table is reproducible to ~1e-16 but not
  byte-identical: joblib's parallel reduction order is not fixed, so the last
  bit of a double moves between runs while rankings do not.

---

## 3. Empirical pipeline and output dependency map

One page a reader can use to answer "if I change X, what has to be rerun?"

3.1 **Stage diagram** — ready
  `raw data → replay → {diagnostics, figures}` and
  `raw data → sweep → {comparison, importance}`, with every script named.

3.2 **Artifact table** — ready
  For each output: producing command, inputs, row count, whether it is
  committed or git-ignored, and its consumers.

3.3 **Dependency rules** — ready
  Which changes invalidate which outputs. The worked example is the τ fix:
  every empirical output stale, the whole synthetic layer untouched, and the
  audit that established the difference.

3.4 **Provenance conventions** — ready
  Both τ units plus K recorded in every row; the derived value read back from
  the object that used it rather than recomputed (`analysis_map.md` §B4); the
  sweep's `_meta.json` sidecar and design fingerprint.

3.5 **Operational notes** — ready
  `data/smoke/` vs `data/`; the refusal to shrink an output; `--resume` and
  what it validates; `tools/validate_rerun.py` after every stage; the archive.

3.6 **Current numbers** — **blocked**

---

## Writing order

1. §3 and §1 — neither depends on the reruns.
2. §2.1–§2.3, §2.6 — verification and the synthetic record.
3. §2.5 before-side — the change record, minus the after numbers.
4. **Reruns.**
5. §2.4, §2.5 after-side, §3.6, then the fiche rewrite.
