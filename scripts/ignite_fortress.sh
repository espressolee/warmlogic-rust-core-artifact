#!/bin/bash
# ==========================================================
# Script: scripts/ignite_fortress.sh
# Description: One-click launcher for the Sovereign Sanctuary.
# ==========================================================

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}🏛️  IGNITING THE SOVEREIGN FORTRESS...${NC}"

# Args
args_lower="$(printf '%s ' "$@" | tr '[:upper:]' '[:lower:]')"

# Resolve workspace paths.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# If we are already inside WarmLogic, REPO_ROOT is the target.
if [[ "$REPO_ROOT" == *"/WarmLogic" ]]; then
  WARMLOGIC_DIR="$REPO_ROOT"
else
  WARMLOGIC_DIR="${REPO_ROOT}/WarmLogic"
fi

# Check for rich library (optional as per hardening requirement)
if python3 -c "import rich" >/dev/null 2>&1; then
  echo -e "${CYAN}✨ Rich UI features enabled.${NC}"
else
  echo -e "${YELLOW}⚠️  Rich UI library not found. Falling back to simple mode.${NC}"
fi

# Prefer WarmLogic venv if present (ensures deps like PyYAML are available).
PYTHON_BIN="python3"
if [[ -x "${WARMLOGIC_DIR}/venv/bin/python3" ]]; then
  PYTHON_BIN="${WARMLOGIC_DIR}/venv/bin/python3"
fi

# Sanity check mode (non-interactive)
if [[ "$args_lower" == *"sanity"* ]]; then
  echo -e "${YELLOW}🏥 Running Comprehensive Sanity Check (no voice / no Ollama required)...${NC}"
  (cd "${WARMLOGIC_DIR}" && "$PYTHON_BIN" scripts/sanity/run_comprehensive_sanity.py)
  exit $?
fi

# 1. Start Bio-Metric Watcher in background
echo -e "${YELLOW}🧬 Activating Vitruvian Pulse (Bio-Watcher)...${NC}"
(cd "${WARMLOGIC_DIR}" && "$PYTHON_BIN" scripts/local_scribe/mac_pulse_watcher.py > /dev/null 2>&1) &
WATCHER_PID=$!

# 2. Check for Themis Lock
if [ -f "${WARMLOGIC_DIR}/warm_logic/kernel/sys/IMPEACHED_SCRIBE.lock" ]; then
    echo -e "\033[0;31m⚖️  WARNING: Themis Impeachment Lock detected. Scribe will be limited.${NC}"
fi

# 3. Start Scribe Voice Interface
echo -e "${GREEN}🎙️  Powering up Scribe Brain...${NC}"
echo -e "${CYAN}--------------------------------------------------${NC}"

# If Ollama is offline, fall back to mock mode so the fortress still boots.
VOICE_ARGS=()
if [[ "$args_lower" == *"--mock"* || "$args_lower" == *"mock"* ]]; then
  VOICE_ARGS+=(--mock)
else
  OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
  if command -v curl >/dev/null 2>&1; then
    if ! curl -fsS "${OLLAMA_HOST%/}/api/tags" >/dev/null 2>&1; then
      echo -e "${YELLOW}⚠️  Ollama appears offline at ${OLLAMA_HOST}. Falling back to MOCK MODE.${NC}"
      echo -e "${YELLOW}   To enable full mode: run 'ollama serve' (and ensure the model is installed).${NC}"
      VOICE_ARGS+=(--mock)
    fi
  fi
fi

if [ -f "${WARMLOGIC_DIR}/scripts/local_scribe/run_voice_interface.py" ]; then
  (cd "${WARMLOGIC_DIR}" && "$PYTHON_BIN" scripts/local_scribe/run_voice_interface.py "${VOICE_ARGS[@]}")
else
  echo -e "${YELLOW}⚠️  Voice interface script missing. Starting in headless mode.${NC}"
  # Fallback to a mock or just wait
  echo -e "${CYAN}Headless session active. Press Ctrl+C to stop.${NC}"
  sleep infinity
fi

# Cleanup on exit
echo -e "\n${YELLOW} shuting down engines...${NC}"
kill $WATCHER_PID
echo -e "${CYAN}Standby mode.${NC}"
