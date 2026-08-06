#!/bin/bash
# Launch a local 3-node WarmLogic Mesh Cluster

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Define Python Interpreter (Miniconda as discovered in previous eras)
PYTHON_EXEC="python3"

# Environment base
export WARM_LOGIC_SIMULATION=1
export WARM_SIM_SANDBOX=1
export PYTHONPATH=$(pwd)/.local/lib/python3.13/site-packages:$(pwd)
export PYTHONUSERBASE=$(pwd)/.local

# Prepare directories
mkdir -p logs
mkdir -p data

# Kill existing python processes related to server.py to start fresh
pkill -f "warm_logic/ui/server.py"
sleep 2

echo ">>> Launching WarmLogic Mesh Cluster..."

# Node 1 (Port 8000, DB: data/node_8000)
export WARM_HTTP_PORT=8000
export WARM_DB_PATH="data/node_8000"
export WARM_IDENTITY_SEED=8000
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8000.log 2>&1 &
echo "[+] Node 1 started on port 8000 (PID: $!)"

# Node 2 (Port 8001, DB: data/node_8001)
export WARM_HTTP_PORT=8001
export WARM_DB_PATH="data/node_8001"
export WARM_IDENTITY_SEED=8001
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8001.log 2>&1 &
echo "[+] Node 2 started on port 8001 (PID: $!)"

# Node 3 (Port 8002, DB: data/node_8002)
export WARM_HTTP_PORT=8002
export WARM_DB_PATH="data/node_8002"
export WARM_IDENTITY_SEED=8002
nohup $PYTHON_EXEC warm_logic/ui/server.py > logs/node_8002.log 2>&1 &
echo "[+] Node 3 started on port 8002 (PID: $!)"

echo ">>> Cluster Active. Logs in logs/"
