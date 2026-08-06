# Changelog

All notable changes to WarmLogic are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.0.0-rc1] - 2026-02-05 (Pre-release)

### Added
- **Post-Quantum Cryptography**: ML-DSA-65 (FIPS 204) implementation in Rust core
- **Byzantine Fault Tolerance**: BFT consensus with 2f+1 quorum threshold
- **Zero-Knowledge Proofs**: Sigma protocol on Ristretto255 curve
- **Sovereign Cockpit**: Web dashboard for node monitoring and governance
- **Kademlia DHT**: Distributed hash table with K=20 buckets
- **Constitutional Guard**: Ed25519-signed YAML invariant enforcement
- **Zanzibar RBAC**: Google-style relationship-based access control
- **Autonomous Patcher**: Self-modification with governance approval

### Changed
- Python minimum version now 3.9+ (was 3.12+)
- Rust core extracted to `warm_logic_rs` crate
- Storage backend unified to Sled + SQLite

### Security
- All cryptographic keys use `zeroize` for memory scrubbing
- TPM 2.0 hardware binding (feature-gated)
- AES-256-GCM encrypted storage option

---

## [0.9.0] - 2026-01-15

### Added
- Initial Rust core with PyO3 bindings
- Basic ledger implementation
- Gossip protocol for manifest propagation

### Changed
- Migrated from pure Python to hybrid Rust+Python architecture

---

## [0.8.0] - 2026-01-01

### Added
- First prototype with Python-only implementation
- Basic governance loop
- File-based ledger storage

---

## Versioning

WarmLogic uses **Semantic Versioning** (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes to API or protocol
- MINOR: New features, backward compatible
- PATCH: Bug fixes only

## Era System

Internal development uses "Eras" for milestone tracking:
- Current stable features
- Experimental features

See [GLOSSARY.md](GLOSSARY.md) for terminology.
