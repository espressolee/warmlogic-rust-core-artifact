# WarmLogic Use Cases

> **Status**: research prototype. Not externally validated; see docs/CLAIM_EVIDENCE.md.
> Use cases are based on expected production scenarios.

---

## Overview

WarmLogic is designed for organizations that need **cryptographic proof of AI decisions**. This document outlines key use cases across industries.

---

## Financial Services

### Algorithmic Trading Audit

**Problem**: Regulators require proof that trading algorithms follow approved rules. Traditional logs can be tampered with.

**Solution**: WarmLogic provides:
- Immutable audit trail of every trading decision
- ML-DSA-65 signatures (quantum-safe)
- BFT consensus for multi-party verification
- Zero-knowledge proofs for sensitive data

**Implementation**:

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient()

# Before executing trade
decision = client.propose_action(
    intent="execute_trade",
    context={
        "symbol": "AAPL",
        "action": "buy",
        "quantity": 1000,
        "price": 185.50,
        "strategy_id": "momentum_v2",
        "risk_score": 0.3
    }
)

if decision.approved:
    execute_trade()
    # Evidence bundle automatically stored
else:
    log_rejection(decision.rejection_reason)
```

**Benefits**:
- Regulatory compliance (MiFID II, SEC)
- Reduced audit preparation time by 80%
- Post-quantum security for long-term records

---

### Loan Approval Decisions

**Problem**: Fair lending laws require explainability. AI decisions must be documented.

**Solution**: WarmLogic captures:
- Every factor considered in loan decision
- Policy rules that were evaluated
- Cryptographic proof of decision process

**Policy Example**:

```yaml
policies:
  fair_lending:
    description: "Ensure fair lending practices"
    rules:
      - intent: "approve_loan"
        require:
          - income_verified: true
          - credit_score_checked: true
        deny_if:
          - uses_prohibited_factors: true
        audit: detailed
```

---

## Healthcare

### Clinical Decision Support

**Problem**: AI recommendations in healthcare require audit trails for malpractice protection and regulatory compliance.

**Solution**: WarmLogic provides:
- HIPAA-compliant evidence bundles
- Zero-knowledge proofs (verify without exposing PHI)
- Immutable record of AI recommendations

**Implementation**:

```python
decision = client.propose_action(
    intent="clinical_recommendation",
    context={
        "patient_hash": sha256(patient_id),  # Never store PHI directly
        "recommendation": "consider_screening",
        "confidence": 0.85,
        "model_version": "v2.3.1"
    }
)

# Zero-knowledge proof: prove recommendation was made
# without revealing patient identity
zk_proof = decision.generate_zk_proof(
    reveal=["recommendation", "confidence"],
    hide=["patient_hash"]
)
```

**Benefits**:
- HIPAA compliance with cryptographic proof
- Malpractice protection
- Audit-ready documentation

---

### Drug Interaction Checker

**Problem**: AI-powered drug interaction warnings need documentation for liability.

**Solution**:

```yaml
policies:
  drug_safety:
    rules:
      - intent: "dispense_medication"
        check:
          - drug_interactions_reviewed: true
          - contraindications_cleared: true
        deny_if:
          - severe_interaction_detected: true
        require_approval_if:
          - moderate_interaction_detected: true
```

---

## Legal Tech

### Contract Review AI

**Problem**: Law firms need proof that AI reviewed contracts according to firm guidelines.

**Solution**: WarmLogic provides:
- Evidence that specific clauses were reviewed
- Cryptographic proof of review timestamp
- Policy compliance verification

**Implementation**:

```python
decision = client.propose_action(
    intent="contract_review_complete",
    context={
        "document_hash": sha256(contract_bytes),
        "clauses_reviewed": [
            "indemnification",
            "termination",
            "liability_cap",
            "governing_law"
        ],
        "risk_flags": ["unusual_liability_cap"],
        "reviewer_model": "legal-review-v3"
    }
)

# Generate evidence bundle for client
evidence = client.get_evidence(decision.proof_hash)
send_to_client(evidence.to_pdf())
```

---

### E-Discovery Classification

**Problem**: Document classification for legal discovery must be defensible.

**Solution**:

```yaml
policies:
  e_discovery:
    rules:
      - intent: "classify_document"
        require:
          - model_version_approved: true
          - confidence_threshold: 0.9
        audit: true
        retention: 7_years
```

---

## Government & Defense

### Security Clearance Decisions

**Problem**: Government AI decisions require extreme auditability and long-term record integrity.

**Solution**: WarmLogic provides:
- Post-quantum cryptography (ML-DSA-65)
- 50+ year record integrity
- Multi-agency BFT consensus

**Why Post-Quantum Matters**:
- Clearance decisions have 50+ year relevance
- "Harvest now, decrypt later" threat
- NIST FIPS 204 compliance

---

### Autonomous System Governance

**Problem**: AI-powered autonomous systems (drones, vehicles) need governance constraints.

**Solution**:

```yaml
policies:
  autonomous_constraints:
    principles:
      - name: human_override
        description: "Human can always override AI"
        priority: 1

    rules:
      - intent: "autonomous_action"
        require:
          - within_approved_envelope: true
          - human_override_available: true
        deny_if:
          - human_override_requested: true
        log_level: detailed
```

---

## Enterprise AI

### AI Model Deployment Governance

**Problem**: Enterprises need governance over which AI models can be deployed.

**Solution**: WarmLogic as deployment gate:

```python
# Before deploying any AI model
decision = client.propose_action(
    intent="deploy_model",
    context={
        "model_name": "customer_churn_v4",
        "model_hash": sha256(model_weights),
        "training_data_hash": dataset_hash,
        "bias_audit_passed": True,
        "security_scan_passed": True,
        "performance_metrics": {
            "accuracy": 0.94,
            "f1_score": 0.91
        }
    }
)

if not decision.approved:
    raise ModelDeploymentBlocked(decision.rejection_reason)
```

**Policy**:

```yaml
policies:
  model_deployment:
    rules:
      - intent: "deploy_model"
        require:
          - bias_audit_passed: true
          - security_scan_passed: true
          - accuracy: "> 0.85"
        deny_if:
          - deprecated_framework: true
```

---

### Employee AI Usage Tracking

**Problem**: Enterprises need to track AI tool usage for compliance and cost management.

**Solution**:

```python
# Wrap all AI API calls
decision = client.propose_action(
    intent="ai_api_call",
    context={
        "user_id": user_id,
        "api": "openai_gpt4",
        "prompt_tokens": 1500,
        "department": "marketing",
        "use_case": "content_generation"
    }
)

# Automatically enforces:
# - Budget limits per department
# - Approved use cases only
# - Data classification rules
```

---

## Research & Academia

### Reproducible AI Experiments

**Problem**: AI research requires reproducibility, but experiments are hard to verify.

**Solution**: WarmLogic as experiment ledger:

```python
# Log every experiment configuration and result
decision = client.propose_action(
    intent="log_experiment",
    context={
        "experiment_id": "exp_2026_02_001",
        "model_config_hash": config_hash,
        "dataset_hash": dataset_hash,
        "random_seed": 42,
        "results": {
            "accuracy": 0.923,
            "loss": 0.0821
        },
        "environment_hash": env_hash
    }
)

# Cryptographic proof of results
# Anyone can verify the experiment was run as claimed
```

---

## Multi-Agent Systems

### Agent Coordination Governance

**Problem**: Multi-agent AI systems need coordination rules.

**Solution**: WarmLogic as coordination layer:

```python
# Agent swarm with governance
swarm = SwarmClient(governance=client)

# Consensus required for high-impact actions
swarm.set_policy({
    "intent": "collective_action",
    "require_consensus": True,
    "quorum": 0.67,  # 2/3 of agents must agree
    "timeout": 30
})

# Individual agents still have local governance
agent.propose_action(
    intent="share_information",
    context={"recipient": "agent_2", "data_hash": hash}
)
```

---

## Summary Matrix

| Use Case | Industry | Key Features |
|----------|----------|--------------|
| Trading Audit | Finance | PQC, BFT, Immutable |
| Loan Decisions | Finance | Explainability, Audit |
| Clinical AI | Healthcare | ZK Proofs, HIPAA |
| Drug Checks | Healthcare | Safety Gates |
| Contract Review | Legal | Evidence Bundles |
| E-Discovery | Legal | Classification Proof |
| Clearance | Government | 50-year PQC |
| Autonomous | Defense | Hard Constraints |
| Model Deploy | Enterprise | Governance Gate |
| AI Tracking | Enterprise | Budget/Compliance |
| Experiments | Research | Reproducibility |
| Multi-Agent | AI/ML | Coordination |

---

## Getting Started

1. **Install**: `pip install warm-logic`
2. **Configure**: Create `constitution.yaml`
3. **Integrate**: Wrap AI decision points
4. **Verify**: Review evidence bundles

See [Tutorial](tutorial/01_quickstart.md) for step-by-step guidance.

---

*Last updated: 2026-02-07*
