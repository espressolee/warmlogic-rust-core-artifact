#!/bin/bash
# Build warm_logic_rs for MilkV Duo S (RISC-V 64-bit)
# Uses Zig for cross-compilation (bundled with maturin) as it handles correct glibc linking better than raw cargo.

echo "🥛 [MilkV Duo S] Building warm_logic_rs for riscv64gc..."

# 1. Check for maturin
if ! command -v maturin &> /dev/null; then
    echo "❌ maturin not found. Installing with zig support..."
    pip install "maturin[zig]"
else
    echo "✅ maturin found."
fi

# 2. Build for RISC-V
# Target: riscv64gc-unknown-linux-musl (Correct for the flashed musl image)
# We use --zig feature of maturin which creates a contained build environment
# Note: We enforce abi3 support for cross-Python compatibility (3.9 - 3.12+)
echo "🚀 Starting compilation (Target: musl, Feature: abi3)..."
# Verify target is installed
rustup target add riscv64gc-unknown-linux-musl

maturin build --release --target riscv64gc-unknown-linux-musl --zig

STATUS=$?

if [ $STATUS -eq 0 ]; then
    echo "✅ Build Success!"
    echo "📦 Artifacts located in target/wheels/:"
    ls -lh target/wheels/*riscv64*
    echo ""
    echo "👉 Now Transfer to MilkV:"
    echo "   scp target/wheels/warm_logic_rs-*.whl root@<MILKV_IP>:/root/"
    echo "   ssh root@<MILKV_IP> 'pip install warm_logic_rs-*.whl'"
else
    echo "💥 Build Failed."
    echo "Check if 'zig' is installed or try docker mode:"
    echo "maturin build --release --target riscv64gc-unknown-linux-gnu -m rust_core/Cargo.toml --compatibility linux"
fi
