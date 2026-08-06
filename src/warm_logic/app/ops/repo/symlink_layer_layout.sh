#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

mklink() {
  local link_path="$1" target="$2"
  mkdir -p "$(dirname "$link_path")"
  if [[ -e "$link_path" || -L "$link_path" ]]; then
    rm -rf "$link_path"
  fi
  ln -s "$target" "$link_path"
  echo "[symlink] $link_path -> $target"
}

# systems layer
mklink "$ROOT/systems/safety_pipeline" "$ROOT/safety_pipeline"
mklink "$ROOT/systems/reflective_os" "$ROOT/reflective_os"
mklink "$ROOT/systems/WarmLogic_Vol1_v1.0_demo" "$ROOT/WarmLogic_Vol1_v1.0/WarmLogic_Vol1_v1.0/demo"

# papers layer
mklink "$ROOT/papers/ai_ethics" "$ROOT/docs/papers/ai_ethics"
mklink "$ROOT/papers/reflective_os" "$ROOT/docs/papers/reflective_os"
mklink "$ROOT/papers/safety_pipeline" "$ROOT/docs/papers/safety_pipeline"
mklink "$ROOT/papers/WarmLogic_Vol1_v1.0" "$ROOT/docs/papers/WarmLogic_Vol1_v1.0"

# ethics layer
mklink "$ROOT/ethics/ai_ethics" "$ROOT/docs/papers/ai_ethics"

# phd_career layer
mklink "$ROOT/phd_career/phd" "$ROOT/docs/papers/ai_ethics/phd"
mklink "$ROOT/phd_career/applications" "$ROOT/docs/papers/ai_ethics/applications"

echo "[done] Created symlinked layer layout."
