#!/bin/bash
set -e

# WarmLogic Hardware Fleet Builder
# Builds Rust Core for IoT targets (ARM64, RISC-V) using Docker/Maturin.

echo "🔒 Building WarmLogic Rust Core for Hardware Fleet..."

# 1. ARM64 (Raspberry Pi 4/Zero 2 W)
echo "   --> Target: aarch64-unknown-linux-gnu (RPi)"
docker run --rm -v "$(pwd)/warm_logic_rs:/io" ghcr.io/pyo3/maturin build --release --target aarch64-unknown-linux-gnu --features python

# 2. RISC-V (VisionFive 2 / Milk-V)
echo "   --> Target: riscv64gc-unknown-linux-gnu (RISC-V)"
# Note: Ensure the docker image supports RISC-V. If not, this might fail or require a specialized image.
# We attempt standard maturin image first.
docker run --rm -v "$(pwd)/warm_logic_rs:/io" ghcr.io/pyo3/maturin build --release --target riscv64gc-unknown-linux-gnu --features python

echo "✅ Build Complete for all targets."
echo "📦 Artifacts located in warm_logic_rs/target/wheels/"
