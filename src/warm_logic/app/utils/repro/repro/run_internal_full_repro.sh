#!/usr/bin/env bash
set -euo pipefail
ROOT=$(pwd)
REPORT_DIR=$ROOT/out/repro_internal
RUN_ID=RUN_OSV2_INTERNAL_$(date -u +%Y%m%dT%H%M%SZ)
LOG=$REPORT_DIR/${RUN_ID}.log
mkdir -p "$REPORT_DIR"
{
  echo "Starting Edition v1.1 internal full repro: $RUN_ID"
  echo "Step 1: ensure editable install"
  python -m pip install -e . >/dev/null
  echo "Step 2: regen figures"
  make os_v2-figures
  echo "Step 3: run evaluation harness"
  bash docs/papers/reflective_os/os_v2/scripts/run_os_v2_eval.sh
  echo "Completed internal repro with artifacts in docs/papers/reflective_os/os_v2/out/${RUN_ID} (per-mode runs)"
} | tee "$LOG"
