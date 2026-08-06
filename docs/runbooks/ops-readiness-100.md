# Ops Readiness 100 Runbook

## Goal
Provide deterministic commands for startup, health, diagnostics, and contract verification in the current `src` layout.

## Preconditions
- Run from repository root.
- Use virtual environment interpreter (`.venv/bin/python`).
- Export package path where required (`PYTHONPATH=src`).

## Gate 1: Version and Packaging Contract
```bash
PYTHONPATH=src .venv/bin/python -m warm_logic.app.cli.wlctl version
PYTHONPATH=src .venv/bin/python - <<'PY'
import warm_logic
from warm_logic.VERSION import __version__ as vmod
print(warm_logic.__version__)
print(vmod)
PY
```
Expected:
- `wlctl v...` line prints version from `src/warm_logic/VERSION`.
- `warm_logic.__version__` equals `warm_logic.VERSION.__version__`.

## Gate 2: CLI Entrypoint Contract
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts='' \
  tests/docs/test_documentation_examples.py::TestCLIImports::test_kernel_loop_entrypoint_import
```
Expected:
- `1 passed`.

## Gate 3: SDK Constructor Contract
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts='' \
  tests/docs/test_documentation_examples.py::TestSDKExamples::test_sovereign_client_host_port_compat
```
Expected:
- `1 passed`.

## Gate 4: Gateway ↔ Rust Contract
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts='' \
  tests/gateway/test_governance_contracts.py
```
Expected:
- All tests pass.

## Gate 5: Historical Regression Set
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts='' \
  tests/safety/test_watchdog.py::test_watchdog_kill \
  src/warm_logic/kernel/tests/integration/test_platform_saturation.py::TestDHTSaturationExtended::test_routing_table_bucket_split \
  src/warm_logic/kernel/tests/integration/test_absolute_truth_final.py::TestTotalCoverageAnnihilator::test_zanzibar_annihilation
```
Expected:
- `3 passed`.

## Gate 6: Rust Test Matrix
```bash
cd rust_core
cargo test --lib -q
cargo test --lib --features python -q
cd ..
```
Expected:
- Both commands pass.

## Gate 7: Operator Docs Smoke
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts='' \
  tests/docs/test_documentation_examples.py
```
Expected:
- All docs example tests pass.

## Failure Triage
- If `wlctl` cannot resolve version/module path, verify `PYTHONPATH=src`.
- If pytest complains about `--cov` addopts conflicts, use `-o addopts=''` for focused gates.
- If multiple pytest processes corrupt coverage DB, rerun sequentially with focused targets.
