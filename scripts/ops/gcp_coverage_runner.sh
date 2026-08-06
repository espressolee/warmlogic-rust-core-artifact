#!/bin/bash
# GCP Kernel Coverage Test Runner (Core Pillars Only)
# Run this script on a GCP Compute Engine VM (Linux x86_64)
# 
# Prerequisites:
#   - Python 3.10+ installed
#   - WarmLogic repo cloned
#   - pip install coverage pytest
#
# Usage:
#   chmod +x scripts/ops/gcp_coverage_runner.sh
#   ./scripts/ops/gcp_coverage_runner.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="${PROJECT_ROOT}/out/coverage_results"

echo "=============================================="
echo "WarmLogic Kernel Coverage Test (Core Pillars)"
echo "=============================================="
echo "Timestamp: ${TIMESTAMP}"
echo "Project Root: ${PROJECT_ROOT}"
echo ""

# Create results directory
mkdir -p "${RESULTS_DIR}"

cd "${PROJECT_ROOT}"

# Ensure dependencies
pip install --quiet coverage pytest 2>/dev/null || true
pip uninstall -y pytest-cov 2>/dev/null || true

echo "[1/3] Running Integration Tests with Coverage..."

python -c "
import sys
import coverage
import unittest
import json

# CORE PILLARS ONLY - excludes ops, substrate, etc.
CORE_SOURCES = [
    'warm_logic/kernel/identity',
    'warm_logic/kernel/sys',
    'warm_logic/kernel/economy',
    'warm_logic/kernel/mesh',
]

cov = coverage.Coverage(
    branch=True,
    source=CORE_SOURCES,
    omit=['*/tests/*', '*/__pycache__/*'],
    data_file='/tmp/wl_coverage_${TIMESTAMP}'
)
cov.start()

from warm_logic.kernel.tests.integration import test_platform_saturation, test_saturation, test_integration_crypto

loader = unittest.TestLoader()
suite = unittest.TestSuite()
suite.addTests(loader.loadTestsFromModule(test_platform_saturation))
suite.addTests(loader.loadTestsFromModule(test_saturation))
suite.addTests(loader.loadTestsFromModule(test_integration_crypto))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

cov.stop()
cov.save()

print()
print('=' * 70)
print('CORE PILLARS COVERAGE REPORT')
print('=' * 70)
cov.report(show_missing=True)

# Save XML
cov.xml_report(outfile='${RESULTS_DIR}/coverage_${TIMESTAMP}.xml')

# Save HTML
cov.html_report(directory='${RESULTS_DIR}/html_${TIMESTAMP}')

# Get total percentage
total = cov.report(show_missing=False)

# Save JSON summary
summary = {
    'timestamp': '${TIMESTAMP}',
    'platform': '$(uname -s)-$(uname -m)',
    'python_version': sys.version.split()[0],
    'tests_run': result.testsRun,
    'failures': len(result.failures),
    'errors': len(result.errors),
    'coverage_percent': round(total, 2),
    'scope': 'Core Pillars (identity, sys, economy, mesh)'
}

with open('${RESULTS_DIR}/coverage_summary_${TIMESTAMP}.json', 'w') as f:
    json.dump(summary, f, indent=2)

print()
print('=' * 70)
print('FINAL SUMMARY')
print('=' * 70)
print(json.dumps(summary, indent=2))
" 2>&1 | tee "${RESULTS_DIR}/test_output_${TIMESTAMP}.log"

echo ""
echo "=============================================="
echo "Coverage Test Complete"
echo "=============================================="
echo "Results saved to: ${RESULTS_DIR}"
ls -la "${RESULTS_DIR}" | tail -10
echo ""
echo "Done."
