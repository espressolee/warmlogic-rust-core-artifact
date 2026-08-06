#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-${HOME}/.warm_logic_onboarding}

python -m warm_logic.cli.wlctl init --base "$BASE"
python -m warm_logic.cli.wlctl run-dev --base "$BASE" --write
python -m warm_logic.cli.wlctl run-dev --base "$BASE" --profile sandbox --write
python -m pytest tests/core/test_wlctl_smoke.py
