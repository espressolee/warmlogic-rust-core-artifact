#!/bin/bash
# Launch a 3-node WarmLogic Mesh Cluster with Node 3 as the BYZANTINE TRAITOR.

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Define Python Interpreter
PYTHON_EXEC="python3"

# Environment base
export WARM_LOGIC_SIMULATION=1
export WARM_SIM_SANDBOX=1
export PYTHONPATH=$(pwd)/.local/lib/python3.13/site-packages:$(pwd)
export PYTHONUSERBASE=$(pwd)/.local

# Prepare directories
mkdir -p logs
mkdir -p data

# Kill existing
pkill -f "warm_logic/ui/server.py"
sleep 2

echo ">>> Launching Byzantine Stress Mesh..."

# ------------------------------------------------------------------------------
# NODE 1: Honest (The Anchor)
# ------------------------------------------------------------------------------
export WARM_HTTP_PORT=8000
export WARM_DB_PATH="data/node_8000"
export WARM_IDENTITY_SEED=8000
# Disable Chaos
export WARM_CHAOS_ENABLED=0
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8000.log 2>&1 &
echo "[+] Node 1 (Honest) started on port 8000 (PID: $!)"

# ------------------------------------------------------------------------------
# NODE 2: Honest (The Follower)
# ------------------------------------------------------------------------------
export WARM_HTTP_PORT=8001
export WARM_DB_PATH="data/node_8001"
export WARM_IDENTITY_SEED=8001
# Disable Chaos
export WARM_CHAOS_ENABLED=0
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8001.log 2>&1 &
echo "[+] Node 2 (Honest) started on port 8001 (PID: $!)"

# ------------------------------------------------------------------------------
# NODE 3: BYZANTINE TRAITOR
# ------------------------------------------------------------------------------
export WARM_HTTP_PORT=8002
export WARM_DB_PATH="data/node_8002"
export WARM_IDENTITY_SEED=8002
# Enable Chaos: High Latency, 20% Packet Loss, 20% Corruption
export WARM_CHAOS_ENABLED=1
export WARM_CHAOS_DROP_RATE=0.2
export WARM_CHAOS_LATENCY=200
export WARM_CHAOS_CORRUPTION=0.2
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8002.log 2>&1 &
echo "[!] Node 3 (BYZANTINE) started on port 8002 (PID: $!)"

echo ">>> Byzantine Cluster Active. Logs in logs/"
