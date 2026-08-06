#!/usr/bin/env bash
set -euo pipefail

echo "[osctl-sanity] validating CLI entrypoints"
python - <<'PY'
import importlib

wlctl = importlib.import_module("warm_logic.app.cli.wlctl")
assert hasattr(wlctl, "main"), "warm_logic.app.cli.wlctl.main is missing"
print("[osctl-sanity] warm_logic.app.cli.wlctl import OK")
PY

echo "[osctl-sanity] done"

