#!/bin/bash
# Launch a 3-node WarmLogic Global Mesh (Stitch v3)
# Simulates a Geo-Distributed Network: US-EAST, EU-WEST, AP-NORTH

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

echo ">>> Launching Global Mesh (Stitch v3)..."

# ------------------------------------------------------------------------------
# NODE 1: US-EAST (Port 8000)
# ------------------------------------------------------------------------------
export WARM_HTTP_PORT=8000
export WARM_DB_PATH="data/node_8000"
export WARM_IDENTITY_SEED=8000
export WARM_REGION="US-EAST"
export WARM_CHAOS_ENABLED=1 
# Chaos Enabled required for Topology latency to take effect in Traffic Shaper logic
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8000.log 2>&1 &
echo "[+] Node 1 (US-EAST) started on port 8000 (PID: $!)"

# ------------------------------------------------------------------------------
# NODE 2: EU-WEST (Port 8001)
# ------------------------------------------------------------------------------
export WARM_HTTP_PORT=8001
export WARM_DB_PATH="data/node_8001"
export WARM_IDENTITY_SEED=8001
export WARM_REGION="EU-WEST"
export WARM_CHAOS_ENABLED=1
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8001.log 2>&1 &
echo "[+] Node 2 (EU-WEST) started on port 8001 (PID: $!)"

# ------------------------------------------------------------------------------
# NODE 3: AP-NORTH (Port 8002)
# ------------------------------------------------------------------------------
export WARM_HTTP_PORT=8002
export WARM_DB_PATH="data/node_8002"
export WARM_IDENTITY_SEED=8002
export WARM_REGION="AP-NORTH"
export WARM_CHAOS_ENABLED=1
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8002.log 2>&1 &
echo "[+] Node 3 (AP-NORTH) started on port 8002 (PID: $!)"

echo ">>> Global Mesh Active. Latency rules enforced by NetworkTopology."
