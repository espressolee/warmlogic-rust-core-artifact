# WarmLogic Operations Runbook

> **Version**: 1.0.0
> **Updated**: 2026-02-10
> **Band**: P4xx (DevOps)

## Quick Reference

### System Health Check

```bash
# 1. Check Rust Core
python3 -c "import warm_logic_rs; print('Rust Core Active')"

# 2. Run fast tests
pytest -m "not slow" -x

# 3. Check coverage
pytest --cov=warm_logic --cov-report=term-missing

# 4. Verify pre-commit
pre-commit run --all-files
```

### Build & Deploy

```bash
# Rebuild Rust Core
cd warm_logic_rs && maturin develop --release

# Install Python deps
pip install -r requirements.txt

# Run gateway
python -m warm_logic.gateway
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WARMLOGIC_API_KEY` | API authentication key | Required |
| `WARMLOGIC_DEBUG` | Enable debug mode (0/1) | 0 |
| `WARMLOGIC_CORS_ORIGINS` | CORS allowed origins | localhost only |
| `ENVIRONMENT` | Deployment environment | development |
| `WARM_LOGIC_LICENSE_KEY` | Enterprise license | None |
| `WARMLOGIC_COMMAND_CENTER` | External data path | ./external/command_center |

## Security Checklist

### Pre-Deployment

- [ ] `WARMLOGIC_DEBUG=0` in production
- [ ] `ENVIRONMENT=production` set
- [ ] `WARMLOGIC_CORS_ORIGINS` explicitly configured
- [ ] API key is secure and rotated
- [ ] No absolute paths in code
- [ ] All tests passing

### Runtime Monitoring

- [ ] Gateway health: `GET /health`
- [ ] Liveness probe: `GET /health/live`
- [ ] Readiness probe: `GET /health/readiness`
- [ ] Prometheus metrics: `GET /metrics`

## Incident Response

### Gateway Not Responding

1. Check liveness: `curl http://localhost:8000/health/live`
2. Check logs: `journalctl -u warmlogic-gateway`
3. Restart: `systemctl restart warmlogic-gateway`

### High Latency

1. Check Prometheus metrics
2. Verify mesh connectivity
3. Check Rust Core status

### Authentication Failures

1. Verify API key configuration
2. Check CORS origins
3. Review gateway logs for SEC-* errors

## P-Series Protocol

All commits must follow P-Series bands:

| Band | Description |
|------|-------------|
| P0xx | Foundation & Identity |
| P1xx | Consensus & Ledger |
| P2xx | Mesh & Networking |
| P3xx | Governance & Sovereignty |
| P4xx | DevOps |

Example: `git commit -m "P3xx: fix governance policy loader"`

## Troubleshooting Guide

### Common Issues

#### 1. Rust Core Import Fails

```bash
# Error: ModuleNotFoundError: No module named 'warm_logic_rs'

# Fix: Rebuild Rust core
cd warm_logic_rs && maturin develop
```

#### 2. Mesh Connection Issues

```bash
# Check peer connectivity
python -c "from warm_logic.kernel.mesh.peers import PeerManager; pm = PeerManager(); print(pm.get_active_peers())"

# Verify network topology
curl http://localhost:8000/api/mesh/topology
```

#### 3. Kernel Loop Deadlock

Symptoms: High CPU, no responses, kernel tick() not progressing.

Recovery steps:
1. Check daemon status: `ps aux | grep sovereign_daemon`
2. Force restart: `kill -9 <pid> && python -m warm_logic.app.cli.sovereign_daemon`
3. Review logs for lock contention
4. Check consensus state: verify quorum is met

#### 4. Policy Validation Failures

```bash
# Validate governance policy
python -c "from warm_logic.config.loader import PolicyValidator; PolicyValidator().validate('config/governance_policy.yaml')"

# Check for schema mismatches
grep -r "schema_version" config/
```

### Escalation Procedures

#### P0 Incidents (Critical)

| Symptom | Action | Timeout |
|---------|--------|---------|
| Complete outage | Page on-call, activate DR | Immediate |
| Data corruption | Stop writes, snapshot state | 5 min |
| Security breach | Isolate system, notify security | Immediate |

#### P1 Incidents (High)

| Symptom | Action | Timeout |
|---------|--------|---------|
| Partial degradation | Investigate, prepare rollback | 15 min |
| Consensus failure | Rebuild quorum, verify state | 30 min |
| High error rate | Analyze logs, identify root cause | 30 min |

### Rollback Procedures

#### Failed Patch Rollback

```bash
# 1. Identify last good commit
git log --oneline -10

# 2. Create rollback branch
git checkout -b rollback/<issue-id>

# 3. Revert to last good state
git revert HEAD~<n>..HEAD

# 4. Test before deploying
pytest -m "not slow" -x

# 5. Deploy with verification
./scripts/deploy.sh --verify
```

#### Consensus State Recovery

1. Stop all kernel instances
2. Backup current state: `cp -r data/consensus data/consensus.bak`
3. Identify last valid checkpoint
4. Restore from checkpoint
5. Verify quorum before resuming

### Monitoring Alerts

| Alert | Threshold | Response |
|-------|-----------|----------|
| HighLatencyP99 | >500ms | Scale pods, check mesh |
| ErrorRateHigh | >1% | Review logs, check deps |
| MemoryPressure | >80% | Restart pod, check leaks |
| DiskSpaceLow | >90% | Clean logs, archive data |
| ConsensusStale | >5 min | Check peer connectivity |

### Learning Modules Data Paths

| Module | Env Variable | Default |
|--------|--------------|---------|
| Experience Replay | `WL_EXPERIENCE_PATH` | ./data/experiences |
| Feedback Memory | `WL_FEEDBACK_PATH` | ./data/feedback |
| Preferences | `WL_PREFS_PATH` | ./data/preferences |

## Contact

- **Repository**: WarmLogic
- **Era**: 4000 ()
- **Maintainers**: espressolee
