#!/bin/bash
# 🏛️ WarmLogic: Sovereign Setup Protocol (setup_dev_env.sh)
# Purpose: One-command reproducible environment setup.

set -e

echo "🦅 [WarmLogic] Initiating Sovereign Setup Protocol..."
echo "---------------------------------------------------"

# 1. Environment Verification
echo "🔍 Checking Environment Requirements..."

# Python Check
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_PYTHON="3.10"

if [[ $(echo -e "$PYTHON_VERSION\n$REQUIRED_PYTHON" | sort -V | head -n1) == "$REQUIRED_PYTHON" ]]; then
    echo "  ✅ Python $PYTHON_VERSION: DETECTED"
else
    echo "  ❌ ERROR: Python $REQUIRED_PYTHON+ required (Found $PYTHON_VERSION)"
    exit 1
fi

# Docker Check (Optional but recommended for reproduction)
if command -v docker >/dev/null 2>&1; then
    echo "  ✅ Docker: DETECTED"
else
    echo "  ⚠️ WARNING: Docker not found. Some reproduction features will be unavailable."
fi

# 2. Virtual Environment Setup
if [ -d ".venv" ]; then
    # Test if venv is broken
    if ! .venv/bin/python3 --version >/dev/null 2>&1; then
        echo "⚠️ .venv appears broken (bad interpreter). Recreating..."
        rm -rf .venv
    fi
fi

if [ ! -d ".venv" ]; then
    echo "🔨 Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "  ✅ Virtual Environment: ACTIVE"

# 3. Dependency Installation
echo "📦 Installing base build tools..."
python3 -m pip install --upgrade pip wheel setuptools

echo "📦 Installing dependencies from requirements.lock..."
if [ -f "requirements.lock" ]; then
    # We try to install from lockfile. If it fails (e.g. python version mismatch), we fallback.
    if ! python3 -m pip install -r requirements.lock; then
        echo "  ⚠️ WARNING: installation from requirements.lock failed. Falling back to pyproject.toml..."
        python3 -m pip install -e ".[dev,dashboard,eval]"
    else
        echo "  ✅ Dependencies: INSTALLED (Deterministic)"
        # Also install the package in editable mode without reinstalling deps
        python3 -m pip install -e ".[dev,dashboard,eval]" --no-deps
    fi
else
    echo "  ⚠️ WARNING: requirements.lock not found. Falling back to pyproject.toml..."
    python3 -m pip install -e ".[dev,dashboard,eval]"
    echo "  ✅ Dependencies: INSTALLED (Dynamic)"
fi

# 4. Kernel Extension Verification
echo "🧪 Verifying Internal Reality (Rust Kernel)..."
python3 -c "
import sys
try:
    # Attempt to load the extension if it exists
    # If not built yet, we don't fail setup but we warn
    import warm_logic.warm_logic_rs
    print('  ✅ [Rust] Kernel Extension: LOADED')
except ImportError:
    print('  ⚠️ [Rust] Kernel Extension: NOT FOUND (Run /rebuild-rust if needed)')
"

# 5. Final Verdict
echo "---------------------------------------------------"
echo "📜 Sovereign Setup Summary:"
echo "  Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "  Status:    READY FOR SOVEREIGN OPS"
echo "---------------------------------------------------"

exit 0
