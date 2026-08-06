# Civilization Deployment Manual

**WarmLogic Sovereign Node v1.0.0 (Mainnet)**

This document provides the canonical instructions for building, deploying, and operating a Sovereign Node in the Mainnet.

## 1. Prerequisites
- **Docker**: v24.0+
- **Docker Compose**: v2.20+
- **Python**: 3.11+ (for local scripts)
- **Minimum Hardware**: 2 vCPU, 4GB RAM, 20GB SSD (Sled persistent storage)

## 2. Building the Sovereign Image
We use a multi-stage Docker build to ensure a minimal production footprint. The build process compiles the Rust core kernels (`warm_logic_rs`) and packages the Python orchestration layer.

```bash
# Build the production image
docker build -t warmlogic/sovereign-node:latest .

# Verify build
docker run --rm warmlogic/sovereign-node:latest python -c "import warm_logic; print(warm_logic.__version__)"
```

## 3. Running a Local Swarm (Simulation)
To simulate a 3-node mesh network locally, use the provided `docker-compose.yml`. This creates a closed loop P2P network with shared gossip channels.

```bash
# Boot the swarm
docker-compose up -d

# Check logs for Genesis/Gossip events
docker-compose logs -f
```

### Accessing the Nodes
- **Node Alpha**: `http://localhost:8001` (UI/API)
- **Node Beta**: `http://localhost:8002`
- **Node Gamma**: `http://localhost:8003`

## 4. Cloud Deployment (Mainnet)
For production deployment on cloud providers (AWS/GCP), we recommend using **Terraform** or **Kubernetes**.

### Docker Run Command (Single Node)
```bash
docker run -d \
  --name sovereign-node \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e WARM_NODE_ID=$(uuidgen) \
  -e WARM_GOSSIP_SEED="node.mainnet.github.com/espressolee/warmlogic-rust-core-artifact:4000" \
  warmlogic/sovereign-node:latest
```

## 5. Genesis Bootstrap
If you are initializing a new network, run the genesis script inside the container:

```bash
docker exec -it sovereign-node python scripts/generate_genesis.py
```

## 6. Security Considerations
- **Ports**: Expose `8000` (API) only to trusted IPs or behind a Load Balancer. Expose `4000` (P2P) to the public internet (0.0.0.0/0) for mesh participation.
- **Storage**: Ensure `/app/data` is mounted to a persistent volume (EBS/PD) to prevent memory loss (Sled DB).
- **Keys**: Inject `SOVEREIGN_PRIV_KEY` via Docker Secrets or Environment Variables. Do not bake keys into the image.

---
**Status**: Ready for Civilization.
