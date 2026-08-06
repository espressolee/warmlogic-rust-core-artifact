#!/usr/bin/env bash
set -e

echo "==============================================="
echo "📦 WarmLogic System Sanity Check"
echo "==============================================="

# Determine project root
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"
export WARMLOGIC_DISABLE_TORCH=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

echo "[1/3] Path integrity check..."
python "$ROOT_DIR/scripts/tests/test_path_integrity.py"
echo "✔ Path integrity OK"

echo "[2/3] Kernel loop → OS artifacts..."
python "$ROOT_DIR/scripts/tests/test_e2e_os_dashboard.py"
echo "✔ Kernel + OS artifacts OK"

echo "[3/3] Dashboard creation..."
python - <<EOF
from model.memory.dashboard.dashboard_commons import create_app
app = create_app()
_ = app.layout
print("✔ Dashboard app creation OK")
EOF

echo "-----------------------------------------------"
echo "🎉 All systems operational!"
echo "==============================================="
