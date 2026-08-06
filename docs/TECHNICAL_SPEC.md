# WarmLogic Technical Specification

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

> **Version**: 1.1-era6000
> **Status**: research prototype; see docs/CLAIM_EVIDENCE.md
> **Audience**: Developers, contributors, security researchers
> **License**: MIT (kernel) + ELv2 (enterprise components)

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Rust Core](#3-rust-core)
4. [Python Kernel](#4-python-kernel)
5. [Network Protocol](#5-network-protocol)
6. [Storage Architecture](#6-storage-architecture)
7. [Security Model](#7-security-model)
8. [API Reference](#8-api-reference)
9. [Governance Workflow](#9-governance-workflow)
10. [Deployment](#10-deployment)
11. [Configuration Reference](#11-configuration-reference)
12. [Schema System](#12-schema-system)
13. [Performance](#13-performance)
14. [Implementation Status](#14-implementation-status)
15. [Contributing](#15-contributing)
16. [Appendix: Constants & Thresholds](#16-appendix-constants--thresholds)

---

## 1. Overview

### 1.1 What WarmLogic Does

WarmLogic attaches **cryptographic evidence** to AI decisions at the runtime level. Every judgment is:

1. **Signed** with post-quantum cryptography (ML-DSA-65, FIPS 204)
2. **Validated** through Byzantine fault-tolerant consensus
3. **Stored** in a tamper-proof embedded ledger
4. **Provable** via zero-knowledge proofs without exposing sensitive data

### 1.2 Design Principles

| Principle | Meaning | Implementation |
|-----------|---------|----------------|
| **SSOT** | Schema > Spec > Code > Test | 187 JSON schemas as source of truth |
| **Evidence-based** | Every claim requires proof | All state transitions carry signatures |
| **Fail-closed** | When uncertain, halt | `tau_ethics > 0.85` → VETO_LOCK |
| **Hardware root** | Software alone is insufficient for trust | TPM/CPU UUID-based key derivation |

### 1.3 Project Structure

```
WarmLogic/
├── warm_logic_rs/          Rust core — crypto, consensus, ledger, ZK proofs
│   └── src/
│       ├── crypto.rs       ML-DSA-65 (FIPS 204) sign/verify
│       ├── consensus.rs    BFT voting engine
│       ├── ledger.rs       Replicated ledger + state machine
│       ├── proof_zk.rs     Sigma protocol ZK proofs (Ristretto255)
│       ├── storage.rs      Sled/Memory store abstraction
│       ├── dht.rs          Kademlia routing table
│       ├── policy_engine.rs Policy verification engine
│       ├── slashing.rs     Violation penalty engine
│       ├── hardware/       vHSM + hardware entropy
│       └── kernel.rs       Reflective loop + mode decision
├── warm_logic/             Python kernel — orchestration, governance
│   ├── kernel/
│   │   ├── sys/            Crypto FFI wrappers, networking, consensus
│   │   ├── mesh/           Kademlia DHT, beacon discovery, sync
│   │   ├── economy/        Replicated ledger (Rust-delegated)
│   │   ├── identity/       KineticIdentity (PQC key management)
│   │   └── ops/            Kernel loop, task scheduler, quorum manager
│   ├── ui/                 Glass Browser (FastAPI, port 8000)
│   └── app/cockpit/        Sovereign Cockpit (FastAPI, port 5001)
└── spec/schema/            JSON schemas (187 files, 34 domains)
```

### 1.4 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Cryptography | Rust + fips204 (ML-DSA-65) | Post-quantum sign/verify |
| Consensus | Rust BFTEngine | Byzantine fault-tolerant voting |
| ZK Proofs | Rust + curve25519-dalek | Sigma protocol on Ristretto255 |
| Ledger | Rust + Sled | Embedded KV store, ACID |
| Orchestration | Python + FastAPI | HTTP API, governance logic |
| Networking | Python asyncio + UDP | Kademlia DHT, beacon discovery |
| FFI | PyO3 0.22 | Zero-copy Rust↔Python bindings |

---

## 2. System Architecture

### 2.1 Layer Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     User Interface                        │
│  Glass Browser (port 8000)  │  Cockpit (port 5001)  │ TUI│
├──────────────────────────────────────────────────────────┤
│                    Python Kernel Layer                     │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐   │
│  │  Mesh   │ │ Economy │ │ Identity │ │  Governance  │   │
│  │  (DHT)  │ │ (Ledger)│ │(Kinetic) │ │   (Policy)   │   │
│  └────┬────┘ └────┬────┘ └────┬─────┘ └──────┬──────┘   │
├───────┼───────────┼───────────┼───────────────┼──────────┤
│                   PyO3 FFI Boundary (zero-copy)           │
├───────┼───────────┼───────────┼───────────────┼──────────┤
│                     Rust Core Layer                        │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐   │
│  │  DHT    │ │ Ledger  │ │  Crypto  │ │  Consensus   │   │
│  │(Routing)│ │ (Sled)  │ │(ML-DSA)  │ │   (BFT)      │   │
│  └─────────┘ └─────────┘ └──────────┘ └─────────────┘   │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐   │
│  │ ZK Proof│ │ Storage │ │ Hardware │ │  Slashing    │   │
│  │(Sigma)  │ │ (Sled)  │ │  (vHSM)  │ │  (Penalty)   │   │
│  └─────────┘ └─────────┘ └──────────┘ └─────────────┘   │
├──────────────────────────────────────────────────────────┤
│                    Hardware Layer                          │
│  TPM/SEP  │  CPU UUID  │  Disk UUID  │  Network Interface │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow: Sovereign Decision

```
① User Input
   │  Transaction(source, target, amount, signature)
   v
② Submission (Python → Rust FFI)
   │  ledger.submit_tx(tx) → RustReplicatedLedger::submit_transaction()
   v
③ Validation (Rust)
   │  Slashing check → Balance check → Mempool addition
   v
④ Consensus (Rust BFT)
   │  Vote { block_hash, voter_id, decision, signature }
   │  ML-DSA-65 signature verification
   │  Votes ≥ quorum (2n/3 + 1) → Block committed
   v
⑤ Block Mining (Rust)
   │  mine_block(miner) → Balance update + State root computation
   v
⑥ ZK Proof Generation (Rust)
   │  Sigma protocol: generate_state_proof(value, blinding)
   │  Proof attached to block
   v
⑦ Storage (Rust Sled + Python SQLite)
   │  blocks tree → Block commit
   │  balances tree → Balance update
   │  SQLite → Audit log
   v
⑧ Propagation (Python P2P)
   │  Mesh sync → Peer verification → Local ledger commit
   v
⑨ Verifiable Evidence Complete
   │  PQC signature + BFT consensus proof + ZK privacy proof
   └─→ Independently verifiable by anyone
```

---

## 3. Rust Core

### 3.1 Module Overview

| Module | File | Function | no_std |
|--------|------|----------|--------|
| `crypto` | `crypto.rs` | ML-DSA-65 sign/verify | Yes |
| `consensus` | `consensus.rs` | BFT consensus engine | Yes |
| `ledger` | `ledger.rs` | Replicated ledger + state machine | No (Sled) |
| `proof_zk` | `proof_zk.rs` | Sigma protocol ZK proofs | Yes |
| `storage` | `storage.rs` | Sled/Memory store | Yes (Memory) |
| `dht` | `dht.rs` | Kademlia routing table | Yes |
| `policy_engine` | `policy_engine.rs` | Policy verification | Yes |
| `slashing` | `slashing.rs` | Violation penalty engine | Yes |
| `hardware` | `hardware/` | vHSM + hardware entropy | No (IOKit) |
| `kernel` | `kernel.rs` | Reflective loop + mode decision | Yes |

### 3.2 Cryptography (`crypto.rs`)

#### Data Structures

```rust
pub struct PQCKeypair {
    pub public_key: String,   // hex-encoded, 1952 bytes raw
    pub private_key: String,  // hex-encoded, 4032 bytes raw
}

pub struct MLDSA;  // ML-DSA-65 (FIPS 204) implementation
```

#### Public API

```rust
impl PQCKeypair {
    /// Generate ML-DSA-65 keypair
    /// Returns: (public_key_hex, private_key_hex)
    pub fn generate() -> (String, String);
}

impl MLDSA {
    /// Sign message with ML-DSA-65
    /// private_key format: "pk_hex:sk_hex"
    /// Returns: signature_hex (3309 bytes raw)
    pub fn sign_raw(private_key: &str, message: &str) -> Result<String, String>;

    /// Verify ML-DSA-65 signature
    /// Returns: true if valid
    pub fn verify_raw(public_key: &str, message: &str, signature: &str) -> bool;
}
```

#### Cryptographic Constants

| Constant | Value | Source |
|----------|-------|--------|
| Public key size | 1,952 bytes | FIPS 204 ML-DSA-65 |
| Secret key size | 4,032 bytes | FIPS 204 ML-DSA-65 |
| Signature size | 3,309 bytes | FIPS 204 ML-DSA-65 |
| Hash function | SHA3-256 | 32-byte output |
| ZK curve | Ristretto255 | curve25519-dalek |

### 3.3 Consensus Engine (`consensus.rs`)

#### Data Structures

```rust
pub struct Vote {
    pub block_hash: String,
    pub voter_id: String,
    pub decision: String,     // "APPROVE" | "REJECT"
    pub signature: String,    // ML-DSA-65 signature
    pub timestamp: f64,
}

pub struct BFTEngine {
    pub quorum_threshold: usize,              // (2n/3) + 1
    votes: HashMap<String, HashSet<String>>,  // block_hash → voter_ids
    committed_blocks: HashSet<String>,
}
```

#### Public API

```rust
impl BFTEngine {
    /// Initialize consensus engine
    /// quorum = (2 * total_validators / 3) + 1
    pub fn new(total_validators: usize) -> Self;

    /// Submit vote with signature verification
    /// Returns: true if quorum reached (block committed)
    pub fn submit_vote(&mut self, vote: Vote) -> bool;

    /// Check block commitment status
    pub fn is_committed(&self, block_hash: &str) -> bool;
}
```

#### Consensus Algorithm

```
1. N validators, quorum = ⌊2N/3⌋ + 1
2. Each vote: authenticated with ML-DSA-65 signature
3. Vote counting: unique voter_id count per block_hash
4. Quorum reached → block committed (added to committed_blocks)
5. Double-vote prevention: 1 vote per voter_id per block_hash
```

### 3.4 Ledger (`ledger.rs`)

#### Data Structures

```rust
pub struct Transaction {
    pub tx_id: String,
    pub source: String,
    pub target: String,
    pub amount: u64,
    pub signature: String,
    pub timestamp: f64,
    pub max_fee: u64,        // EIP-1559 style
    pub priority_fee: u64,   // Miner tip
}

pub struct Block {
    pub index: u32,
    pub timestamp: f64,
    pub tx_ids: Vec<String>,
    pub prev_hash: String,
    pub hash: String,
    pub miner: String,
    pub zk_proof: Option<String>,
    pub state_root: Option<String>,
    pub base_fee_per_gas: u64,
}
```

#### Public API

```rust
impl RustReplicatedLedger {
    pub fn new(path: &str) -> Self;
    pub fn submit_transaction(source, target, amount, signature, timestamp, max_fee, priority_fee);
    pub fn mine_block(miner_address: &str) -> Option<String>;
    pub fn get_balance(address: &str) -> u64;
    pub fn get_state_root() -> String;
    pub fn get_last_block() -> Option<Block>;
}
```

#### Sled Storage Trees

| Tree | Key | Value | Purpose |
|------|-----|-------|---------|
| `balances` | address (String) | u64 (Borsh) | Per-address balance |
| `blocks` | block_hash (String) | Block (Borsh) | Block chain |
| `meta` | "last_block_hash" | String | Latest block hash |
| `locks` | address (String) | bool | Slashing locks |

### 3.5 ZK Proofs (`proof_zk.rs`)

#### Data Structures

```rust
pub struct ZKProof {
    pub challenge: [u8; 32],
    pub z1: [u8; 32],
    pub z2: [u8; 32],
    pub commitment: [u8; 32],
}
```

#### Algorithm: Sigma Protocol (Ristretto255)

```
Prover:
  1. Choose random r1, r2
  2. commitment = r1·G + r2·H  (Pedersen commitment)
  3. challenge = SHA3(commitment ∥ public_data)
  4. z1 = r1 + challenge·v,  z2 = r2 + challenge·r
  5. proof = (challenge, z1, z2, commitment)

Verifier:
  1. Recompute: expected = z1·G + z2·H - challenge·C
  2. Valid if expected == commitment
```

### 3.6 Slashing (`slashing.rs`)

```rust
pub enum Penalty {
    StateLock,           // severity > 0.95: all activity blocked
    EconomicBurn(u64),   // severity > 0.80: balance deduction (100)
    IdentityIsolation,   // network isolation
}
```

### 3.7 Kernel Mode Decision (`kernel.rs`)

#### Reflective Loop

```rust
impl ReflectiveLoop {
    // alpha = 0.5 (default), beta = 0.5 (default)
    // e_stab = alpha * epsilon_c + beta * (1.0 - tau_ethics)

    pub fn compute_mode_raw(&self, epsilon_c: f64, tau_ethics: f64) -> ModeDecision {
        if tau_ethics > 0.85 { return VETO_LOCK }
        if e_stab < 0.3     { return CRITICAL_HALT }
        if e_stab < 0.7     { return SUSPICIOUS }
        return NORMAL;
    }
}
```

---

## 4. Python Kernel

### 4.1 Module Structure

```
warm_logic/kernel/
├── sys/
│   ├── cryptography.py   ML-DSA FFI wrapper + HardwareEnclave
│   ├── network.py        MeshNetworking (DHT orchestration)
│   └── consensus.py      BFT Python wrapper
├── mesh/
│   ├── dht.py            Kademlia DHT (Contact, RoutingTable, SovereignDHT)
│   ├── beacon.py         UDP beacon discovery
│   └── sync.py           P2P message synchronization
├── economy/
│   └── ledger.py         ReplicatedLedger (Rust-delegated)
├── identity/
│   └── kinetic_id.py     KineticIdentity (PQC key management)
├── ops/
│   ├── control.py        KernelLoop, TaskScheduler
│   ├── policy.py         PluginRecord, verify_plugin()
│   └── quorum_manager.py QuorumManager (voting orchestration)
└── api.py                compute_mode() entry point
```

### 4.2 Core Classes

#### KineticIdentity

```python
class KineticIdentity:
    """PQC keypair-based sovereign identity"""

    def __init__(keypair: Optional[Tuple[str, str]] = None):
        # If keypair not provided, generates new ML-DSA-65 keypair via Rust
        # Rust core required (raises RuntimeError otherwise)

    def sign_intent(intent_payload: str) -> str:
        """Sign message with private key. Returns: signature_hex"""

    @staticmethod
    def generate_keypair() -> Tuple[str, str]:
        """Generate ML-DSA-65 keypair. Returns: (public_key_hex, private_key_hex)"""

    @staticmethod
    def verify_intent(public_key: str, payload: str, signature: str) -> bool:
        """Verify signature. Returns: validity"""
```

#### ReplicatedLedger

```python
class ReplicatedLedger:
    """Rust-backed replicated ledger"""

    def __init__(store: SovereignStore, consensus_callback: Callable):
        # Sled DB initialization, Rust core required

    def submit_tx(tx: Transaction) -> bool:
        """Submit transaction. Validates and adds to mempool"""

    def mine_block(miner_address: str) -> Optional[str]:
        """Mine block. Returns: block_hash or None"""

    def receive_external_block(block_data, balance_updates, zk_proof, txs) -> bool:
        """Receive and verify external block. ZK proof + state root verification"""

    def get_balance(address: str) -> int:
        """Query address balance"""

    def get_state_root() -> str:
        """Deterministic hash of all balances"""
```

#### QuorumManager

```python
class QuorumManager:
    """BFT consensus orchestrator"""

    def __init__(ledger: ReplicatedLedger, total_validators: int = 4):
        # Initializes Rust BFTEngine

    def cast_vote(block_hash: str, decision: str) -> None:
        """Create and sign vote (VAL_IDENTITY, VAL_SECRET env vars required)"""

    def on_receive_block(payload: Dict) -> None:
        """Receive external block → verify → APPROVE/REJECT vote"""

    def on_receive_vote(payload: Dict) -> None:
        """Receive vote → submit to BFT engine → check finality"""
```

#### SovereignDHT

```python
class SovereignDHT:
    """Kademlia-based P2P discovery"""

    def __init__(node_id: bytes, address: str = "127.0.0.1", port: int = 4000):
        # K=20, ALPHA=3 Kademlia parameters

    async def start() -> None:
        """Start UDP server"""

    async def bootstrap(seeds: List[Tuple[str, int]]) -> None:
        """Connect to bootstrap nodes and build routing table"""

    async def iterative_find_node(target_id: bytes) -> List[Contact]:
        """Iterative node lookup (ALPHA=3 parallel)"""

    def store(key: bytes, value: str) -> None:
        """Store key-value pair"""
```

### 4.3 Python→Rust FFI Boundary

**Principle**: All cryptographic and consensus operations execute in Rust. Python handles orchestration only.

| Python Call | Rust Function | Data Transfer |
|-------------|---------------|--------------|
| `MLDSA.sign()` | `MLDSA::sign_raw()` | String (hex) |
| `MLDSA.verify()` | `MLDSA::verify_raw()` | String → bool |
| `KineticIdentity.generate_keypair()` | `PQCKeypair::generate()` | → (String, String) |
| `ledger.submit_tx()` | `RustReplicatedLedger::submit_transaction()` | Individual fields |
| `ledger.mine_block()` | `RustReplicatedLedger::mine_block()` | String → Option |
| `BFTEngine.submit_vote()` | `BFTEngine::submit_vote()` | Vote struct |

**FFI Performance**: Measured in Paper #9 — PyO3 zero-copy achieves 300x improvement over baseline (10MB payloads).

---

## 5. Network Protocol

### 5.1 Protocol Stack

```
┌──────────────────────────────────┐
│        Application Layer          │
│  Block propagation, votes, sync   │
├──────────────────────────────────┤
│        Discovery Layer            │
│  Kademlia DHT (port 4000/UDP)    │
│  Beacon broadcast (port 8999/UDP)│
├──────────────────────────────────┤
│        API Layer                  │
│  HTTP/JSON (port 8000, 5001)     │
├──────────────────────────────────┤
│        Transport Layer            │
│  UDP (DHT/beacon) + TCP (HTTP)   │
└──────────────────────────────────┘
```

### 5.2 Beacon Discovery

| Property | Value |
|----------|-------|
| Protocol | UDP broadcast |
| Port | 8999 |
| Interval | 2.0 seconds |
| Payload | `{"type": "beacon", "node_id": "...", "http_port": ...}` |
| Peer TTL | 15 seconds (removed if inactive) |

### 5.3 Kademlia DHT

| Parameter | Value | Description |
|-----------|-------|-------------|
| K | 20 | Bucket size |
| ALPHA | 3 | Parallel lookups |
| Node ID | 32 bytes | SHA3-256(public_key) |
| Distance metric | XOR | Standard Kademlia |
| Messages | PING, FIND_NODE, FIND_VALUE, STORE | JSON-encoded UDP |

### 5.4 PQC Gatekeeper

Every Contact registered in the DHT routing table must pass PQC verification:

```
Verification: SHA3-256(contact.public_key) == contact.node_id
On failure: silent drop (zero-trust)
```

---

## 6. Storage Architecture

### 6.1 Dual Storage

| Layer | Engine | Purpose | Format |
|-------|--------|---------|--------|
| Rust | Sled (embedded KV) | Consensus state (balances, blocks, meta) | Borsh serialization |
| Python | SQLite (SovereignStore) | Audit logs (blocks, events) | JSON |

**Rationale**: Sled for high-performance consensus-path KV, SQLite for queryable audit logs.

### 6.2 Sled Tree Structure

```
data/ledger.sled/
├── balances       address → u64 (Borsh)
├── blocks         block_hash → Block (Borsh)
├── meta           "last_block_hash" → String
└── locks          address → bool (slashing locks)
```

### 6.3 Data Paths

| Data | Default Path | Environment Variable |
|------|-------------|---------------------|
| Ledger DB | `data/ledger.sled` | (hardcoded) |
| Social DB | `data/social_db` | `WARM_DB_PATH` |
| Audit log | SQLite (inside SovereignStore) | — |

---

## 7. Security Model

### 7.1 Threat Model

| Threat | Defense | Status |
|--------|---------|--------|
| Quantum computer signature forgery | ML-DSA-65 (FIPS 204) | Implemented |
| Byzantine nodes (up to 1/3) | BFT consensus (2n/3+1 quorum) | Implemented |
| Key memory exposure | `zeroize` crate (memory scrubbing) | Implemented |
| Hardware tampering | TPM/CPU UUID-based attestation | Simulated |
| Replay attacks | Timestamp + signature inclusion | Implemented |
| Ledger tampering | Merkle state root + ZK proofs | Implemented |
| Policy violations | Slashing engine (StateLock, EconomicBurn) | Implemented |
| Network attacks (packet drop/tamper) | Chaos monkey testing | Test infra ready |
| Sybil attacks | PQC gatekeeper (node_id = hash(pubkey)) | Implemented |

### 7.2 Authentication

```
Node authentication:
  node_id = SHA3-256(ML-DSA-65 public key)
  → All messages carry signature
  → Signature verification failure → silent drop (zero-trust)

API authentication:
  Glass Browser (port 8000): No auth (local-only)
  Cockpit (port 5001): SOVEREIGN_COCKPIT_KEY required
```

### 7.3 Key Lifecycle

```
Generation → Use → (Rotation: not yet implemented) → Destruction (zeroize)
  │           │                                         │
  │           │  ML-DSA-65 sign/verify                  │  Secure memory wipe
  │           └─────────────────────────────────────────┘
  │
  └── HardwareEntropy::derive_seed_raw()
      (macOS: IOPlatformUUID + SerialNumber)
```

> **Note**: Automatic key rotation is not yet implemented. Keys are generated per session.

### 7.4 Hardware Security Modules

WarmLogic supports hardware-backed key storage for production deployments:

| HSM Type | Platform | Key Types | Status |
|----------|----------|-----------|--------|
| **Software HSM** | All | ML-DSA-65, ML-KEM-768 | Development only |
| **Apple Secure Enclave** | macOS 10.13+ | P-256 (hybrid) | Implemented |
| **TPM 2.0** | Linux | P-256, RSA-2048 | Implemented |

```python
from warm_logic.kernel.hardware.hsm import HSMManager, HSMType

# Auto-detect best available HSM
hsm = HSMManager()
hsm.initialize()  # Falls back gracefully: SEP → TPM → Software

# Generate hardware-bound signing key
key = hsm.generate_signing_key("governance-key")
signature = hsm.sign(key.key_id, state_hash)
```

### 7.5 Cross-Region State Synchronization

Multi-region federation uses eventual consistency with causal ordering:

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| **VectorClock** | Causal ordering | Lamport-style logical timestamps |
| **StateMerkleTree** | State verification | SHA-256 hash tree |
| **SyncBatch** | Network transport | Binary protocol (struct-packed) |
| **ConflictResolution** | Concurrent updates | Last-Writer-Wins (LWW) |

```
Region A ──┬── add_local_decision("d-1") ──┬── create_sync_batch("Region B")
           │                               │
           │   VectorClock: {A: 1}         │   decisions + merkle_root
           │                               ▼
           │                          Network
           │                               │
Region B ──┴── receive_sync_batch() ◄──────┘
               │
               ├── Verify merkle_root
               ├── Detect conflicts (concurrent vector clocks)
               └── Apply with LWW resolution
```

---

## 8. API Reference

### 8.1 Glass Browser API (port 8000)

#### Health

```
GET /health/liveness
→ 200 {"status": "alive", "timestamp": 1706832000.0}

GET /health/readiness
→ 200 {"status": "ready"}
→ 503 {"detail": "Not connected to mesh"}

GET /metrics
→ 200 (Prometheus text format)
   warmlogic_uptime_seconds 3600.0
   warmlogic_peer_count 3
   warmlogic_drift_score 0.02
```

#### Identity

```
GET /api/identity
→ 200 {"identity": "a1b2c3d4..."}
```

#### Verification

```
POST /api/verify
Content-Type: application/json
{"message": "Approve this decision"}
→ 200 {"signed_packet": {...}, "public_key": "...", "signature": "..."}
```

#### Social Feed

```
GET /api/social/feed
→ 200 [{"id": "...", "message": "...", "timestamp": ..., "signature": "..."}]

POST /api/social/post
Content-Type: application/json
{"message": "A sovereign message"}
→ 200 {"status": "posted", "id": "..."}
→ 429 {"detail": "Sovereign Rate Limit Exceeded"}
```

#### Mesh

```
GET /api/mesh/peers
→ 200 {"peers": [...], "sync_stats": {...}}
```

### 8.2 Cockpit API (port 5001)

| Endpoint | Auth Required | Description |
|----------|--------------|-------------|
| `GET /api/status` | No | System status |
| `POST /api/verify_key` | No | API key verification |
| `GET /api/mesh` | Yes | Mesh telemetry |
| `GET /api/logs` | No | Recent activity logs |
| `GET /api/logs/stream` | Yes | SSE real-time log stream |
| `GET /api/config` | Yes | Configuration query |
| `POST /api/config/seal` | Yes | Policy configuration update |

**Auth header**: `X-Cockpit-Key: {SOVEREIGN_COCKPIT_KEY}`

**SSE event types**:
- `REALITY_SYNC` — Drift score update
- `TELEMETRY_UPDATE` — System/mesh state

---

## 9. Governance Workflow

### 9.1 State Diagram

```
┌──────────┐     tick ≥ 3     ┌────────────┐
│   INIT   │ ───────────────→ │ AUTHORIZED │
└──────────┘                  └─────┬──────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              tau > 0.85     e_stab < 0.3    e_stab < 0.7
                    │               │               │
                    v               v               v
             ┌───────────┐  ┌─────────────┐  ┌────────────┐
             │ VETO_LOCK │  │CRITICAL_HALT│  │ SUSPICIOUS │
             └───────────┘  └─────────────┘  └────────────┘
```

### 9.2 Decision Chain

| Step | Status | Description |
|------|--------|-------------|
| ① Proposal creation | Not yet implemented | AmendmentProposal |
| ② Vote signing | Implemented | KineticIdentity.sign_intent() |
| ③ BFT consensus | Implemented | BFTEngine.submit_vote() (Rust) |
| ④ Finality detection | Implemented | Log output on quorum |
| ⑤ Network propagation | Not yet implemented | StitchServer |
| ⑥ State application | Partial | Ledger commit works; governance state transition pending |

### 9.3 Plugin System

```python
PluginRecord(
    name="example_plugin",
    package="example-package",
    entry_point="example.main",
    min_version="1.0.0",
    editions_allowed={"pro", "enterprise"},
    modules_required={"warm_logic.kernel"},
    signature="ML-DSA-65 signature",
)

# Verification process:
# 1. Registry existence check
# 2. Signature verification via Rust PolicyEngine
# 3. Edition permission check
# 4. Module dependency check
# 5. Package version check
# 6. Entry point registration check
# 7. External signature file verification
```

---

## 10. Deployment

### 10.1 Node Types

| Type | Components | Consensus | Storage |
|------|-----------|-----------|---------|
| Validator | Full Rust + Python | Yes | Full ledger |
| Beacon | Python mesh only | No | None |
| Gateway | FastAPI server | No | Social feed |

### 10.2 Minimum Network Configuration

```
BFT f+1 fault tolerance minimum:

4 validators → quorum = 3 → tolerates 1 Byzantine node
7 validators → quorum = 5 → tolerates 2 Byzantine nodes
10 validators → quorum = 7 → tolerates 3 Byzantine nodes
```

### 10.3 Port Usage

| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | TCP (HTTP) | Glass Browser UI/API |
| 5001 | TCP (HTTP) | Sovereign Cockpit |
| 8999 | UDP | Beacon broadcast |
| 4000 | UDP | Kademlia DHT |

---

## 11. Configuration Reference

### 11.1 Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `WARM_HTTP_PORT` | 8000 | No | HTTP server port |
| `WARM_DB_PATH` | `data/social_db` | No | Social DB path |
| `WARM_DEV_MODE` | (unset) | No | Set "1" to bypass peer checks |
| `WARM_REGION` | (unset) | No | Network topology region |
| `WARM_LOGIC_SALT` | (unset) | No | Additional key derivation entropy |
| `WARM_LOGIC_SIMULATION` | (unset) | No | Set "1" for simulation mode |
| `WARM_IDENTITY_SEED` | (unset) | No | Identity seed override |
| `SOVEREIGN_COCKPIT_KEY` | (none) | Yes* | Cockpit API key (*when using Cockpit) |
| `COCKPIT_HTTP_PORT` | 5001 | No | Cockpit port |
| `VAL_IDENTITY` | (none) | Yes* | Validator node ID (*for consensus) |
| `VAL_SECRET` | (none) | Yes* | Validator secret key (*for consensus) |
| `WARM_SIM_SANDBOX` | (unset) | No | Disables hardware attestation when set |
| `CHAOS_DROP_RATE` | 0.0 | No | Packet drop rate (0.0–1.0) |
| `CHAOS_LATENCY_MS` | 0 | No | Artificial latency (ms) |
| `CHAOS_CORRUPTION_RATE` | 0.0 | No | Packet corruption rate |

### 11.2 Cargo Feature Flags

| Flag | Dependencies | Description |
|------|-------------|-------------|
| `std` | sha3, rand, hex, serde, chrono, fips204 std | Standard library |
| `python` | PyO3, persistence, std | Python bindings |
| `persistence` | Sled, DashMap, std | Persistent storage |
| `cockpit` | ratatui, crossterm, clap, persistence | TUI dashboard |

---

## 12. Schema System

### 12.1 Overview

| Metric | Value |
|--------|-------|
| Total JSON schemas | 187 |
| Domains | 34 |
| SSOT hierarchy | Schema > Spec > Code > Test |

### 12.2 Key Domains

| Domain | Schema Count | Examples |
|--------|-------------|----------|
| evidence | 15 | CE ledger, audit pack, external incident |
| meta | 40+ | Execution manifest, experiment bundle |
| governance | 19 | GovDec events, tau policy |
| os | 20+ | OS state, scheduler, stability envelope |
| ops | 10 | Audit events, incidents, SBOM |
| security | 4 | Tamper log, red-team experiments |
| ml | 6 | Model registry, pipeline |
| mcp | 9 | MCP traces, tool restrictions |
| research | 6 | A/B experiments, federated traces |

### 12.3 Schema Governance Rules

- **New schemas**: Create under `spec/schema/`, register in `SCHEMA_REGISTRY_v1.md`
- **Changes**: Maintain backward compatibility (new fields must be optional). Create new version (v1 → v2) for breaking changes.
- **Migration**: Migration scripts required for version changes.

---

## 13. Performance

### 13.1 Verified Benchmarks

| Metric | Value | Reproducible | Source |
|--------|-------|-------------|--------|
| PyO3 FFI overhead (10MB) | 300x improvement over baseline | Yes | Paper #9, `scripts/eval/` |
| ML-DSA-65 sign/verify | ~ms per operation | Yes | In-code tests |
| SHA3-256 hashing | ~μs per hash | Yes | Library benchmarks |
| Sled read/write | ~μs latency | Yes | Sled official benchmarks |
| BFT vote processing | O(1) per vote | Yes | HashMap + HashSet |

### 13.2 Target Metrics (Not Yet Verified)

These are goals we're working toward — not achieved numbers:

| Target | Value | Status |
|--------|-------|--------|
| Global finality latency | < 10ms | Needs multi-node benchmark |
| Formal verification latency | < 0.1ms | Needs UDS socket benchmark |
| Decentralized sync | < 15ms | Needs multi-node test |
| Throughput | 50,000+ TPS | Needs load testing |

> We only claim what we can prove. Target metrics are clearly distinguished from verified results.

---

## 14. Implementation Status

### 14.1 Completion Matrix

| Component | Status | Completion | Notes |
|-----------|--------|-----------|-------|
| ML-DSA-65 sign/verify | Working | 95% | Key rotation not yet implemented |
| BFT consensus engine | Working | 85% | Network propagation pending |
| Replicated ledger | Working | 80% | Tx validation + block mining operational |
| ZK proofs | Working | 75% | Basic Sigma protocol |
| Kademlia DHT | Working | 70% | No bootstrap seeds yet |
| Beacon discovery | Working | 90% | UDP local discovery |
| Glass Browser API | Working | 85% | 6 endpoints |
| Cockpit API | Working | 80% | Includes SSE stream |
| Hardware attestation | Partial | 40% | macOS IOKit only, TPM simulated |
| P2P block propagation | Not implemented | 0% | StitchServer stub |
| Proposal creation | Not implemented | 0% | AmendmentProposal stub |
| Auto key rotation | Not implemented | 0% | Session-based keys only |
| CLI tool | Not implemented | 5% | wlctl undocumented |
| Monitoring (Prometheus) | Partial | 30% | Basic metrics only |

### 14.2 Known Stubs (raise RuntimeError)

| Stub | Location | Impact |
|------|----------|--------|
| `StitchServer.broadcast()` | quorum_manager.py | High — no consensus propagation |
| `AmendmentProposal` | control.py | High — governance workflow incomplete |
| `ClosureDaemon` | control.py | Medium — autonomous kernel evolution |
| `EvolutionScheduler` | control.py | Medium — policy scheduling |
| `ConsensusMechanism` | control.py | Medium — upper consensus wrapper |
| `SystemMetrics` (telemetry) | control.py | High — no monitoring |

### 14.3 Critical Gaps for Production

| Gap | Severity | Approach |
|-----|----------|----------|
| P2P propagation | Critical | StitchServer → libp2p or custom TCP |
| Key persistence | Critical | Keystore (file or OS keychain) |
| Security audit | Critical | Third-party audit required |
| Monitoring | High | Complete Prometheus exporter |
| CLI tool | High | Finish typer-based `wlctl` |
| Documentation | High | API docs, tutorials |
| Package distribution | High | PyPI, Docker Hub |
| Test coverage (~60%) | Medium | Target 80% |
| Hardware attestation | Medium | Real TPM integration |

---

## 15. Contributing

### 15.1 Development Setup

```bash
# Prerequisites
Python 3.12+
Rust 1.75+ (with cargo)

# Clone and build
git clone https://github.com/espressolee/warmlogic-rust-core-artifact
cd warmlogic
pip install -r requirements.txt
pip install maturin
cd warm_logic_rs && maturin develop && cd ..

# Verify Rust core
python -c "import warm_logic_rs; print('Rust core loaded')"

# Run tests
pytest tests/ -v

# Start the server
python -m warm_logic.ui.server
```

### 15.2 Where to Contribute

| Area | Difficulty | Impact | Good First Issue |
|------|-----------|--------|-----------------|
| Documentation & tutorials | Easy | High | Yes |
| Docker images | Easy | High | Yes |
| Test coverage | Medium | Medium | Yes |
| PyPI packaging | Medium | High | No |
| CLI tool (`wlctl`) | Medium | High | No |
| Prometheus monitoring | Medium | Medium | No |
| P2P block propagation | Hard | Critical | No |
| TPM integration (Linux/Windows) | Hard | Medium | No |
| libp2p integration | Hard | High | No |

### 15.3 Conventions

- **Commit format**: `feat|fix|docs|refactor: short description`
- **SSOT hierarchy**: Schema changes first, then code, then tests
- **All cryptographic operations**: Must go through Rust core, never Python
- **New schemas**: Register in `SCHEMA_REGISTRY_v1.md`
- **Tests required**: For all meaningful changes

### 15.4 Security Reporting

If you discover a security vulnerability, please report it responsibly:

- **Do NOT** open a public issue
- Email: 70549809+espressolee@users.noreply.github.com
- We aim to acknowledge reports within 48 hours

---

## 16. Appendix: Constants & Thresholds

### 16.1 Cryptographic Constants

```
ML-DSA-65 (FIPS 204):
  Public key:  1,952 bytes
  Secret key:  4,032 bytes
  Signature:   3,309 bytes
  Security:    NIST Level 3 (128-bit post-quantum)

SHA3-256:
  Output:      32 bytes (256 bits)

Ristretto255 (ZK):
  Scalar:      32 bytes
  Point:       32 bytes (compressed)
```

### 16.2 Network Constants

```
Kademlia:
  K (bucket size):       20
  ALPHA (parallel):      3
  Node ID:               32 bytes (SHA3-256)

Beacon:
  Port:                  8999 (UDP)
  Broadcast interval:    2.0 seconds
  Peer TTL:              15 seconds

HTTP:
  Glass Browser:         8000 (default)
  Cockpit:               5001 (default)
  DHT:                   4000 (default)
```

### 16.3 Policy Thresholds

```
Kernel mode:
  VETO_LOCK:     tau_ethics > 0.85
  CRITICAL_HALT: e_stab < 0.3
  SUSPICIOUS:    e_stab < 0.7
  NORMAL:        otherwise

Consensus:
  quorum = ⌊(2 × N) / 3⌋ + 1

Slashing:
  StateLock:      severity > 0.95
  EconomicBurn:   severity > 0.80 (100 unit deduction)

Invariant violations:
  CPU drift:      > 0.05
  Memory usage:   > 0.95

Block fees:
  base_fee_per_gas: 10
  max_fee (default): 20
  priority_fee (default): 1
```

---

*WarmLogic Technical Specification v1.0 — Open Source Edition*
*This document reflects the actual codebase. Unimplemented features and simulation stubs are explicitly marked.*
