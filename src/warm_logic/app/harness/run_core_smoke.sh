#!/usr/bin/env bash
set -euo pipefail

python -m pytest -m smoke_core warm_logic/tests
