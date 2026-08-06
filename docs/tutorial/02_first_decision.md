# Making Your First Governance Decision (Tutorial 2 of 4)

> **research prototype Notice**: WarmLogic is at research prototype status
> (System Prototype Demonstration). APIs may change before 1.0 stable release.

> **Time**: 10 minutes
> **Difficulty**: Intermediate
> **Prerequisites**: [01_quickstart.md](01_quickstart.md) completed

---

## Objective

Learn how to record AI agent decisions with PQC signatures using the WarmLogic SDK.

---

## 1. Initialize the SDK

```python
from warm_logic.sdk import SovereignClient

# Preferred: explicit endpoint
client = SovereignClient(endpoint="http://localhost:8000")

# Compatibility mode (still supported)
# client = SovereignClient(host="localhost", port=8000, timeout=60)

# Verify connection
if client.is_connected():
    print("Kernel connection successful")
else:
    print("Kernel connection failed - verify server is running")
```

---

## 2. Propose Your First Decision

```python
# Propose an email sending intent
decision = client.propose_action(
    intent="send_email",
    context={
        "to": "user@example.com",
        "subject": "Meeting Notice",
        "reason": "Weekly meeting reminder"
    }
)

# Check result
print(f"Decision: {decision.verdict}")          # ALLOW / DENY / PENDING
print(f"Proof Hash: {decision.proof_hash}")     # PQC-signed hash
print(f"Timestamp: {decision.timestamp}")
```

---

## 3. Review the Evidence Bundle

Every approved decision generates an **Evidence Bundle**:

```python
if decision.allowed:
    print("Allowed by governance policy")
    print(f"Reason: {decision.reason}")
    print(f"Proof: {decision.proof_hash}")
```

---

## 4. Handling Rejected Decisions

Requests that violate policies are rejected:

```python
# Attempt a sensitive operation
blocked = client.propose_action(
    intent="delete_database",
    context={"table": "users"}
)

if blocked.denied:
    print(f"Rejected: {blocked.reason}")
    print(f"Verdict: {blocked.verdict}")
```

---

## 5. Modifying Policies

Default policies are defined in `config/constitution.yaml`:

```yaml
# config/constitution.yaml
veto_rules:
  - name: "Block Data Deletion"
    pattern: "delete_*"
    action: BLOCK
    reason: "Data deletion requires manual approval"

permitted_actions:
  - send_email
  - read_document
  - generate_report
```

Restart the kernel after policy changes:

```bash
# Reload policies
wlctl stop && wlctl start
```

---

## Next Steps

- [03_identity_management.md](03_identity_management.md) - Node identity management
- [GLOSSARY.md](../GLOSSARY.md) - Terminology reference
