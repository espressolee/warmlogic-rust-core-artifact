# Building Sovereign Apps with WarmLogic SDK (Tutorial 4 of 4)

> **research prototype Notice**: WarmLogic is at research prototype status
> (System Prototype Demonstration). APIs may change before 1.0 stable release.

> **Time**: 20 minutes
> **Difficulty**: Intermediate
> **Prerequisites**: Tutorials 1-3 completed

Welcome to This tutorial will show you how to build a decentralized, PQC-secured application using the WarmLogic Sovereign SDK.

---

## 1. Installation

Ensure you have WarmLogic installed:

```bash
pip install .
```

---

## 2. Your First Sovereign Client

The `SovereignClient` is your gateway to the mesh. It manages your **Kinetic ID** (Quantum-Resistant Identity) and talks to the BFT swarm.

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient()
print(f"Connected with Identity: {client.identity.id}")
```

---

## 3. Proposing a Task

In WarmLogic, you don't just "write to a database." You **propose an action** to the collective. If it passes the constitutional audit and reaches BFT quorum, it becomes "Truth."

```python
result = client.submit_proposal(
    action="VOTE_FOR_UPGRADE",
    params={"version": "1.0.0"}
)

print(f"Proposal Status: {result['status']}")
print(f"PQC Signature: {result['signature']}")
```

---

## 4. Why This Matters

| Feature | Description |
|---------|-------------|
| **Constitutional Guardrails** | Every action is audited against the governance constitution |
| **Post-Quantum Security** | Your identity is secured by ML-DSA-65 (FIPS 204) |
| **BFT Consistency** | Actions only commit when the swarm agrees |

---

## 5. Advanced: Custom Policies

Create a custom policy for your application:

```yaml
# config/app_policy.yaml
name: "My Sovereign App"
version: "1.0.0"

rules:
  - name: "Rate Limit"
    condition: "requests_per_minute > 100"
    action: THROTTLE

  - name: "Require Multi-Sig"
    condition: "action.type == 'TRANSFER' && amount > 1000"
    action: REQUIRE_MULTISIG
    threshold: 2
```

Load the policy:

```python
client.load_policy("config/app_policy.yaml")
```

---

## 6. Connecting to the Mesh

Join an existing WarmLogic network:

```python
# Connect to bootstrap nodes
client.connect_to_mesh([
    "bootstrap1.github.com/espressolee/warmlogic-rust-core-artifact:4001",
    "bootstrap2.github.com/espressolee/warmlogic-rust-core-artifact:4001"
])

# Verify mesh status
peers = client.list_peers()
print(f"Connected to {len(peers)} peers")
```

---

## Next Steps

- [API_SDK.md](../API_SDK.md) - Full SDK API reference
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture deep dive
