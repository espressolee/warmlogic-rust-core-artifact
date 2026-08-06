#!/bin/bash
# WarmLogic benchmark & simulation automated runner

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_ROOT"

echo ""
echo "📊 WarmLogic benchmark & simulation"
echo "  Start: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. Performance benchmark
echo "=== 1/3: Performance benchmark ==="
python3 scripts/benchmark/drone_benchmark.py

# 2. Stress test
echo ""
echo "=== 2/3: Stress test ==="
python3 scripts/benchmark/stress_test.py

# 3. Long-running simulation (30 minutes)
echo ""
echo "=== 3/3: Long-running simulation (30 minutes) ==="
python3 scripts/benchmark/long_simulation.py --hours 0.5

echo ""
echo "✅ All benchmarks complete"
echo "  End: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "📁 Result files:"
ls -la benchmark_*.json simulation_*.json 2>/dev/null || true
