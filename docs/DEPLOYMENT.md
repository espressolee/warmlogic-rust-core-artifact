# WarmLogic Deployment Guide

> ## ⚠️ NON-AUTHORITATIVE — HISTORICAL DESIGN DOCUMENT
>
> This file describes **design intent**, not the measured state of this
> artifact. It predates the publication audit and its claims were **not**
> re-verified. Several are known to be contradicted by measurement — see
> `KNOWN_LIMITATIONS.md` and `docs/CLAIM_EVIDENCE.md`, which are authoritative.
>
> Known contradictions include: multi-node/BFT deployment (never executed),
> zero-knowledge proofs (the `zk` feature does not compile), formal
> verification (Kani harnesses exist but no CI runs them; TLA+ specs are design
> documents, not checked models), and performance figures (no raw data is bound
> to this artifact).
>
> **Do not cite this file for current status.** Authoritative files:
> `README.md`, `STATUS.md`, `KNOWN_LIMITATIONS.md`, `docs/CLAIM_EVIDENCE.md`,
> `SECURITY.md`, `PUBLIC_PROVENANCE.json`, `SBOM.json`, `AUDIT_PROFILE.json`,
> `LICENSE`, `NOTICE`.

> **Status**: research prototype. Not externally validated; see docs/CLAIM_EVIDENCE.md.
> This guide covers deployment for development, staging, and pilot environments.
> Production deployment requires additional hardening not yet complete.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Deployment Options](#deployment-options)
4. [Configuration](#configuration)
5. [Docker Deployment](#docker-deployment)
6. [Kubernetes Deployment](#kubernetes-deployment)
7. [Multi-Node Setup](#multi-node-setup)
8. [Security Hardening](#security-hardening)
9. [Monitoring](#monitoring)
10. [Backup and Recovery](#backup-and-recovery)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Storage | 20 GB SSD | 100+ GB NVMe |
| Network | 100 Mbps | 1 Gbps |

### Software Requirements

| Software | Version | Notes |
|----------|---------|-------|
| Python | 3.12+ | Required |
| Rust | 1.75+ | For crypto core compilation |
| Docker | 24.0+ | Optional, for containerized deployment |
| Kubernetes | 1.28+ | Optional, for orchestrated deployment |

### Port Requirements

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| REST API Gateway | 8000 | TCP/HTTP | External API |
| Cockpit Server | 5001 | TCP/HTTP | Admin interface |
| DHT P2P | 5101+ | UDP | Peer discovery |
| Prometheus | 9090 | TCP/HTTP | Metrics (optional) |

---

## Quick Start

### Single-Node Development

```bash
# Clone repository
git clone https://github.com/espressolee/WarmLogic
cd warmlogic

# Setup environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# Build Rust core
cd rust_core && maturin develop && cd ..

# Set API key
export SOVEREIGN_COCKPIT_KEY=$(openssl rand -hex 32)
export WARMLOGIC_API_KEY=$SOVEREIGN_COCKPIT_KEY

# Start services
python -m warm_logic.gateway  # REST API on :8000
```

Verify deployment:

```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

---

## Deployment Options

### Option 1: Direct Python

Best for: Development, testing, small pilots

```bash
# Start REST API Gateway
python -m warm_logic.gateway

# Start Cockpit (separate terminal)
python -m warm_logic.app.cockpit.server
```

### Option 2: Docker Compose

Best for: Staging, isolated deployments

```bash
docker-compose up -d
```

### Option 3: Kubernetes

Best for: Production pilots, multi-node, high availability

```bash
kubectl apply -f k8s/
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SOVEREIGN_COCKPIT_KEY` | Yes | - | API authentication key |
| `WARMLOGIC_API_KEY` | Yes | - | Gateway API key |
| `WARMLOGIC_GATEWAY_PORT` | No | 8000 | Gateway port |
| `WARMLOGIC_GATEWAY_HOST` | No | 0.0.0.0 | Gateway bind address |
| `WARMLOGIC_DEBUG` | No | 0 | Enable debug mode (1/0) |
| `WARMLOGIC_CORS_ORIGINS` | No | * | CORS allowed origins |
| `COCKPIT_HTTP_PORT` | No | 5001 | Cockpit port |
| `SOVEREIGN_COMMERCIAL_MODE` | No | 0 | Enable token economy |

### Configuration Files

**constitution.yaml** - Governance policies:

```yaml
version: "1.0"

governance:
  mode: production
  reflective_loop:
    alpha: 0.6  # Ethical weight
    beta: 0.4   # Stability weight

policies:
  - name: default_policy
    rules:
      - intent: "execute_trade"
        require:
          - risk_score: "< 0.5"
        deny_if:
          - market_closed: true

slashing:
  enabled: true
  thresholds:
    state_lock: 0.95
    economic_burn: 0.80
```

---

## Docker Deployment

### Build Image

```bash
docker build -t warmlogic:latest .
```

### Docker Compose

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  gateway:
    image: warmlogic:latest
    command: python -m warm_logic.gateway
    ports:
      - "8000:8000"
    environment:
      - WARMLOGIC_API_KEY=${WARMLOGIC_API_KEY}
      - WARMLOGIC_GATEWAY_PORT=8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  cockpit:
    image: warmlogic:latest
    command: python -m warm_logic.app.cockpit.server
    ports:
      - "5001:5001"
    environment:
      - SOVEREIGN_COCKPIT_KEY=${SOVEREIGN_COCKPIT_KEY}
      - COCKPIT_HTTP_PORT=5001
    depends_on:
      - gateway
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    restart: unless-stopped
```

### Run

```bash
# Set required environment variables
export WARMLOGIC_API_KEY=$(openssl rand -hex 32)
export SOVEREIGN_COCKPIT_KEY=$WARMLOGIC_API_KEY

# Start services
docker-compose up -d

# View logs
docker-compose logs -f gateway

# Stop services
docker-compose down
```

---

## Kubernetes Deployment

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: warmlogic
```

### ConfigMap and Secrets

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: warmlogic-config
  namespace: warmlogic
data:
  WARMLOGIC_GATEWAY_PORT: "8000"
  WARMLOGIC_DEBUG: "0"

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: warmlogic-secrets
  namespace: warmlogic
type: Opaque
stringData:
  WARMLOGIC_API_KEY: "your-api-key-here"  # Replace with secure key
  SOVEREIGN_COCKPIT_KEY: "your-cockpit-key-here"
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: warmlogic-gateway
  namespace: warmlogic
spec:
  replicas: 2
  selector:
    matchLabels:
      app: warmlogic-gateway
  template:
    metadata:
      labels:
        app: warmlogic-gateway
    spec:
      containers:
      - name: gateway
        image: warmlogic:latest
        command: ["python", "-m", "warm_logic.gateway"]
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: warmlogic-config
        - secretRef:
            name: warmlogic-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: warmlogic-gateway
  namespace: warmlogic
spec:
  selector:
    app: warmlogic-gateway
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP

---
apiVersion: v1
kind: Service
metadata:
  name: warmlogic-gateway-lb
  namespace: warmlogic
spec:
  selector:
    app: warmlogic-gateway
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Deploy

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Verify
kubectl get pods -n warmlogic
kubectl logs -n warmlogic -l app=warmlogic-gateway
```

---

## Multi-Node Setup

### BFT Validator Configuration

For Byzantine Fault Tolerance, deploy 4+ nodes (tolerates 1 Byzantine failure).

| Nodes | Quorum | Byzantine Tolerance |
|-------|--------|---------------------|
| 4 | 3 | 1 |
| 7 | 5 | 2 |
| 10 | 7 | 3 |

### Node Configuration

Each node requires:

```bash
# Generate unique node identity
export NODE_ID=$(openssl rand -hex 16)
export NODE_PORT=9000

# Configure peers
export PEER_NODES="node1.example.com:9000,node2.example.com:9000"

# Start with peer discovery
python -m warm_logic.gateway \
  --node-id $NODE_ID \
  --peers $PEER_NODES
```

### Network Topology

```
                    ┌─────────────┐
                    │  Load       │
                    │  Balancer   │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
    │  Node 1 │◄─────►│  Node 2 │◄─────►│  Node 3 │
    │ (Leader)│       │(Follower)│      │(Follower)│
    └────┬────┘       └────┬────┘       └────┬────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Node 4     │
                    │ (Follower)  │
                    └─────────────┘
```

---

## Security Hardening

### API Key Management

```bash
# Generate strong API key
openssl rand -hex 32

# Store in secret manager (AWS example)
aws secretsmanager create-secret \
  --name warmlogic/api-key \
  --secret-string $(openssl rand -hex 32)
```

### TLS Configuration

```bash
# Generate self-signed certificate (development only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout key.pem -out cert.pem

# Run with TLS
uvicorn warm_logic.gateway:gateway_app \
  --ssl-keyfile key.pem \
  --ssl-certfile cert.pem \
  --port 8443
```

### Firewall Rules

```bash
# Allow only necessary ports
ufw allow 8000/tcp  # Gateway
ufw allow 5001/tcp  # Cockpit (internal only)
ufw allow 9000/udp  # DHT (between nodes only)

# Restrict to specific IPs
ufw allow from 10.0.0.0/8 to any port 5001
```

### Network Policies (Kubernetes)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: warmlogic-network-policy
  namespace: warmlogic
spec:
  podSelector:
    matchLabels:
      app: warmlogic-gateway
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: warmlogic-gateway
    ports:
    - port: 9000
      protocol: UDP
```

---

## Monitoring

### Prometheus Configuration

**prometheus.yml**:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'warmlogic-gateway'
    static_configs:
      - targets: ['gateway:8000']
    metrics_path: /metrics

  - job_name: 'warmlogic-cockpit'
    static_configs:
      - targets: ['cockpit:5001']
    metrics_path: /metrics
```

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `warmlogic_gateway_requests_total` | Total API requests | - |
| `warmlogic_gateway_request_latency_seconds` | Request latency | p99 > 1s |
| `warmlogic_consensus_round` | Current BFT round | - |
| `warmlogic_active_validators` | Active validators | < quorum |
| `warmlogic_governance_mode` | Current mode | != NORMAL |

### Grafana Dashboard

Import dashboard from `monitoring/grafana-dashboard.json` or create:

```json
{
  "panels": [
    {
      "title": "Request Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(warmlogic_gateway_requests_total[5m])"
        }
      ]
    },
    {
      "title": "Latency P99",
      "type": "graph",
      "targets": [
        {
          "expr": "histogram_quantile(0.99, rate(warmlogic_gateway_request_latency_seconds_bucket[5m]))"
        }
      ]
    }
  ]
}
```

---

## Backup and Recovery

### Data Locations

| Component | Location | Backup Frequency |
|-----------|----------|------------------|
| Sled Database | `data/sled/` | Daily |
| Configuration | `config/` | On change |
| Ledger | `data/ledger/` | Hourly |
| Keys | `keys/` | On creation |

### Backup Script

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/warmlogic/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Stop services gracefully
docker-compose stop

# Backup data
tar -czf $BACKUP_DIR/data.tar.gz data/
tar -czf $BACKUP_DIR/config.tar.gz config/

# Restart services
docker-compose start

# Upload to S3 (optional)
aws s3 sync $BACKUP_DIR s3://my-backup-bucket/warmlogic/
```

### Recovery

```bash
#!/bin/bash
# restore.sh

BACKUP_DATE=$1  # e.g., 20260207

# Stop services
docker-compose down

# Restore data
tar -xzf /backup/warmlogic/$BACKUP_DATE/data.tar.gz -C /
tar -xzf /backup/warmlogic/$BACKUP_DATE/config.tar.gz -C /

# Start services
docker-compose up -d
```

---

## Troubleshooting

### Common Issues

#### Gateway won't start

```bash
# Check for port conflicts
lsof -i :8000

# Check logs
python -m warm_logic.gateway 2>&1 | head -50

# Verify Rust core
python -c "import warm_logic_rs; print('OK')"
```

#### API returns 401 Unauthorized

```bash
# Verify API key is set
echo $WARMLOGIC_API_KEY

# Test with key
curl -H "X-API-Key: $WARMLOGIC_API_KEY" http://localhost:8000/health
```

#### BFT consensus not reaching quorum

```bash
# Check active validators
curl -H "X-API-Key: $KEY" http://localhost:8000/api/v1/consensus/status

# Check network connectivity between nodes
ping node2.example.com

# Check DHT status
curl -H "X-API-Key: $KEY" http://localhost:8000/api/v1/consensus/network
```

#### High latency

```bash
# Check metrics
curl http://localhost:8000/metrics | grep latency

# Profile with py-spy
py-spy top --pid $(pgrep -f warm_logic.gateway)
```

### Health Checks

```bash
# Liveness (is the process running?)
curl http://localhost:8000/health/live

# Readiness (is it ready to accept requests?)
curl http://localhost:8000/health/ready

# Full health
curl http://localhost:8000/health
```

### Log Analysis

```bash
# View recent logs
docker-compose logs --tail=100 gateway

# Search for errors
docker-compose logs gateway | grep -i error

# JSON log parsing
docker-compose logs gateway | jq 'select(.levelname == "ERROR")'
```

---

## Next Steps

1. **Security Audit**: Before production, complete third-party security audit
2. **HSM Integration**: For production, integrate with hardware security modules
3. **Multi-Region**: Plan for multi-region deployment for high availability

---

*Last updated: 2026-02-07*
*Version: 0.1.0 (experimental)*
