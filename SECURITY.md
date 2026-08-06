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

Email: **https://github.com/espressolee/warmlogic-rust-core-artifact/security**

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

**There is none, and the table that used to be here was withdrawn.**

It promised acknowledgment within 48 hours, assessment within 7 days and a
patch within 30. That contradicted `STATUS.md`, which states this artifact has
no support SLA, and it was never something a single maintainer working on this
part-time could commit to. "Maintained by a small team" was also inaccurate:
it is one person.

What is actually true:

- Reports are read on a **best-effort basis**, with no committed timeline.
- A report may receive **no response at all**. Please plan disclosure on that
  assumption rather than waiting on an acknowledgment that may not come.
- If you need a bounded timeline, do not rely on this channel.

## What is worth reporting

This is a **single-host research artifact** with 6.76% line coverage, no
independent security review, and an explicit list of unsupported fail-open
surfaces in `STATUS.md`. Finding a vulnerability in that second list is
expected, not surprising, and it is already disclosed there.

Most useful: something that contradicts a claim the artifact actually makes —
for example a flaw in the ML-DSA-65 usage, in the build/packaging path, or a
secret or personal identifier that survived sanitization. That last category is
the one to report privately and promptly.

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

> **These are design principles, not achieved properties.** Two of them are
> contradicted by the code in this artifact; see the support boundary in
> `STATUS.md`. Kept here because they state the intent, corrected inline.

1. **Local sovereignty**: no external service is required to run. Not otherwise verified.
2. **Immutable audit trail** — **NOT ACHIEVED.** The Rust `StandardAuditLogger` writes governance events to **stdout**. There is no durable or tamper-evident ledger behind it.
3. **Fail-closed** — **NOT ACHIEVED.** Fail-*open* paths exist: the Python fallback denies three fixed strings and allows everything else, and hardened evaluation accepts an intent carrying no signature.
4. **Post-quantum readiness**: the ML-DSA-65 primitive is real and its roundtrip runs. It is not applied to every decision — the SDK signing path is unreachable.

### Key Security Controls

- **PID locking**: Single kernel instance enforcement
- **vHSM key detection**: Simulated keys are prefixed with `WARM-KEY-SIM-` and rejected in production paths
- **Slashing penalties**: StateLock, EconomicBurn, and IdentityIsolation for Byzantine behavior
- **Dependency pinning**: All dependencies pinned to specific versions in `requirements.txt` and `Cargo.lock`
- **Kani harnesses**: 12 exist in the tree. **No job runs them** — they are not executed verification.
- **Hybrid PQC**: ML-KEM-768 + X25519 with Noise Protocol patterns (tested locally)
- **PKCS#11 / TPM** — **NOT ACHIEVED as hardware-rooted trust.** The seed is derived from host identifiers (CPU UUID, disk id) through a non-cryptographic hasher, with fixed `UNKNOWN_*` fallbacks. Call it a host-identifier-derived demonstration seal, not TPM-backed sealing.

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
