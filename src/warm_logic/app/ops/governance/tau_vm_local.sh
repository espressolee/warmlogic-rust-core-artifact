#!/usr/bin/env bash
# Wrapper for local τ VM (CLI).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

python -m warm_logic.core.governance.tau_vm_cli
