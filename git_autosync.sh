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
#     ./git_autosync.sh --repo NAME --create-remote public|private
#                                     # for a repo with no GitHub remote yet:
#                                     # gate it first, then create the GitHub
#                                     # repo and push, instead of skipping.
#
#  Config file:  autosync_repos.txt  (one repo per line; name, ~path or /path)
#  Logs:         logs/autosync_YYYYMMDD.log
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${AUTOSYNC_CONFIG:-$SCRIPT_DIR/autosync_repos.txt}"
LOG_DIR="${AUTOSYNC_LOG_DIR:-$SCRIPT_DIR/logs}"
STATE_DIR="${AUTOSYNC_STATE_DIR:-$SCRIPT_DIR}"
LAB_ACTIVE="${LAB_ACTIVE:-$HOME/Documents/lab/active}"
GITLEAKS="${GITLEAKS_CMD:-gitleaks}"
GH="${GH_CMD:-gh}"
DRY_RUN=0
ONLY=""
CREATE_REMOTE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --repo)    ONLY="${2:-}"; shift ;;
    --create-remote) CREATE_REMOTE="${2:-}"; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
  shift
done

if [ -n "$CREATE_REMOTE" ]; then
  case "$CREATE_REMOTE" in
    public|private) ;;
    *) echo "--create-remote must be 'public' or 'private', got: $CREATE_REMOTE"; exit 2 ;;
  esac
  if [ -z "$ONLY" ]; then
    echo "--create-remote requires --repo NAME (only create one remote at a time)"; exit 2
  fi
fi

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

if [ -n "$CREATE_REMOTE" ] && ! command -v "$GH" >/dev/null 2>&1; then
  log "ERROR: gh (GitHub CLI) not found on PATH. Needed for --create-remote."
  exit 1
fi

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
# --verbose prints File:/RuleID:/Line: per finding (secret value still
# redacted) so the GUI can show *what* tripped the gate without opening the
# log file. Piped through tee (not >>) so it also reaches stdout — pipefail
# (set above) keeps gitleaks' real exit code, not tee's.
scan_staged(){
  local dir="$1" rc
  "$GITLEAKS" git --staged --no-banner --redact --verbose "$dir" 2>&1 | tee -a "$LOG"; rc=$?
  if [ $rc -ge 2 ]; then
    "$GITLEAKS" protect --staged --no-banner --redact --verbose --source "$dir" 2>&1 | tee -a "$LOG"; rc=$?
  fi
  return $rc
}
scan_history(){
  local dir="$1" rc
  "$GITLEAKS" git --no-banner --redact --verbose "$dir" 2>&1 | tee -a "$LOG"; rc=$?
  if [ $rc -ge 2 ]; then
    "$GITLEAKS" detect --no-banner --redact --verbose --source "$dir" 2>&1 | tee -a "$LOG"; rc=$?
  fi
  return $rc
}

declare -a SUMMARY
N_SYNCED=0; N_BLOCKED=0; N_SKIP=0; N_NOOP=0; N_ERR=0

process_repo(){
  local entry="$1"
  local dir name branch rc needs_create=0
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
    if [ -n "$CREATE_REMOTE" ] && [ "$name" = "$ONLY" ]; then
      log "  no 'origin' remote yet — will create a $CREATE_REMOTE GitHub repo after the gate clears."
      needs_create=1
    else
      log "  SKIP: no 'origin' remote (run the GitHub setup script first)"
      SUMMARY+=("SKIP    $name  (no GitHub remote)"); N_SKIP=$((N_SKIP+1)); return
    fi
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
    if [ "$needs_create" -eq 1 ]; then
      log "  DRY-RUN: would create a $CREATE_REMOTE GitHub repo '$name' and push."
      SUMMARY+=("OK      $name  (dry-run: would create $CREATE_REMOTE repo + push)")
    elif git diff --cached --quiet; then
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

  # ---- create the GitHub repo (first push) or push as usual ----
  if [ "$needs_create" -eq 1 ]; then
    if "$GH" repo create "$name" "--$CREATE_REMOTE" --source=. --remote=origin --push >>"$LOG" 2>&1; then
      log "  created $CREATE_REMOTE GitHub repo and pushed origin/$branch."
      SUMMARY+=("SYNCED  $name  (new $CREATE_REMOTE repo)"); N_SYNCED=$((N_SYNCED+1))
    else
      log "  ERROR: gh repo create failed (see log)."
      SUMMARY+=("ERROR   $name  (repo creation failed)"); N_ERR=$((N_ERR+1))
    fi
    return
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

# Record when a real (non-dry-run) run last completed, regardless of outcome,
# plus a one-word status ("ok" / "attention") — the GUI's tray icon and the
# scheduled background job both read these two files.
if [ "$DRY_RUN" -eq 0 ]; then
  mkdir -p "$STATE_DIR"
  ts > "$STATE_DIR/last_sync.txt"
  if [ $((N_BLOCKED + N_ERR)) -eq 0 ]; then
    echo "ok" > "$STATE_DIR/last_status.txt"
  else
    echo "attention" > "$STATE_DIR/last_status.txt"
  fi
fi

# non-zero exit if anything was blocked or errored (so failures are visible)
[ $((N_BLOCKED + N_ERR)) -eq 0 ]
