# WarmLogic System Architecture v2.0

> **Version**: 2.0
> **Last Updated**: 2026-02-07
> **Status**: research prototype; see docs/CLAIM_EVIDENCE.md
> **Philosophy**: "Hard Shell, Soft Brain"

---

## Table of Contents

1. [Core Philosophy](#1-core-philosophy)
2. [System Overview](#2-system-overview)
3. [Layer Architecture](#3-layer-architecture)
4. [Data Flow](#4-data-flow)
5. [Cryptographic Evidence Chain](#5-cryptographic-evidence-chain)
6. [Component Details](#6-component-details)
7. [Module Dependencies](#7-module-dependencies)
8. [Security Architecture](#8-security-architecture)
9. [Deployment Topology](#9-deployment-topology)
10. [Performance Characteristics](#10-performance-characteristics)

---

## 1. Core Philosophy

WarmLogic solves the AI Paradox: **LLMs are flexible but unsafe; Kernels are rigid but secure.**

### The Hybrid Organism

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ┌───────────────────┐       ┌───────────────────┐        │
│   │   SOFT BRAIN      │       │   HARD SHELL      │        │
│   │   (Python)        │◄─────►│   (Rust)          │        │
│   │                   │ PyO3  │                   │        │
│   │   • Reasoning     │       │   • Crypto        │        │
│   │   • Goals         │       │   • Consensus     │        │
│   │   • Self-Patch    │       │   • Ledger        │        │
│   │   • Governance    │       │   • ZK Proofs     │        │
│   └───────────────────┘       └───────────────────┘        │
│                                                             │
│              ~300x faster crypto via FFI                    │
└─────────────────────────────────────────────────────────────┘
```

| Aspect | Soft Brain (Python) | Hard Shell (Rust) |
|--------|---------------------|-------------------|
| **Role** | Intelligence & Governance | Security & Persistence |
| **Mutability** | Neuroplastic (self-modifying) | Immutable (cryptographically sealed) |
| **Trust Level** | Policy-controlled | Hardware-anchored |
| **Performance** | Flexible | High-performance |

---

## 2. System Overview

### 2.1 Four-Layer Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ Cockpit  │  │   CLI    │  │   SDK    │  │    REST API      │    │
│  │   (UI)   │  │ (wlctl)  │  │ (Python) │  │   (FastAPI)      │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘    │
│       │             │             │                  │              │
├───────┴─────────────┴─────────────┴──────────────────┴──────────────┤
│                        GOVERNANCE KERNEL                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Constitution │  │  Policy VM   │  │   Zanzibar RBAC          │  │
│  │  (Invariants)│  │   (Rules)    │  │   (Permissions)          │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                 │                        │                │
├─────────┴─────────────────┴────────────────────────┴────────────────┤
│                        CRYPTO SUBSTRATE                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ ML-DSA-65│  │   BFT    │  │ZK Proofs │  │  Evidence Bundle │    │
│  │  (PQC)   │  │(Consensus│  │ (Sigma)  │  │    (Audit)       │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘    │
│       │             │             │                  │              │
├───────┴─────────────┴─────────────┴──────────────────┴──────────────┤
│                        STORAGE LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │    Ledger    │  │   Sled DB    │  │     DHT Mesh             │  │
│  │ (Hash Chain) │  │  (Embedded)  │  │    (Kademlia)            │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
WarmLogic/
├── src/warm_logic/           # Python Kernel (Soft Brain)
│   ├── app/                  # Application Layer
│   │   ├── cli/              # wlctl command interface
│   │   ├── cockpit/          # Web dashboard
│   │   └── api/              # REST API
│   ├── kernel/               # Governance Kernel
│   │   ├── constitution.py   # Constitutional invariants
│   │   ├── zanzibar.py       # RBAC
│   │   └── policy_engine.py  # Policy VM
│   ├── sdk/                  # Public SDK
│   ├── os/                   # OS Layer
│   ├── mesh/                 # P2P Networking
│   └── evidence/             # Audit Trail
│
├── rust_core/                # Rust Core (Hard Shell)
│   └── src/
│       ├── lib.rs            # PyO3 exports
│       ├── crypto.rs         # ML-DSA-65
│       ├── consensus.rs      # BFT engine
│       ├── ledger.rs         # Append-only ledger
│       └── proof_zk.rs       # Zero-knowledge proofs
│
├── spec/                     # Protocol specifications
├── tests/                    # Test suites
└── docs/                     # Documentation
```

### 2.3 Runtime Contract Anchors (Verified)

- **Version source of truth**: `src/warm_logic/VERSION`
  - Consumers: `src/warm_logic/__init__.py`, `src/warm_logic/VERSION.py`, `src/warm_logic/app/cli/wlctl.py`
- **CLI kernel entrypoint**: `src/warm_logic/kernel/kernel_loop.py` exposes `run_kernel_loop` for `wlctl start`
- **SDK constructor contract**:
  - Canonical: `SovereignClient(endpoint="...")`
  - Compatibility mode: `SovereignClient(host="localhost", port=8000, timeout=60)`

---

## 3. Layer Architecture

### 3.1 Application Layer

| Component | Location | Technology | Purpose |
|-----------|----------|------------|---------|
| **Cockpit** | `app/cockpit/` | FastAPI + React | Real-time monitoring dashboard |
| **CLI (wlctl)** | `app/cli/` | Typer | Operator command interface |
| **SDK** | `sdk/` | Python | Developer integration API |
| **REST API** | `app/api/` | FastAPI | External system integration |

### 3.2 Governance Kernel

| Component | Location | Purpose |
|-----------|----------|---------|
| **Constitution** | `kernel/constitution.py` | Semantic invariants (cannot be bypassed) |
| **Policy Engine** | `kernel/policy_engine.py` | Dynamic rule evaluation |
| **Zanzibar RBAC** | `kernel/zanzibar.py` | Relationship-based access control |
| **Mode Controller** | `kernel/mode_controller.py` | NORMAL → VETO_LOCK transitions |

### 3.3 Crypto Substrate (Rust)

| Component | File | Technology | Purpose |
|-----------|------|------------|---------|
| **Signatures** | `crypto.rs` | ML-DSA-65 (FIPS 204) | Post-quantum signatures |
| **Consensus** | `consensus.rs` | WL-BFT-v1 | Byzantine fault tolerance |
| **ZK Proofs** | `proof_zk.rs` | Sigma Protocol | Privacy-preserving compliance |
| **Key Management** | `crypto.rs` | Zeroize | Secure key handling |

### 3.4 Storage Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Ledger** | Hash chain | Append-only audit trail |
| **State DB** | Sled (embedded) | Fast key-value storage |
| **DHT** | Kademlia | Distributed peer discovery |

---

## 4. Data Flow

### 4.1 Decision Flow

```
User/AI Intent
      │
      ▼
┌─────────────────┐
│   SDK Client    │  client.propose_action(intent, context)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Policy Engine  │  Evaluate against constitution
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌───────┐
│APPROVE│ │REJECT │
└───┬───┘ └───┬───┘
    │         │
    ▼         ▼
┌─────────────────┐
│  Crypto Core    │  Sign with ML-DSA-65
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  BFT Consensus  │  Reach quorum (2f+1)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Ledger      │  Append to hash chain
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Evidence Bundle │  Return proof to caller
└─────────────────┘
```

### 4.2 Evidence Bundle Structure

```
┌─────────────────────────────────────────────────────┐
│                   Evidence Bundle                    │
├─────────────────────────────────────────────────────┤
│  decision_hash     : SHA3-256(intent + context)     │
│  policy_snapshot   : Hash of active policy          │
│  input_hash        : Hash of original input         │
│  output_hash       : Hash of decision result        │
│  timestamp         : ISO8601 with microseconds      │
│  node_id           : Signer's public key hash       │
│  pqc_signature     : ML-DSA-65 signature            │
│  consensus_proof   : BFT quorum attestation         │
│  zk_proof          : Optional compliance proof      │
└─────────────────────────────────────────────────────┘
```

---

## 5. Cryptographic Evidence Chain

### 5.1 Signature Flow

```
                    ┌─────────────────────────────────┐
                    │         ML-DSA-65               │
                    │    (FIPS 204 - Level 3)         │
                    └───────────────┬─────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│   Keygen      │         │     Sign      │         │    Verify     │
│               │         │               │         │               │
│ (pk, sk) ←    │         │  σ ← Sign(    │         │  ✓ ← Verify(  │
│   random()    │         │    sk, msg)   │         │   pk, msg, σ) │
│               │         │               │         │               │
│  ~1ms         │         │  ~50μs        │         │  ~30μs        │
└───────────────┘         └───────────────┘         └───────────────┘
```

### 5.2 Hash Chain

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Block 0 │───►│ Block 1 │───►│ Block 2 │───►│ Block N │
│         │    │         │    │         │    │         │
│ Genesis │    │prev_hash│    │prev_hash│    │prev_hash│
│  hash   │    │= H(B0)  │    │= H(B1)  │    │= H(Bn-1)│
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

---

## 6. Component Details

### 6.1 SDK (SovereignClient)

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient(host="localhost", port=8000)

# Propose an action
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com"}
)

# Check result
if decision.approved:
    bundle = client.get_evidence(decision.proof_hash)
```

### 6.2 Policy Engine

```yaml
# config/constitution.yaml
veto_rules:
  - name: "Block Data Deletion"
    pattern: "delete_*"
    action: BLOCK
    reason: "Requires manual approval"

permitted_actions:
  - send_email
  - read_document
  - generate_report

rate_limits:
  - action: "api_call"
    max_per_minute: 100
```

### 6.3 Kernel Modes

```
┌─────────┐    threshold    ┌───────────┐    critical    ┌───────────┐
│ NORMAL  │───────────────►│  CAUTION  │───────────────►│ VETO_LOCK │
│         │                 │           │                │           │
│ e_stab  │                 │  e_stab   │                │  e_stab   │
│ < 0.3   │                 │  < 0.6    │                │  ≥ 0.6    │
└─────────┘                 └───────────┘                └───────────┘
      ▲                           │                            │
      │                           │                            │
      └───────────────────────────┴────────────────────────────┘
                            recovery
```

---

## 7. Module Dependencies

### 7.1 Python Package Dependencies

```
warm_logic/
├── sdk/            ─────► kernel/
├── kernel/         ─────► rust_core (via PyO3)
├── app/cli/        ─────► sdk/, kernel/
├── app/cockpit/    ─────► sdk/, kernel/
└── mesh/           ─────► rust_core
```

### 7.2 Rust Crate Dependencies

| Crate | Version | Purpose |
|-------|---------|---------|
| `pyo3` | 0.21 | Python bindings |
| `fips204` | 0.4 | ML-DSA-65 implementation |
| `curve25519-dalek` | 4.1 | ZK proof primitives |
| `sha3` | 0.10 | SHA3-256 hashing |
| `sled` | 0.34 | Embedded database |
| `merlin` | 3.0 | Fiat-Shamir transcripts |
| `zeroize` | 1.8 | Secure memory clearing |

### 7.3 External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.12+ | Kernel runtime |
| Rust | 1.75+ | Crypto core compilation |
| maturin | 1.5+ | PyO3 build tool |

---

## 8. Security Architecture

### 8.1 Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                      UNTRUSTED                               │
│   [Network]    [User Input]    [External AI]    [Plugins]   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            TRUST BOUNDARY: Input Validation                  │
│                 (Policy Engine + Schema)                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SEMI-TRUSTED                              │
│        Python Kernel (Governance + Reasoning)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             TRUST BOUNDARY: PyO3 FFI                         │
│               (Type-safe Rust bridge)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       TRUSTED                                │
│      Rust Core (Crypto, Consensus, Ledger, ZK)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   HARDWARE ANCHOR                            │
│          (TPM/SEP - currently simulated)                     │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Defense Mechanisms

| Defense | Mechanism | Component |
|---------|-----------|-----------|
| **Identity** | ML-DSA-65 keypairs | `crypto.rs` |
| **Integrity** | SHA3-256 hash chains | `ledger.rs` |
| **Confidentiality** | ZK proofs | `proof_zk.rs` |
| **Availability** | BFT consensus | `consensus.rs` |
| **Governance** | Constitutional invariants | `constitution.py` |

---

## 9. Deployment Topology

### 9.1 Single Node (Development)

```
┌─────────────────────────────────────┐
│           Developer Machine          │
│                                      │
│  ┌─────────────┐  ┌──────────────┐  │
│  │  WarmLogic  │  │   Sled DB    │  │
│  │   Kernel    │  │  (Embedded)  │  │
│  └─────────────┘  └──────────────┘  │
│                                      │
└─────────────────────────────────────┘
```

### 9.2 Dual Node (Production)

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ┌─────────────────────┐       ┌─────────────────────┐    │
│   │     PRIMARY      │       │   SECONDARY     │    │
│   │   (Node A)     │◄─────►│    (Node B)       │    │
│   │                     │ P2P   │                     │    │
│   │   • AI Reasoning    │       │   • 24/7 Validation │    │
│   │   • Development     │       │   • Deep Audits     │    │
│   │   • Cognitive Work  │       │   • Anchor Node     │    │
│   └─────────────────────┘       └─────────────────────┘    │
│                                                             │
│                   encrypted mesh                        │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 Swarm (Enterprise)

```
                    ┌─────────────┐
                    │  Bootstrap  │
                    │    Node     │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │   Node 1    │ │   Node 2    │ │   Node 3    │
    │  (Region A) │ │  (Region B) │ │  (Region C) │
    └─────────────┘ └─────────────┘ └─────────────┘
           │               │               │
           └───────────────┴───────────────┘
                    Kademlia DHT
```

---

## 10. Performance Characteristics

### 10.1 Benchmarks

| Operation | Latency | Throughput | Notes |
|-----------|---------|------------|-------|
| ML-DSA-65 Keygen | ~1 ms | 1000/s | One-time per identity |
| ML-DSA-65 Sign | ~50 μs | 20,000/s | Per decision |
| ML-DSA-65 Verify | ~30 μs | 33,000/s | Per verification |
| BFT Consensus (4 nodes) | <100 ms | 10/s | Network-bound |
| Evidence Bundle | <10 ms | 100/s | Full audit package |
| Sled Write | ~100 μs | 10,000/s | Local storage |
| PyO3 FFI Call | <1 μs | 1,000,000/s | Overhead only |

### 10.2 Scalability

| Metric | Single Node | Swarm (4 nodes) | Swarm (16 nodes) |
|--------|-------------|-----------------|------------------|
| Decisions/sec | 100 | 10 | 5 |
| Latency (p99) | 10 ms | 200 ms | 500 ms |
| Storage | Unlimited | Replicated | Sharded |

---

## Related Documentation

- **[TECHNICAL_SPEC.md](TECHNICAL_SPEC.md)**: Full protocol specification
- **[THREAT_MODEL.md](THREAT_MODEL.md)**: Attack surface analysis
- **[API_SDK.md](API_SDK.md)**: SDK reference
- **[WHITEPAPER.md](WHITEPAPER.md)**: Academic foundations
