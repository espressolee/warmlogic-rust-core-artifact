#!/usr/bin/env bash
set -euo pipefail

exec bash src/warm_logic/app/ci/ci/compat_accept_baseline.sh "$@"
