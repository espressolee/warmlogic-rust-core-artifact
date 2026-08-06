# Frequently Asked Questions (FAQ)

> **Status**: research prototype. Not externally validated; see docs/CLAIM_EVIDENCE.md.
> APIs may change before 1.0 stable release.

---

## Table of Contents

1. [General](#general)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Architecture](#architecture)
5. [Security](#security)
6. [Performance](#performance)
7. [Troubleshooting](#troubleshooting)

---

## General

### What is WarmLogic?

WarmLogic is a cryptographic runtime for AI governance. It creates unforgeable evidence for every AI decision using:
- **Post-Quantum Cryptography** (ML-DSA-65)
- **Byzantine Fault Tolerant Consensus**
- **Zero-Knowledge Proofs**

### Why do I need this?

If you're building AI agents that make autonomous decisions, you need to:
1. **Prove** what decisions were made and why
2. **Enforce** governance policies that can't be bypassed
3. **Audit** every action with cryptographic evidence

WarmLogic provides this infrastructure.

### What's the difference between WarmLogic and traditional AI frameworks?

| Aspect | Traditional AI | WarmLogic |
|--------|----------------|-----------|
| Decision audit | Logs (mutable) | Cryptographic evidence (immutable) |
| Policy enforcement | Application layer | Constitutional kernel |
| Signature scheme | Classical (RSA/ECDSA) | Post-quantum (ML-DSA-65) |
| Consensus | None | BFT quorum |
| Privacy | None | Zero-knowledge proofs |

### What is research prototype?

research prototype status means "System Prototype Demonstration". The system works in a representative environment but is not yet production-ready. APIs may change before 1.0.

### Is WarmLogic open source?

Yes. The repository is licensed under Apache-2.0. See [LICENSE](../LICENSE).

---

## Installation

### What are the system requirements?

- **Python**: 3.12 or higher
- **Rust**: 1.75 or higher
- **RAM**: 4 GB minimum, 8 GB recommended
- **OS**: macOS 12+, Ubuntu 22.04+, Windows 11 (WSL2)

### Why does WarmLogic need Rust?

The cryptographic operations (ML-DSA-65, ZK proofs, BFT consensus) are implemented in Rust for:
- **Performance**: ~300x faster than pure Python
- **Memory safety**: No buffer overflows
- **Secure key handling**: Zeroize memory on drop

### Can I use Docker instead of native installation?

Yes. Docker is fully supported:

```bash
docker-compose up -d
```

### Why is compilation slow?

The Rust core (`rust_core`) compiles cryptographic primitives with optimizations. First build takes ~2-5 minutes. Subsequent builds are incremental and much faster.

### How do I upgrade?

```bash
git pull origin main
pip install -r requirements.txt --upgrade
cd rust_core && maturin develop --release
```

---

## Usage

### How do I make my first decision?

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient()
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com"}
)

print(f"Approved: {decision.approved}")
print(f"Proof: {decision.proof_hash}")
```

### What is an Evidence Bundle?

An Evidence Bundle is a cryptographic proof package containing:
- Hash of the decision
- Policy snapshot at decision time
- ML-DSA-65 signature
- BFT consensus attestation
- Optional ZK compliance proof

### How do I define policies?

Policies are defined in `config/constitution.yaml`:

```yaml
veto_rules:
  - name: "Block Deletions"
    pattern: "delete_*"
    action: BLOCK

permitted_actions:
  - send_email
  - read_document
```

### Can I bypass the governance kernel?

No. The constitutional invariants are enforced at the Rust layer. Even a compromised Python process cannot bypass them.

### How do I check the kernel status?

```bash
wlctl status
```

Or via Python:

```python
client = SovereignClient()
print(client.get_status())
```

---

## Architecture

### What is the "Hard Shell, Soft Brain" philosophy?

- **Hard Shell (Rust)**: Immutable cryptographic guarantees. Cannot be modified at runtime.
- **Soft Brain (Python)**: Flexible reasoning and policy evaluation. Can self-modify within constitutional bounds.

### What is the Rust-Python boundary?

The Rust core (`rust_core`) is compiled as a native Python module via PyO3. All cryptographic operations happen in Rust; governance logic lives in Python.

### How does BFT consensus work?

WarmLogic uses a simplified BFT protocol:
1. Proposer broadcasts decision
2. Nodes vote (sign with ML-DSA-65)
3. Quorum reached at `(2n/3) + 1` votes
4. Decision committed to ledger

### What is the ledger?

An append-only hash chain stored in Sled (embedded database). Each block references the previous block's hash, creating tamper-evident history.

### Is the hardware attestation real?

Currently simulated (vHSM). Real TPM/SEP integration is planned for future releases. Simulated keys are prefixed with `WARM-KEY-SIM-`.

---

## Security

### Is WarmLogic quantum-safe?

Yes. All signatures use ML-DSA-65 (FIPS 204), a NIST-standardized post-quantum algorithm. This protects against "harvest now, decrypt later" attacks.

### How are private keys protected?

- Stored in memory with `Zeroize` trait (cleared on drop)
- Never written to disk in plaintext
- Simulated keys are clearly marked

### Has WarmLogic been audited?

Not yet. See [THREAT_MODEL.md](THREAT_MODEL.md) for the pre-audit security analysis. Third-party audit is planned before 1.0.

### What attacks does WarmLogic defend against?

| Attack | Defense |
|--------|---------|
| Signature forgery | ML-DSA-65 (post-quantum) |
| Byzantine nodes | BFT consensus (f < n/3) |
| Ledger tampering | Hash chain + replication |
| Privacy leakage | Zero-knowledge proofs |
| Governance bypass | Constitutional kernel |

### What are the known limitations?

See [THREAT_MODEL.md](THREAT_MODEL.md) Section 6 for documented limitations:
- vHSM is simulated
- Single-bucket Kademlia
- ~60% test coverage
- No UC proof

---

## Performance

### How fast is signing?

ML-DSA-65 operations on Apple M2:
- **Keygen**: ~1 ms
- **Sign**: ~50 μs
- **Verify**: ~30 μs

### What's the throughput?

| Configuration | Decisions/sec |
|---------------|---------------|
| Single node | ~100 |
| 4-node swarm | ~10 |

BFT consensus is the bottleneck in multi-node deployments.

### How much storage does WarmLogic use?

- **Base installation**: ~500 MB
- **Per decision**: ~1 KB (evidence bundle)
- **Ledger growth**: Linear with decisions

---

## Troubleshooting

### `warm_logic_rs` import error

Rebuild the Rust core:

```bash
cd rust_core
maturin develop --release
```

### `maturin: command not found`

Install maturin:

```bash
pip install maturin
```

### Kernel won't start

Check if port 8000 is in use:

```bash
lsof -i :8000
```

### Tests failing

Ensure the Rust core is built:

```bash
cd rust_core && maturin develop --release && cd ..
pytest tests/ -v
```

### Where are logs?

Default location: `~/.warm_logic/logs/`

Or check with:

```bash
wlctl logs --tail 100
```

---

## Still Have Questions?

- [GitHub Discussions](https://github.com/espressolee/warmlogic-rust-core-artifact/discussions)
- [Issue Tracker](https://github.com/espressolee/warmlogic-rust-core-artifact/issues)
- [GLOSSARY.md](GLOSSARY.md) - Term definitions
