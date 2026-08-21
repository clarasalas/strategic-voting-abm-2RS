#!/usr/bin/env bash
#
# run_empirical_rerun.sh -- the corrected empirical rerun, start to finish.
#
# Implements docs/rerun_manifest.md.  Runs unattended: every step is logged,
# every stage is validated before the stages that depend on it, and any failure
# stops the pipeline rather than letting downstream steps run on bad input.
#
#   usage:  tools/run_empirical_rerun.sh
#
# Intended to be launched detached, under caffeinate, so it survives the
# terminal closing and the machine does not sleep mid-run.

set -o errexit
set -o nounset
set -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# The launcher may fix the stamp so it knows the log directory in advance.
STAMP="${RERUN_STAMP:-$(date +%Y%m%d_%H%M%S)}"
LOGDIR="$REPO/logs/rerun_$STAMP"
mkdir -p "$LOGDIR"

# This script's own PID, for monitoring and for stopping it deliberately.
echo $$ > "$LOGDIR/rerun.pid"

MASTER="$LOGDIR/master.log"
COMMIT="$(git rev-parse HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# --------------------------------------------------------------------------- #
#  Run metadata -- written before anything else, so the log identifies the
#  exact code that produced the outputs even if the run later fails.
# --------------------------------------------------------------------------- #
cat > "$LOGDIR/run_metadata.json" <<META
{
  "started_utc":   "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "started_local": "$(date '+%Y-%m-%d %H:%M:%S %Z')",
  "commit":        "$COMMIT",
  "branch":        "$BRANCH",
  "remote":        "$(git config --get remote.origin.url)",
  "python":        "$(python3 --version 2>&1)",
  "host":          "$(hostname)",
  "log_dir":       "$LOGDIR",
  "pid":           $$,
  "manifest":      "docs/rerun_manifest.md",
  "archive":       "data/archive/pre_rerun_2026-08-21",
  "expected_simulations": 14000,
  "steps": {
    "01_replay_nearest":     {"draws": 300, "robust_draws": 100, "sims": 1200},
    "02_prob_variants":      {"draws": 800, "variants": 3,       "sims": 4800},
    "03_sweeps":             {"n_draws": 1000, "n_repeats": 4,   "sims": 8000},
    "04_diagnostics":        {"sims": 0},
    "05_figures":            {"sims": 0},
    "06_compare":            {"sims": 0},
    "07_lhs_importance":     {"sims": 0}
  },
  "planned_outputs": [
    "data/empirical_runs_{2002,2022}.csv",
    "data/empirical_candidate_shares_{2002,2022}.csv",
    "data/empirical_candidate_draws_{2002,2022}.csv",
    "data/empirical_robustness_{2002,2022}.csv",
    "data/empirical_runs_prob_{signal,prior,signal_mu0}_{2002,2022}.csv",
    "data/empirical_candidate_shares_prob_*_{2002,2022}.csv",
    "data/empirical_candidate_draws_prob_*_{2002,2022}.csv",
    "data/behavioral_sweep_{2002,2022}.csv",
    "data/behavioral_sweep_{2002,2022}_design.csv",
    "data/behavioral_sweep_{2002,2022}_meta.json",
    "data/empirical_diagnostics_*.csv",
    "data/empirical_activation_summary_*.csv",
    "data/empirical_shared_activating_draws_*.csv",
    "data/behavioral_compare_2002_2022.csv",
    "figures/*.png",
    "figures/*.pdf",
    "results/tables/lhs_parameter_importance.csv"
  ]
}
META

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$MASTER"; }

# Run one step: tee to its own log, keep PYTHON's exit status (not tee's), and
# abort the whole pipeline if it is non-zero so nothing downstream runs on bad
# input.  pipefail alone would suffice; PIPESTATUS is read as well so the
# failing step can be named in the master log.
run() {
    local name="$1"; shift
    local step_log="$LOGDIR/${name}.log"
    log "START  $name"
    log "       $*"
    set +o errexit
    "$@" 2>&1 | tee -a "$step_log"
    local status=${PIPESTATUS[0]}
    set -o errexit
    if [ "$status" -ne 0 ]; then
        log "FAILED $name (exit $status) -- stopping; dependent steps not run."
        echo "FAILED at $name (exit $status) $(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
            > "$LOGDIR/FAILED"
        exit "$status"
    fi
    log "OK     $name"
}

trap 'log "ABORTED (signal or error) at $(date -u "+%Y-%m-%dT%H:%M:%SZ")"' ERR

log "=========================================================="
log "Corrected empirical rerun"
log "  commit   $COMMIT"
log "  branch   $BRANCH"
log "  logs     $LOGDIR"
log "  expected 14,000 simulations, ~8 h 40 min"
log "=========================================================="

V=tools/validate_rerun.py

# =========================================================================== #
#  STEP 1 -- empirical replay, nearest-party baseline                          #
#  300 main draws/year + 100 draws x 3 robustness variants/year = 1,200 sims   #
# =========================================================================== #
run 01_replay_nearest \
    python3 analysis/empirical/empirical_2002_2022.py --overwrite

run 01_check_runs_2002 \
    python3 $V data/empirical_runs_2002.csv \
        --year 2002 --expect-rows 300 --log "$LOGDIR/01_replay_nearest.log"
run 01_check_runs_2022 \
    python3 $V data/empirical_runs_2022.csv \
        --year 2022 --expect-rows 300 --log "$LOGDIR/01_replay_nearest.log"
run 01_check_robust_2002 \
    python3 $V data/empirical_robustness_2002.csv --year 2002 --expect-rows 300
run 01_check_robust_2022 \
    python3 $V data/empirical_robustness_2022.csv --year 2022 --expect-rows 300
run 01_check_draws_2002 \
    python3 $V data/empirical_candidate_draws_2002.csv \
        --year 2002 --expect-rows 4500
run 01_check_draws_2022 \
    python3 $V data/empirical_candidate_draws_2022.csv \
        --year 2022 --expect-rows 3600

# =========================================================================== #
#  STEP 2 -- probabilistic-initialisation variants, 800 draws each             #
#  800 x 2 years x 3 variants = 4,800 sims                                     #
# =========================================================================== #
run 02a_prob_signal \
    python3 analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source signal \
        --draws 800 --overwrite
run 02b_prob_prior \
    python3 analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source prior \
        --draws 800 --overwrite
run 02c_prob_signal_mu0 \
    python3 analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source signal --mu-zero \
        --draws 800 --overwrite

for v in signal prior signal_mu0; do
    for y in 2002 2022; do
        run "02_check_${v}_${y}" \
            python3 $V "data/empirical_runs_prob_${v}_${y}.csv" \
                --year "$y" --expect-rows 800
    done
done

# =========================================================================== #
#  STEP 3 -- behavioural sweeps (the long one)                                 #
#  1000 draws x 4 repeats x 2 years = 8,000 sims, ~7 h                         #
#                                                                              #
#  --overwrite here is the INITIAL replacement of the archived June outputs.   #
#  If a sweep is interrupted, resume it by hand with the same arguments and    #
#  --resume in place of --overwrite -- never both.                             #
# =========================================================================== #
run 03a_sweep_2002 \
    python3 analysis/empirical/behavioral_sweep.py \
        --year 2002 --n_draws 1000 --n_repeats 4 --seed 20020422 --overwrite
run 03_check_sweep_2002 \
    python3 $V data/behavioral_sweep_2002.csv \
        --year 2002 --expect-rows 1000 --log "$LOGDIR/03a_sweep_2002.log"

run 03b_sweep_2022 \
    python3 analysis/empirical/behavioral_sweep.py \
        --year 2022 --n_draws 1000 --n_repeats 4 --seed 20020422 --overwrite
run 03_check_sweep_2022 \
    python3 $V data/behavioral_sweep_2022.csv \
        --year 2022 --expect-rows 1000 --log "$LOGDIR/03b_sweep_2022.log"

# =========================================================================== #
#  STEP 4-7 -- derived outputs (no simulation)                                 #
# =========================================================================== #
run 04a_diag_nearest \
    python3 analysis/empirical/empirical_diagnostics.py
run 04b_diag_prob_signal \
    python3 analysis/empirical/empirical_diagnostics.py --tag prob_signal
run 04c_diag_prob_prior \
    python3 analysis/empirical/empirical_diagnostics.py --tag prob_prior
run 04d_diag_prob_signal_mu0 \
    python3 analysis/empirical/empirical_diagnostics.py --tag prob_signal_mu0

run 05_figures \
    python3 analysis/empirical/empirical_figures.py

run 06a_compare \
    python3 analysis/empirical/behavioral_compare.py
run 06b_sweep_figure \
    python3 analysis/empirical/behavioral_sweep_figure.py

run 07_lhs_importance \
    python3 analysis/empirical/lhs_importance.py

# =========================================================================== #
#  STEP 8 -- final checks                                                      #
# =========================================================================== #
run 08a_pytest \
    python3 -m pytest -ra

run 08b_archive_intact \
    bash -c 'cd data/archive/pre_rerun_2026-08-21 && shasum -c SHA256SUMS --quiet && echo "archive intact"'

log "=========================================================="
log "COMPLETE  commit $COMMIT"
log "=========================================================="
cat > "$LOGDIR/COMPLETE" <<DONE
finished_utc $(date -u '+%Y-%m-%dT%H:%M:%SZ')
commit       $COMMIT
DONE
