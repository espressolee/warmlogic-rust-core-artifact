#!/bin/bash
set -e

echo "🔒 Building Sovereign Enclave Image..."
docker build -f warm_logic/ops/nitro_enclave/Dockerfile.sovereign -t warmlogic:sovereign .

echo "📐 Calculating PCR0 (Simulated Measurement)..."
# In a real AWS Nitro build, 'nitro-cli build-enclave' generates the PCR values.
# Here we simulate valid measurement by hashing the image ID.

IMAGE_ID=$(docker inspect --format='{{.Id}}' warmlogic:sovereign)
PCR0=$(echo $IMAGE_ID | shasum -a 256 | awk '{print $1}')

echo "---------------------------------------------------"
echo "✅ Enclave Built Successfully"
echo "   Image: warmlogic:sovereign"
echo "   PCR0:  $PCR0 (Bind this to your KMS Policy)"
echo "---------------------------------------------------"
echo "To run (Simulation):"
echo "docker run --rm --read-only --network none warmlogic:sovereign"
