# Runbook: Consensus Stalled

## Alert: ConsensusStalled

**Severity**: Critical
**Component**: Consensus (BFT)
**SLO Impact**: High - No new decisions can be finalized

---

## Description

The BFT consensus mechanism has not completed any rounds in the last 5 minutes. This blocks all governance decisions and evidence bundle creation.

## Symptoms

- Alert: `ConsensusStalled` firing
- `warm_logic_bft_rounds_total` not incrementing
- Pending proposals accumulating
- API decisions returning "consensus unavailable"

## Immediate Actions

### 1. Check Peer Connectivity

```bash
# Check mesh peer count
curl http://warmlogic:8080/api/v1/mesh/peers | jq '.count'

# List connected peers
curl http://warmlogic:8080/api/v1/mesh/peers | jq '.peers[]'
```

### 2. Check Consensus State

```bash
# BFT status
curl http://warmlogic:8080/api/v1/consensus/status | jq

# Pending proposals
curl http://warmlogic:8080/api/v1/consensus/pending | jq '.count'

# Current round
curl http://warmlogic:8080/api/v1/consensus/round | jq
```

### 3. Check Node Health Across Cluster

```bash
# Check all nodes
for node in warmlogic-0 warmlogic-1 warmlogic-2; do
  echo "=== $node ==="
  curl -s "http://${node}:8080/health" | jq '.status'
done
```

## Root Cause Analysis

### Scenario A: Insufficient Peers (< 2f+1)

BFT requires at least 2f+1 nodes for consensus where f is the number of faulty nodes tolerated.

```bash
# Check peer count
PEERS=$(curl -s http://warmlogic:8080/api/v1/mesh/peers | jq '.count')
echo "Connected peers: $PEERS"

# Required for f=1: 3 nodes minimum
if [ "$PEERS" -lt 3 ]; then
  echo "INSUFFICIENT PEERS for BFT consensus"
fi
```

### Scenario B: Network Partition

```bash
# Check network latency between nodes
for node in warmlogic-0 warmlogic-1 warmlogic-2; do
  echo "Latency to $node:"
  ping -c 3 $node | tail -1
done

# Check for packet loss
for node in warmlogic-0 warmlogic-1 warmlogic-2; do
  echo "Packet loss to $node:"
  ping -c 10 $node | grep "packet loss"
done
```

### Scenario C: Leader Election Failed

```bash
# Check current leader
curl http://warmlogic:8080/api/v1/consensus/leader | jq

# Force leader rotation (use with caution)
curl -X POST http://warmlogic:8080/api/v1/consensus/rotate-leader
```

### Scenario D: Proposal Validation Failing

```bash
# Check for validation errors in logs
docker logs warmlogic_kernel 2>&1 | grep -i "proposal.*fail\|invalid\|reject"

# Check recent proposals
curl http://warmlogic:8080/api/v1/consensus/proposals?limit=10 | jq '.[] | {id, status, error}'
```

## Recovery Procedures

### Step 1: Restore Peer Connectivity

```bash
# Restart mesh discovery
curl -X POST http://warmlogic:8080/api/v1/mesh/rediscover

# Wait for peer discovery
sleep 30

# Verify
curl http://warmlogic:8080/api/v1/mesh/peers | jq '.count'
```

### Step 2: Reset Consensus State (Last Resort)

```bash
# This will abort pending proposals
curl -X POST http://warmlogic:8080/api/v1/consensus/reset \
  -H "X-Consensus-Reset-Token: $RESET_TOKEN"

# Verify consensus resumed
sleep 10
curl http://warmlogic:8080/api/v1/consensus/status | jq
```

### Step 3: Scale Up Nodes (If Insufficient)

```bash
# Kubernetes
kubectl scale deployment/warmlogic --replicas=5

# Docker Compose
docker compose up -d --scale warmlogic=5
```

## Verification

```bash
# Check rounds incrementing
watch -n 5 'curl -s http://warmlogic:8080/metrics | grep bft_rounds_total'

# Verify new proposals being processed
curl http://warmlogic:8080/api/v1/consensus/status | jq '.rounds_completed'
```

## Escalation

If consensus cannot be restored within 10 minutes:

1. Page consensus team on-call
2. Consider temporary single-node mode (degraded)
3. Notify stakeholders of governance delay

## Related Alerts

- `ConsensusLowPeerCount`
- `ConsensusHighRoundTime`
- `KernelDown`

---

*Last updated: 2026-02-13*
