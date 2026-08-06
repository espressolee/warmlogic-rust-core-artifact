#!/bin/bash
set -e
echo "🧪 Creating test venv..."
python3 -m venv .venv_test
source .venv_test/bin/activate

echo "📦 Installing build deps..."
pip install --upgrade pip setuptools wheel

echo "🚀 Installing warm_logic (Alpha)..."
pip install -e .

echo "✅ Verifying CLI..."
wlctl --help || python3 -m warm_logic.app.cli.wlctl --help

echo "🎉 Success!"
deactivate
rm -rf .venv_test
