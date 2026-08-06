# WarmLogic Rust Core - Observability Guide

**Version**: 1.0.1
**Date**: 2026-02-12

---

## Overview

WarmLogic Rust Core provides multiple observability entry points for monitoring, debugging, and performance analysis.

---

## 1. Available Metrics APIs

### 1.1 Network Statistics

```python
import warm_logic_rs as wl

# Create network bridge
bridge = wl.RustNetworkBridge()

# Get network stats (includes security metrics)
stats = bridge.get_stats()
print(stats)
# {
#     "messages_sent": 1234,
#     "messages_received": 5678,
#     "bytes_sent": 123456,
#     "bytes_received": 789012,
#     "rate_limited_count": 5,
#     "banned_ips_count": 2
# }
```

### 1.2 Policy Engine Invariants

```python
import warm_logic_rs as wl

engine = wl.PolicyEngine()

# Check system invariants
metrics = {
    "cpu_drift": 0.03,
    "mem_usage": 0.75
}

violations = engine.check_invariants(metrics)
if violations:
    print(f"ALERT: {violations}")
```

### 1.3 Consensus Engine Stats

```python
import warm_logic_rs as wl

engine = wl.BFTEngine(node_id=1, total_nodes=5)

# Get consensus state
state = engine.get_state()
# {"round": 42, "phase": "VOTE", "decided": True}
```

### 1.4 Ledger State

```python
import warm_logic_rs as wl

ledger = wl.RustReplicatedLedger()

# Get ledger stats
stats = {
    "version": ledger.version(),
    "merkle_root": ledger.merkle_root_hex(),
    "tx_count": len(ledger.get_recent_transactions(100))
}
```

### 1.5 HSM Status

```python
import warm_logic_rs as wl

hsm = wl.VirtualHSM()

# Get HSM type and status
status = {
    "type": hsm.hsm_type(),
    "has_key": hsm.public_key() is not None,
    "hardware_backed": hsm.is_hardware_backed()
}
```

---

## 2. Prometheus Integration

### 2.1 Metrics Exporter Pattern

```python
from prometheus_client import Counter, Gauge, Histogram
import warm_logic_rs as wl

# Define metrics
SIGNATURES_TOTAL = Counter('wl_signatures_total', 'Total signatures created')
VERIFICATIONS_TOTAL = Counter('wl_verifications_total', 'Total verifications')
CONSENSUS_ROUNDS = Gauge('wl_consensus_rounds', 'Current consensus round')
SIGNATURE_LATENCY = Histogram('wl_signature_latency_seconds', 'Signature latency')

def sign_with_metrics(keypair, message):
    import time
    start = time.time()
    signature = keypair.sign(message)
    SIGNATURE_LATENCY.observe(time.time() - start)
    SIGNATURES_TOTAL.inc()
    return signature
```

### 2.2 Custom Exporter

```python
from prometheus_client import start_http_server, REGISTRY, Gauge
import warm_logic_rs as wl
import time

class WarmLogicCollector:
    def __init__(self, bridge, engine, ledger):
        self.bridge = bridge
        self.engine = engine
        self.ledger = ledger

        # Network metrics
        self.msg_sent = Gauge('wl_messages_sent', 'Messages sent')
        self.msg_recv = Gauge('wl_messages_received', 'Messages received')
        self.rate_limited = Gauge('wl_rate_limited', 'Rate limited requests')
        self.banned_ips = Gauge('wl_banned_ips', 'Banned IPs count')

        # Consensus metrics
        self.consensus_round = Gauge('wl_consensus_round', 'Current round')

        # Ledger metrics
        self.ledger_version = Gauge('wl_ledger_version', 'Ledger version')

    def collect(self):
        # Network
        stats = self.bridge.get_stats()
        self.msg_sent.set(stats.get('messages_sent', 0))
        self.msg_recv.set(stats.get('messages_received', 0))
        self.rate_limited.set(stats.get('rate_limited_count', 0))
        self.banned_ips.set(stats.get('banned_ips_count', 0))

        # Consensus
        state = self.engine.get_state()
        self.consensus_round.set(state.get('round', 0))

        # Ledger
        self.ledger_version.set(self.ledger.version())

# Usage
bridge = wl.RustNetworkBridge()
engine = wl.BFTEngine(node_id=1, total_nodes=5)
ledger = wl.RustReplicatedLedger()

collector = WarmLogicCollector(bridge, engine, ledger)

# Update metrics periodically
def metrics_loop():
    while True:
        collector.collect()
        time.sleep(15)

# Start Prometheus endpoint
start_http_server(9090)
```

### 2.3 Grafana Dashboard

```json
{
  "panels": [
    {
      "title": "Signatures per Second",
      "targets": [{
        "expr": "rate(wl_signatures_total[5m])"
      }]
    },
    {
      "title": "Signature Latency (p99)",
      "targets": [{
        "expr": "histogram_quantile(0.99, wl_signature_latency_seconds_bucket)"
      }]
    },
    {
      "title": "Consensus Round",
      "targets": [{
        "expr": "wl_consensus_round"
      }]
    },
    {
      "title": "Rate Limited Requests",
      "targets": [{
        "expr": "wl_rate_limited"
      }]
    }
  ]
}
```

---

## 3. Logging

### 3.1 Rust Logging Configuration

```bash
# Log levels: trace, debug, info, warn, error
export RUST_LOG=warn,warm_logic_rs=info

# Per-module control
export RUST_LOG=warm_logic_rs::consensus=debug,warm_logic_rs::net=warn

# File output
export WL_LOG_FILE=/var/log/warmlogic.log
```

### 3.2 Structured Logging (Python)

```python
import logging
import json
import warm_logic_rs as wl

class WarmLogicFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if hasattr(record, 'extra'):
            log_obj.update(record.extra)
        return json.dumps(log_obj)

# Setup
logger = logging.getLogger('warmlogic')
handler = logging.StreamHandler()
handler.setFormatter(WarmLogicFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage
def sign_operation(message):
    keypair = wl.PQCKeypair()
    signature = keypair.sign(message)
    logger.info("signature_created", extra={
        "message_size": len(message),
        "signature_size": len(signature),
        "algorithm": "ML-DSA-65"
    })
    return signature
```

---

## 4. Health Checks

### 4.1 Basic Health Check

```python
import warm_logic_rs as wl

def health_check():
    checks = {}

    # Crypto health
    try:
        keypair = wl.PQCKeypair()
        msg = b"health"
        sig = keypair.sign(msg)
        checks["crypto"] = keypair.verify(msg, sig)
    except Exception as e:
        checks["crypto"] = False
        checks["crypto_error"] = str(e)

    # HSM health
    try:
        hsm = wl.VirtualHSM()
        checks["hsm"] = hsm.public_key() is not None
        checks["hsm_type"] = hsm.hsm_type()
    except Exception as e:
        checks["hsm"] = False
        checks["hsm_error"] = str(e)

    # Ledger health
    try:
        ledger = wl.RustReplicatedLedger()
        checks["ledger"] = ledger.version() >= 0
    except Exception as e:
        checks["ledger"] = False
        checks["ledger_error"] = str(e)

    checks["healthy"] = all([
        checks.get("crypto", False),
        checks.get("hsm", False),
        checks.get("ledger", False)
    ])

    return checks
```

### 4.2 Kubernetes Probes

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: warmlogic
    image: warmlogic/python-bindings:1.0.1
    livenessProbe:
      exec:
        command:
        - python
        - -c
        - "import warm_logic_rs; print('alive')"
      initialDelaySeconds: 5
      periodSeconds: 10
    readinessProbe:
      exec:
        command:
        - python
        - /app/health_check.py
      initialDelaySeconds: 5
      periodSeconds: 5
```

---

## 5. Tracing

### 5.1 OpenTelemetry Integration

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
import warm_logic_rs as wl

# Setup
provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("warmlogic")

# Usage
@tracer.start_as_current_span("sign_message")
def traced_sign(message):
    span = trace.get_current_span()
    keypair = wl.PQCKeypair()

    span.set_attribute("message.size", len(message))
    span.set_attribute("algorithm", "ML-DSA-65")

    signature = keypair.sign(message)
    span.set_attribute("signature.size", len(signature))

    return signature
```

---

## 6. Alerting Rules

### 6.1 Prometheus Alert Rules

```yaml
groups:
- name: warmlogic
  rules:
  - alert: HighSignatureLatency
    expr: histogram_quantile(0.99, wl_signature_latency_seconds_bucket) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High signature latency detected"

  - alert: RateLimitingActive
    expr: increase(wl_rate_limited[5m]) > 100
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Rate limiting is actively blocking requests"

  - alert: IPsBanned
    expr: wl_banned_ips > 10
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Multiple IPs have been banned"

  - alert: ConsensusStalled
    expr: changes(wl_consensus_round[10m]) == 0
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "Consensus has not progressed"
```

---

## 7. Performance Profiling

### 7.1 Benchmark Commands

```bash
# Run crypto benchmarks
cargo bench --bench crypto_bench

# Run consensus benchmarks
cargo bench --bench consensus_bench

# Generate HTML report
cargo bench -- --save-baseline main
```

### 7.2 Flamegraph

```bash
# Install flamegraph
cargo install flamegraph

# Generate profile
cargo flamegraph --bin hyper -- --some-args

# View flamegraph.svg in browser
```

---

## 8. Debugging

### 8.1 Debug Mode

```bash
# Enable backtrace
export RUST_BACKTRACE=1

# Enable all debug logs
export RUST_LOG=debug

# Run with debug output
cargo run --features cockpit
```

### 8.2 Memory Debugging

```bash
# Install valgrind (Linux)
sudo apt install valgrind

# Run with valgrind
valgrind --leak-check=full ./target/release/hyper
```

---

## Summary

| Feature | API | Status |
|---------|-----|--------|
| Network Stats | `bridge.get_stats()` | Production |
| Policy Checks | `engine.check_invariants()` | Production |
| Consensus State | `engine.get_state()` | Production |
| Ledger State | `ledger.version()` | Production |
| HSM Status | `hsm.hsm_type()` | Production |
| Prometheus | Custom exporter | Example |
| OpenTelemetry | Custom integration | Example |
