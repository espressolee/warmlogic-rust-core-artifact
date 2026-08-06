#!/usr/bin/env bash
set -euo pipefail

export GITHUB_OUTPUT="${GITHUB_OUTPUT:-/dev/null}"

exec bash src/warm_logic/app/ci/ci/compat_generate_report.sh "$@"
