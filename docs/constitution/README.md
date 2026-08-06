# The Sovereign Constitution (Law of Physics)

> **"Code is Law" is a metaphor. "TLA+ is Proof" is reality.**

This directory contains the **Formal Specifications** of the WarmLogic Operating System. 
Unlike the Python implementation (which may contain bugs), these specifications define the **Mathematical Truths** that the system must satisfy.

## Invariants

### 1. Methodological Integrity (`core_invariants.tla`)
**Definition**: `(execution_state = "RUNNING") => Trusted(Artifact)`
**Meaning**: The system **physically cannot** execute a model or dataset that does not have a mathematically valid lineage tracing back to a Trusted Root.
**Enforcement**: The GVM (Governance Virtual Machine) implements this logic at the runtime level.

### 2. Ledger Immutability
**Definition**: `Len(ledger') >= Len(ledger)`
**Meaning**: The Refusal Spine is append-only. History can never be rewritten.

## Verification
To verify these invariants against the Python implementation, we use:
1.  **Model Checking**: Running the TLA+ model checker (TLC).
2.  **Runtime Monitors**: The GVM checks these conditions at every state transition.
3.  **Forensic Replay**: Re-deriving the proof from the audit trail.
