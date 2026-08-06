#!/usr/bin/env bash
# AWS port of run_gcloud_paper09_2host.sh
set -euo pipefail

# Configuration
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
REGION="ap-northeast-2"
INSTANCE_TYPE="c6i.xlarge"
# Ubuntu 22.04 LTS (amd64) in ap-northeast-2 (Dynamic search preferred)
AMI_ID="" 
SERVER_NAME="paper09-aws-net-server"
CLIENT_NAME="paper09-aws-net-client"
SSH_USER="ubuntu"
WORK_DIR="/home/ubuntu/WarmLogic"
KEY_NAME="paper09-aws-key"
KEY_FILE="${KEY_NAME}.pem"
SG_NAME="paper09-socket-eval-sg"
PORT=5001

# Ensure run from root
if [[ ! -f "pyproject.toml" ]]; then
    echo "Error: Must run from repo root."
    exit 1
fi

echo "=== AWS Setup Check ==="
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI not found in PATH."
    exit 1
fi

# Find Ubuntu 22.04 AMI
if [[ -z "${AMI_ID}" ]]; then
    echo "Finding latest Ubuntu 22.04 AMI..."
    AMI_ID=$(aws ec2 describe-images --region "${REGION}" \
        --owners 099720109477 \
        --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' --output text)
    echo "Found AMI: ${AMI_ID}"
fi

# 1. SSH Key
if [[ ! -f "${KEY_FILE}" ]]; then
    echo "Creating SSH key pair..."
    aws ec2 create-key-pair --key-name "${KEY_NAME}" --region "${REGION}" --query 'KeyMaterial' --output text > "${KEY_FILE}"
    chmod 400 "${KEY_FILE}"
else
    echo "Using existing key file: ${KEY_FILE}"
fi

# 2. Security Group
if ! aws ec2 describe-security-groups --group-names "${SG_NAME}" --region "${REGION}" >/dev/null 2>&1; then
    echo "Creating security group ${SG_NAME}..."
    SG_ID=$(aws ec2 create-security-group --group-name "${SG_NAME}" --description "Paper 09 benchmark" --region "${REGION}" --query 'GroupId' --output text)
    # Allow SSH (from anywhere for now, or use your IP)
    aws ec2 authorize-security-group-ingress --group-id "${SG_ID}" --protocol tcp --port 22 --cidr 0.0.0.0/0 --region "${REGION}"
    # Allow 5001 from same SG
    aws ec2 authorize-security-group-ingress --group-id "${SG_ID}" --protocol tcp --port "${PORT}" --source-group "${SG_ID}" --region "${REGION}"
else
    SG_ID=$(aws ec2 describe-security-groups --group-names "${SG_NAME}" --region "${REGION}" --query 'SecurityGroups[0].GroupId' --output text)
    echo "Security group ${SG_NAME} exists (${SG_ID})."
fi

echo "=== Packaging Source Code ==="
TAR_NAME="warmlogic_src_aws.tgz"
STAGING_DIR="out/tmp_src_aws_$$"
trap "chmod -R u+w ${STAGING_DIR}; rm -rf ${STAGING_DIR}" EXIT
mkdir -p "${STAGING_DIR}"
git archive --format=tar HEAD | tar -x -C "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}/scripts/eval"
cp -r scripts/eval/. "${STAGING_DIR}/scripts/eval/"
mkdir -p "${STAGING_DIR}/warm_logic_rs"
cp -r rust_core/. "${STAGING_DIR}/warm_logic_rs/"
find "${STAGING_DIR}/warm_logic_rs" -name "target" -type d -exec rm -rf {} + 2>/dev/null || true
tar -czf "${TAR_NAME}" -C "${STAGING_DIR}" .

echo "=== Provisioning EC2 Instances ==="
function get_instance_id() {
    aws ec2 describe-instances --region "${REGION}" \
        --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=running,pending" \
        --query 'Reservations[0].Instances[0].InstanceId' --output text
}

for VM_NAME in "${SERVER_NAME}" "${CLIENT_NAME}"; do
    ID=$(get_instance_id "${VM_NAME}")
    if [[ "${ID}" == "None" ]]; then
        echo "Creating ${VM_NAME}..."
        aws ec2 run-instances \
            --image-id "${AMI_ID}" \
            --instance-type "${INSTANCE_TYPE}" \
            --key-name "${KEY_NAME}" \
            --security-group-ids "${SG_ID}" \
            --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=50,VolumeType=gp3}" \
            --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${VM_NAME}}]" \
            --region "${REGION}" --count 1 >/dev/null
        sleep 5
    fi
done

echo "Waiting for instances to be running..."
while true; do
    S_STATE=$(aws ec2 describe-instances --region "${REGION}" --filters "Name=tag:Name,Values=${SERVER_NAME}" "Name=instance-state-name,Values=running,pending" --query 'Reservations[0].Instances[0].State.Name' --output text)
    C_STATE=$(aws ec2 describe-instances --region "${REGION}" --filters "Name=tag:Name,Values=${CLIENT_NAME}" "Name=instance-state-name,Values=running,pending" --query 'Reservations[0].Instances[0].State.Name' --output text)
    if [[ "${S_STATE}" == "running" && "${C_STATE}" == "running" ]]; then break; fi
    echo "Still waiting (Server=${S_STATE}, Client=${C_STATE})..."
    sleep 10
done

SERVER_IP=$(aws ec2 describe-instances --region "${REGION}" --filters "Name=tag:Name,Values=${SERVER_NAME}" "Name=instance-state-name,Values=running" --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)
SERVER_DNS=$(aws ec2 describe-instances --region "${REGION}" --filters "Name=tag:Name,Values=${SERVER_NAME}" "Name=instance-state-name,Values=running" --query 'Reservations[0].Instances[0].PublicDnsName' --output text)
CLIENT_DNS=$(aws ec2 describe-instances --region "${REGION}" --filters "Name=tag:Name,Values=${CLIENT_NAME}" "Name=instance-state-name,Values=running" --query 'Reservations[0].Instances[0].PublicDnsName' --output text)

# For dev machines without public DNS, try PublicIpAddress
if [[ -z "${SERVER_DNS}" || "${SERVER_DNS}" == "None" ]]; then
    SERVER_DNS=$(aws ec2 describe-instances --region "${REGION}" --filters "Name=tag:Name,Values=${SERVER_NAME}" "Name=instance-state-name,Values=running" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
    CLIENT_DNS=$(aws ec2 describe-instances --region "${REGION}" --filters "Name=tag:Name,Values=${CLIENT_NAME}" "Name=instance-state-name,Values=running" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
fi

echo "Server: ${SERVER_DNS} (${SERVER_IP})"
echo "Client: ${CLIENT_DNS}"

if [ "${SKIP_SETUP:-0}" != "1" ]; then
    echo "=== Uploading and Setup === "
    for DNS in "${SERVER_DNS}" "${CLIENT_DNS}"; do
        echo "Wait for SSH on ${DNS}..."
        until ssh -i "${KEY_FILE}" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${SSH_USER}@${DNS}" exit 2>/dev/null; do
            sleep 5
        done
        scp -i "${KEY_FILE}" -o StrictHostKeyChecking=no "${TAR_NAME}" "${SSH_USER}@${DNS}:~/"
        ssh -i "${KEY_FILE}" -o StrictHostKeyChecking=no "${SSH_USER}@${DNS}" "
            rm -rf ${WORK_DIR} && mkdir -p ${WORK_DIR} && tar -xzf ${TAR_NAME} -C ${WORK_DIR}
            cd ${WORK_DIR}
            sudo apt-get update -qq
            sudo apt-get install -y -qq git build-essential pkg-config python3 python3-venv python3-pip python3-dev >/dev/null
            if ! command -v cargo &>/dev/null; then
                 curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y >/dev/null
            fi
        "
    done

    echo "=== Building Environments on Server ==="
    ssh -i "${KEY_FILE}" -o StrictHostKeyChecking=no "${SSH_USER}@${SERVER_DNS}" "
        cd ${WORK_DIR}
        source \"\$HOME/.cargo/env\"
        python3 scripts/eval/collect_stock_pyo3_telemetry.py --run-id setup_stock --repeats 1 || true
        python3 scripts/eval/collect_patched_pyo3_telemetry.py --run-id setup_patch --repeats 1 || true
    "
fi

echo "=== Running 2-Host Benchmark (AWS) ==="
RATES=${RATES:-"50.0,100.0,200.0"}
MSGS_PER_CONN=${MSGS_PER_CONN:-100}

for ENV_TYPE in "stock" "patched"; do
    if [[ "${ENV_TYPE}" == "stock" && "${SKIP_STOCK:-0}" == "1" ]]; then
        echo "Skipping Stock Benchmark (SKIP_STOCK=1)"
        continue
    fi

    VENV_DIR="_${ENV_TYPE}_pyo3_venv"
    echo "Starting Server Orchestrator (AWS/${ENV_TYPE})..."
    ssh -i "${KEY_FILE}" -o StrictHostKeyChecking=no "${SSH_USER}@${SERVER_DNS}" \
        "cd ${WORK_DIR} && screen -d -m bash -c \"RATES=${RATES} bash ${WORK_DIR}/scripts/eval/eval_paper09_server_orchestrator.sh ${WORK_DIR} ${ENV_TYPE} ${VENV_DIR} ${PORT} aws > ${WORK_DIR}/server_orchestrator_${ENV_TYPE}.log 2>&1\""
    
    echo "Starting Client Orchestrator (AWS/${ENV_TYPE})..."
    RATES=${RATES:-"50.0"}
    MSGS_PER_CONN=${MSGS_PER_CONN:-100}
    ssh -i "${KEY_FILE}" -o StrictHostKeyChecking=no "${SSH_USER}@${CLIENT_DNS}" \
        "cd ${WORK_DIR} && RATES=${RATES} MSGS_PER_CONN=${MSGS_PER_CONN} bash ${WORK_DIR}/scripts/eval/eval_paper09_client_orchestrator.sh ${WORK_DIR} ${SERVER_IP} ${ENV_TYPE} ${PORT} aws"
    
    # Download (Wildcard for Rate Sweep directories)
    echo "Downloading results for ${ENV_TYPE}..."
    mkdir -p "out/bridge_eval"
    scp -i "${KEY_FILE}" -o StrictHostKeyChecking=no -r "${SSH_USER}@${CLIENT_DNS}:${WORK_DIR}/out/bridge_eval/socket_server_net_${ENV_TYPE}_aws_x86_64_*" "out/bridge_eval/"
done

echo "=== Merging Results ==="
for ET in "stock" "patched"; do
  python3 scripts/eval/merge_socket_server_net_telemetry.py \
    recv_only=out/bridge_eval/socket_server_net_${ET}_aws_x86_64_recv_only/socket_server_net_telemetry.json \
    set_bytesvec=out/bridge_eval/socket_server_net_${ET}_aws_x86_64_set_bytesvec/socket_server_net_telemetry.json \
    set_vec=out/bridge_eval/socket_server_net_${ET}_aws_x86_64_set_vec/socket_server_net_telemetry.json \
    --run-id socket_server_net_${ET}_aws_x86_64 \
    --out out/bridge_eval/socket_server_net_${ET}_aws_x86_64/socket_server_net_telemetry.json
done

echo "=== Updating Table 14 ==="
python3 scripts/eval/update_paper09_tables.py --cloud aws

echo "=== Cleanup ==="
S_ID=$(get_instance_id "${SERVER_NAME}")
C_ID=$(get_instance_id "${CLIENT_NAME}")
aws ec2 terminate-instances --instance-ids "${S_ID}" "${C_ID}" --region "${REGION}"
echo "Done."
