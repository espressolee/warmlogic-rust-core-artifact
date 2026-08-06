#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  git_safe_commit.sh --message "P4xx: ..." [--timeout-seconds N] -- <path> [path...]

Behavior:
  - Serializes git operations with scripts/ops/git_mutex.sh
  - Stages only provided paths
  - Commits only provided paths (pathspec commit) to avoid cross-agent leakage
EOF
}

MESSAGE=""
TIMEOUT_SECONDS=120

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message|-m)
      MESSAGE="${2:-}"
      shift 2
      ;;
    --timeout-seconds)
      TIMEOUT_SECONDS="${2:-}"
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
      echo "[GIT-SAFE-COMMIT] unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$MESSAGE" ]]; then
  echo "[GIT-SAFE-COMMIT] --message is required" >&2
  usage
  exit 2
fi

if [[ $# -lt 1 ]]; then
  echo "[GIT-SAFE-COMMIT] at least one path is required" >&2
  usage
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
MUTEX="$ROOT/scripts/ops/git_mutex.sh"

if [[ ! -x "$MUTEX" ]]; then
  echo "[GIT-SAFE-COMMIT] missing executable mutex script: $MUTEX" >&2
  exit 1
fi

paths=("$@")

# Fast existence check to prevent accidental empty commits from typos.
for p in "${paths[@]}"; do
  if [[ ! -e "$ROOT/$p" ]]; then
    echo "[GIT-SAFE-COMMIT] path not found: $p" >&2
    exit 1
  fi
done

bash "$MUTEX" --timeout-seconds "$TIMEOUT_SECONDS" -- \
  git add -- "${paths[@]}"

bash "$MUTEX" --timeout-seconds "$TIMEOUT_SECONDS" -- \
  git commit -m "$MESSAGE" -- "${paths[@]}"
