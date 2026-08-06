#!/usr/bin/env bash
set -euo pipefail

# Export a minimal, safe OSS subset from the private WarmLogic repo.
# Usage: scripts/oss/export_warmlogic_oss_v1.sh [OUTPUT_DIR]
# Default output dir: /tmp/WarmLogic-OSS-export

OSS_ROOT="${1:-/tmp/WarmLogic-OSS-export}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "[OSS export] Target: ${OSS_ROOT}"
rm -rf "${OSS_ROOT}"
mkdir -p "${OSS_ROOT}"

# 1) osctl core (toy subset)
echo "[OSS export] Copying osctl core (toy subset)…"
mkdir -p "${OSS_ROOT}/osctl"
cp -R "${REPO_ROOT}/warm_logic/osctl" "${OSS_ROOT}/osctl"

# 2) Example workload (toy OS v2)
echo "[OSS export] Copying toy OS v2 workload…"
mkdir -p "${OSS_ROOT}/osctl/examples/os_v2_toy/json_schemas"
cp "${REPO_ROOT}/docs/papers/reflective_os/os_v2/event_log_sample.jsonl" \
   "${OSS_ROOT}/osctl/examples/os_v2_toy/event_log_sample.jsonl"
cp "${REPO_ROOT}/docs/papers/reflective_os/os_v2/os_v2_config.yaml" \
   "${OSS_ROOT}/osctl/examples/os_v2_toy/os_v2_config.yaml"
cp "${REPO_ROOT}/docs/papers/reflective_os/os_v2/json_schemas/"*.json \
   "${OSS_ROOT}/osctl/examples/os_v2_toy/json_schemas/" || true

cat > "${OSS_ROOT}/osctl/examples/os_v2_toy/run_osctl.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"
OUT_DIR="$ROOT_DIR/out/osctl_runs_demo"
mkdir -p "$OUT_DIR"
python -m osctl.cli run \
  --config "$ROOT_DIR/osctl/examples/os_v2_toy/os_v2_config.yaml" \
  --events "$ROOT_DIR/osctl/examples/os_v2_toy/event_log_sample.jsonl" \
  --out-dir "$OUT_DIR" \
  --schemas-root "$ROOT_DIR/osctl/examples/os_v2_toy/json_schemas" \
  --run-id DEMO_RUN_001 --no-bundle
python -m osctl.cli verify \
  --run-id DEMO_RUN_001 \
  --out-dir "$OUT_DIR" \
  --schemas-root "$ROOT_DIR/osctl/examples/os_v2_toy/json_schemas"
EOF
chmod +x "${OSS_ROOT}/osctl/examples/os_v2_toy/run_osctl.sh"

# 3) Console (toy)
echo "[OSS export] Copying console backend/templates (toy)…"
mkdir -p "${OSS_ROOT}/console"
cp -R "${REPO_ROOT}/console" "${OSS_ROOT}/console"

# 4) Docs
echo "[OSS export] Copying docs…"
mkdir -p "${OSS_ROOT}/docs"
cp "${REPO_ROOT}/docs/oss/OSS_Overview_v1.md" "${OSS_ROOT}/docs/" || true
cp "${REPO_ROOT}/docs/runtime/Console_Product_Spec_v1.md" "${OSS_ROOT}/docs/Console_Overview_v1.md" || true
cp "${REPO_ROOT}/docs/runtime/Runtime_SLI_SLO_Spec_v1.md" "${OSS_ROOT}/docs/Runtime_SLI_SLO_Spec_v1.md" || true
cp "${REPO_ROOT}/docs/runtime/Quickstart_OSCTL_v1.md" "${OSS_ROOT}/docs/Quickstart_OSCTL_v1.md" || true

# 5) Top-level placeholders
echo "[OSS export] Creating top-level skeleton files…"
cat > "${OSS_ROOT}/README.md" <<'EOF'
(placeholder) See docs/OSS_Overview_v1.md in the private repo for the authoritative description.
EOF

cat > "${OSS_ROOT}/LICENSE" <<'EOF'
(placeholder) Replace with Apache-2.0 or chosen OSS license before publishing.
EOF

echo "[OSS export] Done. Exported to ${OSS_ROOT}"
