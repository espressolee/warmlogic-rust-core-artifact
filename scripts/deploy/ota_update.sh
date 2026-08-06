#!/bin/bash
# WarmLogic OTA Update Skeleton
# This script is triggered by the kernel when a Council Update Proposal is ratified.

set -e

NEW_IMAGE_HASH=$1

if [ -z "$NEW_IMAGE_HASH" ]; then
    echo "❌ Error: No image hash provided."
    exit 1
fi

echo "🔄 Starting OTA Update for WarmLogic Node..."
echo "📍 Target Hash: $NEW_IMAGE_HASH"

# 1. Pull new image
echo "📡 Pulling new image..."
docker pull warmlogic/kernel@sha256:$NEW_IMAGE_HASH

# 2. Atomic Restart
echo "🚀 Performing Atomic Restart..."
docker-compose -f docker/docker-compose.prod.yml down
docker-compose -f docker/docker-compose.prod.yml up -d

# 3. Post-Update Health Check
echo "🏥 Waiting for kernel stabilization..."
sleep 10
HEALTH=$(curl -s http://localhost:8000/health | grep "UP")

if [ ! -z "$HEALTH" ]; then
    echo "✅ Update Successful. Node is back online."
else
    echo "❌ Update Failed. Rollback initiated (if configured)."
    # Rollback logic could be added here.
    exit 1
fi
