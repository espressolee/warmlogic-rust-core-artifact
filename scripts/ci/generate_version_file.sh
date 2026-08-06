#!/usr/bin/env bash
set -euo pipefail

version="$(git describe --tags --always --dirty 2>/dev/null || git rev-parse --short HEAD)"
printf '%s\n' "$version" > VERSION
printf '[VERSION] wrote VERSION=%s\n' "$version"
