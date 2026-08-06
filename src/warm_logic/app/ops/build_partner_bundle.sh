#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DIST_DIR="$ROOT_DIR/dist/partner_bundle"
VERSION=${1:-$(python3 - <<'PY'
from importlib.metadata import version, PackageNotFoundError
try:
    print(version('warm-logic-core'))
except PackageNotFoundError:
    import json, pathlib
    pyproject = pathlib.Path('pyproject.toml')
    ver = "0.0.0"
    if pyproject.exists():
        for line in pyproject.read_text().splitlines():
            if line.strip().startswith('version ='):
                ver = line.split('=',1)[1].strip().strip('"')
                break
    print(ver)
PY
)}
BUNDLE_DIR="$DIST_DIR/warm_logic-$VERSION"

rm -rf "$DIST_DIR"
mkdir -p "$BUNDLE_DIR/dist"

# Build wheel for warm_logic into the bundle
python3 -m build --wheel --outdir "$BUNDLE_DIR/dist" > /dev/null

# Copy install script, docs, configs, sample partner dataset
cp "$ROOT_DIR/install.sh" "$BUNDLE_DIR/install.sh"
cp "$ROOT_DIR/docs/product/Partner_Install_Plan_v1.md" "$BUNDLE_DIR/"
rsync -a "$ROOT_DIR/warm_logic/config/templates" "$BUNDLE_DIR/config/"
rsync -a "$ROOT_DIR/partners/agent_saas_sample" "$BUNDLE_DIR/partners/"

# Include README for bundle root
cat <<README > "$BUNDLE_DIR/README.md"
Warm Logic Core Partner Bundle (v$VERSION)
========================================

Contents:
  - install.sh — bootstraps venv + wlctl init
  - dist/ — wheel artifacts built from current tree
  - config/templates/ — guard/governance/runtime profile templates
  - partners/agent_saas_sample/ — sample dataset & replay scripts
  - docs/product/Partner_Install_Plan_v1.md — install guide

Usage:
  tar -xzf warm_logic-$VERSION.tar.gz && cd warm_logic-$VERSION
  ./install.sh /path/to/runtime
README

# Create tarball
mkdir -p "$DIST_DIR"
tar -czf "$DIST_DIR/warm_logic-$VERSION.tar.gz" -C "$BUNDLE_DIR/.." "$(basename "$BUNDLE_DIR")"

echo "[build_partner_bundle] wrote $DIST_DIR/warm_logic-$VERSION.tar.gz"
