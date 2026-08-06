#!/usr/bin/env bash
set -euo pipefail

rm -rf dist build
python -m pip wheel . -w dist --no-deps --no-build-isolation >/dev/null
wheel_path=$(ls dist/warm_logic-*.whl | head -n 1)
if [[ -z "${wheel_path}" ]]; then
  echo "[run_packaging_checks] Wheel not found in dist/" >&2
  exit 1
fi
site_dir=$(mktemp -d /tmp/wlctl-site-XXXX)
base_dir=$(mktemp -d /tmp/wlctl-ci-XXXX)
cleanup() {
  rm -rf "$site_dir" "$base_dir"
}
trap cleanup EXIT
python - "$wheel_path" "$site_dir" <<'PY'
import sys, zipfile
wheel = sys.argv[1]
target = sys.argv[2]
with zipfile.ZipFile(wheel) as zf:
    zf.extractall(target)
PY
PYTHONPATH="$site_dir${PYTHONPATH:+:$PYTHONPATH}" python -m warm_logic.cli.wlctl init --base "$base_dir" >/dev/null
PYTHONPATH="$site_dir${PYTHONPATH:+:$PYTHONPATH}" python -m warm_logic.cli.wlctl run-dev --base "$base_dir" --no-write >/dev/null
PYTHONPATH="$site_dir${PYTHONPATH:+:$PYTHONPATH}" python -m warm_logic.cli.wlctl research validate-actuation-logs \
  --sample-dir "$(pwd)/out/actuation/rehearsals" >/dev/null
PYTHONPATH="$site_dir${PYTHONPATH:+:$PYTHONPATH}" python -m warm_logic.cli.wlctl research validate-autonomy-episodes \
  --sample-dir "$(pwd)/out/autonomy/episodes" >/dev/null
PYTHONPATH="$site_dir${PYTHONPATH:+:$PYTHONPATH}" python -m warm_logic.cli.wlctl research validate-actuation-hazards \
  --sample-dir "$(pwd)/out/actuation/rehearsals" >/dev/null
PYTHONPATH="$site_dir${PYTHONPATH:+:$PYTHONPATH}" python scripts/research/auto_append_verified_journal.py >/dev/null
