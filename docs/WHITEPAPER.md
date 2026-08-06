# WarmLogic: A Post-Quantum Cryptographic Runtime for Verifiable AI Governance

> **Authors**: espressolee
> **Version**: 1.0 (February 2026)
> **Status**: Release Candidate (experimental)
> **License**: MIT (kernel) + Elastic License v2 (enterprise)

---

## Abstract

Artificial intelligence systems increasingly make consequential decisions in finance, healthcare, hiring, and criminal justice, yet no widely adopted infrastructure exists to produce tamper-proof cryptographic evidence of *why* a decision was made. Existing governance approaches — model cards, datasheets, and regulatory frameworks — prescribe documentation requirements but provide no cryptographic substrate to enforce them. Meanwhile, the imminent threat of quantum computing renders today's digital signatures vulnerable within 10-15 years, undermining the long-term validity of any audit trail built on classical cryptography.

We present **WarmLogic**, an open-source runtime that attaches cryptographic evidence to AI decisions through four integrated mechanisms: (1) **post-quantum digital signatures** using ML-DSA-65 (NIST FIPS 204), (2) **Byzantine fault-tolerant consensus** with a quorum threshold of floor(2N/3)+1, (3) **zero-knowledge proofs** via a Sigma protocol on the Ristretto255 curve, and (4) a **reflective governance kernel** with formally verified safety invariants. The system is implemented as a dual-language runtime — a Rust core for cryptographic safety with `no_std` support, bridged to Python via PyO3 zero-copy FFI achieving a documented 300x throughput improvement over naive binding approaches.

We formalize two core safety properties in TLA+: **MethodologicalIntegrity** (no execution without trusted provenance) and **LedgerImmutable** (the evidence ledger is append-only), both machine-checked via the TLC model checker.

**WarmLogic is a research prototype at research prototype status (experimental)**, designed to provide the evidence infrastructure that the EU AI Act (effective August 2026) and NIST PQC migration timeline (2024-2030) will require. The system is not production-ready. Significant engineering gaps remain, including incomplete P2P block propagation, simulated hardware security module, and pending third-party security audit. The system is open-source, with the cryptographic kernel under MIT license.

**Keywords**: Post-quantum cryptography, AI governance, Byzantine fault tolerance, zero-knowledge proofs, formal verification, FIPS 204, EU AI Act, evidence-based AI

---

## 1. Introduction

### 1.1 Motivation

AI systems are making decisions with real consequences for real people. A credit-scoring model denies a loan. A medical imaging system flags a tumor. A hiring algorithm filters out a candidate. In each case, the affected individual — and the regulator overseeing the institution — has a fundamental question: *why did the AI make this decision, and can we prove it operated within policy?*

Current governance approaches are insufficient to answer this question with cryptographic rigor:

- **Model cards** [Mitchell et al. 2019] and **datasheets for datasets** [Gebru et al. 2021] document intended use and limitations, but produce no runtime evidence that the documented constraints were actually enforced during inference.
- **AI factsheets** [Arnold et al. 2019] capture metadata about AI systems, but this metadata is self-reported and mutable — there is no mechanism to prevent retroactive modification.
- **Regulatory frameworks** such as the EU AI Act (Regulation 2024/1689) mandate decision traceability, human oversight documentation, and risk management for high-risk AI systems (Articles 6, 9, 14, 17), but assume the existence of technical infrastructure that does not yet exist at the cryptographic level.

The gap is not in *what* should be documented, but in *how* to make that documentation tamper-proof, verifiable, and resilient to both classical and quantum adversaries.

This gap is compounded by the quantum computing timeline. NIST finalized its post-quantum cryptography standards in 2024 — FIPS 203 (ML-KEM), FIPS 204 (ML-DSA), and FIPS 205 (SLH-DSA) — with migration guidance recommending completion by 2030 for critical infrastructure. The EU PQC Roadmap sets the same 2030 deadline. Any audit trail built today on classical signatures (ECDSA, Ed25519) will be vulnerable to "harvest now, decrypt later" attacks within the retention periods required by financial and healthcare regulations.

### 1.2 Contributions

This paper presents WarmLogic, the first system to integrate post-quantum cryptography, Byzantine fault tolerance, zero-knowledge proofs, and a reflective governance kernel into a single runtime for AI decision evidence. Our specific contributions are:

1. **Architectural integration of PQC + BFT + ZK + governance**. We demonstrate that ML-DSA-65 signatures can be natively embedded in a BFT consensus protocol where every vote is individually signed and verified, with zero-knowledge proofs attached to committed blocks — all orchestrated by a governance kernel that can halt the system when ethical constraints are violated.

2. **Formal verification of core safety properties**. We specify and machine-check two safety invariants using TLA+ and the TLC model checker: *MethodologicalIntegrity* (the system cannot execute on untrusted artifacts) and *LedgerImmutable* (the evidence ledger is append-only). Additionally, we formalize the witness chain protocol ensuring Byzantine-safe log prefix agreement across nodes.

3. **A reflective governance kernel** with the stability equation `e_stab = alpha * epsilon_c + beta * (1 - tau_ethics)` that defines four operational modes (NORMAL, SUSPICIOUS, CRITICAL_HALT, VETO_LOCK), where ethical constraint violations can autonomously halt the system — a "fail-closed" design philosophy.

4. **A zero-copy FFI bridge** between Python (the dominant ML/AI ecosystem) and Rust (the cryptographic core), achieving a documented 300x throughput improvement over naive sequence-copy approaches for 10MB payloads, enabling practical integration with existing AI pipelines.

5. **An open-source implementation at research prototype**, with 187 JSON schemas across 34 domains enforcing a schema-first development discipline (SSOT: Schema > Spec > Code > Test), 26 TLA+ formal specifications, and 90+ CI workflows.

### 1.3 Paper Organization

Section 2 surveys related work across AI governance, post-quantum cryptography, BFT consensus, and zero-knowledge proofs. Section 3 presents the system design, covering the cryptographic substrate, consensus layer, replicated ledger, and governance kernel. Section 4 details the formal verification approach and results. Section 5 describes implementation decisions. Section 6 presents evaluation results. Section 7 discusses limitations, regulatory alignment, and future work. Section 8 concludes.

---

## 2. Background and Related Work

### 2.1 AI Governance and Accountability

The AI governance landscape has evolved from voluntary frameworks to binding regulation. Model cards [Mitchell et al. 2019] established the practice of documenting model performance characteristics. Datasheets for datasets [Gebru et al. 2021] extended this to training data provenance. AI factsheets [Arnold et al. 2019] proposed comprehensive documentation including fairness metrics, robustness testing, and lineage tracking.

The EU AI Act (Regulation 2024/1689) moves beyond voluntary documentation. Article 9 requires high-risk AI providers to implement risk management systems with "appropriate and targeted measures." Article 14 mandates human oversight with the ability to "interrupt, correct or reverse" AI decisions. Article 17 requires quality management systems with documented procedures for "data management, training, testing and validation."

These requirements implicitly assume that organizations can produce *verifiable evidence* of compliance — that a decision was made by a specific model version, under a specific policy, at a specific time. Current AI observability platforms (Weights & Biases, LangSmith, Arize) provide metric logging and experiment tracking, but this data is stored in mutable databases controlled by the platform operator. There is no cryptographic guarantee against retroactive modification.

WarmLogic addresses this gap by providing a cryptographic evidence infrastructure: every AI decision produces an immutable, signed, consensus-validated evidence receipt that can be independently verified by any third party.

### 2.2 Post-Quantum Cryptography

The NIST Post-Quantum Cryptography Standardization Project [NIST 2024] produced three standards:

- **FIPS 203**: ML-KEM (Module-Lattice Key Encapsulation Mechanism) for key exchange
- **FIPS 204**: ML-DSA (Module-Lattice Digital Signature Algorithm) for digital signatures
- **FIPS 205**: SLH-DSA (Stateless Hash-Based Digital Signature Algorithm) as an alternative

ML-DSA-65, the security level 3 parameter set of FIPS 204, provides 128-bit post-quantum security with the following characteristics:

| Parameter | Value |
|-----------|-------|
| Public key size | 1,952 bytes |
| Secret key size | 4,032 bytes |
| Signature size | 3,309 bytes |
| Security level | NIST Level 3 (128-bit PQ) |
| Assumption | Module-LWE hardness |

WarmLogic uses ML-DSA-65 as the sole signature algorithm, applied uniformly to all operations: key generation, decision signing, vote authentication, and block finalization. This is a deliberate design choice: by standardizing on a single PQC algorithm, we eliminate the complexity of algorithm negotiation while ensuring quantum resistance throughout the system.

Related PQC implementations include liboqs [Stebila and Mosca 2016], the pqcrypto Rust crate ecosystem, and Google's CECPQ2 experiment. To our knowledge, WarmLogic is the first system to integrate ML-DSA-65 into a BFT consensus protocol where every consensus vote is individually PQC-signed and verified.

### 2.3 Byzantine Fault Tolerance

Byzantine fault tolerance, formalized by Lamport, Shostak, and Pease [1982], ensures system correctness when up to f of n nodes behave arbitrarily (including maliciously), provided n >= 3f + 1. PBFT [Castro and Liskov 1999] made BFT practical for real systems. HotStuff [Yin et al. 2019] improved communication complexity to O(n). Tendermint [Buchman 2016] adapted BFT for blockchain consensus.

WarmLogic's BFT engine uses a simplified single-round voting protocol with quorum threshold = floor(2N/3) + 1. Unlike blockchain BFT, WarmLogic's consensus serves a different purpose: not to order financial transactions, but to create *multi-party attestation* that an AI decision evidence record is valid. The key innovation is that every vote carries an ML-DSA-65 signature, verified before counting — meaning that even a quantum adversary cannot forge consensus votes.

### 2.4 Zero-Knowledge Proofs for Privacy-Preserving Governance

Zero-knowledge proofs allow a prover to demonstrate knowledge of a value without revealing the value itself. Sigma protocols [Cramer 1996] provide an efficient framework for interactive proofs of knowledge, which can be made non-interactive via the Fiat-Shamir heuristic [Fiat and Shamir 1986].

WarmLogic implements a Sigma protocol on the Ristretto255 prime-order group [de Valence et al. 2020], using Merlin transcripts [Henry 2019] for the Fiat-Shamir transformation. The proof demonstrates knowledge of values (v, r) such that a Pedersen commitment C = v*G + r*H holds, where G is the Ristretto basepoint and H is derived via SHA3-512 of a domain-separated generator string.

This enables privacy-preserving compliance verification: an organization can prove that its AI system operated within certain parameters (e.g., bias thresholds, confidence bounds) without revealing the proprietary model internals or the specific decision inputs.

### 2.5 Formal Verification of Distributed Systems

TLA+ [Lamport 2002] is a specification language for concurrent and distributed systems. The TLC model checker exhaustively verifies temporal logic properties over finite state models. Amazon Web Services documented the use of TLA+ for verifying critical distributed infrastructure [Newcombe et al. 2015], finding design errors in DynamoDB and S3.

WarmLogic uses TLA+ to specify safety and liveness properties of its core protocol. This approach complements but does not replace the need for formal cryptographic security proofs (which are noted as future work in Section 7).

### 2.6 Comparison with Existing Systems

| Feature | WarmLogic | Ethereum 2.0 | Hyperledger Fabric | AI Factsheets | W&B / LangSmith |
|---------|-----------|-------------|-------------------|---------------|-----------------|
| PQC Signatures | ML-DSA-65 (FIPS 204) | ECDSA (BLS planned) | ECDSA | None | None |
| BFT Consensus | Yes (floor(2N/3)+1) | Yes (Casper) | Raft/PBFT | No | No |
| ZK Proofs | Sigma/Ristretto255 | zk-SNARKs (L2) | No | No | No |
| AI Governance Focus | Primary | None | None | Primary | Partial |
| Formal Verification | 26 TLA+ specs | Partial | No | No | No |
| Hardware Binding | vHSM (simulated) | No | HSM optional | No | No |
| Reflective Kernel | VETO_LOCK mechanism | No | No | No | No |
| Local-First | Yes | No (public chain) | Permissioned | N/A | No (cloud) |
| research prototype | **No (experimental)** | Yes | Yes | N/A | Yes |

**No existing system combines PQC + BFT + ZK + reflective AI governance in a single runtime.** However, WarmLogic is at a significantly earlier maturity stage than production systems like Ethereum 2.0 or Hyperledger Fabric.

---

## 3. System Design

### 3.1 Design Principles

WarmLogic is built on four design principles:

**Evidence-based sovereignty.** Every AI decision must produce a cryptographic evidence receipt. This receipt includes the decision hash, a PQC signature, a consensus proof (BFT votes from multiple validators), and optionally a zero-knowledge proof for privacy-preserving verification. No decision can be executed without generating evidence.

**Schema-first development (SSOT).** The 187 JSON schemas across 34 domains constitute the Single Source of Truth. The hierarchy is: Schema > Specification > Code > Test. Code that does not conform to its schema is treated as a bug, not the schema.

**Fail-closed governance.** When the governance kernel detects an ethical constraint violation (tau_ethics > 0.85), the system enters VETO_LOCK — a hard stop that requires human intervention to clear. This is the opposite of most systems that fail-open to maintain availability. WarmLogic prioritizes correctness over availability when ethics are at stake.

**Hardware-rooted trust (planned).** Node identity is designed to be derived from physical hardware characteristics (CPU UUID, disk UUID) via SHA3-256 hashing. **The current implementation uses a virtual HSM for portability; real TPM 2.0 and Apple Secure Enclave integration is planned but not implemented.**

### 3.2 Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│  Layer 4: Governance Kernel                               │
│  ReflectiveLoop │ PolicyEngine │ SlashingEngine           │
│  e_stab = alpha*epsilon_c + beta*(1-tau_ethics)          │
├──────────────────────────────────────────────────────────┤
│  Layer 3: Consensus & Ledger                              │
│  BFTEngine (2N/3+1) │ ReplicatedLedger (Sled/Borsh)     │
│  EIP-1559 fees │ SHA3-256 state roots                    │
├──────────────────────────────────────────────────────────┤
│  Layer 2: Cryptographic Core                              │
│  ML-DSA-65 (FIPS 204) │ Sigma/Ristretto255 ZK           │
│  SHA3-256 │ Zeroize key material                         │
├──────────────────────────────────────────────────────────┤
│  Layer 1: Hardware Anchor                                 │
│  vHSM (simulated) │ TPM/SEP (planned) │ HardwareEntropy  │
├──────────────────────────────────────────────────────────┤
│  Cross-cutting: PyO3 FFI (zero-copy) │ Kademlia DHT     │
│  187 JSON schemas │ 26 TLA+ specifications               │
└──────────────────────────────────────────────────────────┘
```

The architecture enforces a strict separation: all cryptographic operations execute in Rust (Layers 1-2), consensus and storage in Rust with Python orchestration (Layer 3), and governance logic in Python calling Rust primitives (Layer 4). The PyO3 FFI bridge provides zero-copy data transfer between the two languages.

### 3.3 Cryptographic Substrate

#### 3.3.1 Post-Quantum Identity (ML-DSA-65)

Every node in WarmLogic possesses a unique identity defined by an ML-DSA-65 keypair. Key generation uses the `fips204` crate (v0.4.6) with the `ml-dsa-65` feature flag, calling the standardized `try_keygen()` function with system entropy.

```rust
pub struct PQCKeypair {
    pub public_key: String,   // hex-encoded, 1952 bytes raw
    pub private_key: String,  // hex-encoded, 4032 bytes raw
}
// Derives: Zeroize, ZeroizeOnDrop — keys are scrubbed on deallocation
```

The signing pipeline produces ML-DSA-65 signatures (3,309 bytes) over arbitrary messages:

```
sign(private_key, message) → signature_hex
verify(public_key, message, signature) → bool
```

A security feature: both signing and verification functions explicitly reject simulation keys. If a key begins with the prefix `WARM-KEY-SIM-`, the operation returns an error regardless of the message content. This prevents accidental use of test keys in production contexts.

#### 3.3.2 Post-Quantum Key Encapsulation (ML-KEM-768)

WarmLogic also implements ML-KEM-768 (FIPS 203) for post-quantum key encapsulation, enabling secure key exchange:

| Parameter | Value |
|-----------|-------|
| Encapsulation key size | 1,184 bytes |
| Decapsulation key size | 2,400 bytes |
| Ciphertext size | 1,088 bytes |
| Shared secret size | 32 bytes |
| Security level | NIST Level 3 (128-bit PQ) |

The KEM follows the standard encapsulate/decapsulate pattern:
- `encapsulate(encapsulation_key)` → `(ciphertext, shared_secret)`
- `decapsulate(decapsulation_key, ciphertext)` → `shared_secret`

This enables future integration of post-quantum secure channels for inter-node communication.

#### 3.3.3 Zero-Knowledge Proofs (Sigma Protocol on Ristretto255)

WarmLogic implements an honest-verifier Sigma protocol for proving knowledge of discrete logarithms, instantiated over the Ristretto255 prime-order group using the `curve25519-dalek` crate (v4.1.3).

**Commitment scheme.** A Pedersen commitment is computed as:

```
C = v * G + r * H
```

where G is the Ristretto basepoint, H is derived as `RistrettoPoint::hash_from_bytes::<Sha3_512>("WarmLogic_H_Generator")`, v is the value, and r is a random blinding factor.

**Proof protocol.** The prover demonstrates knowledge of (v, r) without revealing them:

1. Choose random scalars k, s
2. Compute announcement: R = k * G + s * H
3. Compute challenge via Merlin transcript: e = Hash(C || R)
4. Compute responses: z1 = k + e * v, z2 = s + e * r
5. Output proof: (e, z1, z2, R)

**Verification.** The verifier reconstructs:

1. R' = z1 * G + z2 * H - e * C
2. Recomputes e' via Merlin transcript with R'
3. Accepts if e' == e

The use of Merlin transcripts for the Fiat-Shamir transformation provides a composable, domain-separated challenge derivation that resists transcript manipulation attacks.

**Proof size.** Each proof consists of four 32-byte elements (challenge, z1, z2, commitment), totaling 128 bytes — significantly smaller than zk-SNARK proofs (typically 200+ bytes with trusted setup) while providing computational soundness.

#### 3.3.4 Hash Function (SHA3-256)

All hash operations use SHA3-256 (Keccak, FIPS 202), producing 32-byte digests. This includes:

- Node identity: `node_id = SHA3-256(public_key_bytes)`
- Block hashes: `SHA3-256(index || timestamp || tx_ids || prev_hash || miner)`
- State roots: `SHA3-256(sorted_balances_serialization)`
- Transaction IDs: `SHA3-256(source:target:amount:timestamp:max_fee:priority_fee)`

### 3.4 Consensus Layer

#### 3.4.1 BFT Engine

The consensus engine implements a single-round BFT voting protocol. For N validators, the quorum threshold is:

```
quorum = floor(2 * N / 3) + 1
```

This ensures safety (no conflicting blocks committed) when fewer than N/3 validators are Byzantine.

Each vote is a structured record:

```rust
pub struct Vote {
    pub voter_id: String,       // ML-DSA-65 public key of the voter
    pub block_hash: String,     // SHA3-256 hash of the proposed block
    pub round: u64,             // Consensus round number (replay attack prevention)
    pub signature: String,      // ML-DSA-65 signature over "{block_hash}:{round}"
}
```

The intent string signed by each voter follows the format `"{block_hash}:{round}"`. Upon receiving a vote, the engine:

1. Verifies the round number matches the current consensus round (replay attack prevention)
2. Verifies the ML-DSA-65 signature against the voter's public key
3. Enforces `MAX_VOTES_PER_ROUND` (100) to prevent DoS via vote flooding
4. Records the vote (deduplicated by voter_id per round)
5. Checks if the vote count reaches the quorum threshold
6. If quorum is reached, commits the block

**Double-vote and replay prevention.** Votes are tracked per round, and each round resets the vote collection. A vote from a previous round is rejected with "round mismatch" error. The `MAX_VOTES_PER_ROUND` constant (100) bounds memory usage against Byzantine vote flooding.

**Known limitation:** No slashing for double-vote attempts. No view change protocol for leader failure. These are tracked as threats T-B2, T-B6 in the threat model.

#### 3.4.2 Network Layer (Kademlia DHT)

Peer discovery uses a Kademlia distributed hash table with the following parameters:

| Parameter | Value | Description |
|-----------|-------|-------------|
| K | 20 | Maximum contacts per routing bucket |
| ALPHA | 3 | Parallel lookups during iterative find |
| Node ID | 32 bytes | SHA3-256(public_key) |
| Distance | XOR | Standard Kademlia metric |
| Transport | UDP | JSON-encoded messages |

A **PQC gatekeeper** enforces identity verification at the network layer: before a contact is admitted to the routing table, the system verifies that `SHA3-256(contact.public_key) == contact.node_id`. Contacts that fail this check are silently dropped (zero-trust policy).

**Known limitation:** Current implementation uses a single-bucket routing table. Full k-bucket splitting is required for production-scale networks. This is tracked as a known limitation.

### 3.5 Replicated Ledger

The ledger maintains the evidence chain as an ordered sequence of blocks, each containing a set of transactions, a link to the previous block, and an optional ZK proof.

**Storage.** The Sled embedded key-value store (v0.34.7) provides ACID guarantees with Borsh binary serialization. Four storage trees maintain the ledger state:

| Tree | Key | Value | Purpose |
|------|-----|-------|---------|
| `balances` | address | u64 (Borsh) | Per-address balance |
| `blocks` | block_hash | Block (Borsh) | Block chain |
| `meta` | "last_block_hash" | String | Latest block pointer |
| `locks` | address | bool | Slashing locks |

**State root.** After each block, a deterministic state root is computed by sorting all address:balance pairs alphabetically, concatenating them with pipe separators, and hashing with SHA3-256. This enables lightweight state verification: two nodes with the same state root are guaranteed to have identical balance states.

**Fee model.** Transactions include `max_fee` and `priority_fee` fields (EIP-1559 style). The `base_fee_per_gas` is set at the block level (default: 10 units). This creates an economic mechanism that can be tuned for different governance requirements.

**Known limitation:** Sled is a beta-quality embedded database (v0.34.7) with known data loss issues on crash. Not suitable for financial-grade storage without external backup. This is tracked as threat T-L2.

### 3.6 Governance Kernel

#### 3.6.1 Reflective Loop

The core of WarmLogic's governance is the **ReflectiveLoop**, which evaluates system stability at each kernel tick:

```
e_stab = alpha * epsilon_c + beta * (1.0 - tau_ethics)
```

where:
- `alpha = 0.5` (computational stability weight)
- `beta = 0.5` (ethical constraint weight)
- `epsilon_c` is the computational error rate (0.0 = perfect, 1.0 = complete failure)
- `tau_ethics` is the ethical tension score (0.0 = no concern, 1.0 = maximum violation)

The stability score maps to four operational modes:

| Condition | Mode | Behavior |
|-----------|------|----------|
| tau_ethics > 0.85 | VETO_LOCK | Ethics override — all operations halted |
| e_stab < 0.3 | CRITICAL_HALT | System instability — emergency stop |
| e_stab < 0.7 | SUSPICIOUS | Elevated monitoring, restricted operations |
| e_stab >= 0.7 | NORMAL | Full operation |

The VETO_LOCK condition is checked *before* the stability equation — ethical violations take absolute precedence regardless of computational stability. This design embeds a philosophical position: **ethics cannot be overridden by operational convenience**.

**Known limitation:** Governance halt logic is implemented in Python, which can be bypassed by a compromised Python process. Moving critical halt enforcement to Rust is planned. This is tracked as threat T-G2.

#### 3.6.2 Slashing Mechanism

The slashing engine enforces consequences for policy violations through a three-tier penalty system:

| Penalty | Trigger | Effect |
|---------|---------|--------|
| StateLock | severity > 0.95 | Account frozen — no transactions, no mining |
| EconomicBurn | severity > 0.80 | Balance deduction (100 units per violation) |
| IdentityIsolation | Configurable | Network isolation (defined, enforcement in progress) |

Slashing state is persisted to the Sled `locks` tree. A locked account's transactions are rejected at the submission stage, before entering the mempool — providing an early, efficient enforcement point.

#### 3.6.3 Hardware Attestation

The kernel requires hardware attestation at each tick. If the hardware state is "unsealed" (the virtual HSM cannot verify hardware integrity) and the ethical tension score is below 0.9, the system enters `HALT_UNSECURED`. This ensures that the system does not operate in a potentially compromised environment.

**The current implementation uses a virtual HSM (`VirtualHSM`) that derives keys from host hardware entropy (CPU UUID, serial number). This provides no real hardware security.** The architecture is designed for direct TPM 2.0 and Apple Secure Enclave integration, with the vHSM serving as a portable fallback during development.

---

## 4. Formal Verification

### 4.1 Approach

We use TLA+ [Lamport 2002] with the TLC model checker to specify and verify safety and liveness properties of WarmLogic's core protocol. The specification suite consists of 26 TLA+ files covering:

- Core system invariants (provenance, trust, execution safety)
- Witness chain protocol (Byzantine-safe log agreement)
- Kernel finite state machine (mode transitions)
- Drift horizon models (temporal state synchronization)
- T-operator safety (operator composition)
- Adversarial closure (ethics framework closure properties)
- CT pipeline safety (conformance testing)

### 4.2 Core Invariants

The `core_invariants.tla` specification defines three properties over the system state:

**State variables:**
- `ledger`: Sequence of events (the refusal spine)
- `execution_state`: {"IDLE", "RUNNING", "BLOCKED"}
- `provenance_graph`: Map from artifacts to their parent artifacts

**Property 1: MethodologicalIntegrity (Safety)**

```tla+
MethodologicalIntegrity ==
    (execution_state = "RUNNING") =>
    (\A a \in Artifacts: (Running(a) => Trusted(a)))
```

This states that if the system is executing, every artifact being processed must be *Trusted*. Trust is defined recursively: an artifact is trusted if and only if all paths in its lineage graph terminate at elements of the `TrustedRoots` set.

```tla+
Trusted(a) ==
    /\ lineage(a) \ne {}
    /\ \A ancestor \in lineage(a):
        (provenance_graph[ancestor] = {}) => (ancestor \in TrustedRoots)
```

**Property 2: LedgerImmutable (Safety)**

```tla+
LedgerImmutable ==
    Len(ledger') >= Len(ledger) /\
    \A i \in 1..Len(ledger): ledger'[i] = ledger[i]
```

The ledger can only grow — existing entries cannot be modified or deleted. This property is enforced at both the specification level (TLA+) and the implementation level (Sled write-ahead log with append-only semantics).

**Property 3: RefusalInevitability (Liveness)**

```tla+
RefusalInevitability ==
    \A a \in Artifacts:
        (~Trusted(a) /\ RequestExecution(a)) ~> (execution_state = "BLOCKED")
```

If an untrusted artifact requests execution, the system must *eventually* block it. This liveness property ensures that policy violations cannot persist indefinitely.

### 4.3 Witness Chain

The `witness_chain.tla` specification models the multi-node consensus protocol:

**Safety: Log Prefix Agreement**

```tla+
Safety ==
    \forall n1, n2 \in KeySet:
        \forall i \in 1..minLen: log1[i] = log2[i]
```

For any two honest nodes, their logs agree on all entries up to the shorter log's length. This is the standard BFT safety property, ensuring that committed entries are never contradicted.

**Hardware Binding**

```tla+
HardwareBinding ==
    \forall entry \in witnessedLog: entry.signed_by_sep = TRUE
```

Every entry in the witnessed log must carry a hardware signature. **Note: This property is specified but not currently enforced in implementation due to simulated HSM.**

### 4.4 Additional Specifications

| Specification | Properties | Description |
|---------------|------------|-------------|
| `WarmLogic_FSM.tla` | Mode transition safety | Kernel mode state machine with governance SAT gates |
| `DriftHorizon_Model_v1.tla` | Temporal bounds | State synchronization drift limits |
| `T_Operator_Safety.tla` | Operator composition | Safety under T-operator application |
| `E06_adversarial_closure.tla` | Closure properties | Ethics framework adversarial resilience |
| `ct_pipeline_safety.tla` | Pipeline safety | Conformance testing pipeline invariants |
| `WarmLogic_ToyKernel.tla` | Core loop | Simplified kernel model for rapid iteration |

### 4.5 Limitations of Formal Verification

We note important limitations of our verification approach:

1. **Model checking, not theorem proving.** TLC explores finite state spaces. Our specifications are verified for bounded configurations (e.g., 3-node key sets) but are not formally proven for arbitrary N.
2. **Abstraction gap.** TLA+ specifications model the protocol at an abstract level. Implementation bugs below the specification level (e.g., serialization errors, memory safety issues) are not caught by model checking. Rust's type system and borrow checker mitigate but do not eliminate this risk.
3. **No cryptographic security proofs.** The Sigma protocol implementation has not been subjected to a formal security proof in the Universal Composability (UC) framework. The algebraic correctness follows from standard Sigma protocol construction, but a reduction proof against specific hardness assumptions is future work.

---

## 5. Implementation

### 5.1 Language Architecture

WarmLogic uses a dual-language architecture:

**Rust core** (`rust_core/`): Edition 2021, with `#![cfg_attr(not(feature = "std"), no_std)]` for bare-metal portability. All cryptographic operations, consensus logic, ledger state management, ZK proof generation/verification, and storage execute in Rust. The release profile uses `panic = "abort"`, link-time optimization (LTO), and `codegen-units = 1` for maximum performance.

**Python kernel**: Python 3.12+ with strict typing. Handles orchestration, governance policy evaluation, network stack (asyncio UDP for Kademlia DHT and beacon discovery), and HTTP API (FastAPI). Python never performs cryptographic operations directly — all crypto calls are delegated to the Rust core via FFI.

**Design rationale:** Rust provides memory safety (no use-after-free, no data races) and performance characteristics essential for cryptographic code, while Python provides accessibility for the AI/ML community and rapid iteration on governance logic. The FFI bridge is the critical enabler of this separation.

### 5.2 PyO3 FFI Bridge

The bridge uses PyO3 v0.22.6 with a patched vendor directory for optimized `Vec<u8>` extraction. Key optimizations:

- **Zero-copy access**: `&Bound<'_, PyBytes>` provides direct `as_bytes()` slice access without copying
- **Custom BytesVec extractor**: For `Vec<u8>` arguments, a custom extractor performs contiguous buffer copy instead of per-element sequence iteration, avoiding O(N) Python object overhead
- **GIL release**: `py.allow_threads()` releases the Python Global Interpreter Lock during O(N) Rust compute, enabling multi-threaded Python workloads to proceed concurrently

The FFI surface exports 16+ Python classes and 35+ functions, covering all Rust-side functionality. A 6-step consumption benchmark ladder (len → touch_head → touch_tail → full_iter → sum → hash) isolates overhead at each access pattern, confirming the 300x improvement for 10MB payloads.

### 5.3 Dependency Summary

| Crate | Version | Purpose |
|-------|---------|---------|
| fips204 | 0.4.6 | ML-DSA-65 (FIPS 204) signatures |
| fips203 | 0.4.3 | ML-KEM-768 (FIPS 203) key encapsulation |
| curve25519-dalek | 4.1.3 | Ristretto255 group operations |
| merlin | 3.0.0 | Fiat-Shamir transcript |
| sha3 | 0.10.8 | SHA3-256 / SHA3-512 hashing |
| zeroize | 1.7 | Secure memory clearing |
| redb | 2.4.0 | Embedded KV store (ACID-compliant) |
| borsh | 1.3.1 | Binary serialization |
| pyo3 | 0.24.1 | Python FFI bridge |
| dashmap | 5.5 | Concurrent hash map |
| proptest | 1.0 | Property-based testing |

### 5.4 Code Quality

- `#![deny(clippy::unwrap_used)]` and `#![deny(clippy::expect_used)]` — no panics in library code **(Note: Some exceptions exist in current code; tracked as threat T-C6)**
- Property-based testing via `proptest` for randomized input validation
- 90+ GitHub Actions CI workflows covering security scanning, formal verification, benchmark reproduction, and compatibility testing
- Chaos testing infrastructure with Byzantine node injection, network partitions, and slashing condition verification
- **Test suite comprises 334 tests** (205 Rust core + 129 Python kernel) ; measured line coverage is 6.76% (see docs/CLAIM_EVIDENCE.md)

### 5.5 Schema-Driven Development

187 JSON schemas across 34 domains define all data contracts:

| Domain | Count | Examples |
|--------|-------|---------|
| evidence | 15 | CE ledger, audit pack, external incident |
| meta | 40+ | Execution manifest, experiment bundle |
| governance | 19 | GovDec events, tau policy |
| os | 20+ | OS state, scheduler, stability envelope |
| security | 4 | Tamper log, red-team experiments |
| ml | 6 | Model registry, pipeline |
| mcp | 9 | MCP traces, tool restrictions |

Schema changes must maintain backward compatibility (new fields optional). Breaking changes require a new version (v1 → v2) with migration scripts. This discipline ensures that the specification never drifts from the implementation.

---

## 6. Evaluation

### 6.1 Cryptographic Performance

#### 6.1.1 ML-DSA-65 Operations

ML-DSA-65 operations were benchmarked on the development platform. Key generation, signing, and verification all complete within millisecond-scale latency, confirming practical usability for real-time AI decision signing.

| Operation | Latency | Notes |
|-----------|---------|-------|
| Key generation | ~1-2ms | `ml_dsa_65::try_keygen()` |
| Sign (single message) | ~1ms | `sk.try_sign(msg, &[])` |
| Verify (single message) | ~1ms | `pk.verify(msg, &sig)` |

For comparison, classical ECDSA (secp256k1) signs in ~0.1ms but provides no post-quantum security. ML-DSA-65's overhead is modest relative to the quantum resistance it provides.

#### 6.1.2 ZK Proof Operations

| Operation | Latency | Proof Size |
|-----------|---------|------------|
| Proof generation | <1ms | 128 bytes |
| Proof verification | <1ms | — |

The Sigma protocol on Ristretto255 is significantly lighter than SNARK-based systems (which require seconds for proof generation and kilobytes for proof size) at the cost of proving simpler statements.

#### 6.1.3 Hash Operations

SHA3-256 hashing operates at microsecond-scale latency per hash, as expected from the Keccak sponge construction. State root computation scales linearly with the number of accounts (sorting + concatenation + single hash).

### 6.2 Consensus Performance

The BFT engine's vote processing is O(1) per vote (HashMap lookup + HashSet insertion). Quorum detection is a simple integer comparison. The bottleneck is not consensus logic but ML-DSA-65 signature verification per vote, which remains at millisecond scale.

| Validators (N) | Quorum | Fault Tolerance |
|----------------|--------|-----------------|
| 4 | 3 | 1 Byzantine node |
| 7 | 5 | 2 Byzantine nodes |
| 10 | 7 | 3 Byzantine nodes |
| 21 | 15 | 7 Byzantine nodes |

### 6.3 FFI Bridge Performance

The PyO3 zero-copy bridge achieves a **300x throughput improvement** over naive sequence-copy approaches for 10MB byte payloads. This result is documented with 12 evaluation scripts in `scripts/eval/` and reproducible via `reproduce_paper09.sh`.

Key findings from the evaluation suite:

- **Stock PyO3**: Sequence extraction performs per-element Python object creation for `Vec<u8>`, scaling as O(N) with Python object overhead
- **Patched PyO3**: BytesVec extractor performs single contiguous buffer copy, scaling as O(1) relative to element count
- **GIL release**: Enables concurrent Python execution during Rust compute phases
- **Cache effects**: L1/L2 cache boundaries visible in throughput curves at 32KB and 256KB payload sizes

### 6.4 Ledger Performance

Sled provides microsecond-scale read/write latency for individual key-value operations. Block mining (transaction collection + balance update + state root computation + block serialization + storage) completes in the low-millisecond range for typical block sizes.

| Operation | Latency | Notes |
|-----------|---------|-------|
| Sled read | ~1-10μs | Single key lookup |
| Sled write | ~10-50μs | Single key write (with WAL) |
| Block mining | ~5-20ms | Includes state root computation |
| State root | Linear in account count | Sort + SHA3-256 |

### 6.5 Chaos Testing

The chaos testing infrastructure validates system behavior under adversarial conditions:

**Byzantine node injection.** Nodes submitting votes with invalid ML-DSA-65 signatures are correctly rejected. The BFT engine's signature verification step (prior to vote counting) prevents Byzantine votes from influencing consensus.

**Network partition.** When a network partition splits validators, neither partition can reach quorum (by design). Upon partition healing, state synchronization restores ledger consistency. The state root mechanism enables efficient divergence detection.

**Slashing conditions.** Severity thresholds are enforced correctly: transactions from accounts with severity > 0.95 are rejected at submission (StateLock), and accounts with severity > 0.80 receive balance deductions (EconomicBurn of 100 units).

### 6.6 Target Metrics (Not Yet Verified)

The following are engineering goals, not achieved benchmarks:

| Target | Value | Status |
|--------|-------|--------|
| Global finality latency | < 10ms | Requires multi-node benchmark |
| Formal verification latency | < 0.1ms | Requires UDS socket benchmark |
| Decentralized sync | < 15ms | Requires multi-node test |
| Throughput | 50,000+ TPS | Requires load testing |

> **Important distinction:** All numbers in Section 6.1-6.5 are verified results from evaluation scripts. Numbers in 6.6 are aspirational targets that have not been validated.

---

## 7. Discussion

### 7.1 Novelty and Positioning

WarmLogic occupies a unique position at the intersection of three established domains: AI governance, decentralized infrastructure, and sovereign computing. While each domain has mature solutions — W&B/LangSmith for AI observability, Cosmos/Hyperledger for decentralized consensus, Oxide/Thales for sovereign hardware — no prior system integrates post-quantum cryptography, Byzantine fault tolerance, zero-knowledge proofs, and a reflective governance kernel into a unified runtime specifically designed for AI decision evidence.

The reflective loop is architecturally significant beyond its immediate governance function. The stability equation `e_stab = alpha * epsilon_c + beta * (1 - tau_ethics)` encodes a value judgment: that ethical constraint violations should contribute equally to system instability as computational errors. The VETO_LOCK mechanism operationalizes this judgment by making ethics a hard constraint rather than a soft preference.

### 7.2 Regulatory Alignment

WarmLogic is designed to provide the technical infrastructure that upcoming regulations assume exists:

**EU AI Act (effective August 2026).** Article 9 requires risk management systems with "appropriate and targeted measures." WarmLogic's evidence chain — PQC signature + BFT consensus proof + optional ZK proof — constitutes a cryptographically verifiable risk management artifact. Article 14's human oversight requirement aligns with the VETO_LOCK mechanism, which preserves human intervention authority.

**NIST PQC Timeline.** FIPS 204 was finalized in 2024, with recommended migration for critical infrastructure by 2030. WarmLogic's use of ML-DSA-65 provides immediate compliance with emerging PQC requirements, while classical systems face a multi-year migration effort.

**Data Sovereignty.** WarmLogic's local-first architecture — no cloud dependency, no data exfiltration unless explicitly configured for P2P mesh — aligns with data sovereignty requirements in the EU (GDPR), Middle East, and Asia-Pacific regions. Organizations subject to the US CLOUD Act cannot use US-domiciled cloud providers for governance data; WarmLogic provides a local alternative.

**Korean Financial Regulations.** FSS (Financial Supervisory Service) AI model validation guidelines require explainability and auditability of AI-driven financial decisions. NIS (National Intelligence Service) PQC transition roadmap mandates post-quantum readiness for public sector. WarmLogic is designed to address both requirements simultaneously.

### 7.3 Limitations (Critical)

**This section is the most important part of the paper.** We are committed to honest assessment of WarmLogic's current state:

#### 7.3.1 Critical Gaps (Must Fix Before Any Deployment)

| Gap | Description | Impact |
|-----|-------------|--------|
| **P2P Block Propagation** | `StitchServer` component is incomplete | System is effectively single-node only |
| **Third-Party Security Audit** | No external security review | Cannot recommend for any sensitive use |
| ~~**Test Coverage**~~ | ~~900+ tests, ~85% line coverage~~ | 2,587 tests collected; measured line coverage 6.76% |

#### 7.3.2 High-Priority Gaps (Must Fix Before Financial Institution Deployment)

| Gap | Description | Impact |
|-----|-------------|--------|
| **Virtual HSM** | Software-derived seeds, not hardware secure elements | No real hardware trust anchor |
| **Key Zeroization** | Private keys stored as heap Strings; Zeroize on String is best-effort | Keys may persist in memory after use |
| ~~**Sled Database**~~ | ~~Beta storage engine~~ | **RESOLVED**: Migrated to redb (Feb 2026) |
| ~~**Single-Bucket DHT**~~ | ~~Kademlia not fully implemented~~ | **RESOLVED**: Full Kademlia with replacement cache |
| ~~**Governance in Python**~~ | ~~VETO_LOCK bypassable~~ | **RESOLVED**: governance.rs with ML-DSA-65 reset |

#### 7.3.3 Medium-Priority Gaps

| Gap | Description | Impact |
|-----|-------------|--------|
| **No UC Security Proof** | ZK protocol not formally proven secure | Theoretical security gap |
| ~~**Vote Replay**~~ | ~~No epoch/term number in consensus votes~~ | ✅ Resolved (round field added) |
| **No View Change** | Leader failure blocks consensus | Liveness risk in multi-node |
| **FFI Input Validation** | No size limits at Python-Rust boundary | Memory exhaustion possible |

#### Component status

Per-claim grades against re-runnable evidence live in
[CLAIM_EVIDENCE.md](CLAIM_EVIDENCE.md); this document no longer carries a
self-assigned maturity table.

### 7.4 Ethical Considerations

WarmLogic embeds value judgments in its architecture:

- **The VETO_LOCK mechanism assumes that ethics can be quantified** as a scalar `tau_ethics` and that a threshold (0.85) can meaningfully separate acceptable from unacceptable states. In practice, ethical boundaries are contextual and contested. The threshold is a parameter, not a truth.

- **Slashing as deterrence raises proportionality questions.** An automatic 100-unit economic penalty for severity > 0.80 may be appropriate in some contexts and draconian in others. The slashing parameters must be governed, not hardcoded — who decides the thresholds is as important as what the thresholds are.

- **Open-source as accountability.** By releasing the kernel under MIT license, we ensure that the governance logic is inspectable. The code is the specification; claims about system behavior can be verified against the implementation.

### 7.5 Future Work

1. **Security audit**: Third-party review of cryptographic implementation (highest priority)
2. ~~**P2P completion**~~: ✅ NetworkBridge polling loop and delta sync complete (Feb 2026)
3. ~~**Test coverage**~~: coverage remains low (6.76% measured); this is an open gap
4. **Hardware integration**: Replace vHSM with real TPM 2.0 (Linux), Apple Secure Enclave (macOS/iOS)
5. ~~**Full Kademlia**~~: ✅ Replacement cache, failure tracking, refresh candidates (Feb 2026)
6. **UC security proof**: Formal cryptographic security proof for the Sigma protocol variant
7. **AI framework integration**: Bridge to LangChain, Hugging Face Transformers, and vLLM
8. ~~**Storage migration**~~: ✅ Migrated from sled to redb (Feb 2026)
9. **Threshold signatures**: Distributed ML-DSA-65 key generation for shared governance authority

---

## 8. Conclusion

AI systems are making consequential decisions without producing tamper-proof evidence of their reasoning. Current governance frameworks prescribe documentation requirements but provide no cryptographic infrastructure to enforce them. The approaching quantum computing era further threatens the validity of any audit trail built on classical signatures.

WarmLogic addresses this gap with an integrated runtime that combines post-quantum digital signatures (ML-DSA-65, FIPS 204), Byzantine fault-tolerant consensus, zero-knowledge proofs (Sigma protocol on Ristretto255), and a reflective governance kernel with formally verified safety invariants. The system is implemented as a dual-language runtime (Rust + Python) connected by a zero-copy FFI bridge achieving 300x throughput improvement.

Two core safety properties — MethodologicalIntegrity and LedgerImmutable — are specified in TLA+ and machine-checked by the TLC model checker. The VETO_LOCK mechanism ensures that ethical constraint violations can autonomously halt the system, encoding a fail-closed governance philosophy.

**WarmLogic is a research prototype at research prototype.** It is approaching production readiness. Critical gaps remain: no third-party security audit, incomplete P2P block propagation, and simulated hardware security module. The test suite is exercised on both x86_64 and RISC-V (Milk-V Duo) architectures. The system should not be used for sensitive workloads without addressing these gaps and completing security audit.

We release the system as open source (MIT license for the kernel) to invite community contribution, independent security audit, and collaborative improvement. The EU AI Act takes effect for high-risk systems in August 2026. NIST PQC migration targets 2030. The window for building the evidence infrastructure these regulations require is closing. WarmLogic provides a starting point — not a finished product, but a working, formally verified foundation for verifiable AI governance.

---

## References

[1] M. Mitchell, S. Wu, A. Zaldivar, P. Barnes, L. Vasserman, B. Hutchinson, E. Spitzer, I.D. Raji, and T. Gebru. "Model Cards for Model Reporting." *Proceedings of the Conference on Fairness, Accountability, and Transparency (FAccT)*, 2019.

[2] T. Gebru, J. Morgenstern, B. Vecchione, J.W. Vaughan, H. Wallach, H. Daume III, and K. Crawford. "Datasheets for Datasets." *Communications of the ACM*, 64(12):86-92, 2021.

[3] M. Arnold, R.K.E. Bellamy, M. Hind, S. Houde, S. Mehta, A. Mojsilovic, R. Nair, K.N. Ramamurthy, A. Olteanu, D. Piorkowski, D. Reimer, J. Richards, J. Tsay, and K.R. Varshney. "FactSheets: Increasing Trust in AI Services through Supplier's Declarations of Conformity." *IBM Journal of Research and Development*, 63(4/5), 2019.

[4] European Parliament and Council. "Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (AI Act)." *Official Journal of the European Union*, 2024.

[5] National Institute of Standards and Technology. "FIPS 204: Module-Lattice-Based Digital Signature Standard." *Federal Information Processing Standards Publication*, 2024.

[6] National Institute of Standards and Technology. "FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard." 2024.

[7] National Institute of Standards and Technology. "FIPS 205: Stateless Hash-Based Digital Signature Standard." 2024.

[8] L. Lamport, R. Shostak, and M. Pease. "The Byzantine Generals Problem." *ACM Transactions on Programming Languages and Systems*, 4(3):382-401, 1982.

[9] M. Castro and B. Liskov. "Practical Byzantine Fault Tolerance." *Proceedings of the Third Symposium on Operating Systems Design and Implementation (OSDI)*, 1999.

[10] M. Yin, D. Malkhi, M.K. Reiter, G.G. Gueta, and I. Abraham. "HotStuff: BFT Consensus with Linearity and Responsiveness." *Proceedings of the 2019 ACM Symposium on Principles of Distributed Computing (PODC)*, 2019.

[11] E. Buchman. "Tendermint: Byzantine Fault Tolerance in the Age of Blockchains." M.Sc. Thesis, University of Guelph, 2016.

[12] R. Cramer. "Modular Design of Secure yet Practical Cryptographic Protocols." Ph.D. Thesis, University of Amsterdam, 1996.

[13] A. Fiat and A. Shamir. "How to Prove Yourself: Practical Solutions to Identification and Signature Problems." *Advances in Cryptology — CRYPTO '86*, Springer, 1986.

[14] H. de Valence, J. Grigg, G. Tankersley, F. Valsorda, and I. Lovecruft. "The Ristretto Group." *IETF Internet-Draft*, 2020.

[15] D. Henry. "Merlin: Composable Proof Transcripts for Public-Coin Arguments of Knowledge." 2019.

[16] L. Lamport. "Specifying Systems: The TLA+ Language and Tools for Hardware and Software Engineers." Addison-Wesley, 2002.

[17] C. Newcombe, T. Rath, F. Zhang, B. Munteanu, M. Brooker, and M. Deardeuff. "How Amazon Web Services Uses Formal Methods." *Communications of the ACM*, 58(4):66-73, 2015.

[18] D. Stebila and M. Mosca. "Post-quantum key exchange for the Internet and the Open Quantum Safe project." *Selected Areas in Cryptography (SAC)*, 2016.

[19] R. Jung, J.-H. Jourdan, R. Krebbers, and D. Dreyer. "RustBelt: Securing the Foundations of the Rust Programming Language." *Proceedings of the ACM on Programming Languages*, 2(POPL), 2018.

[20] P. Pedersen. "Non-interactive and Information-Theoretic Secure Verifiable Secret Sharing." *Advances in Cryptology — CRYPTO '91*, Springer, 1991.

[21] National Institute of Standards and Technology. "FIPS 202: SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions." 2015.

[22] P. Maymounkov and D. Mazieres. "Kademlia: A Peer-to-peer Information System Based on the XOR Metric." *First International Workshop on Peer-to-Peer Systems (IPTPS)*, 2002.

[23] European Commission. "Recommendation on a Coordinated Implementation Roadmap for the transition to Post-Quantum Cryptography." 2024.

---

## Appendix A: TLA+ Specification — Core Invariants

```tla+
---------------- MODULE core_invariants ----------------
EXTENDS Naturals, Sequences

CONSTANTS
    Artifacts,          \* Set of all possible artifacts
    Signatures,         \* Set of valid cryptographic signatures
    TrustedRoots        \* Set of initial trusted artifacts

VARIABLES
    ledger,             \* The Refusal Spine (Sequence of Events)
    execution_state,    \* Current execution status
    provenance_graph    \* Graph of artifact lineage

TypeOK ==
    /\ ledger \in Seq([type: {"REFUSAL", "EXECUTION"}, reason: STRING])
    /\ execution_state \in {"IDLE", "RUNNING", "BLOCKED"}
    /\ provenance_graph \in [Artifacts -> SUBSET Artifacts]

RECURSIVE lineage(_)
lineage(a) ==
    let parents == provenance_graph[a] IN
    parents \cup UNION {lineage(p) : p \in parents}

Trusted(a) ==
    /\ lineage(a) \ne {}
    /\ \A ancestor \in lineage(a):
        (provenance_graph[ancestor] = {}) => (ancestor \in TrustedRoots)

MethodologicalIntegrity ==
    (execution_state = "RUNNING") =>
    (\A a \in Artifacts: (Running(a) => Trusted(a)))

LedgerImmutable ==
    Len(ledger') >= Len(ledger) /\
    \A i \in 1..Len(ledger): ledger'[i] = ledger[i]

RefusalInevitability ==
    \A a \in Artifacts:
        (~Trusted(a) /\ RequestExecution(a)) ~> (execution_state = "BLOCKED")

THEOREM Spec => []MethodologicalIntegrity
THEOREM Spec => []LedgerImmutable
================================================================
```

## Appendix B: TLA+ Specification — Witness Chain

```tla+
--------------------------- MODULE WitnessChain ---------------------------
EXTENDS Naturals, Sequences, FiniteSets

VARIABLES
    nodeState,      \* Map of nodeId -> [term, log, commitIndex]
    messages,       \* Set of messages in flight
    identityKeys,   \* Map of nodeId -> public key (Silicon-Rooted)
    witnessedLog    \* The globally witnessed and hardware-signed state

Constant KeySet == {"node1", "node2", "node3"}

Safety ==
    \forall n1, n2 \in KeySet:
        LET log1 == nodeState[n1].log
            log2 == nodeState[n2].log
            minLen == IF Len(log1) < Len(log2) THEN Len(log1) ELSE Len(log2)
        IN \forall i \in 1..minLen: log1[i] = log2[i]

HardwareBinding ==
    \forall entry \in witnessedLog: entry.signed_by_sep = TRUE

Init ==
    /\ nodeState = [n \in KeySet |-> [term |-> 0, log |-> << >>, commitIndex |-> 0]]
    /\ messages = {}
    /\ identityKeys = [n \in KeySet |-> "PUB_KEY_" \o n]
    /\ witnessedLog = << >>

Next ==
    \/ \E n \in KeySet:
        /\ nodeState[n].term' = nodeState[n].term + 1
        /\ UNCHANGED <<messages, identityKeys, witnessedLog>>
    \/ \E n \in KeySet, m \in messages:
        /\ m.type = "Commit"
        /\ m.valid_sig = TRUE
        /\ nodeState' = [nodeState EXCEPT ![n].commitIndex = m.index]
        /\ UNCHANGED <<messages, identityKeys, witnessedLog>>
=============================================================================
```

## Appendix C: Threat Model Summary

For complete threat analysis, see `docs/THREAT_MODEL.md`. Key threats:

| ID | Threat | Priority | Status |
|----|--------|----------|--------|
| T-N5 | StitchServer incomplete | Critical | Known gap |
| ~~T-L2~~ | ~~Sled beta storage~~ | ~~Critical~~ | ✅ Resolved (redb 2.4.0) |
| T-C6 | Panic in sign path | Critical | Fix in progress |
| T-C1 | Key zeroization unreliable | High | Known gap |
| T-B5 | Unbounded HashMap DoS | High | Known gap |
| ~~T-G2~~ | ~~Python governance bypass~~ | ~~High~~ | ✅ Resolved (governance.rs) |

---

*WarmLogic Whitepaper v1.0 — February 2026*
*espressolee*
*Source code: github.com/espressolee/WarmLogic*
*Status: Release Candidate (experimental) — Pending Security Audit*
