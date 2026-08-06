#!/usr/bin/env bash
set -euo pipefail

# Paper 09 reproduction script (host).
#
# Generates:
# - Patched telemetry (macOS host): out/bridge_eval/bridge_eval_v3_pyo3_patch/full_telemetry.json
# - Stock telemetry (macOS host):   out/bridge_eval/bridge_eval_v3_stock_pyo3/full_telemetry.json
# - Multi-host combined telemetry:  out/bridge_eval/multi_host/combined.json (Table 1 input)
# - Vec<u8> semantics checks:       out/bridge_eval/vec_u8_semantics_{stock,patched}_macos_arm64/vec_u8_semantics.json
# - Socket ingest workload:         out/bridge_eval/socket_kv_{stock,patched}_macos_arm64/socket_kv_telemetry.json
# - E2E bytes telemetry:            out/bridge_eval/e2e_bytes_macos_arm64/e2e_bytes_telemetry.json
# - Cache effects:                  out/bridge_eval/cache_effects/cache_effects.json
# - HTTP server load (Table 16):    out/bridge_eval/http_server_load_{stock,patched}_macos_arm64/http_server_load_telemetry.json
# - Figures: src/warm_logic/docs/papers/09_boundary_elimination/figures/*.svg
# - Auto-updated tables in paper.md (Table 1–21 markers)
#
# Optional:
# - RUN_DOCKER=1 to (re)generate Linux/Docker telemetry for Table 1.
# - RUN_FASTAPI=1 to (re)generate the ASGI workload (Table 18; requires pip/network).
# - RUN_PYO3_PREVALENCE=1 to (re)generate the crates.io snapshot scan (Table 19; requires network).
# - RUN_ECOSYSTEM_CASES=1 to (re)generate ecosystem case studies (Tables 20–21; requires network for build deps).

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

REPEATS="${REPEATS:-5}"
WARMUP="${WARMUP:-200}"
RUN_DOCKER="${RUN_DOCKER:-0}"
RUN_FASTAPI="${RUN_FASTAPI:-0}"
RUN_PYO3_PREVALENCE="${RUN_PYO3_PREVALENCE:-0}"
RUN_ECOSYSTEM_CASES="${RUN_ECOSYSTEM_CASES:-0}"
PYO3_PREVALENCE_LIMIT="${PYO3_PREVALENCE_LIMIT:-500}"
PYO3_PREVALENCE_OUT="${PYO3_PREVALENCE_OUT:-out/bridge_eval/pyo3_vec_u8_prevalence/pyo3_vec_u8_prevalence_top500.json}"

echo "[paper09] REPEATS=$REPEATS WARMUP=$WARMUP RUN_DOCKER=$RUN_DOCKER RUN_FASTAPI=$RUN_FASTAPI RUN_PYO3_PREVALENCE=$RUN_PYO3_PREVALENCE RUN_ECOSYSTEM_CASES=$RUN_ECOSYSTEM_CASES"

echo
echo "[paper09] Collect patched telemetry..."
python3 scripts/eval/collect_patched_pyo3_telemetry.py \
  --run-id bridge_eval_v3_pyo3_patch \
  --repeats "$REPEATS" \
  --warmup "$WARMUP"

echo
echo "[paper09] Verify Vec<u8> extraction semantics (patched)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/verify_paper09_vec_u8_semantics.py \
  --run-id vec_u8_semantics_patched_macos_arm64

echo
echo "[paper09] Collect stock telemetry..."
python3 scripts/eval/collect_stock_pyo3_telemetry.py \
  --run-id bridge_eval_v3_stock_pyo3 \
  --repeats "$REPEATS" \
  --warmup "$WARMUP" \
  --pyo3-version 0.22.6

echo
echo "[paper09] Verify Vec<u8> extraction semantics (stock)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_stock_pyo3_venv/bin/python \
  scripts/eval/verify_paper09_vec_u8_semantics.py \
  --run-id vec_u8_semantics_stock_macos_arm64

echo
echo "[paper09] SovereignKV workload (stock)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_stock_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_sovereignkv.py \
  --run-id sovkv_stock_macos_arm64 \
  --repeats "$REPEATS" \
  --warmup-ops 100 \
  --ops 1000 \
  --keys 64 \
  --size 1000000

echo
echo "[paper09] SovereignKV workload (patched)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_sovereignkv.py \
  --run-id sovkv_patched_macos_arm64 \
  --repeats "$REPEATS" \
  --warmup-ops 100 \
  --ops 1000 \
  --keys 64 \
  --size 1000000

echo
echo "[paper09] Socket ingest → SovereignKV (stock)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_stock_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_socket_kv.py \
  --run-id socket_kv_stock_macos_arm64 \
  --repeats "$REPEATS" \
  --warmup-messages 50 \
  --messages 1000 \
  --keys 64 \
  --size 1000000

echo
echo "[paper09] Socket ingest → SovereignKV (patched)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_socket_kv.py \
  --run-id socket_kv_patched_macos_arm64 \
  --repeats "$REPEATS" \
  --warmup-messages 50 \
  --messages 1000 \
  --keys 64 \
  --size 1000000

echo
echo "[paper09] Socket mux ingest → SovereignKV (stock)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_stock_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_socket_mux_kv.py \
  --run-id socket_mux_kv_stock_macos_arm64 \
  --repeats "$REPEATS" \
  --conns 8 \
  --warmup-frames-per-conn 50 \
  --frames-per-conn 200 \
  --keys 256 \
  --size 1000000

echo
echo "[paper09] Socket mux ingest → SovereignKV (patched)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_socket_mux_kv.py \
  --run-id socket_mux_kv_patched_macos_arm64 \
  --repeats "$REPEATS" \
  --conns 8 \
  --warmup-frames-per-conn 50 \
  --frames-per-conn 200 \
  --keys 256 \
  --size 1000000

echo
echo "[paper09] Vec<u8> input-variant ablation (stock)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_stock_pyo3_venv/bin/python \
  scripts/eval/eval_vec_u8_input_variants.py \
  --run-id vec_u8_input_variants_stock \
  --repeats "$REPEATS" \
  --warmup "$WARMUP" \
  --iterations 200 \
  --batch 1 \
  --size 10000000

echo
echo "[paper09] Vec<u8> input-variant ablation (patched)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_vec_u8_input_variants.py \
  --run-id vec_u8_input_variants_patched \
  --repeats "$REPEATS" \
  --warmup "$WARMUP" \
  --iterations 200 \
  --batch 1 \
  --size 10000000

echo
echo "[paper09] Run E2E bytes pipeline (patched wheel)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_e2e_bytes_pipeline.py \
  --run-id e2e_bytes_macos_arm64 \
  --repeats "$REPEATS" \
  --warmup 10

echo
echo "[paper09] Cache effects (patched wheel)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_cache_effects.py

echo
echo "[paper09] C-API contiguous-copy anchor (patched wheel)..."
out/bridge_eval/_patched_pyo3_venv/bin/python -m pip install -e scripts/eval/capi_baseline >/dev/null
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_capi_anchor.py \
  --run-id capi_anchor_macos_arm64 \
  --repeats "$REPEATS" \
  --warmup "$WARMUP" \
  --size 10000000

echo
echo "[paper09] GIL release trade-off microbench (patched wheel)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_gil_tradeoff.py \
  --run-id gil_tradeoff_macos_arm64 \
  --repeats "$REPEATS" \
  --warmup "$WARMUP" \
  --iterations 200 \
  --batch 1 \
  --size 10000000 \
  --out out/bridge_eval/gil_tradeoff/gil_tradeoff.json

echo
echo "[paper09] GIL concurrency benchmark (stock)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_stock_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_gil_concurrency.py \
  --run-id gil_concurrency_stock_macos_arm64 \
  --repeats "$REPEATS" \
  --size 10000000 \
  --threads 1,8 \
  --warmup-calls-per-thread 20 \
  --calls-per-thread 100 \
  --out out/bridge_eval/gil_concurrency_stock_macos_arm64/gil_concurrency.json

echo
echo "[paper09] GIL concurrency benchmark (patched)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_gil_concurrency.py \
  --run-id gil_concurrency_patched_macos_arm64 \
  --repeats "$REPEATS" \
  --size 10000000 \
  --threads 1,8 \
  --warmup-calls-per-thread 20 \
  --calls-per-thread 100 \
  --out out/bridge_eval/gil_concurrency_patched_macos_arm64/gil_concurrency.json

echo
echo "[paper09] Socket server sustained-load benchmark (stock)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_stock_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_socket_server_load.py \
  --run-id socket_server_load_stock_macos_arm64 \
  --out-root out \
  --repeats "$REPEATS" \
  --conns 4 \
  --payload-bytes 100000 \
  --warmup-msgs-per-conn 10 \
  --msgs-per-conn 100 \
  --rate-hz 50.0 \
  --timeout-s 60 \
  --apis recv_only,set_bytesvec,set_vec

echo
echo "[paper09] Socket server sustained-load benchmark (patched)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_socket_server_load.py \
  --run-id socket_server_load_patched_macos_arm64 \
  --out-root out \
  --repeats "$REPEATS" \
  --conns 4 \
  --payload-bytes 100000 \
  --warmup-msgs-per-conn 10 \
  --msgs-per-conn 100 \
  --rate-hz 50.0 \
  --timeout-s 60 \
  --apis recv_only,set_bytesvec,set_vec

echo
echo "[paper09] HTTP server sustained-load benchmark (stock)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_stock_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_http_server_load.py \
  --run-id http_server_load_stock_macos_arm64 \
  --out-root out \
  --repeats "$REPEATS" \
  --conns 4 \
  --payload-bytes 100000 \
  --warmup-msgs-per-conn 10 \
  --msgs-per-conn 100 \
  --rate-hz 50.0 \
  --timeout-s 60 \
  --apis recv_only,set_bytesvec,set_vec

echo
echo "[paper09] HTTP server sustained-load benchmark (patched)..."
WARM_LOGIC_RS_USE_INSTALLED=1 \
  out/bridge_eval/_patched_pyo3_venv/bin/python \
  scripts/eval/eval_paper09_http_server_load.py \
  --run-id http_server_load_patched_macos_arm64 \
  --out-root out \
  --repeats "$REPEATS" \
  --conns 4 \
  --payload-bytes 100000 \
  --warmup-msgs-per-conn 10 \
  --msgs-per-conn 100 \
  --rate-hz 50.0 \
  --timeout-s 60 \
  --apis recv_only,set_bytesvec,set_vec

if [[ "$RUN_FASTAPI" == "1" ]]; then
  echo
  echo "[paper09] FastAPI+uvicorn sustained-load benchmark (stock)..."
  if out/bridge_eval/_stock_pyo3_venv/bin/python -m pip install --quiet fastapi==0.128.0 uvicorn==0.40.0; then
    WARM_LOGIC_RS_USE_INSTALLED=1 \
      out/bridge_eval/_stock_pyo3_venv/bin/python \
      scripts/eval/eval_paper09_fastapi_server_load.py \
      --run-id fastapi_server_load_stock_macos_arm64 \
      --out-root out \
      --repeats "$REPEATS" \
      --conns 4 \
      --payload-bytes 100000 \
      --warmup-msgs-per-conn 10 \
      --msgs-per-conn 100 \
      --rate-hz 50.0 \
      --timeout-s 60 \
      --apis recv_only,set_bytesvec,set_vec
  else
    echo "[paper09] WARN: pip install failed (stock venv); skipping FastAPI workload."
  fi

  echo
  echo "[paper09] FastAPI+uvicorn sustained-load benchmark (patched)..."
  if out/bridge_eval/_patched_pyo3_venv/bin/python -m pip install --quiet fastapi==0.128.0 uvicorn==0.40.0; then
    WARM_LOGIC_RS_USE_INSTALLED=1 \
      out/bridge_eval/_patched_pyo3_venv/bin/python \
      scripts/eval/eval_paper09_fastapi_server_load.py \
      --run-id fastapi_server_load_patched_macos_arm64 \
      --out-root out \
      --repeats "$REPEATS" \
      --conns 4 \
      --payload-bytes 100000 \
      --warmup-msgs-per-conn 10 \
      --msgs-per-conn 100 \
      --rate-hz 50.0 \
      --timeout-s 60 \
      --apis recv_only,set_bytesvec,set_vec
  else
    echo "[paper09] WARN: pip install failed (patched venv); skipping FastAPI workload."
  fi
else
  echo
  echo "[paper09] Skipping FastAPI workload (set RUN_FASTAPI=1 to run)."
fi

if [[ "$RUN_DOCKER" == "1" ]]; then
  echo
  echo "[paper09] Linux/Docker telemetry..."
  bash scripts/eval/run_bridge_eval_docker.sh bridge_eval_v3_linux
else
  echo
  echo "[paper09] Skipping Linux/Docker telemetry (set RUN_DOCKER=1 to run)."
fi

echo
echo "[paper09] Rebuild multi-host combined telemetry (Table 1 input)..."
linux_telemetry="out/bridge_eval/bridge_eval_v3_linux/full_telemetry.json"
x86_telemetry="out/bridge_eval/x86_64_patched_pyo3/full_telemetry.json"
x86_pack="out/bridge_eval/x86_64_cloud_pack.tgz"

merge_inputs=(out/bridge_eval/bridge_eval_v3_pyo3_patch/full_telemetry.json)

if [[ -f "${linux_telemetry}" ]]; then
  merge_inputs+=("${linux_telemetry}")
else
  echo "[paper09] WARN: missing ${linux_telemetry} (multi-host table will omit Linux/Docker)"
fi

if [[ -f "${x86_telemetry}" ]]; then
  merge_inputs+=("${x86_telemetry}")
elif [[ -f "${x86_pack}" ]]; then
  merge_inputs+=("${x86_pack}")
else
  echo "[paper09] WARN: missing x86_64 telemetry input (multi-host table will omit x86_64)"
  echo "[paper09]       See: src/warm_logic/docs/papers/09_boundary_elimination/cloud_x86_64_vm_guide.md"
fi

python3 scripts/eval/merge_bridge_telemetry.py "${merge_inputs[@]}" --out out/bridge_eval/multi_host/combined.json

echo
echo "[paper09] Scaling classification (patched)..."
python3 scripts/eval/classify_bridge_scaling.py \
  --input out/bridge_eval/bridge_eval_v3_pyo3_patch/full_telemetry.json \
  --out out/bridge_eval/classification/bridge_eval_v3_pyo3_patch.json

echo
echo "[paper09] Regenerate figures..."
python3 scripts/eval/plot_bridge_svg.py \
  --input out/bridge_eval/bridge_eval_v3_pyo3_patch/full_telemetry.json \
  --out-dir src/warm_logic/docs/papers/09_boundary_elimination/figures
python3 scripts/eval/plot_vec_u8_stock_vs_patched_svg.py
python3 scripts/eval/plot_vec_u8_stock_vs_patched_svg.py \
  --stat p99 \
  --out src/warm_logic/docs/papers/09_boundary_elimination/figures/fig_vec_u8_stock_vs_patched_p99.svg
python3 scripts/eval/plot_pyo3_patch_effect_svg.py

if [[ "$RUN_PYO3_PREVALENCE" == "1" ]]; then
  echo
  echo "[paper09] PyO3 Vec<u8> prevalence snapshot (Table 19; crates.io scan)..."
  if python3 -u scripts/eval/scan_pyo3_vec_u8_prevalence.py --limit "$PYO3_PREVALENCE_LIMIT" --out "$PYO3_PREVALENCE_OUT"; then
    echo "[paper09] Prevalence snapshot written: $PYO3_PREVALENCE_OUT"
  else
    echo "[paper09] WARN: prevalence scan failed; keeping existing snapshot (if any)."
  fi
else
  echo
  echo "[paper09] Skipping prevalence scan (set RUN_PYO3_PREVALENCE=1 to run)."
fi

if [[ "$RUN_ECOSYSTEM_CASES" == "1" ]]; then
  echo
  echo "[paper09] Ecosystem case studies (Tables 20–21; may require network for build deps)..."
  if python3 scripts/eval/eval_paper09_rust_strings_case.py; then
    echo "[paper09] rust-strings case study done."
  else
    echo "[paper09] WARN: rust-strings case study failed; keeping existing artifact (if any)."
  fi
  if python3 scripts/eval/eval_paper09_vtracer_case.py; then
    echo "[paper09] vtracer case study done."
  else
    echo "[paper09] WARN: vtracer case study failed; keeping existing artifact (if any)."
  fi
else
  echo
  echo "[paper09] Skipping ecosystem case studies (set RUN_ECOSYSTEM_CASES=1 to run)."
fi

echo
echo "[paper09] Update paper tables from telemetry..."
python3 scripts/eval/update_paper09_tables.py

echo
echo "[paper09] DONE"
