#!/usr/bin/env bash
# Single source of truth for the supported core path: local clean-checkout
# checks, CI, and external reproducers all call this. See STATUS.md and
# KNOWN_LIMITATIONS.md for what is and is not covered.
set -euo pipefail
PY="${PYTHON:-python3}"

echo "== rust: format check =="
( cd rust_core && cargo fmt --check )

echo "== rust: type-check the library (no link step; pyo3 needs the interpreter) =="
( cd rust_core && cargo check --lib --features python )

echo "== python: dev install =="
$PY -m pip install -e ".[dev]" >/dev/null

echo "== build+install the extension (maturin links against this interpreter) =="
# maturin is installed here, not assumed: this script is the single source of
# truth for the supported path, so it must work on a bare checkout.
$PY -m pip install -q maturin
# `maturin develop` requires an ACTIVE virtualenv and fails without one. A
# hosted CI runner and a plain system interpreter both have none, so `develop`
# only ever worked because the author's shell happened to be inside a venv.
# `build` + `pip install` is interpreter-explicit and works in both, which is
# the point: this script must be the procedure, not a procedure.
( cd rust_core && "$PY" -m maturin build --release --features python \
    --interpreter "$PY" --out ../dist )
$PY -m pip install --force-reinstall --no-deps dist/warm_logic_rs-*.whl

echo "== core tests (the supported subset, not the full legacy suite) =="
$PY -m pytest -q tests/ci tests/docs

echo "== documented sanity: ML-DSA-65 roundtrip =="
$PY -c "import warm_logic_rs as rs; pk,sk=rs.generate_keypair(); s=rs.sign(sk,'ci'); assert rs.verify(pk,'ci',s); print('core sanity OK: ML-DSA-65 sign+verify')"

echo "PASS: supported core surface"
