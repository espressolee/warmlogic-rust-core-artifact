#!/bin/bash
# Check architecture and suggest build command

ARCH=$(uname -m)
echo "🔍 Detected Architecture: $ARCH"

if [ "$ARCH" == "aarch64" ]; then
    echo "✅ Running on ARM64 (Jetson/Pi). Native build recommended."
    echo "🚀 Running: maturin develop --release"
    maturin develop --release
elif [ "$ARCH" == "x86_64" ]; then
    echo "⚠️  Running on x86_64. You are likely on a Dev Machine."
    echo "To build for Jetson/Pi, use cross-compilation:"
    echo "maturin build --release --target aarch64-unknown-linux-gnu"
elif [ "$ARCH" == "arm64" ]; then
    echo "🍎 Running on Apple Silicon (M1/M2/M3)."
    echo "⚠️  Native build produces macOS binaries. For Linux ARM64 (Jetson/Pi), use Docker/Cross."
    echo "Recommended: Build on the target device itself."
else
    echo "❌ Unknown Architecture: $ARCH"
fi
