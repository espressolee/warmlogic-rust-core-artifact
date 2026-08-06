#!/usr/bin/env bash
# Paper 09: x86_64 Benchmark Bootstrap Script
# Usage: curl -s <raw_url> | bash
# Or: bash bootstrap_x86_64_eval.sh <git_repo_url>
set -euo pipefail

REPO_URL="${1:-}"
REPEATS="${REPEATS:-5}"

echo "=============================================="
echo "  Paper 09: x86_64 Boundary Elimination Eval"
echo "=============================================="
echo

# 1. Verify architecture
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" ]]; then
    echo "ERROR: This script must run on x86_64, got: $ARCH"
    echo "If you're on ARM Mac, use a cloud VM (GCP/AWS/Azure)."
    exit 1
fi
echo "[OK] Architecture: $ARCH"

# 2. Install system dependencies (Ubuntu/Debian)
echo
echo ">>> Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git curl ca-certificates build-essential pkg-config \
    python3 python3-venv python3-pip python3-dev

# 3. Install Rust
if ! command -v rustc &>/dev/null; then
    echo
    echo ">>> Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi
echo "[OK] Rust: $(rustc --version)"

# 4. Clone or use existing repo
if [[ -n "$REPO_URL" ]]; then
    echo
    echo ">>> Cloning repository..."
    git clone "$REPO_URL" WarmLogic
    cd WarmLogic
elif [[ -d "WarmLogic" ]]; then
    cd WarmLogic
elif [[ -f "scripts/eval/collect_host_pack.sh" ]]; then
    echo "[OK] Already in WarmLogic directory"
else
    echo "ERROR: No repo URL provided and no WarmLogic directory found."
    echo "Usage: bash bootstrap_x86_64_eval.sh <git_repo_url>"
    exit 1
fi

echo "[OK] Working dir: $(pwd)"
echo "[OK] Git commit: $(git rev-parse HEAD 2>/dev/null || echo 'N/A')"

# 5. Create Python venv
echo
echo ">>> Setting up Python venv..."
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip wheel -q
python -m pip install maturin -q
echo "[OK] Python: $(python --version)"
echo "[OK] maturin: $(maturin --version)"

# 6. Run the benchmark
echo
echo ">>> Running benchmark (REPEATS=$REPEATS)..."
echo "    This may take 10-30 minutes depending on VM specs."
echo
REPEATS="$REPEATS" bash scripts/eval/collect_host_pack.sh x86_64_cloud

# 7. Summary
echo
echo "=============================================="
echo "  DONE!"
echo "=============================================="
echo
echo "Output file: out/bridge_eval/x86_64_cloud_pack.tgz"
echo
echo "To download to your local machine:"
echo "  scp $(whoami)@<VM_IP>:$(pwd)/out/bridge_eval/x86_64_cloud_pack.tgz ./"
echo
echo "To merge with existing telemetry (on local):"
echo "  python3 scripts/eval/merge_bridge_telemetry.py \\"
echo "    out/bridge_eval/x86_64_cloud_pack.tgz \\"
echo "    out/bridge_eval/bridge_eval_v3_pyo3_patch/full_telemetry.json \\"
echo "    --out out/bridge_eval/multi_host/combined.json"
