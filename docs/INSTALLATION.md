# Installation Guide

> **Status**: research prototype. Not externally validated; see docs/CLAIM_EVIDENCE.md.
> APIs may change before 1.0 stable release.

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **Python** | 3.12 or higher |
| **Rust** | 1.75 or higher |
| **RAM** | 4 GB |
| **Disk** | 2 GB free space |
| **OS** | macOS 12+, Ubuntu 22.04+, Windows 11 (WSL2) |

### Recommended

| Component | Recommendation |
|-----------|----------------|
| **Python** | 3.12.x |
| **Rust** | 1.78+ (latest stable) |
| **RAM** | 8 GB+ |
| **CPU** | Multi-core (Rust compilation benefits from parallelism) |

---

## Supported Platforms

| Platform | Architecture | Status |
|----------|-------------|--------|
| macOS | Apple Silicon (M1/M2/M3) | Fully Supported |
| macOS | Intel x86_64 | Fully Supported |
| Linux | x86_64 | Fully Supported |
| Linux | ARM64 | Fully Supported |
| Windows | WSL2 | Supported |
| Docker | Universal | Fully Supported |

---

## Quick Installation (Recommended)

The fastest way to get started:

```bash
git clone https://github.com/espressolee/WarmLogic
cd warmlogic
make setup
```

This command will:
1. Create a Python virtual environment
2. Install all Python dependencies
3. Compile the Rust core (`rust_core`) optimized for your hardware
4. Run verification tests

---

## Platform-Specific Instructions

### macOS (Homebrew)

```bash
# 1. Install prerequisites
brew install python@3.12 rustup-init

# 2. Initialize Rust
rustup-init -y
source ~/.cargo/env

# 3. Verify versions
python3 --version  # Should be 3.12+
rustc --version    # Should be 1.75+

# 4. Clone and install
git clone https://github.com/espressolee/WarmLogic
cd warmlogic
make setup
```

### Ubuntu / Debian

```bash
# 1. Update package list
sudo apt update

# 2. Install Python 3.12
sudo apt install python3.12 python3.12-venv python3.12-dev

# 3. Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# 4. Install build dependencies
sudo apt install build-essential pkg-config libssl-dev

# 5. Clone and install
git clone https://github.com/espressolee/WarmLogic
cd warmlogic
make setup
```

### RHEL / Fedora

```bash
# 1. Install Python 3.12
sudo dnf install python3.12 python3.12-devel

# 2. Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# 3. Install build dependencies
sudo dnf install gcc openssl-devel

# 4. Clone and install
git clone https://github.com/espressolee/WarmLogic
cd warmlogic
make setup
```

### Windows (WSL2)

```powershell
# 1. Enable WSL2 (PowerShell as Admin)
wsl --install -d Ubuntu-22.04

# 2. Open Ubuntu terminal, then follow Ubuntu instructions above
```

---

## Docker Installation

For isolated or enterprise deployments:

```bash
# Pull and run
docker-compose up -d

# Access dashboard
open http://localhost:8000

# View logs
docker-compose logs -f warmlogic

# Stop
docker-compose down
```

### Custom Docker Build

```bash
# Build from source
docker build -t warmlogic:local .

# Run with custom config
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  warmlogic:local
```

---

## Manual Installation (From Source)

For development or custom configurations:

```bash
# 1. Clone repository
git clone https://github.com/espressolee/WarmLogic
cd warmlogic

# 2. Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Compile Rust core
cd rust_core
maturin develop --release
cd ..

# 5. Install in editable mode
pip install -e .

# 6. Verify installation
python -c "import warm_logic_rs; print('Rust Core Active')"
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WARM_LOGIC_ROOT` | `~/.warm_logic` | Data directory |
| `WARM_LOGIC_CONFIG` | `config/default.yaml` | Configuration file |
| `WARM_LOGIC_LOG_LEVEL` | `INFO` | Logging level |
| `WARM_LOGIC_PORT` | `8000` | API server port |
| `RUST_LOG` | `warn` | Rust logging level |

Example:

```bash
export WARM_LOGIC_ROOT=/data/warmlogic
export WARM_LOGIC_LOG_LEVEL=DEBUG
warmlogic start
```

---

## Verification

After installation, verify everything works:

```bash
# 1. Check Rust core is loaded
python -c "import warm_logic_rs; print('OK: Rust Core')"

# 2. Check SDK imports
python -c "from warm_logic.sdk import SovereignClient; print('OK: SDK')"

# 3. Run test suite
pytest tests/ -v --tb=short

# 4. Start kernel (interactive test)
warmlogic --version
```

Expected output:

```
OK: Rust Core
OK: SDK
================================ test session starts ================================
...
================================ X passed in Y.ZZs ================================
WarmLogic 1.0.0-rc1
```

---

## Troubleshooting

### `maturin: command not found`

Install maturin in your virtual environment:

```bash
pip install maturin
```

### `Cargo not found`

Install Rust:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

### `Python.h not found`

Install Python development headers:

```bash
# Ubuntu/Debian
sudo apt install python3.12-dev

# macOS (usually included with Homebrew Python)
brew reinstall python@3.12

# Fedora
sudo dnf install python3.12-devel
```

### `OpenSSL not found`

Install OpenSSL development files:

```bash
# Ubuntu/Debian
sudo apt install libssl-dev

# macOS
brew install openssl

# Fedora
sudo dnf install openssl-devel
```

### `Permission denied` during installation

Don't use `sudo pip`. Use a virtual environment instead:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Rust compilation fails on Apple Silicon

Ensure you have the correct target:

```bash
rustup target add aarch64-apple-darwin
```

### Import errors after installation

Reinstall in development mode:

```bash
pip install -e .
```

### Tests fail with `warm_logic_rs` import error

Rebuild the Rust core:

```bash
cd rust_core
maturin develop --release
cd ..
```

### Docker container won't start

Check logs and ensure ports aren't in use:

```bash
docker-compose logs warmlogic
lsof -i :8000  # Check if port is in use
```

---

## Upgrade Guide

### From Previous Version

```bash
# 1. Pull latest changes
git pull origin main

# 2. Update dependencies
pip install -r requirements.txt --upgrade

# 3. Rebuild Rust core
cd rust_core
maturin develop --release
cd ..

# 4. Verify
pytest tests/ -v
```

### Docker Upgrade

```bash
docker-compose pull
docker-compose up -d
```

---

## Uninstall

### Remove WarmLogic

```bash
# Remove package
pip uninstall warm_logic

# Remove data directory (optional - WARNING: deletes all data)
rm -rf ~/.warm_logic
```

### Remove Docker

```bash
docker-compose down -v
docker rmi warmlogic:latest
```

---

## Next Steps

After installation:

1. [Quickstart Tutorial](tutorial/01_quickstart.md) - Your first sovereign decision
2. [Architecture Overview](ARCHITECTURE.md) - Understand the system
3. [API Reference](API_SDK.md) - SDK documentation

---

## Getting Help

- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [GitHub Issues](https://github.com/espressolee/WarmLogic/issues)
- [GitHub Discussions](https://github.com/espressolee/WarmLogic/discussions)
