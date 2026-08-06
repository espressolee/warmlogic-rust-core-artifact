# Security Policy

WarmLogic is a research prototype that handles cryptographic operations and governance decisions. We take security seriously and appreciate responsible disclosure.

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` branch (latest) | Yes |
| Tagged releases | Yes (latest only) |
| Older branches | No |

Only the latest `main` branch and the most recent tagged release receive security fixes.

---

## Reporting a Vulnerability

**Do not create a public GitHub issue for security vulnerabilities.**

### Preferred: GitHub Security Advisories

Use GitHub's private vulnerability reporting:
**Security > Report a vulnerability**

### Alternative: Email

Email: **https://github.com/espressolee/WarmLogic/security**

Include:
- Affected file paths and modules
- Minimal reproduction steps (local-only; do not attach sensitive data)
- Expected vs actual behavior
- Any evidence artifacts (logs, run IDs, manifests, hashes)

### What NOT to Include in Public Channels

- Exploit code or proof-of-concept attacks
- Credentials, keys, or tokens
- Information that could enable others to exploit the vulnerability

---

## Response Timeline

| Action | Timeline |
|--------|----------|
| Initial acknowledgment | Within 48 hours |
| Vulnerability assessment | Within 7 days |
| Patch development | Within 30 days (critical: 7 days) |
| Public disclosure | After patch release + 14 days |

This is a research project maintained by a small team. We respond on a best-effort basis but prioritize security issues.

---

## Scope

### In Scope

| Component | Path |
|-----------|------|
| Rust cryptographic core | `rust_core/src/` |
| Python kernel | `warm_logic/` |
| Consensus engine | `rust_core/src/consensus.rs` |
| Ledger and storage | `rust_core/src/ledger.rs` |
| ZK proof system | `rust_core/src/proof_zk.rs` |
| PQC signatures | `rust_core/src/crypto.rs` |
| PyO3 FFI bridge | `rust_core/src/lib.rs` |
| Governance kernel | `warm_logic/kernel/` |
| Network layer (DHT) | `warm_logic/mesh/` |
| CI/CD workflows | `.github/workflows/` |

### Out of Scope

- Test files (`tests/`)
- Documentation content (`docs/`)
- Third-party dependencies (report to their maintainers)
- Development tooling (`scripts/` except security-related scripts)
- Issues requiring physical access to the machine

---

## Security Architecture

### Design Principles

1. **Local sovereignty**: No data leaves the local environment unless explicitly authorized
2. **Immutable audit trail**: All governance actions are logged irreversibly (append-only JSONL with SHA-256 integrity hashes)
3. **Fail-closed**: The governance kernel halts on ethical constraint violations rather than continuing in a degraded state
4. **Post-quantum readiness**: ML-DSA-65 (FIPS 204) signatures protect against quantum threats

### Key Security Controls

- **PID locking**: Single kernel instance enforcement
- **vHSM key detection**: Simulated keys are prefixed with `WARM-KEY-SIM-` and rejected in production paths
- **Slashing penalties**: StateLock, EconomicBurn, and IdentityIsolation for Byzantine behavior
- **Dependency pinning**: All dependencies pinned to specific versions in `requirements.txt` and `Cargo.lock`
- **Kani verification**: 12 formal verification harnesses for safety invariants
- **Hybrid PQC**: ML-KEM-768 + X25519 key exchange with Noise Protocol patterns
- **PKCS#11 integration**: Hardware key storage via TPM 2.0 / HSM

### Known Limitations

These are documented limitations, not vulnerabilities:

- vHSM is simulated (hardware security module not yet integrated with real TPM/SEP)
- StitchServer P2P block propagation is incomplete
- No formal UC (Universal Composability) proof for ZK protocol
- No third-party security audit completed yet

### Resolved (Feb 2026)

- ~~Single-bucket Kademlia DHT~~ → Full Kademlia with iterative lookup + NAT traversal
- ~~Governance halt in Python only~~ → Rust VetoEngine with ML-DSA-65 reset
- ~~Vote replay attack risk~~ → Round field added to Vote struct
- ~~Sled beta storage~~ → Migrated to redb 2.4.0
- ~~No PQC key exchange~~ → ML-KEM-768 (FIPS 203) with Noise Protocol Framework
- ~~No formal verification~~ → 12 Kani model checking harnesses
- ~~No conviction voting~~ → Time-weighted voting with 0.1x-6x multipliers
- ~~No hardware key storage~~ → PKCS#11 integration for TPM 2.0

---

## Security Scanning

Run the same security gate as CI locally:

```bash
# Secret detection
bash scripts/ci/run_detect_secrets_gate.sh out.detect-secrets.json

# Dependency audit (Python)
pip-audit

# Dependency audit (Rust)
cargo audit

# Clippy security lints
cd rust_core && cargo clippy --all-targets
```

---

## Bug Bounty

**No monetary bug bounty is offered.** This is a single-maintainer research
project with no budget to honour one.

Reports are handled on a best-effort basis through private coordinated
disclosure (see above). Reporters who wish to be credited will be named in the
advisory and the release notes for the fix.

*No entries yet.*

---

## Incident Response

If a security anomaly is detected (unexpected lock file, hash mismatch, unauthorized key material):

1. **Terminate** all kernel instances
2. **Isolate** the network interface if applicable
3. **Audit** by running `scripts/ops/governance_audit.py`
4. **Restore** from the last known good session
5. **Report** the incident via the channels above
