#!/usr/bin/env bash
# ==========================================================
# Script: run_ml_modes.sh
# Project: Warm Logic — Model Layer
# Description: Convenience script to run deterministic vs real ML modes.
# Author: espressolee
# ==========================================================

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
LOG_DIR="$ROOT_DIR/out/logs"
mkdir -p "$LOG_DIR"

echo "[ML mode] Deterministic (ml_disabled)" && \
  PROFILE=ml_disabled bash "$ROOT_DIR/model/run_all.sh" phase40-ml-runtime > "$LOG_DIR/ml_disabled.log" 2>&1 || echo "⚠️ deterministic mode failed"

echo "[ML mode] Real (ml_enabled)" && \
  PROFILE=ml_enabled bash "$ROOT_DIR/model/run_all.sh" phase40-ml-runtime > "$LOG_DIR/ml_enabled.log" 2>&1 || echo "⚠️ real mode failed"

echo "Logs: out/logs/ml_disabled.log, out/logs/ml_enabled.log"
