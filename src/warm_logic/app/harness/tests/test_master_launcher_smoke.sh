#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export RUN_ALL_MASTER_DRY_RUN=1

commands=(
  "start"
  "pipelines --devloop v2 --skip-ct --skip-ml"
  "phase-tests-1-19"
  "run-all benchmark"
  "-- dashboard"
  "cluster start"
  "cluster pipelines --devloop v3 --skip-ml"
  "cluster health"
  "cluster status"
  "cluster run-all benchmark"
  "cluster -- dashboard"
)

for cmd in "${commands[@]}"; do
  echo "[TEST] master launcher -> ${cmd}"
  bash model/run_all_master.sh ${cmd}
done
