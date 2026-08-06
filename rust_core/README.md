# WarmLogic

> **Cryptographic proof for every AI decision.**
> Post-quantum. Byzantine fault-tolerant. Local-first.

[![Version](https://img.shields.io/badge/version-0.4.0+kinetic-blue)](rust_core/Cargo.toml)
[![License: MIT](https://img.shields.io/badge/kernel-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://python.org)
[![Rust](https://img.shields.io/badge/rust-1.75+-orange)](https://rust-lang.org)

---

## Why WarmLogic?

AI agents are "black boxes". You can't prove **why** they did something, or **if** they followed the rules.

WarmLogic solves this by wrapping AI reasoning in a **cryptographic kernel** that creates unforgeable evidence for every decision.

| Problem                          | WarmLogic Solution                                         |
| -------------------------------- | ---------------------------------------------------------- |
| AI decisions are unverifiable    | Every decision signed with ML-DSA-65 (Post-Quantum)        |
| Single points of failure         | BFT consensus across node swarm                            |
| Privacy vs. compliance trade-off | Zero-knowledge proofs for compliance without data exposure |
| Regulatory uncertainty           | Constitutional guardrails with formal verification         |
| Trust in centralized AI          | Local-first, sovereign data ownership                      |

---

## Architecture

```
+----------------------------------------------------------+
|                    WarmLogic Stack                        |
+----------------------------------------------------------+
|  Application Layer  |  CLI / Cockpit UI / REST API       |
+---------------------+------------------------------------+
|  Governance Kernel  |  Constitution / RBAC / Policy VM   |
+---------------------+------------------------------------+
|  Crypto Substrate   |  ML-DSA-65 / ZK Proofs / BFT      |
+---------------------+------------------------------------+
|  Storage Layer      |  Ledger / redb / DHT Mesh         |
+----------------------------------------------------------+
```

**Key Components:**

- **Rust Core** (`rust_core/`): High-performance cryptography, consensus, and ledger
- **Python Kernel** (`src/warm_logic/`): Governance logic, SDK, and application layer
- **PyO3 Bridge**: ~300x faster than pure Python for crypto operations

---

## Core Features

| Feature                       | Description                                            |
| ----------------------------- | ------------------------------------------------------ |
| **Post-Quantum Cryptography** | ML-DSA-65 (FIPS 204) signatures resist quantum attacks |
| **BFT Consensus**             | Byzantine fault-tolerant agreement across nodes        |
| **Zero-Knowledge Proofs**     | Verify compliance without exposing data                |
| **Constitutional Governance** | Formal rules that cannot be bypassed                   |
| **Evidence Bundles**          | Immutable audit trail for every decision               |
| **Local-First**               | Your data stays on your hardware                       |
| **Swarm Mesh**                | P2P network with Kademlia DHT                          |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Rust 1.75+
- macOS, Linux, or Docker

### Installation (3 Lines)

```bash
git clone https://github.com/espressolee/warmlogic-rust-core-artifact
cd warmlogic
make setup
```

This installs dependencies, compiles the Rust core, and verifies system integrity.

### Run the Sovereign Kernel

```bash
# Start the CLI interface
warmlogic

# Or start with the web dashboard
python -m warm_logic.ui.server
```

### Docker (Alternative)

```bash
docker-compose up -d
# Dashboard: http://localhost:8000
```

---

## Your First Sovereign Decision

```python
from warm_logic.sdk import SovereignClient

# Connect to local kernel
client = SovereignClient()

# Propose an action
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com", "subject": "Hello"}
)

# Every decision has cryptographic proof
print(f"Decision: {decision.verdict}")
print(f"Proof Hash: {decision.proof_hash}")
print(f"PQC Signature: {decision.signature[:32]}...")
```

---

## Zero-Knowledge Proofs (Python API)

Generate and verify Groth16 proofs for governance decisions:

```python
import warm_logic_rs as wl

# Create prover and run trusted setup
prover = wl.ZKGovernanceProver()
prover.setup()

# Generate a 192-byte proof
result = prover.prove(
    decision_hash=bytes(32),
    policy_hash=bytes(32),
    decision_type="policy",  # policy|veto|quorum|compliance|identity
    epoch=1234567890,
    node_id=bytes(32),
    authority_level=10,      # private witness
    threshold=5,             # private witness
    approval_count=7,        # private witness
)

# Verify proof (public inputs only)
valid = prover.verify(
    proof_hex=result['proof_hex'],
    decision_hash=bytes(32),
    policy_hash=bytes(32),
    decision_type="policy",
    epoch=1234567890,
    node_id=bytes(32),
)
print(f"Proof valid: {valid}")  # True
```

---

## Benchmarks

| Metric                  | Value   | Notes                  |
| ----------------------- | ------- | ---------------------- |
| ML-DSA-65 Sign          | ~50 us  | Post-quantum signature |
| ML-DSA-65 Verify        | ~30 us  | Verification           |
| BFT Consensus (4 nodes) | <100 ms | Agreement latency      |
| Evidence Bundle         | <10 ms  | Full audit package     |
| PyO3 FFI Overhead       | <1 us   | Rust-Python bridge     |

*Benchmarks on Apple M2. See docs/BENCHMARKS.md for details.*

---

## Documentation

| Document                                                    | Description                                    |
| ----------------------------------------------------------- | ---------------------------------------------- |
| Installation Guide                  | Detailed platform instructions                 |
| Architecture                        | System design deep dive                        |
| [Whitepaper](docs/WHITEPAPER.md)                            | Academic foundations                           |
| Technical Spec                    | Protocol details                               |
| API/SDK Reference                        | Developer API documentation                    |
| Tutorials                                 | Step-by-step guides                            |
| Ops Readiness Runbook | Deterministic startup/health/diagnostics gates |
| Glossary                                | Terminology reference                          |

---

## Project Status

> **research prototype**: System Prototype Demonstrated
> Hardware security integration complete (TPM 2.0 + Apple Secure Enclave).
> APIs may change before 1.0 stable release.

| Component             | Status    | Notes                                     |
| --------------------- | --------- | ----------------------------------------- |
| Rust Crypto Core      | ✅ Stable  | ML-DSA-65, ML-KEM-768, BFT, ZK            |
| Python Kernel         | ✅ Stable  | 28 subsystems, 334 tests                  |
| Test Suite            | ✅ 100%    | 143 Rust + 334 Python tests (2026-02-12)  |
| BFT Consensus         | ✅ Stable  | Multi-node with delta sync                |
| Zero-Knowledge Proofs | ✅ Stable  | Groth16 (BLS12-381) + Python bindings     |
| Governance Engine     | ✅ Stable  | ZK-SNARK verified decisions               |
| WASM Support          | ✅ Stable  | 31KB binary, wasm-bindgen bindings        |
| Virtual HSM (vHSM)    | ✅ Stable  | Software HSM, production-ready            |
| TPM 2.0 Integration   | ✅ Working  | GCE vTPM tested, PCR read verified        |
| Secure Enclave (SEP)  | ✅ Working  | Apple Silicon M-series, ECDSA P-256    |
| RISC-V (VisionFive 2) | ✅ Working  | JH7110 TRNG verified, 239 tests passed    |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=warm_logic

# Format code
make format
```

---

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md) for responsible disclosure.

---

## Community

- [GitHub Discussions](https://github.com/espressolee/warmlogic-rust-core-artifact/discussions)
- [Issue Tracker](https://github.com/espressolee/warmlogic-rust-core-artifact/issues)

---

## License

Apache License 2.0 — see the LICENSE file at the repository root.

---

## Acknowledgments

WarmLogic builds on:
- [ML-DSA (FIPS 204)](https://csrc.nist.gov/pubs/fips/204/final) - NIST Post-Quantum Standard
- [PyO3](https://pyo3.rs/) - Rust-Python bindings
- [Sled](https://sled.rs/) - Embedded database
- The broader open-source cryptography community

---

*Built by espressolee.*
