#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_ID=$(gcloud config get-value project)
ZONE="us-central1-a"
MACHINE_TYPE="e2-standard-4"
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_FAMILY="ubuntu-2204-lts"
SERVER_NAME="paper09-net-server"
CLIENT_NAME="paper09-net-client"
SSH_USER="ubuntu"
WORK_DIR="WarmLogic"
FW_RULE="paper09-socket-net-8080"

# Ensure run from root
if [[ ! -f "pyproject.toml" ]]; then
    echo "Error: Must run from repo root."
    exit 1
fi

echo "=== Packaging Source Code ==="
TAR_NAME="warmlogic_src.tgz"
STAGING_DIR="out/tmp_src_2host_$$"
# Cleanup trap
trap "chmod -R u+w ${STAGING_DIR}; rm -rf ${STAGING_DIR}" EXIT

mkdir -p "${STAGING_DIR}"

# 1. Extract git archive
git archive --format=tar HEAD | tar -x -C "${STAGING_DIR}"

# 2. Overlay scripts and warm_logic_rs
mkdir -p "${STAGING_DIR}/scripts/eval"
cp -r scripts/eval/. "${STAGING_DIR}/scripts/eval/"
mkdir -p "${STAGING_DIR}/warm_logic_rs"
cp -r rust_core/. "${STAGING_DIR}/warm_logic_rs/"
# Prune build artifacts
find "${STAGING_DIR}/warm_logic_rs" -name "target" -type d -exec rm -rf {} + 2>/dev/null || true
find "${STAGING_DIR}/warm_logic_rs" -name ".target*" -type d -exec rm -rf {} + 2>/dev/null || true
rm -rf "${STAGING_DIR}/warm_logic_rs/.cargo_local"
rm -rf "${STAGING_DIR}/warm_logic_rs/.cargo_home"

# 3. Create .tgz
tar -czf "${TAR_NAME}" -C "${STAGING_DIR}" .
# Cleanup handled by trap
echo "Created ${TAR_NAME} ($(du -h ${TAR_NAME} | cut -f1))"

if [ "${SKIP_SETUP:-0}" != "1" ]; then
    echo "=== Provisioning VMs ==="
    for VM_NAME in "${SERVER_NAME}" "${CLIENT_NAME}"; do
        if ! gcloud compute instances describe "${VM_NAME}" --zone="${ZONE}" >/dev/null 2>&1; then
            echo "Creating ${VM_NAME}..."
            gcloud compute instances create "${VM_NAME}" \
                --project="${PROJECT_ID}" --zone="${ZONE}" \
                --machine-type="${MACHINE_TYPE}" \
                --image-family="${IMAGE_FAMILY}" --image-project="${IMAGE_PROJECT}" \
                --boot-disk-size="50GB" --boot-disk-type="pd-balanced" \
                --tags="${VM_NAME}" \
                --quiet
            echo "Waiting for SSH..."
            sleep 20
        else
            echo "${VM_NAME} already exists."
        fi

        # Upload Code
        echo "Uploading code to ${VM_NAME}..."
        MAX_RETRIES=5
        COUNT=0
        SUCCESS=0
        while [[ $COUNT -lt $MAX_RETRIES ]]; do
            if gcloud compute scp "${TAR_NAME}" "${SSH_USER}@${VM_NAME}:~/" --zone="${ZONE}" --verbosity=error; then
                SUCCESS=1
                break
            fi
            sleep 5
            COUNT=$((COUNT+1))
        done
        if [[ $SUCCESS -eq 0 ]]; then echo "Failed upload to ${VM_NAME}"; exit 1; fi

        # Provision Deps
        echo "Provisioning deps on ${VM_NAME}..."
        CMD="
            set -e
            rm -rf ${WORK_DIR}
            mkdir -p ${WORK_DIR}
            tar -xzf ${TAR_NAME} -C ${WORK_DIR}
            cd ${WORK_DIR}
            sudo apt-get update -qq
            sudo apt-get install -y -qq git build-essential pkg-config python3 python3-venv python3-pip python3-dev >/dev/null
            if ! command -v cargo &> /dev/null; then
                 curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y >/dev/null
            fi
        "
        gcloud compute ssh "${SSH_USER}@${VM_NAME}" --zone="${ZONE}" --command="${CMD}"
    done

    echo "=== Network Setup ==="
    if ! gcloud compute firewall-rules describe "${FW_RULE}" >/dev/null 2>&1; then
        echo "Creating firewall rule ${FW_RULE}..."
        gcloud compute firewall-rules create "${FW_RULE}" \
          --network=default \
          --allow=tcp:8080 \
          --target-tags="${SERVER_NAME}" \
          --source-tags="${CLIENT_NAME}" \
          --quiet
    else
        echo "Firewall rule ${FW_RULE} exists."
    fi

    echo "=== Building Environments on Server ==="
    BUILD_CMD="
        cd ${WORK_DIR}
        source \"\$HOME/.cargo/env\"
        export PATH=\"\$HOME/.cargo/bin:\$PATH\"
        # Build Stock Venv
        echo 'Building Stock Venv...'
        python3 scripts/eval/collect_stock_pyo3_telemetry.py --run-id setup_stock --repeats 1 || true
        # Build Patched Venv
        echo 'Building Patched Venv...'
        python3 scripts/eval/collect_patched_pyo3_telemetry.py --run-id setup_patch --repeats 1 || true
    "
    gcloud compute ssh "${SSH_USER}@${SERVER_NAME}" --zone="${ZONE}" --command="${BUILD_CMD}"
fi
SERVER_IP=$(gcloud compute instances describe "${SERVER_NAME}" --zone="${ZONE}" --format='get(networkInterfaces[0].networkIP)')
echo "Server Internal IP: ${SERVER_IP}"

echo "=== Running 2-Host Benchmark ==="

RUN_IDS=""

# Helper for reliable gcloud calls
function run_with_retry() {
    local MAX_RETRIES=5
    local COUNT=0
    while [[ $COUNT -lt $MAX_RETRIES ]]; do
        if "$@"; then
            return 0
        fi
        RC=$?
        echo "Command failed with exit code $RC. Retrying ($((COUNT+1))/${MAX_RETRIES}) in 5s..."
        sleep 5
        COUNT=$((COUNT+1))
    done
    return 255
}

for ENV_TYPE in "stock" "patched"; do
    VENV_DIR="_${ENV_TYPE}_pyo3_venv"
    # For client run_id, we need to match what merge script expects?
    # Actually we just pull the dirs.
    
    # 1. Start Server Orchestrator (Async, decoupled from SSH)
    echo "Starting Server Orchestrator on ${SERVER_NAME}..."
    gcloud compute ssh "${SSH_USER}@${SERVER_NAME}" --zone="${ZONE}" --command="nohup bash ${WORK_DIR}/scripts/eval/eval_paper09_server_orchestrator.sh ${WORK_DIR} ${ENV_TYPE} ${VENV_DIR}  >> server_orchestrator_${ENV_TYPE}.log 2>&1 &"
    
    # 2. Start Client Orchestrator (Sync)
    echo "Starting Client Orchestrator on ${CLIENT_NAME}..."
    gcloud compute ssh "${SSH_USER}@${CLIENT_NAME}" --zone="${ZONE}" --command="bash ${WORK_DIR}/scripts/eval/eval_paper09_client_orchestrator.sh ${WORK_DIR} ${SERVER_IP} ${ENV_TYPE}"
    
    # 3. Download results for all 3 APIs
    for API in "recv_only" "set_bytesvec" "set_vec"; do
        CLIENT_RUN_ID_BASE="socket_server_net_${ENV_TYPE}_gcp_x86_64_${API}"
        echo "Downloading results for ${API}..."
        run_with_retry gcloud compute scp --recurse "${SSH_USER}@${CLIENT_NAME}:${WORK_DIR}/out/bridge_eval/${CLIENT_RUN_ID_BASE}" "out/bridge_eval/" --zone="${ZONE}"
    done
done

echo "=== Merging Results ==="
# Merge Stock
python3 scripts/eval/merge_socket_server_net_telemetry.py \
  recv_only=out/bridge_eval/socket_server_net_stock_gcp_x86_64_recv_only/socket_server_net_telemetry.json \
  set_bytesvec=out/bridge_eval/socket_server_net_stock_gcp_x86_64_set_bytesvec/socket_server_net_telemetry.json \
  set_vec=out/bridge_eval/socket_server_net_stock_gcp_x86_64_set_vec/socket_server_net_telemetry.json \
  --run-id socket_server_net_stock_gcp_x86_64 \
  --out out/bridge_eval/socket_server_net_stock_gcp_x86_64/socket_server_net_telemetry.json

# Merge Patched
python3 scripts/eval/merge_socket_server_net_telemetry.py \
  recv_only=out/bridge_eval/socket_server_net_patched_gcp_x86_64_recv_only/socket_server_net_telemetry.json \
  set_bytesvec=out/bridge_eval/socket_server_net_patched_gcp_x86_64_set_bytesvec/socket_server_net_telemetry.json \
  set_vec=out/bridge_eval/socket_server_net_patched_gcp_x86_64_set_vec/socket_server_net_telemetry.json \
  --run-id socket_server_net_patched_gcp_x86_64 \
  --out out/bridge_eval/socket_server_net_patched_gcp_x86_64/socket_server_net_telemetry.json

echo "=== Updating Table 14 ==="
python3 scripts/eval/update_paper09_tables.py

echo "=== Cleanup ==="
echo "Deleting VMs..."
gcloud compute instances delete "${SERVER_NAME}" "${CLIENT_NAME}" --zone="${ZONE}" --quiet
echo "Done."
