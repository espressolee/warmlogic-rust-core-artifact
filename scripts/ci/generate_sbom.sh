#!/bin/bash
# WarmLogic SBOM Generator
# Generates a CycloneDX SBOM for the sovereign runtime.

set -e

OUT_DIR="out/sbom"
mkdir -p "$OUT_DIR"

echo "🛡️ Generating CycloneDX SBOM..."

# Use the locked requirements for maximum precision
if [ -f requirements.lock ]; then
    # We use --requirements instead of --pip to ensure we use the hash-verified lockfile
    cyclonedx-py requirements requirements.lock --format json --output "$OUT_DIR/bom.json"
    cyclonedx-py requirements requirements.lock --format xml --output "$OUT_DIR/bom.xml"
else
    echo "⚠️ requirements.lock not found. Falling back to environment scan..."
    cyclonedx-py environment --format json --output "$OUT_DIR/bom.json"
fi

echo "✅ SBOM generated at $OUT_DIR/bom.json"
