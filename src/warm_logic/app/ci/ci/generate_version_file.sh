#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f VERSION && -s VERSION ]]; then
  echo "[version] VERSION already present: $(head -n1 VERSION)"
  exit 0
fi

ver="${WARM_LOGIC_VERSION:-}"
if [[ -z "$ver" ]]; then
  if command -v git >/dev/null 2>&1; then
    ver=$(git describe --tags --always 2>/dev/null || true)
  fi
fi
ver=${ver:-0}
echo "$ver" > VERSION
echo "[version] Wrote VERSION=$ver"
