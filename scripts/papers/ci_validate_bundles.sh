#!/usr/bin/env bash
set -euo pipefail

dir="out/submission"
if [[ "${1:-}" == "--dir" ]]; then
  dir="${2:-out/submission}"
fi

[[ -d "$dir" ]] || { echo "[BUNDLE-VALIDATE] missing directory: $dir" >&2; exit 1; }

mapfile -t bundles < <(find "$dir" -type f -name "*_bundle.zip" | sort)
[[ ${#bundles[@]} -gt 0 ]] || { echo "[BUNDLE-VALIDATE] no bundle zips found under $dir" >&2; exit 1; }

for z in "${bundles[@]}"; do
  unzip -t "$z" >/dev/null
  echo "[BUNDLE-VALIDATE] OK $z"
done
