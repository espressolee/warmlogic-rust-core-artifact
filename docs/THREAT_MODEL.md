# WarmLogic Threat Model

> **Version**: 1.0 (February 2026)
> **Status**: Pre-audit baseline
> **Purpose**: Document attack surfaces, threat actors, and current mitigations in preparation for third-party security audit.

---

## 1. System Overview

WarmLogic is a dual-language runtime (Rust + Python) that attaches cryptographic evidence to AI decisions. The system handles:

- Post-quantum key generation and signing (ML-DSA-65)
- Byzantine fault-tolerant consensus
- Zero-knowledge proof generation and verification
- Append-only ledger storage
- Peer-to-peer networking (Kademlia DHT)
- Governance policy enforcement

### Trust Boundaries

```
+---------------------------------------------------------------+
|  UNTRUSTED                                                    |
|  [Network]  [User Input]  [External AI Models]                |
+---------------------------------------------------------------+
        |            |              |
        v            v              v
+---------------------------------------------------------------+
|  BOUNDARY: Python Kernel (input validation, policy engine)    |
+---------------------------------------------------------------+
        |
        v
+---------------------------------------------------------------+
|  TRUSTED: Rust Core (crypto, consensus, ledger, ZK proofs)    |
+---------------------------------------------------------------+
        |
        v
+---------------------------------------------------------------+
|  TRUSTED: Hardware Layer (TPM/SEP — currently simulated)      |
+---------------------------------------------------------------+
```

**Primary trust boundary**: The PyO3 FFI interface between Python and Rust. All data crossing this boundary should be treated as potentially adversarial.

---

## 2. Threat Actors

### A1: External Network Attacker
- **Capability**: Can observe and inject network traffic
- **Goal**: Disrupt consensus, forge evidence, partition nodes
- **Relevance**: High (Kademlia DHT is UDP-based)

### A2: Byzantine Node Operator
- **Capability**: Controls one or more nodes in the BFT cluster
- **Goal**: Commit fraudulent blocks, double-vote, manipulate consensus
- **Relevance**: High (core threat model for BFT)

### A3: Insider with DB Access
- **Capability**: Physical access to the machine running WarmLogic
- **Goal**: Tamper with ledger, extract private keys, modify audit logs
- **Relevance**: High (financial institution scenario)

### A4: Quantum Adversary (Future)
- **Capability**: Access to a cryptographically relevant quantum computer
- **Goal**: Forge signatures on historical audit records ("harvest now, decrypt later")
- **Relevance**: Medium (10-15 year timeline, but audit records have long retention)

### A5: Malicious AI Model
- **Capability**: Provides crafted inputs to the WarmLogic SDK
- **Goal**: Bypass policy engine, generate misleading evidence bundles
- **Relevance**: Medium (depends on SDK integration pattern)

---

## 3. Attack Surface Analysis

### 3.1 Cryptographic Module (`rust_core/src/crypto.rs`)

**Assets**: Private keys, signatures, key generation entropy

| Threat | Description | Current Mitigation | Gap |
|--------|-------------|-------------------|-----|
| T-C1: Key extraction | Private key leaked from memory | `Zeroize` + `ZeroizeOnDrop` derive on `PQCKeypair` | Keys stored as hex Strings — `Zeroize` on String is best-effort, not guaranteed (heap allocator may retain copies) |
| T-C2: Simulated key acceptance | vHSM simulated keys (`WARM-KEY-SIM-`) accepted in production | `verify_raw()` rejects `WARM-KEY-SIM-` prefix (line 82) | Only checked in verify path. Sign path does not reject simulated keys. No runtime flag to enforce production-only mode |
| T-C3: Key generation entropy | Weak RNG leads to predictable keys | Uses `fips204::ml_dsa_65::try_keygen()` which uses OS entropy | No additional entropy health check. No FIPS 140-3 validated RNG |
| T-C4: Private key format | Private key stored as `pk_hex:sk_hex` concatenation | Functional | Non-standard format. If pk portion is modified, sign path may use wrong public key context |
| T-C5: Timing side-channel | `verify_raw()` returns early on various failure conditions | Multiple early returns (hex decode, length check, etc.) | Early returns may leak information about key/signature structure. Not constant-time at the application layer (underlying `fips204` crate may be constant-time) |
| T-C6: Panic in sign path | `py_generate()` calls `sign_raw().expect()` | `sign_raw()` returns `Result` | Python-facing `sign()` at line 114 uses `.expect()` — panics on failure instead of returning error. Violates `#![deny(clippy::expect_used)]` if applied to this module |

**Priority**: T-C1 (key zeroization), T-C6 (panic), T-C5 (timing)

### 3.2 Consensus Engine (`rust_core/src/consensus.rs`)

**Assets**: Vote integrity, quorum finality, block commitment

| Threat | Description | Current Mitigation | Gap |
|--------|-------------|-------------------|-----|
| T-B1: Forged vote | Attacker submits vote with invalid signature | `submit_vote()` calls `MLDSA::verify_raw()` on every vote | Working correctly |
| T-B2: Double voting | Same voter submits multiple votes for same block | `HashSet<String>` for voter IDs per block | Prevents duplicate voter_id but does not detect if same validator uses different key pairs. No slashing for double-vote attempts |
| T-B3: Vote replay | Old votes replayed for new blocks | Block hash is part of signed intent (`VOTE:{block_hash}:{decision}`) | No term/epoch number in vote. A vote for a reused block hash could theoretically be replayed |
| T-B4: Quorum manipulation | Attacker controls enough nodes to reach quorum | Standard BFT threshold: `(2N/3)+1` | No validator set management. No mechanism to add/remove validators dynamically. No stake-based validator selection |
| T-B5: Memory exhaustion | Attacker floods votes for many block hashes | No limit on `votes` HashMap size | Unbounded HashMap growth. No eviction of old/uncommitted vote sets |
| T-B6: No view change | Leader failure blocks consensus | No view change protocol | Single-leader assumption. No leader rotation or timeout mechanism |

**Priority**: T-B5 (DoS), T-B3 (replay), T-B6 (liveness)

### 3.3 Zero-Knowledge Proofs (`rust_core/src/proof_zk.rs`)

**Assets**: Proof integrity, commitment binding, witness secrecy

| Threat | Description | Current Mitigation | Gap |
|--------|-------------|-------------------|-----|
| T-Z1: H generator manipulation | If H = k*G for known k, Pedersen commitment is not hiding | H derived from `SHA3-512("WarmLogic_H_Generator")` via `from_uniform_bytes` | Correct: nothing-up-my-sleeve derivation. No known issue |
| T-Z2: Weak randomness in proof | Predictable k,s in Sigma protocol | Uses `Scalar::random(&mut OsRng)` | Relies on OS entropy. No additional randomness checks |
| T-Z3: Vartime operations | Side-channel leakage from variable-time scalar multiplication | Uses `vartime_multiscalar_mul` in verification | Verification is acceptable (public inputs). Proof generation also safe (random k,s). Documented as design choice |
| T-Z4: Proof malleability | Third party creates alternative valid proof for same commitment | Fiat-Shamir via Merlin transcript | Transcript binds challenge to commitment + announcement. Standard construction |
| T-Z5: Commitment reuse | Same commitment used across multiple proofs leaks information | No commitment deduplication check | Application layer should track used commitments |

**Priority**: T-Z5 (commitment reuse tracking)

### 3.4 Ledger (`rust_core/src/ledger.rs`)

**Assets**: Block integrity, state consistency, append-only property

| Threat | Description | Current Mitigation | Gap |
|--------|-------------|-------------------|-----|
| T-L1: Ledger tampering | Direct modification of Sled database files | Hash chain (each block references previous block hash) | Sled is an embedded DB — anyone with filesystem access can modify it. No disk encryption. No integrity check on startup beyond hash chain |
| T-L2: Sled data corruption | Sled beta-quality storage engine loses data | Sled's built-in crash recovery | Sled is pre-1.0 (v0.34.7). Known issues with data loss on crash. Not suitable for financial-grade storage without external backup |
| T-L3: State root manipulation | Incorrect state root allows invalid balance proofs | State root recalculated from transaction replay | No Merkle tree for efficient proof of inclusion/exclusion |

**Priority**: T-L1 (filesystem access), T-L2 (Sled reliability)

### 3.5 PyO3 FFI Boundary (`rust_core/src/lib.rs`)

**Assets**: Data integrity across language boundary, memory safety

| Threat | Description | Current Mitigation | Gap |
|--------|-------------|-------------------|-----|
| T-F1: Oversized input | Python passes very large strings/bytes to Rust | No input size validation at FFI boundary | Rust may allocate unbounded memory based on Python input |
| T-F2: Invalid UTF-8 | Python passes non-UTF-8 bytes as string arguments | PyO3 handles UTF-8 validation | Low risk — PyO3 enforces str type |
| T-F3: Concurrent access | Multiple Python threads call Rust simultaneously | GIL release for long operations | Rust structs not inherently thread-safe. BFTEngine uses `&mut self` which prevents concurrent access |

**Priority**: T-F1 (input size validation)

### 3.6 Network Layer (Python Kademlia DHT)

**Assets**: Node identity, routing table integrity, message authenticity

| Threat | Description | Current Mitigation | Gap |
|--------|-------------|-------------------|-----|
| T-N1: Eclipse attack | Attacker fills routing table with malicious nodes | PQC signature verification on messages | Single-bucket Kademlia — no k-bucket splitting. Trivially eclipsable in current implementation |
| T-N2: Sybil attack | Attacker creates many identities cheaply | No proof-of-work or stake requirement | Node ID derived from key generation — free to create unlimited identities |
| T-N3: Message spoofing | Forged messages attributed to legitimate nodes | Messages signed with ML-DSA-65 | Signature verification prevents spoofing |
| T-N4: UDP amplification | Attacker uses WarmLogic nodes as amplifier | No rate limiting | Standard UDP amplification risk |
| T-N5: Block propagation | StitchServer incomplete — blocks don't propagate | N/A | **Critical gap**: BFT consensus exists but blocks cannot propagate between nodes. System is effectively single-node |

**Priority**: T-N5 (critical functionality gap), T-N1 (eclipse), T-N2 (Sybil)

### 3.7 Governance Kernel (Python)

**Assets**: Policy enforcement, halt capability, operational mode integrity

| Threat | Description | Current Mitigation | Gap |
|--------|-------------|-------------------|-----|
| T-G1: Policy bypass | Malicious input crafted to avoid policy evaluation | Policy engine validates all actions | Policy engine rules are configurable — misconfiguration could create gaps |
| T-G2: Halt evasion | System should halt but doesn't | Four-mode system (NORMAL → VETO_LOCK) with e_stab formula | Python-based — a compromised Python process could skip halt checks |
| T-G3: Audit log tampering | Append-only JSONL logs modified | SHA-256 integrity hash per entry | No external witness. Logs stored on same filesystem — root access can delete or truncate |

**Priority**: T-G2 (halt enforcement in Python vs Rust), T-G3 (audit log integrity)

---

## 4. Risk Summary

### Critical (Must fix before any deployment)

| ID | Threat | Component |
|----|--------|-----------|
| T-N5 | StitchServer incomplete — no P2P block propagation | Network |
| T-L2 | Sled beta storage for financial data | Ledger |
| T-C6 | Panic in Python-facing sign path | Crypto |

### High (Must fix before financial institution deployment)

| ID | Threat | Component |
|----|--------|-----------|
| T-C1 | Key zeroization on heap Strings is unreliable | Crypto |
| T-B5 | Unbounded HashMap growth in BFTEngine | Consensus |
| T-L1 | No disk encryption for Sled database | Ledger |
| T-N1 | Single-bucket Kademlia trivially eclipsable | Network |
| T-N2 | Free Sybil identity creation | Network |
| T-G2 | Governance halt logic in Python (bypassable) | Kernel |

### Medium

| ID | Threat | Component |
|----|--------|-----------|
| T-C5 | Non-constant-time application-layer verification | Crypto |
| T-B3 | Vote replay (no epoch/term) | Consensus |
| T-B6 | No view change protocol | Consensus |
| T-F1 | No input size validation at FFI boundary | FFI |
| T-Z5 | No commitment reuse tracking | ZK Proofs |
| T-G3 | Audit log integrity (same filesystem) | Kernel |

### Low

| ID | Threat | Component |
|----|--------|-----------|
| T-C2 | Simulated key not rejected in sign path | Crypto |
| T-C4 | Non-standard private key format | Crypto |
| T-Z3 | Vartime operations (acceptable for verification) | ZK Proofs |
| T-F2 | Invalid UTF-8 (handled by PyO3) | FFI |

---

## 5. Recommendations for Security Audit

### Audit Scope (Recommended)

**Phase 1 — Cryptographic Core** (highest priority)
- `rust_core/src/crypto.rs` — ML-DSA-65 key management, sign/verify
- `rust_core/src/proof_zk.rs` — Sigma protocol, Pedersen commitments
- `rust_core/src/consensus.rs` — BFT vote verification
- Focus: correctness, side-channels, memory safety

**Phase 2 — Storage and State**
- `rust_core/src/ledger.rs` — Block chain integrity, state management
- Sled database reliability assessment
- Hash chain verification completeness

**Phase 3 — FFI and Integration**
- `rust_core/src/lib.rs` — PyO3 boundary safety
- Python kernel policy enforcement
- Input validation completeness

### Pre-Audit Actions

1. Add `cargo-fuzz` targets for all public Rust APIs
2. Run `cargo-audit` and resolve all advisories
3. Add input size limits at FFI boundary
4. Fix `.expect()` in Python-facing sign path
5. Document all known limitations in code comments

---

## 6. Known Limitations (Not Vulnerabilities)

These are documented design limitations at research prototype:

| Limitation | Impact | Plan |
|-----------|--------|------|
| vHSM is simulated | No hardware trust anchor | TPM/SEP integration planned |
| Single-bucket Kademlia | Not scalable for large networks | K-bucket splitting in roadmap |
| StitchServer incomplete | Effectively single-node | P2P block propagation in development |
| No UC proof | Composability not formally proven | Academic collaboration planned |
| Sled is beta | Storage reliability concerns | Evaluate RocksDB/SQLite migration |
| macOS-only hardware attestation | Limited cross-platform support | Linux TPM support planned |
| ~60% test coverage | Insufficient for crypto code | Target 80%+ with fuzzing |

---

## 7. Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02 | Initial threat model, pre-audit baseline |
