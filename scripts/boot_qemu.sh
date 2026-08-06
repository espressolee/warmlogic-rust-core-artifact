#!/bin/bash
set -e

# 1. Build Kernel (no_std)
echo "💿 Building WarmLogic Kernel (Nightly)..."
cd "$(dirname "$0")/../rust_core/kernel"
cargo +nightly build --target x86_64-unknown-none -Z build-std=core,alloc,compiler_builtins -Z build-std-features=compiler-builtins-mem

# 2. Build Image (std host tool)
echo "🛠️  Creating Bootable Disk Image..."
cd ../boot_builder
cargo +nightly run --target aarch64-apple-darwin

echo "💿 Unikernel Image Generated."
