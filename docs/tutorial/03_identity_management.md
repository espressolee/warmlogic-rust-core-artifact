# Identity Management (Tutorial 3 of 4)

> **research prototype Notice**: WarmLogic is at research prototype status
> (System Prototype Demonstration). APIs may change before 1.0 stable release.

> **Time**: 15 minutes
> **Difficulty**: Intermediate
> **Prerequisites**: [01_quickstart.md](01_quickstart.md) completed

---

## Overview

In WarmLogic, **Identity** is the cryptographic credential that uniquely identifies a node.
All identities are protected by **ML-DSA-65 (FIPS 204)** post-quantum signatures.

---

## 1. Creating a New Identity

### Using CLI

```bash
# Initialize new identity
wlctl init

# Example output:
# Identity created: 87d50cb96fcedf73...
#    Stored in: .warm_logic/identity.json
```

### Using Python

```python
from warm_logic.kernel.identity.kinetic_id import KineticIdentity
import hashlib

# Generate keypair (ML-DSA-65)
public_key, private_key = KineticIdentity.generate_keypair()

# Compute Node ID (SHA256 of public key)
pub_bytes = bytes.fromhex(public_key)
node_id = hashlib.sha256(pub_bytes).hexdigest()

print(f"Node ID: {node_id[:32]}...")
print(f"Public Key: {public_key[:64]}...")
```

---

## 2. Verifying Identity

```bash
# Display current identity
wlctl identity

# Display full keys
wlctl identity --full
```

In Python:

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient()
identity = client.get_identity()

print(f"Node ID: {identity.node_id}")
print(f"Public Key: {identity.public_key}")
print(f"Era: {identity.era}")
```

---

## 3. Backing Up Identity

> **Important**: If you lose your private key, you cannot recover your node identity.

### Secure Backup

```bash
# Copy identity file (to secure storage)
cp .warm_logic/identity.json /secure/backup/warmlogic_identity.json.bak

# Or encrypted backup
tar -cz .warm_logic/ | gpg -c > warmlogic_identity.tar.gz.gpg
```

---

## 4. Restoring Identity

```bash
# Restore from backup
cp /secure/backup/warmlogic_identity.json.bak .warm_logic/identity.json

# Verify
wlctl identity
```

---

## 5. Multi-Node Environment

When operating multiple nodes in a Swarm:

```bash
# Node 1 (port 4001)
WARM_LOGIC_ROOT=./node1 wlctl init
WARM_LOGIC_ROOT=./node1 wlctl start --port 4001

# Node 2 (port 4002)
WARM_LOGIC_ROOT=./node2 wlctl init
WARM_LOGIC_ROOT=./node2 wlctl start --port 4002
```

Connecting nodes:

```python
# Node 2 bootstraps to Node 1
from warm_logic.kernel.mesh.dht import SovereignDHT

dht = SovereignDHT(node_id, "127.0.0.1", 4002)
await dht.start()
await dht.bootstrap([("127.0.0.1", 4001)])
```

---

## Security Considerations

| Item             | Recommendation                      |
| ---------------- | ----------------------------------- |
| Private Key Storage | Encrypted volume or HSM          |
| Backup Frequency | Immediately after creation + periodic |
| Network Exposure | Restrict DHT port with firewall    |
| Key Rotation     | Not currently supported (planned for ) |

---

## Next Steps

- [04_building_sovereign_apps.md](04_building_sovereign_apps.md) - Building sovereign applications
- [GLOSSARY.md](../GLOSSARY.md) - "Kinetic Identity", "Sovereign" definitions
- OPERATOR_HANDBOOK.md - Operator guide
