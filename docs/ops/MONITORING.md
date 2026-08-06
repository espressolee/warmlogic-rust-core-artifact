# Monitoring & Observability

> **Mantra**: "If you can't measure it, you don't control it."

## 🩺 System Health

### Healthcheck Endpoint
**GET** `/health`
- **Purpose**: Liveness probe for Load Balancers or Kubernetes.
- **Response**:
  ```json
  {
    "status": "ok",
    "kernel": "active",
    "timestamp": 1706830000.0
  }
  ```

## 📊 Key Metrics

| Metric                | Threshold (Warning) | Threshold (Critical) | Description                                          |
| --------------------- | ------------------- | -------------------- | ---------------------------------------------------- |
| **Tick Drift**        | > 50ms              | > 200ms              | Divergence from wall-clock time. Indicates overload. |
| **Consensus Latency** | > 1.0s              | > 5.0s               | Time to finalize a block.                            |
| **Peer Count**        | < 3                 | 0                    | Connectivity to the Sovereign Mesh.                  |
| **Memory Usage**      | > 1GB               | > 2GB                | Kernel memory footprint.                             |

## 📜 Logs

Logs are structured and follow the pattern: `DATE LEVEL [COMPONENT] MESSAGE`.
Location: `logs/node_{PORT}.log` (default).

**Example**:
```text
2026-02-01 12:00:00 INFO [KERNEL] Tick 4092 completed in 12ms.
2026-02-01 12:00:01 WARN [P2P] Peer connection timeout: 192.168.1.55
```

### Log Levels
- **INFO**: Standard heartbeat.
- **WARN**: Transient issues (timeouts, drift).
- **ERROR**: Action required (Validation failure).
- **CRITICAL**: System Halt (Attestation failure, integrity breach).

---

## 🧪 Harsh Benchmarking Suite (Performance Standards)

To certify "Civilizational Scale", we enforce the following stress tests:

| Benchmark ID               | Stress Target  | Workload                 | Success Criteria        |
| :------------------------- | :------------- | :----------------------- | :---------------------- |
| **Civilizational Scaling** | **Throughput** | 1,000 shards, 10k events | Finality < 1,000ms      |
| **Logic Fuzzing**          | **Safety**     | 1M random transitions    | 0% Invariant Violations |
| **Adversarial Stress**     | **Truth**      | 34% Byzantine Injection  | 0 False Truth Ingestion |
| **Evolution Cycle**        | **Agility**    | Self-patch synthesis     | Intent-to-Patch < 15s   |
