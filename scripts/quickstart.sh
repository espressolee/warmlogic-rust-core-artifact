#!/bin/bash
# WarmLogic Quickstart Script (v0.4.0)
# "Quick start in 30 seconds"

set -e

echo "🏰 WarmLogic: Initializing Sovereign Infrastructure..."

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.12+."
    exit 1
fi

# 2. Check Rust (Optional for binary install, required for dev)
if ! command -v cargo &> /dev/null; then
    echo "⚠️  Rust/Cargo not found. Rust core features may require manual build."
fi

# 3. Create Virtual Env
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv --clear
fi

# Detect OS to source activate correctly
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# 4. Install WarmLogic
echo "⚡ Installing WarmLogic and dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e .

# 5. Initialize Identity
if [ ! -d ".warm_logic" ]; then
    echo "🔑 Generating Sovereign Identity..."
    python3 -m warm_logic.app.cli.wlctl init
fi

# 6. Run Diagnostic
echo "🔍 Running Sovereign Diagnostic..."
python3 -m warm_logic.app.cli.wlctl status
python3 -m warm_logic.app.cli.wlctl version

echo "---"
echo "✅ WarmLogic is ready!"
echo "🚀 To start your node: python3 -m warm_logic.app.cli.wlctl start --foreground"
echo "📊 To view metrics: curl http://localhost:8000/metrics (after start)"
