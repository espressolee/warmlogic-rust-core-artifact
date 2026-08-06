# WarmLogic Quickstart Guide

## Prerequisites

- Python 3.9+
- Rust 1.75+ (for building from source)
- Git

## Installation

### Option 1: From PyPI (Recommended)

```bash
pip install warm-logic
```

### Option 2: From Source

```bash
# Clone repository
git clone https://github.com/espressolee/WarmLogic.git
cd warmlogic

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Build Rust core
cd rust_core && maturin develop --release && cd ..

# Verify installation
python -c "import warm_logic_rs; print('Rust Core:', warm_logic_rs.__version__)"
```

## Quick Demo

### 1. Initialize Sovereign Identity

```python
from warm_logic.kernel.sys.cryptography import MLDSA

# Generate post-quantum keypair
keypair = MLDSA.generate_keypair()
print(f"Public Key: {keypair['public_key'][:32]}...")
print(f"Algorithm: ML-DSA-65 (FIPS 204)")
```

### 2. Create Governance Engine

```python
from warm_logic.kernel.ops.governance_engine import GovernanceEngine

# Initialize with default thresholds
engine = GovernanceEngine(tau_ethics=0.85, epsilon_c=0.1)

# Evaluate a decision
decision = engine.evaluate(context={"action": "deploy_update"})
print(f"Verdict: {decision.verdict}")
print(f"Confidence: {decision.confidence}")
```

### 3. Join DHT Mesh Network

```python
import asyncio
from warm_logic.kernel.mesh.dht import SovereignDHT

async def main():
    # Create DHT node
    dht = SovereignDHT(port=8468)
    await dht.start()

    # Bootstrap to network
    await dht.bootstrap([("seed.example.com", 8468)])

    print(f"Node ID: {dht.node_id.hex()}")
    print(f"Routing table size: {len(dht.routing)}")

asyncio.run(main())
```

### 4. BFT Consensus

```python
from warm_logic.kernel.sys.consensus import BFTEngine, Vote

# Create 4-validator BFT engine
engine = BFTEngine(total_validators=4)

# Propose a block
engine.propose("block_hash_abc123")

# Cast votes
for i in range(3):
    vote = Vote(
        block_hash="block_hash_abc123",
        voter_id=f"validator_{i}",
        signature=f"sig_{i}"
    )
    if engine.cast_vote(vote):
        print("Consensus reached!")
```

## Configuration

### Environment Variables

```bash
# Core settings
export WL_NODE_ID="your-node-id"
export WL_DATA_DIR="./sovereign_db"

# Network settings
export WL_BOOTSTRAP_NODES="seed1.example.com:8468,seed2.example.com:8468"
export WL_LISTEN_PORT=8468

# Security settings
export WL_REALITY_ENFORCEMENT=true
export WL_REQUIRE_HARDWARE_ATTESTATION=false
```

### Policy Configuration

Create `config/governance_policy.yaml`:

```yaml
governance:
  tau_ethics_threshold: 0.85
  epsilon_c_max: 0.15
  veto_threshold: 0.90
  grace_period_ticks: 100

consensus:
  quorum_ratio: 0.67
  min_validators: 3
  timeout_ms: 5000

mesh:
  k_bucket_size: 20
  alpha_concurrency: 3
  refresh_interval_s: 3600
```

## Running Tests

```bash
# All tests
pytest tests/

# Fast tests only
pytest tests/ -m "not slow"

# With coverage
pytest tests/ --cov=src/warm_logic --cov-report=html
```

## Troubleshooting

### Rust Core Not Found

```bash
# Rebuild Rust core
cd rust_core && maturin develop --release

# Verify
python -c "import warm_logic_rs; print(dir(warm_logic_rs))"
```

### Hardware Attestation Failure

If running in a virtual environment without TPM:

```bash
export WL_REQUIRE_HARDWARE_ATTESTATION=false
```

### DHT Bootstrap Timeout

Check network connectivity and firewall settings:

```bash
# Test connectivity
nc -zv seed.example.com 8468
```

## Next Steps

- [Architecture Guide](./ARCHITECTURE.md)
- [Security Model](./SECURITY.md)
- [API Reference](./API_SDK.md)
- [Whitepaper](./WHITEPAPER.md)

## Support

- GitHub Issues: https://github.com/espressolee/WarmLogic/issues
- Documentation: https://github.com/espressolee/WarmLogic/tree/main/docs
