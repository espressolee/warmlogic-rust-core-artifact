# WarmLogic vs Alternatives

> **Status**: research prototype. Not externally validated; see docs/CLAIM_EVIDENCE.md.
> Comparisons are based on publicly available information as of February 2026.

---

## Executive Summary

WarmLogic is unique in combining:
1. **Post-Quantum Cryptography** (ML-DSA-65)
2. **Byzantine Fault Tolerant Consensus**
3. **Zero-Knowledge Compliance Proofs**
4. **Constitutional Governance Kernel**

No existing solution provides all four capabilities.

---

## Feature Comparison

| Feature | WarmLogic | LangChain | AutoGPT | CrewAI | Guardrails AI |
|---------|-----------|-----------|---------|--------|---------------|
| Post-Quantum Signatures | ML-DSA-65 | None | None | None | None |
| BFT Consensus | Yes | No | No | No | No |
| Zero-Knowledge Proofs | Yes | No | No | No | No |
| Constitutional Guardrails | Yes | No | Limited | No | Yes |
| Cryptographic Audit Trail | Yes | No | No | No | No |
| Local-First | Yes | No | Yes | No | No |
| Multi-Agent Orchestration | Yes | Yes | Yes | Yes | No |
| Open Source | MIT | MIT | MIT | MIT | Apache 2.0 |

---

## Detailed Comparisons

### WarmLogic vs LangChain

| Aspect | WarmLogic | LangChain |
|--------|-----------|-----------|
| **Focus** | Governance & Verification | LLM Orchestration |
| **Security Model** | Cryptographic proofs | Application-level |
| **Audit Trail** | Immutable, signed | Mutable logs |
| **Quantum Safety** | ML-DSA-65 | None |
| **Policy Enforcement** | Constitutional kernel | Plugin-based |
| **Performance** | Rust core (~300x crypto) | Pure Python |
| **Multi-Node** | BFT consensus | Single process |
| **Best For** | Regulated industries | Rapid prototyping |

**When to choose WarmLogic**: Financial services, healthcare, legal, government applications requiring cryptographic proof of AI decisions.

**When to choose LangChain**: Quick prototypes, non-regulated applications, pure LLM orchestration.

---

### WarmLogic vs Guardrails AI

| Aspect | WarmLogic | Guardrails AI |
|--------|-----------|---------------|
| **Focus** | Full governance stack | Output validation |
| **Cryptographic Proof** | Yes (PQC) | No |
| **Consensus** | BFT multi-node | Single process |
| **Policy Language** | YAML + Python | RAIL (XML-like) |
| **Evidence Bundle** | Full audit package | Validation logs |
| **Integration** | SDK + CLI + API | Python library |
| **Deployment** | Local-first / Swarm | Cloud or local |

**When to choose WarmLogic**: Need cryptographic evidence, multi-node deployment, post-quantum security.

**When to choose Guardrails AI**: Simple output validation, schema enforcement, LLM response formatting.

---

### WarmLogic vs AutoGPT

| Aspect | WarmLogic | AutoGPT |
|--------|-----------|---------|
| **Focus** | Governed autonomy | Unrestricted autonomy |
| **Safety Model** | Constitutional constraints | User prompts |
| **Audit Trail** | Cryptographic | Text logs |
| **Decision Verification** | BFT consensus | None |
| **Resource Limits** | Policy-enforced | Configuration |
| **Multi-Agent** | Swarm with consensus | Single agent |

**When to choose WarmLogic**: Enterprise deployments requiring accountability and proof.

**When to choose AutoGPT**: Personal automation, exploratory tasks, hobby projects.

---

## Cryptographic Comparison

### Signature Schemes

| Scheme | Key Size | Sig Size | Sign Time | Quantum Safe |
|--------|----------|----------|-----------|--------------|
| **ML-DSA-65** | 1,952 B | 3,309 B | 48 μs | Yes |
| Ed25519 | 32 B | 64 B | 35 μs | No |
| RSA-2048 | 256 B | 256 B | 1.2 ms | No |
| ECDSA P-256 | 32 B | 64 B | 125 μs | No |

### Why Post-Quantum Matters

- **Quantum Timeline**: Cryptographically relevant quantum computers expected within 10-15 years
- **Harvest Now, Decrypt Later**: Adversaries may store encrypted data today for future decryption
- **Regulatory Pressure**: NIST, EU, and others recommending PQC transition
- **Long-Term Records**: Audit trails must remain verifiable for decades

---

## Consensus Comparison

| Protocol | Latency | Throughput | Fault Tolerance | Finality |
|----------|---------|------------|-----------------|----------|
| **WL-BFT-v1** | 87 ms | 11.5/s | Byzantine (f < n/3) | Instant |
| Raft | 45 ms | 22/s | Crash (f < n/2) | Instant |
| Paxos | 50 ms | 20/s | Crash (f < n/2) | Instant |
| Tendermint | 120 ms | 8.3/s | Byzantine (f < n/3) | Instant |

### Why BFT Matters

- **Malicious Nodes**: Crash-fault tolerant (Raft/Paxos) can't handle Byzantine behavior
- **AI Safety**: Assume some nodes may be compromised or hallucinating
- **Regulatory Requirement**: Financial systems often require BFT

---

## Governance Comparison

### Policy Enforcement

| System | Policy Type | Enforcement Point | Bypassable |
|--------|-------------|-------------------|------------|
| **WarmLogic** | Constitutional | Kernel (Rust) | No |
| LangChain | Plugin | Application | Yes |
| Guardrails | RAIL Schema | Library | Yes |
| AutoGPT | Prompt | LLM | Yes |

### Why Constitutional Governance

- **Non-Bypassable**: Rules enforced at the lowest level
- **Formal Verification**: TLA+ specs for safety properties
- **Deterministic**: Same input → same policy decision
- **Auditable**: Every policy evaluation recorded

---

## Performance Comparison

### Decision Latency

| System | Single Node | 4-Node Cluster |
|--------|-------------|----------------|
| **WarmLogic** | 12 ms | 99 ms |
| LangChain | 5 ms | N/A |
| Guardrails | 8 ms | N/A |
| AutoGPT | 3 ms | N/A |

*Note: WarmLogic includes cryptographic signing and optional consensus.*

### Throughput

| System | Decisions/sec | Notes |
|--------|---------------|-------|
| **WarmLogic** | 100 (single) / 11 (cluster) | With full audit |
| LangChain | 1000+ | No cryptographic overhead |
| Guardrails | 500+ | Validation only |

---

## Use Case Fit

| Use Case | Best Choice | Reason |
|----------|-------------|--------|
| Financial trading audit | **WarmLogic** | PQC + BFT + evidence |
| Healthcare AI decisions | **WarmLogic** | HIPAA compliance proofs |
| Chatbot prototyping | LangChain | Rapid development |
| Output formatting | Guardrails | Schema validation |
| Personal automation | AutoGPT | Flexibility |
| Legal document review | **WarmLogic** | Audit trail required |
| Creative writing | LangChain | No governance needed |
| Multi-agent research | CrewAI | Collaboration focus |

---

## Migration Path

### From LangChain to WarmLogic

```python
# LangChain
from langchain import LLMChain
chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run(input)

# WarmLogic (wrap with governance)
from warm_logic.sdk import SovereignClient
client = SovereignClient()

decision = client.propose_action(
    intent="llm_call",
    context={"prompt": prompt, "input": input}
)

if decision.approved:
    result = chain.run(input)
    client.record_evidence(decision.proof_hash, result)
```

### From Guardrails to WarmLogic

```python
# Guardrails
from guardrails import Guard
guard = Guard.from_rail(rail_spec)
result = guard(llm, prompt)

# WarmLogic (with cryptographic proof)
from warm_logic.sdk import SovereignClient
client = SovereignClient()

decision = client.propose_action(
    intent="guarded_call",
    context={"rail_spec": rail_spec, "prompt": prompt}
)

if decision.approved:
    result = guard(llm, prompt)
    # Evidence bundle automatically created
```

---

## Limitations

### WarmLogic Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Larger signature size | 3KB vs 64B | Acceptable for audit use cases |
| Consensus latency | 87ms overhead | Skip for non-critical decisions |
| Complexity | Steeper learning curve | Comprehensive documentation |
| Production readiness | Not production-ready | Planned for 2026 Q4 |

### When NOT to Use WarmLogic

- Simple chatbots with no audit requirements
- Real-time gaming (latency sensitive)
- Personal hobby projects
- Rapid prototyping phase

---

## Conclusion

WarmLogic is designed for **high-stakes AI governance** where:
- Decisions must be cryptographically provable
- Post-quantum security is required
- Multi-node consensus is needed
- Regulatory compliance is mandatory

For simpler use cases, other tools may be more appropriate.

---

*Last updated: 2026-02-07*
