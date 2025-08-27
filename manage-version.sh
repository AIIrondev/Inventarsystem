#!/bin/bash

# Standalone version manager for this repo
# Supports pinning to a commit/tag/branch, one-time use, clearing the lock,
# applying the lock, listing refs, and showing status. Optional restart.

set -euo pipefail

PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
cd "$PROJECT_DIR"

LOCK_FILE="$PROJECT_DIR/.version-lock"
RESTART=false
FORCE=false

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { echo "ERROR: $*" >&2; }

usage() {
  cat <<USAGE
Usage:
  $0 pin <ref> [--restart] [--force]     Persistently lock to a commit/tag/branch and deploy it
  $0 use <ref> [--restart] [--force]     Use ref once (no persistence) and deploy it
  $0 clear [--restart] [--force]         Remove lock, switch back to main, pull latest
  $0 apply [--restart] [--force]         Re-apply the current lock (if any)
  $0 status                               Show current commit and lock state
  $0 list [--tags|--commits]              List tags or recent commits (default: tags)

Notes:
  - <ref> can be a tag name, branch name, or full/short commit hash
  - --restart calls ./restart.sh after switching
  - --force discards local changes (git reset --hard) if needed
USAGE
}

ensure_git_ready() {
  # Avoid "dubious ownership" errors
  git config --global --add safe.directory "$PROJECT_DIR" >/dev/null 2>&1 || true
  # Fetch refs and tags
  git fetch --all --tags --prune
}

ensure_clean_or_force() {
  if ! git diff --quiet || ! git diff --cached --quiet; then
    if [ "$FORCE" = true ]; then
      log "Discarding local changes (force)"
      git reset --hard
      git clean -fdx >/dev/null 2>&1 || true
    else
      err "Working tree has local changes. Re-run with --force to discard."
      exit 2
    fi
  fi
}

restart_if_requested() {
  if [ "$RESTART" = true ]; then
    if [ -x "$PROJECT_DIR/restart.sh" ]; then
      log "Restarting services..."
      "$PROJECT_DIR/restart.sh"
    else
      log "restart.sh not found or not executable; skipping restart"
    fi
  fi
}

checkout_ref() {
  local ref="$1"

  # Try tag
  if git show-ref --verify --quiet "refs/tags/$ref"; then
    git checkout -B locked-tag-"$ref" "tags/$ref"
    return 0
  fi
  # Try remote branch
  if git show-ref --verify --quiet "refs/remotes/origin/$ref"; then
    git checkout -B locked-branch-"$ref" "origin/$ref"
    return 0
  fi
  # Try local branch
  if git show-ref --verify --quiet "refs/heads/$ref"; then
    git checkout "$ref"
    return 0
  fi
  # Try commit-ish
  if git rev-parse --verify --quiet "$ref^{commit}" >/dev/null; then
    git checkout -B locked-commit "$ref"
    return 0
  fi

  err "Could not resolve ref '$ref' to tag/branch/commit"
  exit 3
}

deploy_main_latest() {
  ensure_clean_or_force
  if git show-ref --verify --quiet refs/heads/main; then
    git checkout main
  else
    git checkout -B main origin/main
  fi
  git pull --ff-only
}

cmd_status() {
  local head_commit
  head_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
  echo "Current commit: $head_commit"
  if [ -f "$LOCK_FILE" ]; then
    echo "Version lock: $(cat "$LOCK_FILE")"
  else
    echo "Version lock: none (tracking main)"
  fi
}

cmd_list() {
  local mode="tags"
  for a in "$@"; do
    case "$a" in
      --tags) mode="tags" ;;
      --commits) mode="commits" ;;
    esac
  done
  ensure_git_ready
  if [ "$mode" = "tags" ]; then
    git tag --list | sort -V
  else
    git --no-pager log --oneline -n 30
  fi
}

cmd_pin() {
  local ref="$1"
  ensure_git_ready
  ensure_clean_or_force
  echo "$ref" > "$LOCK_FILE"
  checkout_ref "$ref"
  log "Pinned to: $ref (commit $(git rev-parse --short HEAD))"
  restart_if_requested
}

cmd_use() {
  local ref="$1"
  ensure_git_ready
  ensure_clean_or_force
  checkout_ref "$ref"
  log "Using (one-time): $ref (commit $(git rev-parse --short HEAD))"
  restart_if_requested
}

cmd_clear() {
  ensure_git_ready
  [ -f "$LOCK_FILE" ] && rm -f "$LOCK_FILE"
  deploy_main_latest
  log "Cleared version lock; now on main @ $(git rev-parse --short HEAD)"
  restart_if_requested
}

cmd_apply() {
  ensure_git_ready
  if [ -f "$LOCK_FILE" ]; then
    ensure_clean_or_force
    local ref
    ref=$(cat "$LOCK_FILE")
    checkout_ref "$ref"
    log "Applied lock: $ref (commit $(git rev-parse --short HEAD))"
  else
    log "No lock present; keeping main"
    deploy_main_latest
  fi
  restart_if_requested
}

# Parse global flags that can appear after subcommand too
parse_tail_flags() {
  for a in "$@"; do
    case "$a" in
      --restart) RESTART=true ;;
      --force)   FORCE=true ;;
    esac
  done
}

main() {
  local cmd="${1:-}"; shift || true
  case "$cmd" in
    pin)
      [ $# -ge 1 ] || { usage; exit 1; }
      local ref="$1"; shift; parse_tail_flags "$@"; cmd_pin "$ref" ;;
    use)
      [ $# -ge 1 ] || { usage; exit 1; }
      local ref="$1"; shift; parse_tail_flags "$@"; cmd_use "$ref" ;;
    clear)
      parse_tail_flags "$@"; cmd_clear ;;
    apply)
      parse_tail_flags "$@"; cmd_apply ;;
    status)
      cmd_status ;;
    list)
      cmd_list "$@" ;;
    --help|-h|help|"")
      usage ;;
    *)
      err "Unknown command: $cmd"; usage; exit 1 ;;
  esac
}

main "$@"
