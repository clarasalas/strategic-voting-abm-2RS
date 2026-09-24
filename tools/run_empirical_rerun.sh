#!/usr/bin/env bash
#
# run_empirical_rerun.sh -- the corrected empirical rerun, start to finish.
#
# Implements docs/rerun_manifest.md.  Runs unattended: every step is logged,
# every stage is validated before the stages that depend on it, and any failure
# stops the pipeline rather than letting downstream steps run on bad input.
#
#   usage:  RUN_NAME=<name> RERUN_ARCHIVE=<dir> tools/run_empirical_rerun.sh
#
#   RUN_NAME       names the run; logs go to logs/<RUN_NAME>/
#                  (default: rerun_<timestamp>)
#   RERUN_ARCHIVE  the archive of the previous outputs, taken with
#                  tools/archive_pre_rerun.sh BEFORE this run; the last step
#                  verifies it is still intact.  Required: a run that has not
#                  archived what it will overwrite does not start.
#   RERUN_SMOKE=1  the same commands at a few draws each, for checking the
#                  pipeline end to end (in a scratch worktree, not in the
#                  checkout that holds real outputs)
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
RUN_NAME="${RUN_NAME:-rerun_$STAMP}"
ARCHIVE="${RERUN_ARCHIVE:?set RERUN_ARCHIVE to the archive taken before this run}"
SMOKE="${RERUN_SMOKE:-0}"
LOGDIR="$REPO/logs/$RUN_NAME"
if [ -e "$LOGDIR" ]; then
    echo "Refusing to reuse an existing run directory: $LOGDIR" >&2
    exit 1
fi
if [ ! -f "$REPO/$ARCHIVE/SHA256SUMS" ]; then
    echo "No archive at $ARCHIVE (missing SHA256SUMS).  Run" >&2
    echo "tools/archive_pre_rerun.sh first; it is what keeps the previous" >&2
    echo "outputs after this run overwrites them." >&2
    exit 1
fi
mkdir -p "$LOGDIR"

# Draw counts.  The smoke run uses the same commands at a few draws each.
if [ "$SMOKE" = "1" ]; then
    N_MAIN=6;  N_ROBUST=3;  N_PROB=6;  N_SWEEP=8;  N_REP=2
else
    N_MAIN=300; N_ROBUST=100; N_PROB=800; N_SWEEP=1000; N_REP=4
fi
N_VARIANTS=4                       # robustness variants in empirical_2002_2022.py
K_2002=15; K_2022=12
SIMS=$(( 2 * N_MAIN + 2 * N_ROBUST * N_VARIANTS + 3 * 2 * N_PROB + 2 * N_SWEEP * N_REP ))

# Hashes of every input the pipeline reads, so the run records exactly which
# party positions, electorates, polls and results it used.
INPUT_HASHES="$(cd "$REPO" && shasum -a 256 \
    data/party_positions_{2002,2022}.csv data/voters_ideology_{2002,2022}.csv \
    data/polls_{2002,2022}.csv data/results_{2002,2022}.csv)"
echo "$INPUT_HASHES" > "$LOGDIR/inputs.sha256"

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
  "run_name":      "$RUN_NAME",
  "smoke":         $([ "$SMOKE" = "1" ] && echo true || echo false),
  "dirty_tree":    $([ -n "$(git status --porcelain --untracked-files=no)" ] && echo true || echo false),
  "manifest":      "docs/rerun_manifest.md",
  "archive":       "$ARCHIVE",
  "inputs_sha256": "logs/$RUN_NAME/inputs.sha256",
  "seeds":         {"replay_master": 20020422, "sweep": 20020422, "lhs_importance": 42},
  "expected_simulations": $SIMS,
  "steps": {
    "01_replay_nearest":     {"draws": $N_MAIN, "robust_draws": $N_ROBUST, "robust_variants": $N_VARIANTS},
    "02_prob_variants":      {"draws": $N_PROB, "variants": 3},
    "03_sweeps":             {"n_draws": $N_SWEEP, "n_repeats": $N_REP},
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
log "Empirical rerun: $RUN_NAME$([ "$SMOKE" = "1" ] && echo '  (SMOKE)')"
log "  commit   $COMMIT"
log "  branch   $BRANCH"
log "  logs     $LOGDIR"
log "  archive  $ARCHIVE"
log "  expected $SIMS simulations"
log "=========================================================="

V=tools/validate_rerun.py

# =========================================================================== #
#  STEP 1 -- empirical replay, nearest-party baseline                          #
#  main draws/year + robustness draws x 4 variants/year                        #
# =========================================================================== #
run 01_replay_nearest \
    python3 analysis/empirical/empirical_2002_2022.py \
        --draws $N_MAIN --robust-draws $N_ROBUST --overwrite

run 01_check_runs_2002 \
    python3 $V data/empirical_runs_2002.csv \
        --year 2002 --expect-rows $N_MAIN --log "$LOGDIR/01_replay_nearest.log"
run 01_check_runs_2022 \
    python3 $V data/empirical_runs_2022.csv \
        --year 2022 --expect-rows $N_MAIN --log "$LOGDIR/01_replay_nearest.log"
run 01_check_robust_2002 \
    python3 $V data/empirical_robustness_2002.csv --year 2002 \
        --expect-rows $(( N_ROBUST * N_VARIANTS ))
run 01_check_robust_2022 \
    python3 $V data/empirical_robustness_2022.csv --year 2022 \
        --expect-rows $(( N_ROBUST * N_VARIANTS ))
run 01_check_draws_2002 \
    python3 $V data/empirical_candidate_draws_2002.csv \
        --year 2002 --expect-rows $(( N_MAIN * K_2002 ))
run 01_check_draws_2022 \
    python3 $V data/empirical_candidate_draws_2022.csv \
        --year 2022 --expect-rows $(( N_MAIN * K_2022 ))

# =========================================================================== #
#  STEP 2 -- probabilistic-initialisation variants                            #
#  N_PROB draws x 2 years x 3 variants (full run: 800 -> 4,800 sims)           #
# =========================================================================== #
run 02a_prob_signal \
    python3 analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source signal \
        --draws $N_PROB --overwrite
run 02b_prob_prior \
    python3 analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source prior \
        --draws $N_PROB --overwrite
run 02c_prob_signal_mu0 \
    python3 analysis/empirical/empirical_2002_2022.py \
        --sincere-init probabilistic --salience-source signal --mu-zero \
        --draws $N_PROB --overwrite

for v in signal prior signal_mu0; do
    for y in 2002 2022; do
        run "02_check_${v}_${y}" \
            python3 $V "data/empirical_runs_prob_${v}_${y}.csv" \
                --year "$y" --expect-rows $N_PROB
    done
done

# =========================================================================== #
#  STEP 3 -- behavioural sweeps (the long one)                                 #
#  N_SWEEP draws x N_REP repeats x 2 years (full run: 8,000 sims, ~3 h)       #
#                                                                              #
#  --overwrite here is the INITIAL replacement of the archived outputs.        #
#  If a sweep is interrupted, resume it by hand with the same arguments and    #
#  --resume in place of --overwrite -- never both.                             #
# =========================================================================== #
run 03a_sweep_2002 \
    python3 analysis/empirical/behavioral_sweep.py \
        --year 2002 --n_draws $N_SWEEP --n_repeats $N_REP --seed 20020422 --overwrite
run 03_check_sweep_2002 \
    python3 $V data/behavioral_sweep_2002.csv \
        --year 2002 --expect-rows $N_SWEEP --log "$LOGDIR/03a_sweep_2002.log"

run 03b_sweep_2022 \
    python3 analysis/empirical/behavioral_sweep.py \
        --year 2022 --n_draws $N_SWEEP --n_repeats $N_REP --seed 20020422 --overwrite
run 03_check_sweep_2022 \
    python3 $V data/behavioral_sweep_2022.csv \
        --year 2022 --expect-rows $N_SWEEP --log "$LOGDIR/03b_sweep_2022.log"

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
#  STEP 8 -- final checks and derived tables                                   #
# =========================================================================== #
# The demo page's France 2022 preset replays the empirical inputs, so it is
# recomputed here; the suite below checks it against the inputs.
run 08a_demo_preset \
    python3 demo/precompute.py --preset-only --force

run 08b_pytest \
    python3 -m pytest -ra

# Regenerates results/tables/ from this run's outputs.  With new inputs the
# tables are EXPECTED to change: review and commit them, then run
# tools/check_tables_reproduce.py on the committed state -- that check fails
# by design while regenerated tables are still uncommitted.
run 08c_make_tables \
    python3 analysis/empirical/make_empirical_tables.py

run 08d_archive_intact \
    bash -c "cd '$ARCHIVE' && shasum -c SHA256SUMS --quiet && echo 'archive intact'"

log "=========================================================="
log "COMPLETE  commit $COMMIT"
log "=========================================================="
cat > "$LOGDIR/COMPLETE" <<DONE
finished_utc $(date -u '+%Y-%m-%dT%H:%M:%SZ')
commit       $COMMIT
DONE
