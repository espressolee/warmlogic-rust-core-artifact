# Runbook: Kernel Down

## Alert: KernelDown

**Severity**: Critical
**Component**: Kernel
**SLO Impact**: High - All governance decisions blocked

---

## Description

The WarmLogic Kernel is not responding to Prometheus scrapes. This indicates the kernel process has crashed, is unresponsive, or network connectivity is lost.

## Symptoms

- Alert: `KernelDown` firing
- No metrics being collected from kernel
- API endpoints returning 503/504
- BFT consensus stalled

## Immediate Actions

### 1. Check Kernel Process Status

```bash
# Docker
docker ps | grep warmlogic
docker logs warmlogic_kernel --tail 100

# Kubernetes
kubectl get pods -l app=warmlogic
kubectl logs -l app=warmlogic --tail=100
```

### 2. Check System Resources

```bash
# Memory
free -h
docker stats warmlogic_kernel --no-stream

# Disk
df -h /var/lib/warmlogic

# CPU
top -p $(pgrep -f warmlogic)
```

### 3. Check Network Connectivity

```bash
# From monitoring host
curl -v http://warmlogic:8080/health

# Check DNS
nslookup warmlogic

# Check port
nc -zv warmlogic 8080
```

## Recovery Procedures

### Scenario A: Process Crashed

```bash
# Restart container
docker restart warmlogic_kernel

# Or in Kubernetes
kubectl rollout restart deployment/warmlogic
```

### Scenario B: Out of Memory

```bash
# Check OOM kills
dmesg | grep -i "killed process"

# Increase memory limit
docker update --memory=4g warmlogic_kernel
```

### Scenario C: Disk Full

```bash
# Check disk usage
du -sh /var/lib/warmlogic/*

# Clean old evidence bundles (keep last 7 days)
find /var/lib/warmlogic/evidence -mtime +7 -delete

# Clean old logs
find /var/lib/warmlogic/logs -mtime +3 -delete
```

### Scenario D: Network Issues

```bash
# Check Docker network
docker network inspect warmlogic_net

# Recreate network if needed
docker network disconnect warmlogic_net warmlogic_kernel
docker network connect warmlogic_net warmlogic_kernel
```

## Verification

After recovery, verify kernel health:

```bash
# Health endpoint
curl http://warmlogic:8080/health

# Metrics endpoint
curl http://warmlogic:8080/metrics | head -20

# BFT status
curl http://warmlogic:8080/api/v1/consensus/status
```

## Escalation

If kernel cannot be recovered within 15 minutes:

1. Page on-call engineer
2. Create incident in PagerDuty
3. Escalate to Kernel team lead

## Related Alerts

- `KernelHighLatency`
- `KernelMemoryHigh`
- `ConsensusStalled`

---

*Last updated: 2026-02-13*
