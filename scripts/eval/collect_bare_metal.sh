#!/bin/sh
set -eu

# collect_bare_metal.sh
#
# Runs the full Paper 09 bridge evaluation suite on a dedicated/bare-metal host.
# Compared to 'collect_host_pack.sh', this script:
# 1. Uses higher repeats (10 vs 5) to ensure statistical significance.
# 2. Pins to a specific CPU core (if taskset is available) to minimize migration variance.
# 3. Explicitly checks for performance governor.

# Default: pin to core 2 (assuming core 0 handles IRQs/kernel tasks).
# Override with CORE_ID envar.
CORE_ID="${CORE_ID:-2}"

if command -v taskset > /dev/null 2>&1; then
    PIN_CMD="taskset -c $CORE_ID"
    echo "Pinning benchmarks to core $CORE_ID..."
else
    PIN_CMD=""
    echo "WARN: taskset not found; running without CPU pinning."
fi

# Check governor (informational)
if [ -f /sys/devices/system/cpu/cpu$CORE_ID/cpufreq/scaling_governor ]; then
    GOV=$(cat /sys/devices/system/cpu/cpu$CORE_ID/cpufreq/scaling_governor)
    echo "Core $CORE_ID governor: $GOV"
    if [ "$GOV" != "performance" ]; then
        echo "WARN: Governor is not 'performance'. Consider setting it for consistent results."
    fi
fi

# Base collection via existing scripts but wrapped with pinning
# 1. Setup (Assumes script is run from inside the unpacked WarmLogic directory)
if [ ! -d "rust_core" ]; then
    echo "Error: rust_core directory not found. Please run this script from the root of the unpacked archive."
    exit 1
fi

# Ensure Python venv for isolated environment
python3 -m venv bare_metal_env
source bare_metal_env/bin/activate
pip install maturin packaging

# Run Stock Collection
echo "Running Stock PyO3 benchmark (Pinned)..."
$PIN_CMD env OFFLINE_CARGO=1 python3 scripts/eval/collect_stock_pyo3_telemetry.py \
    --run-id bare_metal_stock \
    --repeats 10 \
    --warmup 500

# Run Patched Collection
echo "Running Patched PyO3 benchmark (Pinned)..."
$PIN_CMD env OFFLINE_CARGO=1 python3 scripts/eval/collect_patched_pyo3_telemetry.py \
    --run-id bare_metal_patched \
    --repeats 10 \
    --warmup 500

# Package results
echo "Packaging results..."
HOST_ID="bare_metal_$(hostname | tr -cd '[:alnum:]')"
PACK_NAME="${HOST_ID}_pack.tgz"
OUT_DIR="out/bridge_eval"

tar -czf "$OUT_DIR/$PACK_NAME" \
    -C "$OUT_DIR" \
    bare_metal_stock \
    bare_metal_patched

echo "Done. Created $OUT_DIR/$PACK_NAME"
echo "Please transfer this file to the analysis host."
