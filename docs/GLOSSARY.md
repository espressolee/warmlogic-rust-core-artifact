# WarmLogic Glossary

> **Purpose**: This document defines the specialized terminology used throughout the WarmLogic project to bridge the gap between AI-optimized nomenclature and human understanding.

## 🌟 Core Concepts

### Sovereign
**Definition**: A system property where the operating environment is verifiable and independent of external control.
**Context**: Enforced via Hardware Root of Trust and PQC signatures.

### Kinetic
**Definition**: Properties or identities derived dynamically from runtime behavior or cryptographic proofs.
**Example**: "Kinetic Identity" vs. static database ID.

### P-Series (Phase Series)
**Definition**: Granular milestones (P001 - P999).
- **P2xx**: Completed features.
- **P3xx**: Active development.

---

## 🏗️ Architecture

### Kernel
The high-level Python brain of the system. Manages agentic workflows, policies, and SDK interactions.

### Substrate
The low-level Rust foundation. Handles "Security-Critical" tasks: Cryptography, Persistence, and BFT.

### Mesh
The P2P network layer. Uses Kademlia DHT for discovery and Gossip for state propagation.

### Ledger
The immutable record of all signed governance decisions and state transitions.

### Cockpit
The developer control plane. Provides APIs and TUIs for monitoring kernel health.

### Glass
The web-based visualization UI (Dashboard) for real-time decision tracking.

### Hive
A cluster of multiple Sovereign Nodes working in a Quorum.

---

## 🔐 Cryptography

### ML-DSA-65 (FIPS 204)
The primary signature algorithm (Module-Lattice-based Digital Signature Algorithm). Post-quantum secure.

### ML-KEM (FIPS 203)
The planned key encapsulation mechanism for secure node-to-node channel establishment.

### ZK-Proof (Zero-Knowledge Proof)
A mathematical proof that a statement is true without revealing the data itself. Used for private governance.

### Dilithium
The internal name often used for the ML-DSA lattice-based signature scheme.

### MMR (Merkle Mountain Range)
A specialized Merkle tree structure used for efficient append-only logging in the Ledger.

### Evidence Bundle
A package containing an intent, the policy used, and the signed verdict/proof.

---

## 🕸️ Consensus & Mesh

### BFT (Byzantine Fault Tolerance)
The ability of a system to reach consensus even if some nodes are malicious or failing.

### Finality
The point at which a transaction or decision is guaranteed to be irreversible.

### SSOT (Single Source of Truth)
The principle that there is only one authoritative version of system state.

### Quorum
The minimum number of nodes required to validate a governance decision (usually 2f+1).

### DHT (Distributed Hash Table)
A decentralized system for mapping keys to values, used by the Mesh for peer discovery.

### Slashing
The penalty mechanism for nodes that submit invalid proofs or violate consensus rules.

---

## ⚖️ Governance & Policy

### Constitution
The root policy file that defines the fundamental constraints of an agent.

### GOVDEC (Governance Decision)
An immutable record of an approved or rejected action.

### Veto
A high-priority policy override that can block an action regardless of other approvals.

### CE (Counter-Example) / Forensic Proof
A specific scenario or data point that proves a policy violation.

### τ (Tau)
The time constant for governance convergence. Controls the speed of consensus.

---

## 💻 Hardware & Identity

### vHSM (Virtual Hardware Security Module)
A software-defined security boundary that emulates an HSM for local development.

### SEP (Secure Enclave Processor)
The dedicated security chip on Apple hardware used by WarmLogic for anchor keys.

### TPM (Trusted Platform Module)
The standard hardware security chip on Linux/Windows machines for attestation.

### IOPlatformUUID
The unique hardware identifier used on macOS to anchor a Sovereign Node to a physical machine.

### Seed Phrase
The 24-word mnemonic used to derive the Sovereign Private Key.
