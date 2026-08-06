#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  quarantine_untracked_noise.sh --dry-run
  quarantine_untracked_noise.sh --apply

Behavior:
  - Never deletes files.
  - Moves only high-confidence untracked noise into:
    .repo_hygiene/quarantine/<timestamp>/
  - Writes a manifest to:
    .repo_hygiene/manifests/<timestamp>.tsv

Rules:
  1) Any untracked path under .lake/
  2) Any untracked path under rust_core/target 2/
  3) Numbered duplicate files that match: "<name> <n>.<ext>"
     and where "<name>.<ext>" exists.
  4) Clear runtime/build artifacts:
     - *.bak
     - docs/papers/**/paper.(aux|log|out|pdf)
     - src/cockpit.log
     - ultimate_benchmark_*.log
     - src/warm_logic/_warm_logic_rs*.so
     - data/redb_social/**, data/redb_social_db/**, data/social.db
  5) Evidence snapshots with retained latest pointer:
     - docs/papers/**/evidence/*.YYYYMMDDTHHMMSSZ.(json|md|log)
       only when matching *.latest.<ext> exists
  6) Explicit local/runtime leftovers:
     - docs/papers/**/evidence/**/*.log
     - docs/papers/10_post_quantum_sovereignty/cross_host_hosts.json
     - state/kernel/state.json
     - test_list.txt
EOF
}

if [[ "${1:-}" != "--dry-run" && "${1:-}" != "--apply" ]]; then
  usage
  exit 2
fi

MODE="$1"
ROOT="$(git rev-parse --show-toplevel)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
QROOT="$ROOT/.repo_hygiene/quarantine/$STAMP"
MANIFEST_DIR="$ROOT/.repo_hygiene/manifests"
MANIFEST="$MANIFEST_DIR/$STAMP.tsv"

mkdir -p "$MANIFEST_DIR"

TMP_ALL="$(mktemp)"
TMP_CAND="$(mktemp)"
trap 'rm -f "$TMP_ALL" "$TMP_CAND"' EXIT

git -C "$ROOT" ls-files -o --exclude-standard > "$TMP_ALL"

while IFS= read -r rel; do
  [[ -z "$rel" ]] && continue
  reason=""

  if [[ "$rel" == .lake/* ]]; then
    reason="lake-artifact"
  elif [[ "$rel" == "rust_core/target 2/"* ]]; then
    reason="rust-target-artifact"
  elif [[ "$rel" == *.bak ]]; then
    reason="backup-artifact"
  elif [[ "$rel" =~ ^docs/papers/.+/paper\.(aux|log|out|pdf)$ ]]; then
    reason="latex-build-artifact"
  elif [[ "$rel" == "src/cockpit.log" ]]; then
    reason="runtime-log"
  elif [[ "$rel" == ultimate_benchmark_*.log ]]; then
    reason="runtime-log"
  elif [[ "$rel" == src/warm_logic/_warm_logic_rs*.so ]]; then
    reason="local-extension-artifact"
  elif [[ "$rel" == data/redb_social/* || "$rel" == data/redb_social_db/* || "$rel" == data/social.db ]]; then
    reason="runtime-db-artifact"
  elif [[ "$rel" =~ ^docs/papers/.+/evidence/.+\.log$ ]]; then
    reason="evidence-log-artifact"
  elif [[ "$rel" == docs/papers/10_post_quantum_sovereignty/cross_host_hosts.json ]]; then
    reason="local-host-config"
  elif [[ "$rel" == state/kernel/state.json ]]; then
    reason="runtime-state-artifact"
  elif [[ "$rel" == test_list.txt ]]; then
    reason="generated-list-artifact"
  elif [[ "$rel" =~ ^(docs/papers/.+/evidence/.+)\.[0-9]{8}T[0-9]{6}Z\.(json|md|log)$ ]]; then
    base="${BASH_REMATCH[1]}"
    ext="${BASH_REMATCH[2]}"
    latest="${base}.latest.${ext}"
    if [[ -e "$ROOT/$latest" ]]; then
      reason="evidence-snapshot"
    fi
  elif [[ "$rel" =~ ^(.+)\ ([0-9]+)(\.[^/]+)$ ]]; then
    base="${BASH_REMATCH[1]}${BASH_REMATCH[3]}"
    if [[ -e "$ROOT/$base" ]]; then
      reason="numbered-duplicate"
    fi
  fi

  if [[ -n "$reason" ]]; then
    printf '%s\t%s\n' "$rel" "$reason" >> "$TMP_CAND"
  fi
done < "$TMP_ALL"

if [[ ! -s "$TMP_CAND" ]]; then
  echo "[HYGIENE] no quarantine candidates"
  exit 0
fi

count="$(wc -l < "$TMP_CAND" | tr -d ' ')"
echo "[HYGIENE] candidates=$count mode=$MODE"
awk -F'\t' '{print $2}' "$TMP_CAND" | sort | uniq -c | sort -rn | sed 's/^/[HYGIENE] /'

if [[ "$MODE" == "--dry-run" ]]; then
  echo "[HYGIENE] preview (first 40):"
  head -n 40 "$TMP_CAND" | awk -F'\t' '{printf "  %s  (%s)\n",$1,$2}'
  exit 0
fi

mkdir -p "$QROOT"
printf "source\tdestination\treason\n" > "$MANIFEST"

while IFS=$'\t' read -r rel reason; do
  src="$ROOT/$rel"
  [[ -e "$src" ]] || continue
  dst="$QROOT/$rel"
  mkdir -p "$(dirname "$dst")"
  mv "$src" "$dst"
  printf '%s\t%s\t%s\n' "$rel" "${dst#$ROOT/}" "$reason" >> "$MANIFEST"
done < "$TMP_CAND"

moved="$(( $(wc -l < "$MANIFEST" | tr -d ' ') - 1 ))"
echo "[HYGIENE] moved=$moved"
echo "[HYGIENE] manifest=${MANIFEST#$ROOT/}"
