# WarmLogic Troubleshooting Guide

> **Status**: research prototype. Not externally validated; see docs/CLAIM_EVIDENCE.md.
> Some issues may be due to the prototype nature of the software.

---

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Runtime Errors](#runtime-errors)
3. [Performance Problems](#performance-problems)
4. [Network Issues](#network-issues)
5. [Database Issues](#database-issues)
6. [SDK/API Errors](#sdkapi-errors)
7. [Common Error Messages](#common-error-messages)
8. [Diagnostic Commands](#diagnostic-commands)
9. [Getting Help](#getting-help)

---

## Installation Issues

### `maturin: command not found`

**Symptom**: `make setup` fails with maturin not found.

**Solution**:
```bash
# Activate virtual environment first
source .venv/bin/activate

# Install maturin
pip install maturin

# Retry setup
make setup
```

---

### `Cargo not found` or `rustc not found`

**Symptom**: Rust toolchain not installed.

**Solution**:
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Reload shell
source ~/.cargo/env

# Verify
rustc --version  # Should be 1.75+
```

---

### `Python.h not found`

**Symptom**: Compilation fails looking for Python headers.

**Solution**:
```bash
# Ubuntu/Debian
sudo apt install python3.12-dev

# macOS (Homebrew)
brew reinstall python@3.12

# Fedora
sudo dnf install python3.12-devel
```

---

### `OpenSSL not found`

**Symptom**: Rust compilation fails with OpenSSL errors.

**Solution**:
```bash
# Ubuntu/Debian
sudo apt install libssl-dev pkg-config

# macOS
brew install openssl
export OPENSSL_DIR=$(brew --prefix openssl)

# Fedora
sudo dnf install openssl-devel
```

---

### Rust compilation fails on Apple Silicon

**Symptom**: Build errors on M1/M2/M3 Macs.

**Solution**:
```bash
# Ensure correct target
rustup target add aarch64-apple-darwin

# Clean and rebuild
cd rust_core
cargo clean
maturin develop --release
```

---

### `Permission denied` during pip install

**Symptom**: Can't install packages.

**Solution**:
```bash
# Never use sudo pip. Use virtual environment.
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Runtime Errors

### `ModuleNotFoundError: No module named 'warm_logic_rs'`

**Symptom**: Rust core not loaded.

**Solution**:
```bash
# Rebuild Rust core
cd rust_core
maturin develop --release
cd ..

# Verify
python -c "import warm_logic_rs; print('OK')"
```

---

### `ImportError: cannot import name 'SovereignClient'`

**Symptom**: SDK import fails.

**Solution**:
```bash
# Reinstall in editable mode
pip install -e .

# Verify
python -c "from warm_logic.sdk import SovereignClient; print('OK')"
```

---

### Kernel won't start

**Symptom**: `wlctl start` hangs or fails.

**Diagnosis**:
```bash
# Confirm CLI wiring and version source
PYTHONPATH=src .venv/bin/python -m warm_logic.app.cli.wlctl version

# Confirm kernel entrypoint import contract
PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts='' \
  tests/docs/test_documentation_examples.py::TestCLIImports::test_kernel_loop_entrypoint_import

# Run foreground for direct traceback
PYTHONPATH=src .venv/bin/python -m warm_logic.app.cli.wlctl start --foreground

# Check runtime state artifact
ls -la .warm_logic/kernel.pid
```

---

### `VETO_LOCK` state stuck

**Symptom**: Kernel entered VETO_LOCK and won't recover.

**Solution**:
```bash
# Check current state
wlctl status

# Force recovery (if safe)
wlctl recover --force

# Or restart with clean state
wlctl stop
rm -rf ~/.warm_logic/state/
wlctl start
```

---

## Performance Problems

### Slow first operation

**Symptom**: First API call takes seconds.

**Cause**: JIT compilation and cache warming.

**Solution**: This is expected. Subsequent calls will be faster.

---

### High memory usage

**Symptom**: Process uses >2GB RAM.

**Diagnosis**:
```bash
# Check memory
ps aux | grep warm_logic

# Reduce batch size
export WARM_LOGIC_BATCH_SIZE=100
```

---

### Slow consensus

**Symptom**: BFT consensus takes >500ms.

**Diagnosis**:
```bash
# Check network latency
ping <peer_ip>

# Check node count
wlctl peers

# Reduce cluster size for testing
```

---

### Database slow

**Symptom**: Storage operations are slow.

**Solution**:
```bash
# Ensure SSD storage
df -h ~/.warm_logic

# Compact database
wlctl db compact

# Check disk I/O
iostat -x 1
```

---

## Network Issues

### Can't connect to peers

**Symptom**: `wlctl peers` shows 0 peers.

**Diagnosis**:
```bash
# Check if DHT is running
wlctl status

# Check firewall
sudo ufw status

# Allow DHT port
sudo ufw allow 4001/udp
```

---

### Bootstrap fails

**Symptom**: Can't join existing network.

**Solution**:
```bash
# Verify bootstrap node is reachable
nc -zv <bootstrap_ip> 4001

# Try manual bootstrap
wlctl bootstrap --peer <ip>:4001
```

---

### Messages not propagating

**Symptom**: Decisions don't reach all nodes.

**Diagnosis**:
```bash
# Check peer connections
wlctl peers --verbose

# Check message queue
wlctl queue status
```

---

## Database Issues

### `sled` corruption

**Symptom**: Database errors on startup.

**Solution**:
```bash
# Backup current state
cp -r ~/.warm_logic/sled ~/.warm_logic/sled.bak

# Attempt recovery
wlctl db recover

# Or start fresh (loses data)
rm -rf ~/.warm_logic/sled
wlctl init
```

---

### Out of disk space

**Symptom**: Write errors.

**Solution**:
```bash
# Check space
df -h ~/.warm_logic

# Prune old data
wlctl db prune --before 30d

# Move data directory
export WARM_LOGIC_ROOT=/new/location
```

---

### State inconsistency

**Symptom**: Hash chain validation fails.

**Solution**:
```bash
# Verify chain
wlctl verify --chain

# Replay from backup
wlctl restore --from /backup/location
```

---

## SDK/API Errors

### `ConnectionRefusedError`

**Symptom**: Can't connect to kernel.

**Solution**:
```python
# Check kernel is running
# wlctl status

# Verify host/port
client = SovereignClient(host="127.0.0.1", port=8000)
```

---

### `PolicyViolationError`

**Symptom**: Action rejected by policy.

**Solution**:
```python
# Check rejection reason
print(decision.rejection_reason)
print(decision.violated_policy)

# Review constitution.yaml
# Adjust policy or action
```

---

### `SignatureVerificationError`

**Symptom**: Signature validation fails.

**Diagnosis**:
```bash
# Check key validity
wlctl identity --verify

# Regenerate if corrupted
wlctl identity --regenerate
```

---

### Timeout errors

**Symptom**: Operations timeout.

**Solution**:
```python
# Increase timeout
client = SovereignClient(timeout=60)

# Or per-operation
decision = client.propose_action(..., timeout=30)
```

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `WARM-KEY-SIM-*` | Using simulated keys | Expected in dev; use real keys in prod |
| `Quorum not reached` | Not enough nodes | Add more nodes or reduce quorum |
| `Evidence bundle expired` | Old proof | Request fresh evidence |
| `Policy not found` | Missing constitution | Run `wlctl init` |
| `Ledger hash mismatch` | Corruption | Run `wlctl verify --repair` |

---

## Diagnostic Commands

### System Status

```bash
# Overall status
wlctl status

# Detailed health check
wlctl health --verbose

# Version info
wlctl version
```

### Logs

```bash
# View recent logs
wlctl logs --tail 100

# Follow logs
wlctl logs -f

# Debug level
WARM_LOGIC_LOG_LEVEL=DEBUG wlctl start
```

### Database

```bash
# Database stats
wlctl db stats

# Verify integrity
wlctl db verify

# Export for analysis
wlctl db export --format json > dump.json
```

### Network

```bash
# List peers
wlctl peers

# Network stats
wlctl network stats

# Test connectivity
wlctl ping <node_id>
```

### Python Diagnostics

```python
import warm_logic_rs as wl
import warm_logic

# Check Rust core
print(f"Rust version: {wl.__version__}")

# Check Python version
print(f"Python version: {warm_logic.__version__}")

# Run self-test
wl.self_test()
```

---

## Getting Help

### Before Asking

1. Check this guide
2. Check [FAQ.md](FAQ.md)
3. Search [GitHub Issues](https://github.com/espressolee/WarmLogic/issues)
4. Run diagnostics: `wlctl diagnose > report.txt`

### Reporting Issues

Include:
- WarmLogic version: `wlctl version`
- Python version: `python --version`
- Rust version: `rustc --version`
- OS and version
- Full error message
- Steps to reproduce
- Diagnostic output: `wlctl diagnose`

### Resources

- [GitHub Issues](https://github.com/espressolee/WarmLogic/issues)
- [GitHub Discussions](https://github.com/espressolee/WarmLogic/discussions)
- [FAQ](FAQ.md)
- [Installation Guide](INSTALLATION.md)

---

*Last updated: 2026-02-07*
