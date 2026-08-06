#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-out.detect-secrets.json}"
BASELINE=".secrets.baseline"
EXCLUDE_REGEX='^\.secrets\.baseline$'

if ! command -v detect-secrets-hook >/dev/null 2>&1; then
  echo "[FAIL] detect-secrets-hook not found."
  echo "Install: python -m pip install detect-secrets==1.5.0"
  exit 1
fi

if [ ! -f "$BASELINE" ]; then
  echo "[FAIL] Missing $BASELINE"
  echo "Generate: detect-secrets scan > $BASELINE"
  exit 1
fi

tmp="${TMPDIR:-/tmp}/detect-secrets.$RANDOM.$RANDOM.json"
rm -f "$tmp"

set +e
git ls-files -z | xargs -0 detect-secrets-hook \
  --baseline "$BASELINE" \
  --exclude-files "$EXCLUDE_REGEX" \
  --json \
  -- > "$tmp"
rc=$?
set -e

if [ ! -s "$tmp" ]; then
  echo '[]' > "$tmp"
fi

TMP_OUT="$tmp" python - <<'PY'
import json
import os
import sys

tmp = os.environ["TMP_OUT"]
with open(tmp, "r", encoding="utf-8") as f:
    json.load(f)
PY

mv "$tmp" "$OUT"

if [ "$rc" -ne 0 ]; then
  echo "[FAIL] detect-secrets found new secrets (see $OUT)"
  exit "$rc"
fi

echo "[OK] detect-secrets baseline clean (wrote $OUT)"
