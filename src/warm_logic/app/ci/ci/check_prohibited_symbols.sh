#!/usr/bin/env bash
set -euo pipefail

# Fail if prohibited glyphs (✓ △ ✗) appear in Markdown files.
# Usage: scripts/ci/check_prohibited_symbols.sh [ROOT=.] [--allow path]...

ROOT="${1:-.}"
shift || true

ALLOW=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow) ALLOW+=("$2"); shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

mapfile -t FILES < <(find "$ROOT" -type f -name "*.md" \
  -not -path "*/.git/*" -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/venv/*")

status=0
for f in "${FILES[@]}"; do
  skip=0
  for a in "${ALLOW[@]:-}"; do
    [[ "$f" == *"$a"* ]] && skip=1 && break
  done
  [[ $skip -eq 1 ]] && continue
  if rg -n "[✓△✗]" "$f" >/dev/null; then
    echo "[symbol-lint] Prohibited symbol in: $f" >&2
    rg -n "[✓△✗]" "$f" | sed 's/^/  > /' >&2
    status=1
  fi
done

if [[ $status -ne 0 ]]; then
  echo "[symbol-lint] FAIL: replace ✓/△/✗ with PASS/PARTIAL/FAIL (or equivalent words)." >&2
  exit 1
fi

echo "[symbol-lint] OK — no prohibited symbols in Markdown"
