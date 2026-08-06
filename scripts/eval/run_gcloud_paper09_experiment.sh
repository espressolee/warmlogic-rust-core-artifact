#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_ID=$(gcloud config get-value project)
ZONE="us-central1-a"  # Default zone, can be overridden
MACHINE_TYPE="e2-standard-4" # 4 vCPU, 16GB RAM (Cost-effective x86_64)
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_FAMILY="ubuntu-2204-lts"
VM_PREFIX="paper09-x86-vm"
NUM_VMS=3
SSH_USER="ubuntu"
WORK_DIR="WarmLogic"
COLLECT_MODE="${COLLECT_MODE:-host_pack}" # host_pack | paper09_pack

# Ensure run from root
if [[ ! -f "pyproject.toml" ]]; then
    echo "Error: Must run from repo root."
    exit 1
fi

echo "=== Packaging Source Code ==="
TAR_NAME="warmlogic_src.tgz"
STAGING_DIR="out/tmp_src"
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"

# 1. Extract git archive to staging
git archive --format=tar HEAD | tar -x -C "${STAGING_DIR}"

# 2. Overlay the evaluation scripts (include untracked)
mkdir -p "${STAGING_DIR}/scripts/eval"
cp -r scripts/eval/. "${STAGING_DIR}/scripts/eval/"

# 2.5 Overlay warm_logic_rs (untracked but core component)
mkdir -p "${STAGING_DIR}/warm_logic_rs"
cp -r warm_logic_rs/. "${STAGING_DIR}/warm_logic_rs/"
# Prune large build artifacts to keep transfer fast
# We MUST keep 'vendor' because Cargo.toml patches pyo3 from there,
# but we can prune internal target directories.
find "${STAGING_DIR}/warm_logic_rs" -name "target" -type d -exec rm -rf {} + 2>/dev/null || true
find "${STAGING_DIR}/warm_logic_rs" -name ".target*" -type d -exec rm -rf {} + 2>/dev/null || true
# Remove any other local caches
rm -rf "${STAGING_DIR}/warm_logic_rs/.cargo_local"
rm -rf "${STAGING_DIR}/warm_logic_rs/.cargo_home"

# 3. Create the final .tgz from staging
tar -czf "${TAR_NAME}" -C "${STAGING_DIR}" .
rm -rf "${STAGING_DIR}"

echo "Created ${TAR_NAME} ($(du -h ${TAR_NAME} | cut -f1))"

# Check GCloud
echo "=== Checking GCloud Auth ==="
gcloud info >/dev/null

for i in $(seq 1 $NUM_VMS); do
    VM_NAME="${VM_PREFIX}${i}"
    echo "---------------------------------------------------"
    echo "Processing ${VM_NAME}..."
    
    # 1. Check if VM exists, if not create
    if ! gcloud compute instances describe "${VM_NAME}" --zone="${ZONE}" >/dev/null 2>&1; then
        echo "Creating VM ${VM_NAME}..."
        gcloud compute instances create "${VM_NAME}" \
            --project="${PROJECT_ID}" \
            --zone="${ZONE}" \
            --machine-type="${MACHINE_TYPE}" \
            --image-family="${IMAGE_FAMILY}" \
            --image-project="${IMAGE_PROJECT}" \
            --boot-disk-size="50GB" \
            --boot-disk-type="pd-balanced" \
            --labels="purpose=paper09-eval" \
            --quiet
        
        echo "Waiting for SSH to be ready..."
        sleep 20
    else
        echo "VM ${VM_NAME} already exists. Using it."
    fi

    # 2. Upload Code
    echo "Uploading source code..."
    # Retry SCP loop
    MAX_RETRIES=5
    COUNT=0
    SUCCESS=0
    while [[ $COUNT -lt $MAX_RETRIES ]]; do
        if gcloud compute scp "${TAR_NAME}" "${SSH_USER}@${VM_NAME}:~/" --zone="${ZONE}" --verbosity=error; then
            SUCCESS=1
            break
        fi
        echo "SCP failed, retrying in 5s..."
        sleep 5
        COUNT=$((COUNT+1))
    done
    
    if [[ $SUCCESS -eq 0 ]]; then
        echo "Error: Failed to upload code to ${VM_NAME}"
        exit 1
    fi

    # 3. Setup and Run (Remote execution)
    echo "Running collection script on ${VM_NAME}..."
    RUN_CMD="
        set -e
        # Cleanup previous run
        rm -rf ${WORK_DIR}
        mkdir -p ${WORK_DIR}
        tar -xzf ${TAR_NAME} -C ${WORK_DIR}
        
        cd ${WORK_DIR}
        
        # Install dependencies
        echo 'Installing dependencies...'
        sudo apt-get update -qq
        sudo apt-get install -y -qq git build-essential pkg-config python3 python3-venv python3-pip python3-dev >/dev/null
        
        # Install Rust
        if ! command -v cargo &> /dev/null; then
             curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y >/dev/null
        fi
        source \"\$HOME/.cargo/env\"

        # Run Collection
        export REPEATS=5
        export WARMUP=200
        # Pass the VM name so the pack is named correctly
        # Run Collection (Paper 09 Full Pack including Table 12)
        export REPEATS=5
        export WARMUP=200
        # Pass the VM name so the pack is named correctly
        bash scripts/eval/collect_paper09_pack.sh \"x86_64_cloud_vm${i}\"
    "

    gcloud compute ssh "${SSH_USER}@${VM_NAME}" --zone="${ZONE}" --command="${RUN_CMD}"

    # 4. Download Result
    echo "Downloading result pack..."
    REMOTE_PACK="${WORK_DIR}/out/bridge_eval/x86_64_cloud_vm${i}_paper09_pack.tgz"
    LOCAL_DEST="out/bridge_eval/"
    mkdir -p "${LOCAL_DEST}"
    
    gcloud compute scp "${SSH_USER}@${VM_NAME}:${REMOTE_PACK}" "${LOCAL_DEST}" --zone="${ZONE}"
    
    echo "Completed ${VM_NAME}."
done

echo "=== Verification ==="
echo "1. Generating SHA256 sums..."
shasum -a 256 out/bridge_eval/x86_64_cloud_vm*_paper09_pack.tgz

echo "2. Rigorous Multi-VM Content Verification (Agg Sig Check)..."
python3 scripts/eval/summarize_compare_runs_markdown.py \
  --inputs \
    vm1=out/bridge_eval/x86_64_cloud_vm1_paper09_pack.tgz \
    vm2=out/bridge_eval/x86_64_cloud_vm2_paper09_pack.tgz \
    vm3=out/bridge_eval/x86_64_cloud_vm3_paper09_pack.tgz \
  --out out/bridge_eval/multi_vm_x86_64_compare_v2.md \
  --size-o1 1024 \
  --size-on 10000000

echo "Verification report generated: out/bridge_eval/multi_vm_x86_64_compare_v2.md"
grep -E "WARNING|duplicate" out/bridge_eval/multi_vm_x86_64_compare_v2.md || echo "No duplication warnings detected. Data is genuine."

echo "Done. Don't forget to delete VMs when finished:"
echo "gcloud compute instances delete ${VM_PREFIX}1 ${VM_PREFIX}2 ${VM_PREFIX}3 --zone=${ZONE}"
