# WarmLogic Docker Deployment Guide

> Production-ready containerized deployment for WarmLogic sovereign mesh networks.

## Prerequisites

- Docker 24.0+
- Docker Compose v2.20+
- 4GB RAM minimum (8GB recommended for 3-node cluster)

## Quick Start

```bash
# From project root
cd deploy/docker

# Start 3-node mesh cluster
docker compose -f docker-compose.multinode.yaml up -d

# Verify all nodes are healthy
docker compose -f docker-compose.multinode.yaml ps

# Check health endpoints
curl http://localhost:8000/health  # Node 0 (Seed)
curl http://localhost:8001/health  # Node 1 (Mesh)
curl http://localhost:8002/health  # Node 2 (Mesh)
```

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │          Docker Network                 │
                    │          (172.28.0.0/16)                │
                    └─────────────────────────────────────────┘
                              │         │         │
               ┌──────────────┼─────────┼─────────┼──────────────┐
               │              ▼         ▼         ▼              │
               │     ┌─────────┐ ┌─────────┐ ┌─────────┐         │
               │     │ Node 0  │ │ Node 1  │ │ Node 2  │         │
               │     │ (Seed)  │ │ (Mesh)  │ │ (Mesh)  │         │
               │     │172.28.  │ │172.28.  │ │172.28.  │         │
               │     │  0.10   │ │  0.11   │ │  0.12   │         │
               │     └────┬────┘ └────┬────┘ └────┬────┘         │
               │          │          │          │                │
               └──────────┼──────────┼──────────┼────────────────┘
                          │          │          │
                     :8000       :8001       :8002
                          │          │          │
                    ┌─────▼──────────▼──────────▼─────┐
                    │         Host Machine            │
                    └─────────────────────────────────┘
```

## Port Mapping

| Host Port | Container Port | Protocol | Service           |
|-----------|---------------|----------|-------------------|
| 8000      | 8000          | TCP      | Node 0 REST API   |
| 8001      | 8000          | TCP      | Node 1 REST API   |
| 8002      | 8000          | TCP      | Node 2 REST API   |
| 9000      | 9000          | UDP      | Node 0 P2P (DHT)  |
| 9001      | 9000          | UDP      | Node 1 P2P (DHT)  |
| 9002      | 9000          | UDP      | Node 2 P2P (DHT)  |
| 9090      | 9090          | TCP      | Node 0 Prometheus |
| 9091      | 9090          | TCP      | Node 1 Prometheus |
| 9092      | 9090          | TCP      | Node 2 Prometheus |

## Environment Variables

| Variable                   | Default       | Description                    |
|---------------------------|---------------|--------------------------------|
| `WARMLOGIC_NODE_ID`       | `0`           | Unique node identifier         |
| `WARMLOGIC_GATEWAY_PORT`  | `8000`        | REST API port                  |
| `WARMLOGIC_ROLE`          | `mesh`        | Node role: `seed` or `mesh`    |
| `WARMLOGIC_LOG_LEVEL`     | `INFO`        | Log verbosity                  |
| `WARMLOGIC_API_KEY`       | -             | API authentication key         |
| `WARMLOGIC_BOOTSTRAP_NODES` | -           | Comma-separated peer addresses |
| `ENVIRONMENT`             | `production`  | Environment mode               |

## API Authentication

All `/api/v1/*` endpoints require authentication:

```bash
# Without API key (fails)
curl http://localhost:8000/api/v1/governance/status
# {"detail":{"error":"configuration_error","message":"API key not configured..."}}

# With API key (works)
export WARMLOGIC_API_KEY="your-secret-key"
curl -H "X-API-Key: $WARMLOGIC_API_KEY" http://localhost:8000/api/v1/governance/status
```

To enable API authentication, set the environment variable in docker-compose:

```yaml
environment:
  - WARMLOGIC_API_KEY=your-production-secret-key
```

## Available Endpoints

### Public (No Auth Required)
- `GET /health` - Health status
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe
- `GET /metrics` - Prometheus metrics
- `GET /docs` - OpenAPI documentation

### Protected (X-API-Key Required)
- `GET /api/v1/governance/status` - Governance mode
- `POST /api/v1/governance/propose` - Propose action
- `POST /api/v1/governance/evaluate` - Policy evaluation
- `GET /api/v1/consensus/status` - BFT status
- `GET /api/v1/mesh/status` - DHT network status
- `GET /api/v1/crypto/info` - Cryptographic algorithms

## Operations

### View Logs

```bash
# All nodes
docker compose -f docker-compose.multinode.yaml logs -f

# Specific node
docker compose -f docker-compose.multinode.yaml logs -f warmlogic-node-0
```

### Scale Nodes

```bash
# Start additional mesh nodes (requires config update)
docker compose -f docker-compose.multinode.yaml up -d --scale warmlogic-node-1=2
```

### Health Monitoring

```bash
# Check container health status
docker ps --format "table {{.Names}}\t{{.Status}}" | grep warmlogic

# Prometheus metrics
curl -s http://localhost:8000/metrics | grep warmlogic
```

### Shutdown

```bash
# Stop and remove containers
docker compose -f docker-compose.multinode.yaml down

# Stop and remove volumes (DESTRUCTIVE)
docker compose -f docker-compose.multinode.yaml down -v
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.multinode.yaml logs warmlogic-node-0

# Common issues:
# - Port already in use: Change host ports in docker-compose.yaml
# - Memory exhaustion: Increase Docker memory limit
```

### Health Check Failing

```bash
# Verify container is running
docker ps | grep warmlogic

# Check internal health
docker exec warmlogic-node-0 curl -s http://localhost:8000/health
```

### Network Issues

```bash
# Inspect Docker network
docker network inspect docker_warmlogic-mesh

# Test inter-node connectivity
docker exec warmlogic-node-1 curl -s http://172.28.0.10:8000/health
```

## Production Checklist

- [ ] Set strong `WARMLOGIC_API_KEY` for all nodes
- [ ] Configure `WARMLOGIC_CORS_ORIGINS` (not wildcard)
- [ ] Enable TLS termination (nginx/traefik proxy)
- [ ] Set up log aggregation (ELK/Loki)
- [ ] Configure Prometheus alerting
- [ ] Set resource limits in docker-compose
- [ ] Enable persistent volumes for `/app/data`
- [ ] Configure backup strategy

## Security Notes

1. **Non-root user**: Containers run as `warmlogic` user (UID 999)
2. **API protection**: All sensitive endpoints require X-API-Key
3. **Network isolation**: Mesh network is on dedicated Docker bridge
4. **No secrets in images**: All credentials via environment variables

---

*Last updated: 2026-02-12*
