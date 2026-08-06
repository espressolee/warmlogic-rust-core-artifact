## Security Policy (Warm Logic OSS)

Warm Logic is a research-grade, evidence-centric governance OS. It is **not** a production security product, and its security posture is intentionally conservative about claims.

Scope notes (read first):
- Project limitations / anti-use: `docs/oss/Safety_Scope_Warnings_v1.md`
- OSS positioning: `docs/oss/WarmLogic_OSS_Positioning_v1.md`

### Supported versions

Only the latest `main` branch is supported for security fixes.

### Reporting a vulnerability

Please prefer private reporting:
- If this repository has GitHub “Private vulnerability reporting” enabled, use **Security → Report a vulnerability**.

If private reporting is not available:
- Open an issue **without exploit details** (only a minimal description and affected paths).
- Include “SECURITY:” in the title so it can be triaged quickly.

### What to include

- Affected file paths / modules
- Minimal reproduction steps (local-only; avoid attaching sensitive data)
- Expected vs actual behavior
- Any evidence artifacts that help validate the report (logs, run_id, manifests, hashes), if applicable

### Response expectations

This is an OSS research project; triage and fixes are best-effort. If a report requires additional proof (artifact bundle, logs, or run_id), it may be marked as “missing evidence” until the report can be reproduced.

### Secret scanning (local)

- Run the same baseline gate as CI:
  - `bash scripts/ci/run_detect_secrets_gate.sh out.detect-secrets.json`
# 🛡️ SECURITY & GOVERNANCE POLICY
**Version**: 1.1 (Production Hardening Phase)
**Effective Date**: 2026-01-22

---

## 🏛️ Local Sovereignty Principles
1. **Absolute Air-Gap**: No data shall leave the local environment unless explicitly authorized via `/export`.
2. **Single instance**: Only one instance of the Kernel (Scribe) may be active at any time.
3. **Immutable History**: All governance actions are logged irreversibly.

## 🔒 Implemented Security Controls

### 1. Access Control (PID Lock)
- **Mechanism**: File-based locking (`/tmp/scribe_brain.lock`).
- **Policy**: Duplicate instances are terminated immediately with `CRITICAL` alert.
- **Reference**: `scripts/local_scribe/brain.py` (`_check_pid_lock`)

### 2. Immutable Audit Logging
- **Mechanism**: JSONL Append-only logs with SHA-256 Integrity Hash.
- **Location**: `out/audit/governance_log_YYYYMM.jsonl`
- **Scope**: All system commands (`/set`, `/pardon`, `/save`, `/export`).
- **Audit**: `scripts/ops/governance_audit.py` (Planned)

### 3. Dependency Sanitation
- **Policy**: All dependencies are pinned to specific versions in `requirements.txt`.
- **Review**: Regular automated scanning against known vulnerabilities.

### 4. Themis Impeachment Protocol
- **Trigger**: Violation of Constitutional Axioms.
- **Normalization**: Agent names are case-normalized (`strip().lower()`) to prevent 3-strikes bypass.
- **Effect**: Full system lockout (VETO) via persistent lock file.
- **Remediation**: Manual intervention required to release `IMPEACHED_SCRIBE.lock`.

### 5. Heritage Resiliency (Hermes)
- **Mechanism**: Cross-node heritage sharding and gossip.
- **Policy**: In discovery mode, nodes sync peers from trusted registries.
- **Heritage**: Distributed across shards to prevent partition-based state loss.

### 6. Hardware Governance Enclave (HGE)
- **Mechanism**: TPM PCR-bound state hashing.
- **Verification**: Kernel heartbeats verify that the physical hardware state matches the signed manifest.

---

## 🚨 Incident Response
If a security anomaly is detected (e.g., unexpected lock file, hash mismatch):
1. **Terminate**: Stop all Scribe instances.
2. **Isolate**: Disconnect network interface (if applicable).
3. **Audit**: Run `scripts/ops/governance_audit.py`.
4. **Restore**: Recover from the last known good session (`/resume`).

---
*Authorized by the Council of 42*

---

## 🔐 Vulnerability Reporting

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report them via:
1. **Email**: https://github.com/espressolee/warmlogic-rust-core-artifact/security
2. **GitHub Security Advisories**: [Report a vulnerability](https://github.com/warmlogic/warmlogic-core/security/advisories/new)

### Response Timeline

| Action                   | Timeline                          |
| ------------------------ | --------------------------------- |
| Initial Response         | Within 48 hours                   |
| Vulnerability Assessment | Within 7 days                     |
| Patch Development        | Within 30 days (critical: 7 days) |
| Public Disclosure        | After patch release + 14 days     |

---

## 💰 Bug Bounty Program

| Severity                                     | Reward               |
| -------------------------------------------- | -------------------- |
| **Critical** (RCE, Full System Compromise)   | $100 - $500          |
| **High** (Privilege Escalation, Auth Bypass) | $50 - $100           |
| **Medium** (Information Disclosure, DoS)     | $20 - $50            |
| **Low** (Minor Security Issues)              | Recognition + Credit |

### Scope

**In Scope:**
- `warm_logic/` - All core modules
- `warm_logic/alignment/intent_guard.py` - IntentGuard
- `warm_logic/system/ledger/merkle_log.py` - MerkleChain
- `warm_logic/consensus/_consensus.py` - Consensus
- `warm_logic/rust/enclave/` - SGX Enclave

**Out of Scope:**
- `tests/` - Test files
- Third-party dependencies (report to their maintainers)

---

## 🏆 Hall of Fame

Security researchers who responsibly disclose vulnerabilities will be recognized here.
