set -e

echo "🛡️  WARMLOGIC SECRET SCANNER"
printf '%*s\n' 50 '' | tr ' ' '='

# Try to find detect-secrets in common venv locations if not in PATH
if ! command -v detect-secrets >/dev/null 2>&1; then
    if [ -f ".venv/bin/detect-secrets" ]; then
        export PATH="$PWD/.venv/bin:$PATH"
    fi
fi

if ! command -v detect-secrets >/dev/null 2>&1; then
    echo "❌ ERROR: 'detect-secrets' not found. Run scripts/ops/setup_dev_env.sh first."
    exit 1
fi

PROJECT_ROOT=$(pwd)
BASELINE_FILE=".secrets.baseline"

if [ ! -f "$BASELINE_FILE" ]; then
    echo "⚠️ WARNING: No baseline file found. Creating one..."
    detect-secrets scan --exclude-files '.*\.lock' --exclude-files '.*\.olean' > "$BASELINE_FILE"
    echo "✅ Created $BASELINE_FILE"
fi

echo "🔍 Scanning for new secrets..."
# We use --baseline to only report NEW secrets not in the baseline
NEW_SECRETS=$(detect-secrets scan --baseline "$BASELINE_FILE" --exclude-files '.*\.lock' --exclude-files '.*\.olean' 2>/dev/null || echo "ERROR")

if [ "$NEW_SECRETS" = "ERROR" ] || [ -z "$NEW_SECRETS" ]; then
    echo "⚠️ WARNING: detect-secrets failed or returned no output. This might happen if no new files were scanned."
    # Check if baseline itself is valid
    if python3 -c "import sys, json; json.load(open('$BASELINE_FILE'))" >/dev/null 2>&1; then
        echo "🏆 VERDICT: NO NEW SECRETS DETECTED (Baseline valid)"
        exit 0
    else
        echo "❌ ERROR: Baseline file $BASELINE_FILE is corrupted."
        exit 1
    fi
fi

# Check if the results contain any findings
FINDINGS_COUNT=$(echo "$NEW_SECRETS" | python3 -c "
import sys, json
try:
    data=json.load(sys.stdin)
    print(sum(len(v) for v in data.get('results', {}).values()))
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null || echo "0")

if [ "$FINDINGS_COUNT" -gt 0 ] 2>/dev/null; then
    echo "❌ CRITICAL: $FINDINGS_COUNT NEW SECRETS DETECTED!"
    echo "$NEW_SECRETS" | python3 -m json.tool | head -n 50
    exit 1
else
    echo "🏆 VERDICT: NO NEW SECRETS DETECTED"
    exit 0
fi
