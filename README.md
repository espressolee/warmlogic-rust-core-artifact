# WarmLogic

> A **single-host research prototype** of a post-quantum signing and
> governance kernel: real ML-DSA-65 (FIPS 204) signatures, real AES-256-GCM,
> in-process BFT, and a Python governance layer.
>
> **`espressolee/warmlogic-rust-core-artifact`** — Sanitized, versioned Rust
> research artifact for bounded post-quantum signing and governance
> experiments; **not the current WarmLogic canonical.**
>
> **Read first:** [STATUS.md](STATUS.md) (what this is / is not) · [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) · [docs/CLAIM_EVIDENCE.md](docs/CLAIM_EVIDENCE.md) (per-claim grades) · [PUBLIC_PROVENANCE.json](PUBLIC_PROVENANCE.json) · [SBOM.json](SBOM.json)
>
> Every capability claim is graded against re-runnable evidence in
> **[docs/CLAIM_EVIDENCE.md](docs/CLAIM_EVIDENCE.md)** — read that before
> trusting anything below. Coverage is 6.76%; there has been no independent
> security review.

[![Version](https://img.shields.io/badge/version-1.1.0-blue)](rust_core/Cargo.toml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://python.org)
[![Rust](https://img.shields.io/badge/rust-1.85+-orange)](https://rust-lang.org)

---

## Why WarmLogic?

AI agents are "black boxes". You can't prove **why** they did something, or **if** they followed the rules.

WarmLogic **explores** whether wrapping AI reasoning in a cryptographic kernel
can produce durable evidence about decisions. It does not solve the problem
above, and this artifact does not demonstrate that it does.

A note on what a signature can and cannot do, since the earlier wording blurred
it: a signature can show that a particular key signed particular bytes and that
the record was not altered afterwards. It cannot show *why* a decision was
made, that the stated reasoning was the actual reasoning, that a policy was
semantically obeyed, or that the decision was correct. Authenticity is not
justification.

| Intended design | Status **in this artifact** |
| --- | --- |
| Sign every decision with ML-DSA-65 | The ML-DSA-65 primitive is real (`fips204`) and its roundtrip runs. Decisions are **not** signed end-to-end: the SDK signing path is unreachable. |
| BFT consensus across a node swarm | Single host only. 34 in-process unit tests; **no multi-node deployment has ever been run.** |
| Zero-knowledge proofs for compliance | **Does not build** — `cargo check --features zk` fails. Off in default builds and in the wheel. |
| Signed policy documents checked at runtime | **Demonstration stub** — amendment checks that a signature string is non-empty; no cryptographic verification. |
| Local-first data ownership | Runs locally. No sovereignty property is verified.|

The right-hand column is the claim. The left-hand column is not.

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
- **PyO3 Bridge**: native-speed crypto operations from Python (see docs/BENCHMARKS.md for measured numbers)

---

## Core Features

Status column uses the grades from [docs/CLAIM_EVIDENCE.md](docs/CLAIM_EVIDENCE.md).
Read that file before relying on any row here.

| Feature | Description | Status |
| --- | --- | --- |
| **Post-Quantum Signatures** | ML-DSA-65 (FIPS 204), via the `fips204` crate | verified in CI |
| **Authenticated Encryption** | AES-256-GCM | tested locally |
| **Post-Quantum KEM** | ML-KEM-768 (FIPS 203), via `fips203` | tested locally |
| **Noise Protocol Framework** | Hybrid PQC key exchange | tested locally |
| **BFT Consensus** | Byzantine fault-tolerant agreement | **single host only** — 34 unit tests in-process; no multi-node deployment has ever been run |
| **Conviction Voting** | Time-weighted governance multipliers | tested locally |
| **Constitutional Governance** | Signed policy document checked at runtime | **demonstration stub** — signature/ZK verification is not implemented; see constitution.py |
| **Evidence Bundles** | Audit records for decisions | tested locally |
| **Local-First** | No external service is required to run | by construction |
| **Swarm Mesh / DHT** | Kademlia with iterative lookup | tested locally; the Python `RustDHT` binding is **not exported** |
| **Federation** | Cross-cluster node communication | single host only |
| **Zero-Knowledge Proofs** | arkworks Groth16 code exists | **does not build** — `cargo check --features zk` fails; off in default builds and the wheel |
| **Formal Verification** | Kani harnesses and TLA+ files exist | **not run** — no CI executes `cargo kani`; the TLA+ files are design documents, not checked models |
| **Neural Mesh / Federated Learning** | Adaptive routing, distributed training | experimental; not covered by the CI test surface |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Rust 1.85+
- macOS, Linux, or Docker

### Installation (3 Lines)

```bash
git clone https://github.com/espressolee/warmlogic-rust-core-artifact
cd warmlogic-rust-core-artifact
make setup
```

This installs dependencies, compiles the Rust core, and checks that the
extension imports. It does not verify system integrity in any security sense.

### Run it

```bash
# The console script is `wlctl` (there is no `warmlogic` command)
wlctl --help

# Or the web dashboard
python -m warm_logic.ui.server
```

The supported, CI-exercised surface is narrower than either of those. If you
only want the part that is actually verified, run the core path directly:

```bash
bash scripts/ci_core.sh
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

print(f"Decision: {decision.verdict}")     # ALLOW / DENY
print(f"Proof Hash: {decision.proof_hash}")

# NOTE: signing is opt-in (propose_action(..., require_signature=True)) and
# currently unreachable through the hardened bridge -- the Rust MoralGateway is
# deliberately left unregistered because it is a fail-open stub. On the default
# path `decision.signature` is None. See docs/CLAIM_EVIDENCE.md.
# ML-DSA-65 signing itself is real and works directly:
#     import warm_logic_rs as rs
#     pk, sk = rs.generate_keypair()
```

---

## Benchmarks

| Metric                  | Value   | Notes                  |
| ----------------------- | ------- | ---------------------- |
| ML-DSA-65 Sign          | ~50 us  | Post-quantum signature |
| ML-DSA-65 Verify        | ~30 us  | Verification           |
| Evidence Bundle         | <10 ms  | Full audit package     |
| PyO3 FFI Overhead       | <1 us   | Rust-Python bridge     |

*Indicative local measurements on one Apple M2 host, not a benchmarked claim: no
multi-node figures are given because no multi-node deployment has been run.
See [docs/BENCHMARKS.md](docs/BENCHMARKS.md).*

---

## Documentation

| Document                                                    | Description                                    |
| ----------------------------------------------------------- | ---------------------------------------------- |
| [Claim ↔ Evidence Ledger](docs/CLAIM_EVIDENCE.md)              | **Read first** — every claim graded against evidence |
| [Installation Guide](docs/INSTALLATION.md)                  | Detailed platform instructions                 |
| [Architecture](docs/ARCHITECTURE.md)                        | System design deep dive                        |
| [Whitepaper](docs/WHITEPAPER.md)                            | Academic foundations                           |
| [Technical Spec](docs/TECHNICAL_SPEC.md)                    | Protocol details                               |
| [API/SDK Reference](docs/API_SDK.md)                        | Developer API documentation                    |
| [Tutorials](docs/tutorial/)                                 | Step-by-step guides                            |
| [Ops Readiness Runbook](docs/runbooks/ops-readiness-100.md) | Deterministic startup/health/diagnostics gates |
| [CI Evidence Gates Runbook](docs/runbooks/ci-evidence-gates.md) | CI artifact evidence generation/verification |
| [Glossary](docs/GLOSSARY.md)                                | Terminology reference                          |

---

## Docker Deployment

> **UNVERIFIED CONFIGURATION.** The compose file below exists in the tree, but
> a multi-node mesh has **never been deployed or exercised** — not locally, not
> in CI, not by anyone. The commands are recorded as historical intent. Do not
> read them as a supported or tested path, and do not report success from them
> as evidence that BFT consensus works across hosts.

```bash
# Build and start multi-node cluster
docker compose -f deploy/docker/docker-compose.multinode.yaml up -d

# Check node health
curl http://localhost:8000/health  # Node 0 (Seed)
curl http://localhost:8001/health  # Node 1 (Mesh)
curl http://localhost:8002/health  # Node 2 (Mesh)

# View Prometheus metrics
curl http://localhost:8000/metrics

# Stop cluster
docker compose -f deploy/docker/docker-compose.multinode.yaml down
```

| Port  | Service             | Description           |
|-------|---------------------|-----------------------|
| 8000  | REST API (Node 0)   | Seed node gateway     |
| 8001  | REST API (Node 1)   | Mesh node gateway     |
| 8002  | REST API (Node 2)   | Mesh node gateway     |
| 9000  | UDP P2P (Node 0)    | Kademlia DHT          |
| 9090  | Prometheus (Node 0) | Metrics endpoint      |

**API Authentication**: All `/api/v1/*` endpoints require `X-API-Key` header. Set `WARMLOGIC_API_KEY` environment variable.

---

## Project Status

A second status table used to live here, marking almost everything
"Implemented" — including the ZK feature (which does not build), the Kani
harnesses (which no CI runs) and multi-node BFT (never deployed). It is
removed rather than corrected in place: one honest status source is better
than two that disagree.

Per-claim grades live in [docs/CLAIM_EVIDENCE.md](docs/CLAIM_EVIDENCE.md);
the shortest summary is in [STATUS.md](STATUS.md) and the gaps are listed in
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

---

## Validation Snapshot

**Measured 2026-08-06 on the published tree:**

| Check | Result |
|---|---|
| CI-exercised Python subset (`tests/ci`, `tests/docs`) | 57 passed |
| Clean-checkout build + sanity (`scripts/ci_core.sh`) | passed (ML-DSA-65 sign/verify roundtrip) |
| Rust library, `--features python` | builds, 0 errors |
| Full Python collection | 3,051 tests collected, **22 modules fail to collect** |
| Full strict suite | **not green** — the collection errors above, plus hardware-attestation tests that fail without a TPM |
| Line coverage | **6.76%** (1,226 / 18,145) |

An earlier snapshot in this README reported "3151 passed" for the full strict
suite with live E2E enabled, dated 2026-02-14. That measurement does not
reproduce on this tree and has been replaced rather than kept as decoration.

```bash
# Full strict run (default)
pytest -n auto -q -W error -ra

# Full strict run with live E2E prerequisites enabled
WARM_RUN_MESH_E2E=1 WARM_UI_BASE_URL=http://127.0.0.1:8011 pytest -n auto -q -W error -ra
```


---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Format code
make format

# Run linters
make lint
```

---

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md) for responsible disclosure.

---

## Community

- [GitHub Discussions](https://github.com/espressolee/WarmLogic/discussions)
- [Issue Tracker](https://github.com/espressolee/WarmLogic/issues)

---

## License

Apache License 2.0 (see [LICENSE](LICENSE)).

---

## Acknowledgments

WarmLogic builds on:
- [ML-DSA (FIPS 204)](https://csrc.nist.gov/pubs/fips/204/final) - NIST Post-Quantum Digital Signature Standard
- [ML-KEM (FIPS 203)](https://csrc.nist.gov/pubs/fips/203/final) - NIST Post-Quantum Key Encapsulation
- [Noise Protocol Framework](https://noiseprotocol.org/) - Cryptographic handshake patterns
- [Kani Model Checker](https://model-checking.github.io/kani/) - Rust formal verification
- [PyO3](https://pyo3.rs/) - Rust-Python bindings
- [redb](https://github.com/cberner/redb) - ACID-compliant embedded database
- [curve25519-dalek](https://github.com/dalek-cryptography/curve25519-dalek) - Ristretto255 elliptic curve
- The broader open-source cryptography community

---

*Built by espressolee.*
