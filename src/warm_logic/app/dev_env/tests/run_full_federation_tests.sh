#!/usr/bin/env bash
# ==========================================================
# File: run_full_federation_tests.sh
# Project: Warm Logic — DevEnv
# Purpose:
#   Mega-suite runner for DevEnv v1.6:
#     - Start wl_eventbus in background
#     - Run all unit + federation tests
#     - Stop EventBus cleanly
#
# Usage:
#   cd dev_env
#   chmod +x dev_env/tests/run_full_federation_tests.sh
#   dev_env/tests/run_full_federation_tests.sh
# ==========================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[MegaSuite] Warm Logic DevEnv v1.6 test run"
echo "[MegaSuite] ROOT=${ROOT}"

EVENTBUS_LOG="${ROOT}/eventbus_test.log"
EVENTBUS_PID=""

start_eventbus() {
  echo "[MegaSuite] starting wl_eventbus ..."
  wl_eventbus >"${EVENTBUS_LOG}" 2>&1 &
  EVENTBUS_PID=$!
  echo "[MegaSuite] wl_eventbus pid=${EVENTBUS_PID}"

  # wait for /health
  python3 - << 'EOF'
import json, time, urllib.request

for _ in range(20):
    try:
        data = urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=0.5).read()
        j = json.loads(data.decode("utf-8"))
        if j.get("status") == "ok":
            print("[MegaSuite] EventBus is up")
            break
    except Exception:
        time.sleep(0.3)
else:
    raise SystemExit("[MegaSuite] EventBus /health did not respond")
EOF
}

stop_eventbus() {
  if [ -n "${EVENTBUS_PID:-}" ]; then
    echo "[MegaSuite] stopping wl_eventbus (pid=${EVENTBUS_PID})"
    kill "${EVENTBUS_PID}" 2>/dev/null || true
    sleep 1
    if ps -p "${EVENTBUS_PID}" >/dev/null 2>&1; then
      echo "[MegaSuite] force killing wl_eventbus"
      kill -9 "${EVENTBUS_PID}" 2>/dev/null || true
    fi
  fi
}

trap stop_eventbus EXIT

start_eventbus

echo "[MegaSuite] running pytest suites ..."
cd "${ROOT}"

 # Run canonical v1.6 federation + eventbus suites
pytest \
  "${ROOT}/tests/test_paths.py" \
  "${ROOT}/tests/test_eventbus_router.py" \
  "${ROOT}/tests/test_eventbus_transports.py" \
  "${ROOT}/tests/test_eventbus_integration.py" \
  "${ROOT}/tests/test_eventbus_load.py" \
  "${ROOT}/tests/test_multi_node_routing.py" \
  "${ROOT}/tests/test_watcher_and_agent_stream.py" \
  "${ROOT}/tests/test_federation_bootstrap.py" \
  "${ROOT}/tests/test_cluster_manager.py" \
  "${ROOT}/tests/test_federation_router.py" \
  "${ROOT}/tests/test_federation_router_integration.py" \
  "${ROOT}/tests/test_agent_proxy.py"

echo "[MegaSuite] all tests completed"
