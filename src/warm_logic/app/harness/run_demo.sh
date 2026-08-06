#!/bin/bash
# ==========================================================
# WarmLogic Demo Runner
# Quick-start script for presentations.
# ==========================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║             WarmLogic Sovereign Governance Demo               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required"
    exit 1
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

# Parse args
PORT=${1:-8888}

echo "Starting demo server on port $PORT..."
echo "Dashboard: http://localhost:$PORT"
echo "API Docs:  http://localhost:$PORT/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$PROJECT_ROOT"
python3 -m warm_logic.app.harness.demo_server --port "$PORT"
