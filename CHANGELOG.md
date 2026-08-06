# Changelog

All notable changes to the **WarmLogic** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-13

### Kinetic Fusion Release
**WarmLogic v1.1.0** extends the Sovereign Civilizational Infrastructure with multi-region federation, hardware security modules, and post-quantum consensus integration.

### New Features (Federation & Security)
- **Cross-Region State Synchronization** (`state_sync.py`):
  - Vector Clock-based causal ordering for distributed decisions
  - Merkle Tree state verification for efficient sync validation
  - Last-Writer-Wins (LWW) conflict resolution with callback hooks
  - Binary protocol for efficient network transmission

- **Hardware Security Module Integration** (`hsm.py`):
  - **Apple Secure Enclave**: P-256 key generation, signing, verification via OpenSSL bridge
  - **TPM 2.0**: Full tpm2-tools integration for Linux hardware attestation
  - **HSM Manager**: Auto-detection of best available HSM with graceful fallback

- **ML-DSA-65 BFT Consensus** (`consensus.py`):
  - Post-quantum signature generation for all proposals
  - Vote signature verification with registered public keys
  - Automatic voter registration during vote reception

### Infrastructure
- 68 CI/CD workflow files for comprehensive testing
- 42 new unit tests for features
- Repository cleanup: Removed 7,000+ obsolete files (-710,000 lines)

### Security posture: no independent audit; see docs/CLAIM_EVIDENCE.md for measured status

---

## [1.0.0] (closure) - 2026-02-11

### 🚀 Initial release
**WarmLogic v1.0.0-omega** marks the transition from a research prototype to a a post-quantum signing/governance kernel. This is a single-host research prototype; see docs/CLAIM_EVIDENCE.md for the graded status of each claim.

### ✨ New Features (Sovereignty)
- **Sovereign Intelligence Daemon**: A recursive, self-improving agent loop (`sovereign_intelligence.py`) capable of proactive goal setting and evolution.
- **Hardware Anchoring**:
  - `HardwareAttestation` binds the OS to specific Silicon IDs (Milk-V Duo S / SG2000).
  - `ShieldGuard` (Rust) enforces memory boundaries and secret protection in the kernel.
- **Kinetic Permissions**: PQC-signed (ML-DSA-65) Access Control Lists (ACL) integrated into the DHT.
- **Formal Verification**: TLA+ invariants and ZK-Proof commitments ensure system safety cannot be bypassed.
- **Physical Networking**:
  - WAN Resilience (Tailscale Binding).
  - Thermal Throttling (Biological feedback from hardware sensors).

### 🛡️ Security Hardening
- **Simulation Purge**: Removed all artificial delays, mocks, and "Training Wheels". The system runs on bare metal reality.
- **Byzantine Revocation**: Implemented signed BRL (Byzantine Revocation List) to eject compromised nodes.
- **Killpulse**: A "emergency-halt" watchdog that can physically halt the kernel if ethical invariants ($\tau_{ethics} < 0.85$) are violated.

### 🏗️ Infrastructure
- **Universal Build**: Docker-based production pipeline with `STRICT_HARDWARE=1` enforcement.
- **Sovereign Economy**: Integrated Token Ledger and Compute Market for AI-to-AI resource exchange.

### 🐛 Bug Fixes
- Fixed `AttributeError` in `CreditManager` persistence logic.
- Resolved `SocialStore` lock contention during high-stress booting.
- Corrected Python 3.9 type hinting incompatibilities in `shield.py`.
- Fixed `HardwareLock` race conditions during multi-threaded initialization.

---
## [0.9.3] - 2026-01-20
### Added
- Initial Rust Core integration (`warm_logic_rs`).
- Basic DHT Kademlia routing.
