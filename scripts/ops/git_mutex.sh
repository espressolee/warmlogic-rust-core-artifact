#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  git_mutex.sh [--timeout-seconds N] [--stale-seconds N] -- <command> [args...]

Purpose:
  Serialize git operations across parallel agents in one repository.
  Also heals stale .git/index.lock when safe.
EOF
}

TIMEOUT_SECONDS=120
STALE_SECONDS=10

while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout-seconds)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --stale-seconds)
      STALE_SECONDS="${2:-}"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[GIT-MUTEX] unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
LOCK_DIR="$ROOT/.git/.wl_git_mutex"
LOCK_OWNER="$LOCK_DIR/owner"
INDEX_LOCK="$ROOT/.git/index.lock"

index_lock_age_seconds() {
  if [[ ! -f "$INDEX_LOCK" ]]; then
    echo 0
    return 0
  fi
  local mtime now
  if ! mtime="$(stat -f %m "$INDEX_LOCK" 2>/dev/null)"; then
    echo 0
    return 0
  fi
  now="$(date +%s)"
  echo $(( now - mtime ))
}

acquire_lock() {
  local started now
  started="$(date +%s)"

  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    now="$(date +%s)"
    if (( now - started >= TIMEOUT_SECONDS )); then
      echo "[GIT-MUTEX] timeout waiting lock: ${LOCK_DIR#$ROOT/}" >&2
      if [[ -f "$LOCK_OWNER" ]]; then
        echo "[GIT-MUTEX] current owner: $(cat "$LOCK_OWNER" 2>/dev/null || true)" >&2
      fi
      return 1
    fi
    sleep 0.2
  done

  {
    echo "pid=$$"
    echo "host=$(hostname 2>/dev/null || echo unknown)"
    echo "cwd=$PWD"
    echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "cmd=$*"
  } > "$LOCK_OWNER"
}

release_lock() {
  rm -rf "$LOCK_DIR" 2>/dev/null || true
}

heal_stale_index_lock() {
  [[ -f "$INDEX_LOCK" ]] || return 0

  # If any git process is running, do not touch index.lock.
  if pgrep -f "^git( |$)|/git( |$)" >/dev/null 2>&1; then
    return 1
  fi

  # If index.lock is open by a non-git process, allow force-heal only
  # when lock age exceeds STALE_SECONDS.
  if command -v lsof >/dev/null 2>&1; then
    if lsof "$INDEX_LOCK" >/dev/null 2>&1; then
      local age
      age="$(index_lock_age_seconds)"
      if (( age < STALE_SECONDS )); then
        return 1
      fi
      echo "[GIT-MUTEX] forcing stale index.lock cleanup (age=${age}s)"
    fi
  fi

  rm -f "$INDEX_LOCK"
  echo "[GIT-MUTEX] removed stale .git/index.lock"
  return 0
}

wait_for_index_lock_clear() {
  local started now
  started="$(date +%s)"
  while [[ -f "$INDEX_LOCK" ]]; do
    if heal_stale_index_lock; then
      [[ -f "$INDEX_LOCK" ]] || return 0
    fi
    now="$(date +%s)"
    if (( now - started >= TIMEOUT_SECONDS )); then
      echo "[GIT-MUTEX] timeout waiting .git/index.lock to clear" >&2
      if command -v lsof >/dev/null 2>&1; then
        lsof "$INDEX_LOCK" 2>/dev/null || true
      fi
      return 1
    fi
    sleep 0.2
  done
  return 0
}

acquire_lock "$@"
trap release_lock EXIT

wait_for_index_lock_clear

run_with_index_lock_retries() {
  local attempt max_attempts rc
  attempt=0
  max_attempts=3

  while true; do
    attempt=$(( attempt + 1 ))
    if "$@"; then
      return 0
    fi
    rc=$?

    # Retry only when index.lock exists and we still have budget.
    if [[ -f "$INDEX_LOCK" ]] && (( attempt < max_attempts )); then
      echo "[GIT-MUTEX] index.lock race detected; retry ${attempt}/${max_attempts}" >&2
      wait_for_index_lock_clear || return "$rc"
      continue
    fi

    return "$rc"
  done
}

echo "[GIT-MUTEX] exec: $*"
run_with_index_lock_retries "$@"
