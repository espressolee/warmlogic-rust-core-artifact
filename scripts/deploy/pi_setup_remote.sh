#!/bin/bash
# Raspberry Pi Setup Script (Remote side)
# This script runs ON the Pi.

echo "🥧 [RPi Setup] Starting environment preparation..."

# 1. Update and basic tools
sudo apt update
sudo apt install -y python3-pip python3-venv git build-essential pkg-config libssl-dev

# 2. Install Rust
if ! command -v cargo &> /dev/null; then
    echo "🦀 Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
else
    echo "✅ Rust already installed."
fi

# 3. Setup Virtual Environment
cd ~/warm_logic
if [ ! -d ".venv" ]; then
    echo "🐍 Creating Virtual Environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# 4. Install Python deps
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install maturin numpy pymavlink

# 5. Build Rust Engine
echo "⚙️  Building warm_logic_rs (on-device)..."
maturin develop --release

echo "✅ Raspberry Pi Setup Complete!"
