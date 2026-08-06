#!/bin/bash
# Hyper-Isolated Coverage Execution Script
# Bypasses host environment permission barriers for clean coverage data collection.

set -e

REPO_ROOT="$(pwd)"
EXPORT_COV_FILE="/tmp/warm_logic.coverage"

echo "🧹 [1/3] Purging .DS_Store files to prevent collection errors..."
find warm_logic/kernel -name ".DS_Store" -delete || true

echo "🚀 [2/3] Executing hyper-isolated pytest run..."
# We use -p no:cov to prevent the built-in plugin from hitting permission errors on root .coverage
# We ensure we run from REPO_ROOT and set it as the pytest root
cd "$REPO_ROOT"
COVERAGE_FILE="$EXPORT_COV_FILE" python3 -m coverage run --source=warm_logic/kernel -m pytest -p no:cov -o "addopts=" --rootdir="$REPO_ROOT" warm_logic/kernel/tests/

echo "📊 [3/3] Generating coverage report from isolated data..."
python3 -m coverage report --data-file="$EXPORT_COV_FILE"
python3 -m coverage json --data-file="$EXPORT_COV_FILE" -o /tmp/warm_logic_coverage.json

echo "✅ Coverage execution complete. Data available at $EXPORT_COV_FILE and /tmp/warm_logic_coverage.json"
