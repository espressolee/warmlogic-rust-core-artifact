#!/usr/bin/env bash
set -euo pipefail

echo "Proposed top-level layering (non-destructive plan)"
cat << 'PLAN'
systems/
  -> safety_pipeline/ (symlink to ./safety_pipeline)
  -> reflective_os/ (symlink to ./reflective_os)
  -> WarmLogic_Vol1_v1.0/demo (symlink to ./WarmLogic_Vol1_v1.0/WarmLogic_Vol1_v1.0/demo)
papers/
  -> docs/papers/ai_ethics
  -> docs/papers/reflective_os
  -> docs/papers/safety_pipeline
  -> docs/papers/WarmLogic_Vol1_v1.0
ethics/
  -> docs/papers/ai_ethics (preferred entry)
phd_career/
  -> docs/papers/ai_ethics/phd
  -> docs/papers/ai_ethics/applications
PLAN

echo
echo "This script prints the proposed mapping only. To realize it via symlinks, run: scripts/repo/symlink_layer_layout.sh"
