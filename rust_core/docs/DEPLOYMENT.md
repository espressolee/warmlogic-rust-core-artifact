# WarmLogic Rust Core - Deployment Guide

> ## ⚠️ NON-AUTHORITATIVE — HISTORICAL DESIGN DOCUMENT
>
> This file describes **design intent**, not the measured state of this
> artifact. It predates the publication audit and its claims were **not**
> re-verified. Several are known to be contradicted by measurement — see
> `KNOWN_LIMITATIONS.md` and `docs/CLAIM_EVIDENCE.md`, which are authoritative.
>
> Known contradictions include: multi-node/BFT deployment (never executed),
> zero-knowledge proofs (the `zk` feature does not compile), formal
> verification (Kani harnesses exist but no CI runs them; TLA+ specs are design
> documents, not checked models), and performance figures (no raw data is bound
> to this artifact).
>
> **Do not cite this file for current status.** Authoritative files:
> `README.md`, `STATUS.md`, `KNOWN_LIMITATIONS.md`, `docs/CLAIM_EVIDENCE.md`,
> `SECURITY.md`, `PUBLIC_PROVENANCE.json`, `SBOM.json`, `AUDIT_PROFILE.json`,
> `LICENSE`, `NOTICE`.

**Version**: 1.0.1
**Date**: 2026-02-12
**Security Score**: 96/100

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Deployment Options](#2-deployment-options)
3. [Docker Deployment](#3-docker-deployment)
4. [Native Deployment](#4-native-deployment)
5. [Python Integration](#5-python-integration)
6. [Security Configuration](#6-security-configuration)
7. [Monitoring](#7-monitoring)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 8+ GB |
| Disk | 1 GB | 10+ GB |
| Network | 100 Mbps | 1 Gbps |

### Software Requirements

| Software | Version | Notes |
|----------|---------|-------|
| Rust | 1.75+ | For native builds |
| Python | 3.11+ | For PyO3 bindings |
| Docker | 24.0+ | For containerized deployment |
| OpenSSL | 3.0+ | For TLS |

### Supported Platforms

| Platform | Architecture | Status |
|----------|--------------|--------|
| Linux | x86_64 | research prototype |
| Linux | aarch64 | Tested |
| macOS | Apple Silicon | research prototype |
| macOS | Intel | research prototype |
| Windows | x86_64 | Experimental |
| WASM | wasm32 | Browser Only |

---

## 2. Deployment Options

### Option A: Docker (Recommended)

Best for: Production deployments, CI/CD, containerized environments

```bash
docker-compose up -d rust-core
```

### Option B: Native Library

Best for: Embedded systems, performance-critical applications

```bash
cargo build --release
```

### Option C: Python Package

Best for: Integration with Python applications

```bash
pip install warm_logic_rs
# or
maturin develop --features python
```

---

## 3. Docker Deployment

### Quick Start

```bash
cd rust_core

# Build image
docker build -t warmlogic/rust-core:1.0.1 .

# Run container
docker run -d \
  --name warmlogic \
  --read-only \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  warmlogic/rust-core:1.0.1
```

### Docker Compose

```bash
# Development
docker-compose up -d rust-core

# Run tests
docker-compose run test

# Security audit
docker-compose run audit
```

### Multi-Architecture Build

```bash
# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t warmlogic/rust-core:1.0.1 \
  --push .
```

---

## 4. Native Deployment

### Build from Source

```bash
# Clone repository
git clone https://github.com/espressolee/warmlogic-rust-core-artifact
cd rust_core

# Build release
cargo build --release

# Run tests
cargo test --all-features

# Install library
cargo install --path .
```

### Feature Flags

| Flag | Description | Default |
|------|-------------|---------|
| `std` | Standard library | Yes |
| `python` | PyO3 bindings | No |
| `persistence` | redb storage | No |
| `zk` | Zero-knowledge proofs | No |
| `ml` | Neural network | No |
| `sep-hardware` | Apple Secure Enclave | No |
| `cockpit` | TUI dashboard | No |

```bash
# Build with specific features
cargo build --release --features "std,python,zk"
```

### Cross-Compilation

```bash
# Install target
rustup target add aarch64-unknown-linux-gnu

# Build for ARM64
cargo build --release --target aarch64-unknown-linux-gnu
```

---

## 5. Python Integration

### Installation

```bash
# Via pip (when published)
pip install warm_logic_rs

# From source
cd rust_core
pip install maturin
maturin develop --features python
```

### Usage Example

```python
import warm_logic_rs as wl

# Create PQC keypair
keypair = wl.PQCKeypair()
print(f"Public key: {keypair.public_key_hex()[:32]}...")

# Sign message
message = b"Hello, WarmLogic!"
signature = keypair.sign(message)

# Verify signature
is_valid = keypair.verify(message, signature)
print(f"Signature valid: {is_valid}")
```

### Available Classes

| Class | Description |
|-------|-------------|
| `PQCKeypair` | Post-quantum key generation |
| `MLDSA` | ML-DSA-65 signatures |
| `MLKEM` | ML-KEM-768 key encapsulation |
| `RustReplicatedLedger` | Blockchain ledger |
| `RustDHT` | Kademlia DHT |
| `BFTEngine` | Consensus engine |
| `VirtualHSM` | Software HSM |
| `HybridHSM` | Hardware + Software HSM |

---

## 6. Security Configuration

### HSM Selection

| Environment | Recommended HSM | Why |
|-------------|-----------------|-----|
| Development | VirtualHSM | Easy setup, no hardware |
| Staging | VirtualHSM | Test functionality |
| Production (Low) | VirtualHSM | Cost-effective |
| Production (High) | HybridHSM | Hardware binding + PQC |

### HybridHSM Configuration

```rust
use warm_logic_rs::hardware::{HybridHSM, HSMOperations};

// Create HybridHSM (combines hardware attestation + PQC)
let hsm = HybridHSM::new()?;

// Sign with ML-DSA-65 (quantum resistant)
let signature = hsm.sign(message)?;

// Get hardware attestation
let attestation = hsm.get_attestation_report()?;
```

### Network Security

```bash
# Rate limiting (default: 100 msg/IP/sec)
export WL_RATE_LIMIT=100

# Message size limit (default: 8KB)
export WL_MAX_MESSAGE_SIZE=8192

# Ban duration (default: 5 minutes)
export WL_BAN_DURATION=300
```

### TLS Configuration

```bash
# Generate self-signed cert (development only)
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem -out cert.pem \
  -days 365 -nodes

# For production, use proper CA certificates
```

---

## 7. Monitoring

### Metrics Endpoints

| Endpoint | Description |
|----------|-------------|
| `/health` | Basic health check |
| `/metrics` | Prometheus metrics |
| `/ready` | Readiness probe |
| `/live` | Liveness probe |

### Prometheus Metrics

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'warmlogic'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: '/metrics'
```

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `wl_signatures_total` | Counter | Total signatures created |
| `wl_verifications_total` | Counter | Total verifications |
| `wl_consensus_rounds` | Counter | BFT rounds completed |
| `wl_network_messages` | Counter | Messages processed |
| `wl_signature_latency_ms` | Histogram | Signing latency |

### Logging

```bash
# Set log level
export RUST_LOG=warn,warm_logic_rs=info

# Log to file
export WL_LOG_FILE=/var/log/warmlogic.log
```

---

## 8. Troubleshooting

### Common Issues

#### Build Failures

```bash
# Clear cache
cargo clean

# Update dependencies
cargo update

# Rebuild
cargo build --release
```

#### Memory Issues

```bash
# Increase stack size
ulimit -s unlimited

# For Docker
docker run --ulimit stack=67108864:67108864 ...
```

#### HSM Issues

```bash
# Check SEP availability (macOS)
system_profiler SPSecureElementDataType

# Check TPM availability (Linux)
ls /dev/tpm*
```

### Debug Mode

```bash
# Enable debug logging
RUST_LOG=debug cargo run

# Run with backtrace
RUST_BACKTRACE=1 cargo run
```

### Support

- **Issues**: https://github.com/espressolee/warmlogic-rust-core-artifact/issues
- **Security**: https://github.com/espressolee/warmlogic-rust-core-artifact/security
- **Documentation**: https://github.com/espressolee/warmlogic-rust-core-artifact/tree/main/docs

---

## Appendix: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUST_LOG` | `warn` | Log level |
| `WL_RATE_LIMIT` | `100` | Messages per IP per second |
| `WL_MAX_MESSAGE_SIZE` | `8192` | Max message size (bytes) |
| `WL_BAN_DURATION` | `300` | IP ban duration (seconds) |
| `WL_HSM_TYPE` | `virtual` | HSM type (virtual/hybrid) |
| `WL_DATA_DIR` | `./data` | Data directory |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.1 | 2026-02-12 | HybridHSM, security fixes |
| 1.0.0 | 2026-02-01 | Initial release |
