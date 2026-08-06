#!/bin/bash
# run_sole_tenant_noise_reduction.sh
# Automates the collection of Table 1/13 results on a less-noisy (Sole-tenant) environment.

set -e

RUN_ID=${1:-"x86_64_sole_tenant_$(date +%Y%m%d_%H%M%S)"}
PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
ZONE="us-central1-a"
REGION="us-central1"
NODE_TEMPLATE="paper09-sole-template"
NODE_GROUP="paper09-sole-group"
VM_NAME="paper09-sole-x86"
MACHINE_TYPE="c3-standard-4"

if [ -z "$PROJECT" ]; then
    echo "ERROR: GCP Project not set. Please run 'gcloud config set project <PROJECT_ID>'"
    exit 1
fi

echo "=== Environment Check ==="
echo "Project: $PROJECT"
echo "Region/Zone: $REGION/$ZONE"
echo "RunID: $RUN_ID"

# Step 1: Resource Setup
echo "=== Step 1: Provisioning Sole-tenant Infrastructure ==="
# Find a suitable node type
NODE_TYPE=$(gcloud compute sole-tenancy node-types list --zones="$ZONE" --format="value(name)" | head -n 1)
if [ -z "$NODE_TYPE" ]; then
    echo "ERROR: No sole-tenant node types found in $ZONE"
    exit 1
fi
echo "Using Node Type: $NODE_TYPE"

gcloud compute sole-tenancy node-templates create "$NODE_TEMPLATE" \
  --node-type="$NODE_TYPE" \
  --region="$REGION" \
  --node-affinity-labels="paper=paper09" --quiet || true

gcloud compute sole-tenancy node-groups create "$NODE_GROUP" \
  --node-template="$NODE_TEMPLATE" \
  --target-size=1 \
  --zone="$ZONE" --quiet || true

echo "=== Step 2: Creating VM on Sole-tenant Node ==="
gcloud compute instances create "$VM_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --node-group="$NODE_GROUP" \
  --image-family="ubuntu-2404-lts" \
  --image-project="ubuntu-os-cloud" \
  --boot-disk-size="50GB" \
  --boot-disk-type="pd-balanced" \
  --labels="purpose=paper09-sole-tenant" \
  --quiet

# Step 3: Setup and Run
echo "=== Step 3: Preparing Environment on VM ==="
# Helper to run SSH commands
run_ssh() {
    gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="$1" --quiet
}

run_ssh "sudo apt-get update && sudo apt-get install -y git curl ca-certificates build-essential pkg-config python3 python3-venv python3-pip python3-dev"
run_ssh "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"

echo "=== Step 4: Cloning Repository and Running Benchmark ==="
REPO_URL=$(git remote get-url origin)
run_ssh "git clone $REPO_URL WarmLogic && cd WarmLogic && source \$HOME/.cargo/env && bash scripts/eval/collect_host_pack.sh $RUN_ID"

# Step 4: Retrieval und Cleanup
echo "=== Step 5: Retrieving Telemetry Pack ==="
mkdir -p out/bridge_eval
gcloud compute scp "ubuntu@${VM_NAME}:~/WarmLogic/out/bridge_eval/${RUN_ID}_pack.tgz" out/bridge_eval/ --zone="$ZONE" --quiet

echo "=== Step 6: Cleanup ==="
gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --quiet
gcloud compute sole-tenancy node-groups delete "$NODE_GROUP" --zone="$ZONE" --quiet
gcloud compute sole-tenancy node-templates delete "$NODE_TEMPLATE" --region="$REGION" --quiet

echo "=== COMPLETED ==="
echo "Pack saved to: out/bridge_eval/${RUN_ID}_pack.tgz"
echo "Next: Use scripts/eval/merge_bridge_telemetry.py to integrate results."
