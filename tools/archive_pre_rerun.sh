#!/usr/bin/env bash
#
# archive_pre_rerun.sh -- snapshot the current empirical evidence before a rerun.
#
# A rerun overwrites every empirical output in data/.  This takes a
# checksummed, read-only copy of what exists first.  (First written for the
# 2026-08-21 rerun after the tau_hat -> tau_absolute fix; its archive is
# data/archive/pre_rerun_2026-08-21/.)
#
# It is deliberately a copy rather than a git commit: data/ and figures/ are
# git-ignored on purpose (bulky, regenerable), and the archive inherits that.
#
#   usage:  tools/archive_pre_rerun.sh [STAMP] [FICHE_HTML] [NOTE_MD]
#
#           STAMP        archive name under data/archive/  (default: today)
#           FICHE_HTML   exported copy of the fiche technique, if available
#                        ("" to skip)
#           NOTE_MD      markdown describing what the archived outputs are and
#                        what they can support; copied into INVENTORY.md
#
# Nothing is deleted or modified: the script only reads the working tree and
# writes under data/archive/<STAMP>/.

set -o errexit
set -o nounset
set -o pipefail

STAMP="${1:-pre_rerun_$(date +%Y-%m-%d)}"
FICHE_SRC="${2:-}"
NOTE_SRC="${3:-}"
if [ -n "$NOTE_SRC" ] && [ ! -f "$NOTE_SRC" ]; then
    echo "Note file not found: $NOTE_SRC" >&2
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$REPO/data/archive/$STAMP"

if [ -e "$DEST" ]; then
    echo "Refusing to overwrite an existing archive: $DEST" >&2
    echo "Pass a different STAMP, or move the old one aside." >&2
    exit 1
fi

echo "==> archiving into $DEST"
mkdir -p "$DEST"/{data,logs,figures,results/tables,fiche}

# --- 1. raw empirical / behavioural / sweep CSVs ---------------------------
# These are the outputs the rerun will replace.
copied_data=0
# The sweeps' *_meta.json sidecars carry the design fingerprint --resume checks.
for pattern in 'empirical_*.csv' 'behavioral_*.csv' 'sweep_*.csv' 'behavioral_*.json'; do
    while IFS= read -r -d '' f; do
        cp -p "$f" "$DEST/data/"
        copied_data=$((copied_data + 1))
    done < <(find "$REPO/data" -maxdepth 1 -name "$pattern" -type f -print0)
done
echo "    data/      $copied_data file(s)"

# --- 2. run logs ------------------------------------------------------------
# The pre-fix logs are the only surviving direct evidence of the bug: they
# carry the "tau >= 2.0" UserWarnings that the corrected runs must not emit.
copied_logs=0
while IFS= read -r -d '' f; do
    cp -p "$f" "$DEST/logs/"
    copied_logs=$((copied_logs + 1))
done < <(find "$REPO" -maxdepth 1 -name '*.log' -type f -print0)
# per-run driver logs (logs/<run>/), kept under their run name
if [ -d "$REPO/logs" ]; then
    while IFS= read -r -d '' d; do
        cp -Rp "$d" "$DEST/logs/"
        copied_logs=$((copied_logs + $(find "$d" -type f | wc -l)))
    done < <(find "$REPO/logs" -mindepth 1 -maxdepth 1 -type d -print0)
fi
echo "    logs/      $copied_logs log(s)"

# --- 3. figures -------------------------------------------------------------
# Every figure in figures/ is downstream of the empirical layer.
copied_figs=0
if [ -d "$REPO/figures" ]; then
    while IFS= read -r -d '' f; do
        cp -p "$f" "$DEST/figures/"
        copied_figs=$((copied_figs + 1))
    done < <(find "$REPO/figures" -maxdepth 1 -type f -print0)
fi
echo "    figures/   $copied_figs file(s)"

# --- 4. committed result tables --------------------------------------------
# These are in git, so this copy is for convenience rather than safety.
copied_tables=0
if [ -d "$REPO/results/tables" ]; then
    while IFS= read -r -d '' f; do
        cp -p "$f" "$DEST/results/tables/"
        copied_tables=$((copied_tables + 1))
    done < <(find "$REPO/results/tables" -maxdepth 1 -type f -print0)
fi
echo "    results/   $copied_tables table(s)"

# --- 5. fiche technique snapshot -------------------------------------------
fiche_note="NOT CAPTURED -- no export supplied"
if [ -n "$FICHE_SRC" ] && [ -f "$FICHE_SRC" ]; then
    cp -p "$FICHE_SRC" "$DEST/fiche/fiche_technique_$STAMP.html"
    fiche_note="fiche/fiche_technique_$STAMP.html"
    echo "    fiche/     1 snapshot"
else
    echo "    fiche/     none supplied"
fi

# --- 6. manifest ------------------------------------------------------------
# Paths are relative to the archive root so `shasum -c` works from there.
cd "$DEST"
find . -type f ! -name SHA256SUMS ! -name INVENTORY.md -print0 \
    | sort -z \
    | xargs -0 shasum -a 256 > SHA256SUMS
n_files=$(wc -l < SHA256SUMS | tr -d ' ')
echo "==> SHA256SUMS: $n_files file(s)"

# --- 7. inventory -----------------------------------------------------------
{
    echo "# Pre-rerun evidence archive -- $STAMP"
    echo
    echo "Snapshot of the empirical layer taken immediately before a rerun."
    echo "Read-only; git-ignored; never committed."
    echo
    echo "Repository state at capture time:"
    echo
    echo '```'
    echo "commit   $(git -C "$REPO" rev-parse HEAD)"
    echo "branch   $(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
    echo "captured $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo '```'
    echo
    echo "## Contents"
    echo
    echo "| Directory | Files | What it holds |"
    echo "|---|---:|---|"
    echo "| \`data/\` | $copied_data | Raw empirical, probabilistic-variant, diagnostics and behavioural-sweep CSVs |"
    echo "| \`logs/\` | $copied_logs | Root-level run logs and per-run driver logs (logs/<run>/) |"
    echo "| \`figures/\` | $copied_figs | Every empirical and behavioural figure (PNG + PDF) |"
    echo "| \`results/tables/\` | $copied_tables | Committed summary tables (also in git) |"
    echo "| \`fiche/\` | - | $fiche_note |"
    echo
    echo "Total: $n_files files, listed with SHA-256 digests in \`SHA256SUMS\`."
    echo
    echo "## Verifying"
    echo
    echo '```'
    echo "cd data/archive/$STAMP && shasum -c SHA256SUMS"
    echo '```'
    echo
    if [ -n "$NOTE_SRC" ]; then
        echo "## What this archive holds"
        echo
        cat "$NOTE_SRC"
    fi
} > INVENTORY.md

# --- 8. verify --------------------------------------------------------------
echo "==> verifying"
if shasum -c SHA256SUMS --quiet; then
    echo "==> OK: $n_files file(s) verified in $DEST"
else
    echo "==> CHECKSUM VERIFICATION FAILED" >&2
    exit 1
fi
