#!/usr/bin/env bash
set -e

echo "==============================================="
echo "📦 WarmLogic System Sanity Check"
echo "==============================================="

# Determine project root
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"
export WARMLOGIC_DISABLE_TORCH=1
export OMP_NUM_THREADS=1

echo "[1/3] Nucleus Integrity (100-Year Restart)..."
python3 "$ROOT_DIR/scripts/verify_100_year_restart.py" || exit 1
echo "✔ Nucleus Integrity OK"

echo "[2/3] Kinetic Identity (Hardware Binding)..."
python3 "$ROOT_DIR/scripts/test_kinetic_identity.py" || exit 1
echo "✔ Kinetic Identity OK"

echo "[3/3] distributed Mesh (Sovereign Sieve)..."
python3 "$ROOT_DIR/scripts/test_galactic_mesh.py" || exit 1
echo "✔ distributed Mesh OK"

echo "-----------------------------------------------"
echo "🎉 All systems operational!"
echo "==============================================="
