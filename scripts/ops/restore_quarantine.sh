#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  restore_quarantine.sh --manifest <path> --dry-run
  restore_quarantine.sh --manifest <path> --apply

Manifest format (TSV):
  source<TAB>destination<TAB>reason
EOF
}

MODE=""
MANIFEST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST="${2:-}"
      shift 2
      ;;
    --dry-run|--apply)
      MODE="$1"
      shift
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$MODE" || -z "$MANIFEST" ]]; then
  usage
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
[[ -f "$MANIFEST" ]] || [[ -f "$ROOT/$MANIFEST" ]] || {
  echo "[HYGIENE] manifest not found: $MANIFEST"
  exit 1
}

if [[ -f "$ROOT/$MANIFEST" ]]; then
  MANIFEST="$ROOT/$MANIFEST"
fi

echo "[HYGIENE] mode=$MODE manifest=${MANIFEST#$ROOT/}"

tail -n +2 "$MANIFEST" | while IFS=$'\t' read -r rel dst reason; do
  [[ -z "$rel" ]] && continue
  src="$ROOT/$dst"
  target="$ROOT/$rel"
  if [[ "$MODE" == "--dry-run" ]]; then
    echo "  restore $dst -> $rel  ($reason)"
    continue
  fi
  [[ -e "$src" ]] || continue
  mkdir -p "$(dirname "$target")"
  mv "$src" "$target"
done

echo "[HYGIENE] restore complete"
