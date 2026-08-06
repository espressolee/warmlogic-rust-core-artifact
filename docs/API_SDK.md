# Sovereign SDK API Reference

> **Status**: Experimental
> **Warning**: This API may change without notice. Do not use in production.

The `warm_logic.sdk` package provides high-level abstractions for interacting with the WarmLogic governance kernel.

---

## `SovereignClient`

The main entry point for applications.

### Constructor

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient(endpoint: str | None = None)
```

**Parameters:**
- `endpoint`: Optional kernel endpoint URL. If `None`, uses local kernel.

**Note:** A `UserWarning` is raised on instantiation to remind developers of experimental status.

---

### `propose_action(intent, context, *, require_proof=False) -> Decision`

Proposes an action to the governance kernel for evaluation.

```python
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com", "subject": "Hello"},
    require_proof=False
)
```

**Parameters:**
- `intent` (str): The action intent (e.g., `"send_email"`, `"execute_trade"`)
- `context` (dict | None): Additional context for the decision
- `require_proof` (bool): If `True`, requires cryptographic proof (needs Rust core)

**Returns:** `Decision` object

**Raises:** `RuntimeError` if `require_proof=True` but Rust core is not available

---

### `health_check() -> dict`

Returns the health status of the kernel connection.

```python
status = client.health_check()
# {'status': 'ok', 'endpoint': 'local', 'rust_core': True, ...}
```

---

## `Decision`

Represents a governance decision from the kernel.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `verdict` | str | `"ALLOW"`, `"DENY"`, or `"PENDING"` |
| `reason` | str | Human-readable explanation |
| `proof_hash` | str | Deterministic hash for audit trail |
| `timestamp` | datetime | UTC timestamp of decision |
| `metadata` | dict | Additional metadata |
| `allowed` | bool | `True` if verdict is `"ALLOW"` |
| `denied` | bool | `True` if verdict is `"DENY"` |

### Example

```python
if decision.allowed:
    execute_action()
else:
    log_rejection(decision.reason)
```

---

## Complete Example

```python
from warm_logic.sdk import SovereignClient

# Initialize client
client = SovereignClient()

# Check health
print(client.health_check())

# Propose an action
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com", "subject": "Hello"}
)

print(f"Verdict: {decision.verdict}")
print(f"Reason: {decision.reason}")
print(f"Proof Hash: {decision.proof_hash}")

if decision.allowed:
    print("Action approved!")
```

---

## Limitations

| Feature | Status |
|---------|--------|
| Python-only policy evaluation | Active (fallback) |
| Rust cryptographic core | Optional |
| ZK proof generation | Requires Rust core |
| BFT consensus | Not available (single-node) |
| Production hardening | Not ready |

---

## Future API (Planned)

The following features are planned for v1.0.0:

- `SovereignIdentity`: PQC key management (ML-DSA-65)
- `SovereignSession`: Session-aware nonce generation
- `get_truth(state_key)`: Verified ledger state with ZK proofs
- Multi-node BFT consensus

See DEVELOPMENT_ROADMAP.md for timeline.
