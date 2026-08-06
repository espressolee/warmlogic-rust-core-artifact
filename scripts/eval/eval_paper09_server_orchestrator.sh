#!/bin/bash
set -e
WORK_DIR=$1
ENV_TYPE=$2
VENV_DIR=$3
PORT=${4:-8080}
CLOUD=${5:-gcp}

# Ensure only one instance runs
LOCKFILE="/tmp/paper09_server.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "SERVER ORCHESTRATOR: Already running, exiting."
    exit 0
fi

cd "$WORK_DIR"
source "$HOME/.cargo/env" || true

# Configurable parameters via ENV
RATES=${RATES:-"50.0"}

# Convert comma-separated RATES to array
IFS=',' read -ra RATE_ARRAY <<< "$RATES"

for API in "recv_only" "set_bytesvec" "set_vec"; do
    for RATE in "${RATE_ARRAY[@]}"; do
        echo "SERVER ORCHESTRATOR: Starting API=$API RATE=$RATE for ENV=$ENV_TYPE"
        pkill -9 -f eval_paper09_socket_server_net.py || true
        sleep 2
        
        # Start server with 5 repeats as a blocking call
        echo "SERVER ORCHESTRATOR: Executing server script..."
        WARM_LOGIC_RS_USE_INSTALLED=1 "${WORK_DIR}/out/bridge_eval/${VENV_DIR}/bin/python" -u "${WORK_DIR}/scripts/eval/eval_paper09_socket_server_net.py" server \
            --run-id "socket_server_net_${ENV_TYPE}_${CLOUD}_x86_64" \
            --api "$API" --bind-host 0.0.0.0 --port "$PORT" --conns 4 --payload-bytes 100000 --repeats 5 --timeout-s 1200
            
        echo "SERVER ORCHESTRATOR: Finished API=$API RATE=$RATE"
        sleep 2
    done
done
echo "SERVER ORCHESTRATOR: COMPLETED ALL PHASES"
