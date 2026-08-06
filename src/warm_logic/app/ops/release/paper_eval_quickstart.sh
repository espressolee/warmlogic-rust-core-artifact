#!/usr/bin/env bash
# Warm Logic OS v1 reproducibility quick-start
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_PATH="${VENV_PATH:-$ROOT/.venv}"
PY_BIN="$VENV_PATH/bin/python"
PIP_BIN="$VENV_PATH/bin/pip"

log() {
  echo "[quickstart] $*"
}

log "creating virtualenv at $VENV_PATH"
python3 -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"
log "installing requirements from lockfiles"
"$PIP_BIN" install -r requirements.lock -r demo/requirements.lock >/dev/null

log "seeding synthetic assets"
PYTHONPATH="$ROOT" "$PY_BIN" -m scripts.release.load_synthetic_assets

log "running paper-eval-e1"
PYTHONPATH="$ROOT" bash model/run_all.sh paper-eval-e1
log "running paper-eval-e2"
PYTHONPATH="$ROOT" bash model/run_all.sh paper-eval-e2
log "running paper-eval-e3"
PYTHONPATH="$ROOT" bash model/run_all.sh paper-eval-e3
log "running compare suite"
PYTHONPATH="$ROOT" make paper-compare-suite
log "running local LLM baseline/stress"
PYTHONPATH="$ROOT" make paper-local-llm-baseline
PYTHONPATH="$ROOT" make paper-local-llm-stress
log "quick start complete"
