#!/bin/bash
# WarmLogic Defense Demo Runner
# Runs the defense demonstration.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo ""
echo "🎖️  WarmLogic Defense Demonstration System"
echo "   $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

cd "$PROJECT_ROOT"

# Run demo
python3 scripts/demo/defense_demo.py

echo ""
echo "Demo complete. Check the result files."
