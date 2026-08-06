#!/bin/bash
# WarmLogic SBOM Generator
# Generates a unified CycloneDX SBOM for both Rust and Python dependencies.

set -e

OUTPUT_DIR="meta/security"
mkdir -p "$OUTPUT_DIR"

echo "🛡️  Generating WarmLogic SBOM..."

# 1. Python SBOM
if command -v cyclonedx-py &> /dev/null; then
    echo "🐍 Harvesting Python dependencies..."
    cyclonedx-py requirements ./requirements.lock --output-format json --output-file "$OUTPUT_DIR/sbom_python.json"
else
    echo "⚠️  cyclonedx-py not found. Skipping Python SBOM."
fi

# 2. Rust SBOM
if command -v cargo-cyclonedx &> /dev/null; then
    echo "🦀 Harvesting Rust dependencies..."
    cd warm_logic_rs
    cargo cyclonedx --format json --output-pattern "$OUTPUT_DIR/sbom_rust.json"
    cd ..
else
    echo "⚠️  cargo-cyclonedx not found. Skipping Rust SBOM."
# 3. Sign artifacts (Defense-Grade Provenance)
if command -v cosign &> /dev/null; then
    echo "🔏 Signing SBOM artifacts..."
    cosign sign-blob --yes "$OUTPUT_DIR/sbom_python.json" --output-signature "$OUTPUT_DIR/sbom_python.json.sig"
    cosign sign-blob --yes "$OUTPUT_DIR/sbom_rust.json" --output-signature "$OUTPUT_DIR/sbom_rust.json.sig"
else
    echo "ℹ️  cosign not found. Skipping artifact signing."
fi

echo "✅ SBOM generation complete. Check $OUTPUT_DIR"
