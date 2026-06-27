#!/bin/bash
# =============================================================================
#  git_autosync.sh  —  leak-gated auto commit & push for your GitHub projects
# -----------------------------------------------------------------------------
#  For each repo listed in autosync_repos.txt it will:
#     1. stage all changes (respecting .gitignore)
#     2. SCAN with gitleaks  ->  if any secret is found, that repo is BLOCKED
#        (nothing is committed or pushed) and the run is flagged.
#     3. if clean: commit (auto message) and push to GitHub.
#
#  Usage:
#     ./git_autosync.sh              # sync everything in the config
#     ./git_autosync.sh --dry-run    # scan + report only, never commit/push
#     ./git_autosync.sh --repo NAME  # just one repo from the config
#
#  Config file:  autosync_repos.txt  (one repo per line; name, ~path or /path)
#  Logs:         logs/autosync_YYYYMMDD.log
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${AUTOSYNC_CONFIG:-$SCRIPT_DIR/autosync_repos.txt}"
LOG_DIR="$SCRIPT_DIR/logs"
LAB_ACTIVE="${LAB_ACTIVE:-$HOME/Documents/lab/active}"
GITLEAKS="${GITLEAKS_CMD:-gitleaks}"
DRY_RUN=0
ONLY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --repo)    ONLY="${2:-}"; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
  shift
done

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/autosync_$(date +%Y%m%d).log"
ts(){ date '+%Y-%m-%d %H:%M:%S'; }
log(){ echo "$(ts) | $*" | tee -a "$LOG"; }
rule(){ echo "---------------------------------------------" | tee -a "$LOG"; }

log "=== git_autosync start (dry-run=$DRY_RUN) ==="

# --- preflight -------------------------------------------------------------
if ! command -v "$GITLEAKS" >/dev/null 2>&1; then
  log "ERROR: gitleaks not found on PATH."
  log "       Install it once with:  brew install gitleaks"
  exit 1
fi
log "gitleaks: $("$GITLEAKS" version 2>/dev/null | head -1)"

if [ ! -f "$CONFIG" ]; then
  log "ERROR: config file not found: $CONFIG"
  exit 1
fi

resolve_repo(){
  local p="$1"
  case "$p" in
    /*) printf '%s' "$p" ;;
    "~"*) printf '%s' "${p/#\~/$HOME}" ;;
    *)  printf '%s' "$LAB_ACTIVE/$p" ;;
  esac
}

# Run a gitleaks scan. Returns: 0 = clean, 1 = LEAK found, 2 = tool error.
# Tries modern subcommand first, falls back to legacy for older gitleaks.
scan_staged(){
  local dir="$1" rc
  "$GITLEAKS" git --staged --no-banner --redact "$dir" >>"$LOG" 2>&1; rc=$?
  if [ $rc -ge 2 ]; then
    "$GITLEAKS" protect --staged --no-banner --redact --source "$dir" >>"$LOG" 2>&1; rc=$?
  fi
  return $rc
}
scan_history(){
  local dir="$1" rc
  "$GITLEAKS" git --no-banner --redact "$dir" >>"$LOG" 2>&1; rc=$?
  if [ $rc -ge 2 ]; then
    "$GITLEAKS" detect --no-banner --redact --source "$dir" >>"$LOG" 2>&1; rc=$?
  fi
  return $rc
}

declare -a SUMMARY
N_SYNCED=0; N_BLOCKED=0; N_SKIP=0; N_NOOP=0; N_ERR=0

process_repo(){
  local entry="$1"
  local dir name branch rc
  dir="$(resolve_repo "$entry")"
  name="$(basename "$dir")"
  rule
  log "REPO: $name  ($dir)"

  if [ ! -d "$dir/.git" ]; then
    log "  SKIP: not a git repository"
    SUMMARY+=("SKIP    $name  (not a git repo)"); N_SKIP=$((N_SKIP+1)); return
  fi
  rm -f "$dir/.git/index.lock" 2>/dev/null
  cd "$dir" || { log "  SKIP: cannot cd"; SUMMARY+=("SKIP    $name  (cd failed)"); N_SKIP=$((N_SKIP+1)); return; }

  if ! git remote get-url origin >/dev/null 2>&1; then
    log "  SKIP: no 'origin' remote (run the GitHub setup script first)"
    SUMMARY+=("SKIP    $name  (no GitHub remote)"); N_SKIP=$((N_SKIP+1)); return
  fi

  git add -A

  # ---- THE GATE ----
  log "  scanning for secrets..."
  scan_staged "$dir"; rc=$?
  if [ $rc -eq 1 ]; then
    log "  BLOCKED: gitleaks found a secret in your changes. Nothing committed or pushed."
    git reset -q 2>/dev/null
    SUMMARY+=("BLOCKED $name  (secret in changes - see log)"); N_BLOCKED=$((N_BLOCKED+1)); return
  elif [ $rc -ge 2 ]; then
    log "  ERROR: gitleaks failed to run on staged changes. Skipping for safety."
    git reset -q 2>/dev/null
    SUMMARY+=("ERROR   $name  (scanner error)"); N_ERR=$((N_ERR+1)); return
  fi
  scan_history "$dir"; rc=$?
  if [ $rc -eq 1 ]; then
    log "  BLOCKED: a secret exists in this repo's git HISTORY. Refusing to push."
    log "           Clean the history before publishing (see README)."
    git reset -q 2>/dev/null
    SUMMARY+=("BLOCKED $name  (secret in history - see log)"); N_BLOCKED=$((N_BLOCKED+1)); return
  elif [ $rc -ge 2 ]; then
    log "  ERROR: gitleaks failed on history. Skipping for safety."
    git reset -q 2>/dev/null
    SUMMARY+=("ERROR   $name  (scanner error)"); N_ERR=$((N_ERR+1)); return
  fi
  log "  clean ."

  branch="$(git branch --show-current)"
  branch="${branch:-main}"

  if [ "$DRY_RUN" -eq 1 ]; then
    if git diff --cached --quiet; then
      log "  DRY-RUN: clean, nothing to commit."
      SUMMARY+=("OK      $name  (dry-run: nothing to commit)")
    else
      log "  DRY-RUN: would commit & push these staged changes:"
      git diff --cached --name-status | sed 's/^/      /' | tee -a "$LOG"
      SUMMARY+=("OK      $name  (dry-run: would sync)")
    fi
    git reset -q 2>/dev/null
    N_NOOP=$((N_NOOP+1)); return
  fi

  # ---- commit (only if there is something staged) ----
  if git diff --cached --quiet; then
    log "  no file changes to commit."
  else
    git commit -q -m "autosync: $(ts)" && log "  committed changes."
  fi

  # ---- push (covers new commit AND any earlier unpushed commits) ----
  if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    if git push >>"$LOG" 2>&1; then log "  pushed to origin/$branch."; SUMMARY+=("SYNCED  $name"); N_SYNCED=$((N_SYNCED+1))
    else log "  ERROR: push failed (see log)."; SUMMARY+=("ERROR   $name  (push failed)"); N_ERR=$((N_ERR+1)); fi
  else
    if git push -u origin "$branch" >>"$LOG" 2>&1; then log "  pushed & set upstream origin/$branch."; SUMMARY+=("SYNCED  $name"); N_SYNCED=$((N_SYNCED+1))
    else log "  ERROR: push failed (see log)."; SUMMARY+=("ERROR   $name  (push failed)"); N_ERR=$((N_ERR+1)); fi
  fi
}

# --- iterate config --------------------------------------------------------
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%%#*}"; line="$(echo "$line" | xargs)"   # strip comments + trim
  [ -z "$line" ] && continue
  if [ -n "$ONLY" ] && [ "$(basename "$(resolve_repo "$line")")" != "$ONLY" ]; then continue; fi
  process_repo "$line"
done < "$CONFIG"

# --- summary ---------------------------------------------------------------
rule
log "SUMMARY:"
for s in "${SUMMARY[@]:-}"; do [ -n "$s" ] && log "   $s"; done
log "synced=$N_SYNCED blocked=$N_BLOCKED skipped=$N_SKIP errors=$N_ERR noop=$N_NOOP"
log "=== git_autosync end ==="

# non-zero exit if anything was blocked or errored (so failures are visible)
[ $((N_BLOCKED + N_ERR)) -eq 0 ]
