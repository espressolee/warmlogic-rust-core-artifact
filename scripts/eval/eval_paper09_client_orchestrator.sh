#!/bin/bash
set -e
WORK_DIR=$1
SERVER_IP=$2
ENV_TYPE=$3
PORT=${4:-8080}
CLOUD=${5:-gcp}

# Ensure only one instance runs
LOCKFILE="/tmp/paper09_client.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "CLIENT ORCHESTRATOR: Already running, exiting."
    exit 0
fi

cd "$WORK_DIR"

# Ensure no stale clients are running
echo "Cleaning up stale clients..."
pkill -f "eval_paper09_socket_server_net.py client" || true
sleep 1
pkill -9 -f "eval_paper09_socket_server_net.py client" || true
sleep 1

# Configurable parameters via ENV
RATES=${RATES:-"50.0"}
MSGS_PER_CONN=${MSGS_PER_CONN:-100}

# Convert comma-separated RATES to array
IFS=',' read -ra RATE_ARRAY <<< "$RATES"

for API in "recv_only" "set_bytesvec" "set_vec"; do
    for RATE in "${RATE_ARRAY[@]}"; do
        echo "CLIENT ORCHESTRATOR: Starting API=$API RATE=$RATE for ENV=$ENV_TYPE against $SERVER_IP"
        RUN_ID="socket_server_net_${ENV_TYPE}_${CLOUD}_x86_64_${API}_rate${RATE}"
        
        # Wait for server port to be open (up to 5 minutes)
        SUCCESS=0
        for i in {1..60}; do
            if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$SERVER_IP/$PORT" 2>/dev/null; then
                echo "CLIENT ORCHESTRATOR: Server port $PORT is open"
                SUCCESS=1
                break
            fi
            echo "CLIENT ORCHESTRATOR: Waiting for server port $PORT... ($i/60)"
            sleep 5
        done
        
        if [[ $SUCCESS -eq 0 ]]; then
            echo "CLIENT ORCHESTRATOR: ERROR - Server did not open port $PORT within timeout"
            exit 1
        fi
        
        # Small buffer
        sleep 5
        
        python3 -u "${WORK_DIR}/scripts/eval/eval_paper09_socket_server_net.py" client \
            --run-id "$RUN_ID" \
            --api "$API" --server-host "$SERVER_IP" --port "$PORT" --conns 4 --payload-bytes 100000 \
            --warmup-msgs-per-conn 10 --msgs-per-conn "$MSGS_PER_CONN" --rate-hz "$RATE" --repeats 5 --timeout-s 1200 \
            --out-root "${WORK_DIR}/out"
            
        echo "CLIENT ORCHESTRATOR: Finished API=$API RATE=$RATE"
        # Wait for server to definitely exit and clean up before next phase
        sleep 15
    done
done
echo "CLIENT ORCHESTRATOR: COMPLETED ALL PHASES"
