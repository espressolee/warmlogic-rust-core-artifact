#!/usr/bin/env bash
set -euo pipefail

image="warm_logic_bridge_eval:local"
run_id="${1:-bridge_eval_v3_linux}"
repeats="${REPEATS:-3}"

docker build -f scripts/eval/Dockerfile.bridge_eval -t "${image}" .

docker run --rm \
  -v "$PWD:/work" \
  -w /work \
  "${image}" \
  "python3 --version \
   && rustc --version \
   && host_target=\$(rustc -vV | sed -n 's/^host: //p') \
   && echo docker_host_target=\${host_target} \
   && cd warm_logic_rs \
   && CARGO_TARGET_DIR=/tmp/target maturin build --release --target \${host_target} --out /tmp/wheels \
   && python3 -m pip install --force-reinstall /tmp/wheels/*.whl \
   && cd /work \
   && WARM_LOGIC_RS_USE_INSTALLED=1 python3 scripts/eval/eval_bridge_v3.py --run-id ${run_id} --repeats ${repeats}"

echo "Wrote: out/bridge_eval/${run_id}/full_telemetry.json"
