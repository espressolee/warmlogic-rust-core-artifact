# Changelog

All notable changes to WarmLogic Rust Core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- HybridHSM architecture combining hardware attestation with PQC signatures
- Apple Secure Enclave real API support (`sep-hardware` feature)
- SECURITY_FINDINGS.md comprehensive vulnerability report
- ONE_PAGER.md bilingual executive summary
- PITCH_DECK.md investor presentation outline

### Changed
- Updated pyo3 from 0.22.6 to 0.24.2 (fixes RUSTSEC-2025-0020 buffer overflow)
- Updated ratatui from 0.26 to 0.29
- Security score improved from 95/100 to 96/100

### Security
- Fixed pyo3 buffer overflow vulnerability (RUSTSEC-2025-0020)

---

## [1.0.1] - 2026-02-12

### Added
- **HybridHSM**: New HSM architecture for hardware attestation + software PQC
  - Combines ECDSA P-256 (hardware) with ML-DSA-65 (software)
  - Provides quantum resistance with hardware binding
- **Apple Secure Enclave**: Real SEP integration when `sep-hardware` feature enabled
  - Key generation using `SecKey::generate()`
  - ECDSA signing with SHA-256
- TPM 2.0 framework (signing implementation pending)
- Rate limiting: 100 messages/IP/second with auto-ban
- Message size validation: 8KB maximum
- IP banning mechanism: 5-minute ban on violations
- Sybil attack prevention: NodeId = SHA3(pubkey) binding
- Eclipse attack mitigation: Maximum 3 peers per /24 subnet
- Replay protection: Round-bound vote messages
- Lock poisoning recovery for all critical mutexes

### Changed
- HSM abstraction layer unified across vHSM, SEP, and TPM backends
- Vote verification now mandatory with ML-DSA-65 signatures
- Key material properly zeroized after use
- AES-GCM nonce generation randomized (was hardcoded)

### Fixed
- **C1**: AES-GCM nonce reuse vulnerability (`hardware/mod.rs`)
- **C2**: Private key exposure in memory (`hardware/v_hsm.rs`)
- **C3**: Vote signature verification bypass (`consensus/bft.rs`)
- **C4**: Sigma protocol challenge reuse (`crypto.rs`)
- **H1**: Key material not zeroized (`hardware/mod.rs`)
- **H2**: Panic on HSM signing failure (`hardware/v_hsm.rs`)
- **H3**: TPU mutex poisoning panic (`hardware/tpu.rs`)
- **H4**: Unbounded vote count DoS (`consensus/bft.rs`)
- **H5**: Unverified peer updates (`net/kademlia.rs`)
- **H6-H7**: Missing rate limiting and IP banning (`net/transport.rs`)
- **M1-M8**: Network security hardening (see SECURITY_AUDIT.md)

### Security
- 4 CRITICAL vulnerabilities fixed
- 7 HIGH vulnerabilities fixed
- 8 MEDIUM vulnerabilities fixed
- Security score: 96/100

---

## [1.0.0] - 2026-02-01

### Added
- Post-quantum cryptography (ML-DSA-65, ML-KEM-768) via NIST FIPS 203/204
- BFT consensus engine with quorum detection
- Merkle state machine ledger
- Kademlia DHT for peer discovery
- VirtualHSM (software) for development
- Zero-knowledge proofs (Groth16 with arkworks)
- Hardware entropy sources (macOS, Linux)
- PyO3 Python bindings for FFI
- WASM build support
- Bare-metal kernel binary

### Security
- Initial security implementation
- Cryptographic primitives from audited RustCrypto crates
- NIST FIPS certified algorithms

---

## [0.9.0] - 2026-01-15

### Added
- Core cryptographic module (`crypto.rs`)
- Consensus module (`consensus/bft.rs`)
- Ledger module (`ledger.rs`)
- Network module (`net/`)
- Hardware abstraction (`hardware/`)

### Changed
- Refactored from monolithic design to modular architecture

---

## Version History Summary

| Version | Date | Security Score | Key Changes |
|---------|------|----------------|-------------|
| 1.0.1 | 2026-02-12 | 96/100 | HybridHSM, security fixes |
| 1.0.0 | 2026-02-01 | 85/100 | Initial stable release |
| 0.9.0 | 2026-01-15 | 70/100 | Alpha release |

---

## Upgrade Guide

### From 1.0.0 to 1.0.1

1. Update Cargo.toml version
2. Run `cargo update`
3. No API breaking changes
4. Consider switching from `VirtualHSM` to `HybridHSM` for production

### Dependencies Updated

| Crate | From | To | Reason |
|-------|------|-----|--------|
| pyo3 | 0.22.6 | 0.24.2 | Security fix (RUSTSEC-2025-0020) |
| ratatui | 0.26 | 0.29 | Bug fixes |

---

## Links

- [Security Audit](docs/SECURITY_AUDIT.md)
- [Security Findings](docs/SECURITY_FINDINGS.md)
- [Project Scale](PROJECT_SCALE.md)
