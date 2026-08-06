#!/bin/sh
set -e

INSTALL_ROOT=${1:-/root}
echo "=== Offline Rust Installer ==="
echo "Target Root: $INSTALL_ROOT"

export RUSTUP_HOME=$INSTALL_ROOT/.rustup
export CARGO_HOME=$INSTALL_ROOT/.cargo
export PATH="$CARGO_HOME/bin:$PATH"

if [ -d "$CARGO_HOME/bin" ]; then
    echo "Rust already installed at $CARGO_HOME."
    cargo --version
    exit 0
fi

if [ ! -f "rust-1.75.0-riscv64gc-unknown-linux-gnu.tar.gz" ]; then
    echo "Error: rust tarball not found!"
    ls -l
    exit 1
fi

echo "Extracting Rust binaries..."
tar -xzf rust-1.75.0-riscv64gc-unknown-linux-gnu.tar.gz

echo "Installing Rust..."
cd rust-1.75.0-riscv64gc-unknown-linux-gnu
./install.sh --prefix=$CARGO_HOME --components=cargo,rustc,rust-std-riscv64gc-unknown-linux-gnu

echo "Configuring environment..."
# Create env file
mkdir -p $CARGO_HOME
echo "export RUSTUP_HOME=$RUSTUP_HOME" > $CARGO_HOME/env
echo "export CARGO_HOME=$CARGO_HOME" >> $CARGO_HOME/env
echo 'export PATH="$CARGO_HOME/bin:$PATH"' >> $CARGO_HOME/env

# Verify
source $CARGO_HOME/env
rustc --version
cargo --version

echo "Rust installation complete."
cd ..
rm -rf rust-1.75.0-riscv64gc-unknown-linux-gnu
