# Fleet Management Guide

> **Sovereign Reality**

This guide covers the operational lifecycle of WarmLogic nodes in a distributed physical environment.

## 1. Node Provisioning
Use the bootstrap_node.sh script to prepare fresh hardware.

```bash
# (bootstrap endpoint not yet provisioned; install from source per README)
```

## 2. Configuration Profiles
For production environments, use the `docker-compose.prod.yml` manifest which includes:
- **Resource Constraints**: Limits memory to 512MB to avoid OOM on 1GB boards.
- **Hardware Entropy**: Mounts `/dev/hwrng` for PQC safety.
- **Persistence**: Managed via `SovereignStore` in Docker volumes.

## 3. Monitoring & Maintenance
WarmLogic exposes Prometheus metrics at `:8000/metrics`.
- **Health Check**: `GET /health` returns the kernel state.
- **TPS Monitoring**: Monitor `warm_logic_consensus_throughput` via Grafana.

## 4. OTA Updates (Alpha)
WarmLogic supports "Lazy Consensus" updates.
1. An operator proposes a new binary hash.
2. Nodes download and verify the hash against the blockchain.
3. Upon BFT agreement (2/3+), the `warmlogic_kernel_prod` container is restarted with the new image.

---
*Maintained by the espressolee.*
