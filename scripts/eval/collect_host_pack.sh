#!/usr/bin/env bash
set -euo pipefail

run_prefix="${1:-host_run}"
repeats="${REPEATS:-3}"
py="python3"

echo "=== Host info ==="
python3 --version
uname -a
echo "machine: $(uname -m)"
echo "os-release:"
cat /etc/os-release 2>/dev/null || true
echo

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "=== Build + install wheel (patched PyO3, isolated venv) ==="
  # IMPORTANT: build from a clean staging copy (see collect_patched_pyo3_telemetry.py) to avoid
  # accidentally packaging local artifacts (e.g., stray CFFI wrappers) which can shadow the
  # extension module at import time.
  python3 scripts/eval/collect_patched_pyo3_telemetry.py \
    --run-id "${run_prefix}_bootstrap" \
    --repeats 1 \
    --warmup 0
  py="out/bridge_eval/_patched_pyo3_venv/bin/python"
elif [[ -x "out/bridge_eval/_patched_pyo3_venv/bin/python" ]]; then
  py="out/bridge_eval/_patched_pyo3_venv/bin/python"
else
  echo "ERROR: SKIP_BUILD=1 but out/bridge_eval/_patched_pyo3_venv/bin/python is missing"
  exit 1
fi
export WARM_LOGIC_RS_USE_INSTALLED=1

echo "=== Run bridge eval ==="
"${py}" scripts/eval/eval_bridge_v3.py --run-id "${run_prefix}_bridge" --repeats "${repeats}"

echo "=== Run cache effects (10MB) ==="
"${py}" scripts/eval/eval_cache_effects.py --run-id "${run_prefix}_cache_10mb" --size 10000000 --pool-count 16 --iterations 100 --warmup 20

echo "=== Run scaling classifier ==="
"${py}" scripts/eval/classify_bridge_scaling.py \
  --input "out/bridge_eval/${run_prefix}_bridge/full_telemetry.json" \
  --out "out/bridge_eval/classification/${run_prefix}_bridge.json"

echo "=== Pack results ==="
out_dir="out/bridge_eval/${run_prefix}_pack"
mkdir -p "${out_dir}"

host_info="${out_dir}/host_info.txt"
git_rev="$(git rev-parse HEAD 2>/dev/null || true)"
if [[ -z "${git_rev}" ]]; then
  git_rev="(not a git repo)"
fi
{
  echo "git: ${git_rev}"
  echo
  echo "python (system): $(python3 --version 2>&1 || true)"
  echo "python (eval): $("${py}" --version 2>&1 || true)"
  echo "uname: $(uname -a 2>&1 || true)"
  echo "machine: $(uname -m 2>&1 || true)"
  echo "machine-id (/etc/machine-id): $(cat /etc/machine-id 2>/dev/null || true)"
  echo "machine-id (/var/lib/dbus/machine-id): $(cat /var/lib/dbus/machine-id 2>/dev/null || true)"
  echo "dmi product_uuid: $(cat /sys/class/dmi/id/product_uuid 2>/dev/null || true)"
  echo
  echo "os-release:"
  cat /etc/os-release 2>/dev/null || true
  echo
  echo "rustc: $(rustc --version 2>&1 || true)"
  echo "cargo: $(cargo --version 2>&1 || true)"
  echo "maturin (eval): $("${py}" -m maturin --version 2>&1 || true)"
  echo "pip (system): $(python3 -m pip --version 2>&1 || true)"
  echo "pip (eval): $("${py}" -m pip --version 2>&1 || true)"
  echo
  echo "cloud metadata (best effort):"
  if command -v curl >/dev/null 2>&1; then
    echo "gcp instance id: $(curl -fsS --max-time 0.3 -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/id 2>/dev/null || true)"
    echo "gcp instance name: $(curl -fsS --max-time 0.3 -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/name 2>/dev/null || true)"
    echo "gcp machine type: $(curl -fsS --max-time 0.3 -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/machine-type 2>/dev/null || true)"
    echo "gcp zone: $(curl -fsS --max-time 0.3 -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/zone 2>/dev/null || true)"

    aws_token="$(curl -fsS --max-time 0.3 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' 2>/dev/null || true)"
    if [[ -n "${aws_token}" ]]; then
      echo "aws instance id: $(curl -fsS --max-time 0.3 -H \"X-aws-ec2-metadata-token: ${aws_token}\" http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || true)"
      echo "aws instance type: $(curl -fsS --max-time 0.3 -H \"X-aws-ec2-metadata-token: ${aws_token}\" http://169.254.169.254/latest/meta-data/instance-type 2>/dev/null || true)"
    else
      echo "aws instance id: $(curl -fsS --max-time 0.3 http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || true)"
      echo "aws instance type: $(curl -fsS --max-time 0.3 http://169.254.169.254/latest/meta-data/instance-type 2>/dev/null || true)"
    fi

    echo "azure instance metadata (truncated):"
    curl -fsS --max-time 0.3 -H Metadata:true "http://169.254.169.254/metadata/instance?api-version=2021-02-01" 2>/dev/null | head -c 4000 || true
    echo
  else
    echo "curl not found; skipping cloud metadata probes"
  fi
  echo
  echo "lscpu:"
  lscpu 2>/dev/null || true
  echo
  echo "virt:"
  systemd-detect-virt 2>/dev/null || true
} >"${host_info}"

cp "out/bridge_eval/${run_prefix}_bridge/full_telemetry.json" "${out_dir}/"
cp "out/bridge_eval/cache_effects/${run_prefix}_cache_10mb.json" "${out_dir}/"
cp "out/bridge_eval/classification/${run_prefix}_bridge.json" "${out_dir}/"

tar_path="out/bridge_eval/${run_prefix}_pack.tgz"
COPYFILE_DISABLE=1 tar -czf "${tar_path}" -C "${out_dir}" .

echo "Wrote: ${tar_path}"
