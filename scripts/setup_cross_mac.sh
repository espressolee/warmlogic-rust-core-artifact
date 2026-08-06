#!/bin/bash
echo "🛠️  WarmLogic: Setting up Universal Cross-Compilation Environment (RISC-V + ARM64)"

# 1. Rust Targets
echo "[1/3] Configuring Rust Targets..."
targets=("riscv64gc-unknown-linux-gnu" "aarch64-unknown-linux-gnu")

for target in "${targets[@]}"; do
    if rustup target list | grep "$target (installed)" > /dev/null; then
        echo "✅ Rust Target ($target) is already installed."
    else
        echo "⚠️  Installing Rust Target: $target..."
        rustup target add $target
    fi
done

# 2. RISC-V Toolchain (Milk-V / VisionFive)
echo "[2/3] Checking RISC-V Toolchain..."
if command -v riscv64-unknown-linux-gnu-gcc > /dev/null; then
    echo "✅ RISC-V GNU Toolchain found."
else
    echo "❌ RISC-V Linker NOT found."
    echo "👉 Install: brew tap riscv-software-src/riscv && brew install riscv-tools"
fi

# 3. ARM64 Toolchain (Raspberry Pi Zero 2 W)
echo "[3/3] Checking ARM64 Toolchain..."
if command -v aarch64-unknown-linux-gnu-gcc > /dev/null; then
    echo "✅ ARM64 Linux Toolchain found."
else
    echo "❌ ARM64 Linker NOT found."
    echo "👉 Install: brew install messense/macos-cross-toolchains/aarch64-unknown-linux-gnu"
fi

echo "🎉 Universal Setup Complete. Ready for Multi-Silicon Deployment."
