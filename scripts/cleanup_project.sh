#!/usr/bin/env bash
# WarmLogic Project Cleanup Script
# Removes temporary files, test artifacts, and caches
# Run with: bash scripts/cleanup_project.sh

set -e

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT_DIR"

echo "==============================================="
echo "🧹 WarmLogic Project Cleanup"
echo "==============================================="
echo "Current size: $(du -sh . 2>/dev/null | cut -f1)"
echo ""

# Phase 1: Safe cleanup (test artifacts, caches)
echo "[Phase 1] Removing test artifacts..."

# redb test directories
REDB_COUNT=$(ls -d redb_test_* 2>/dev/null | wc -l | tr -d ' ')
if [ "$REDB_COUNT" -gt 0 ]; then
    rm -rf redb_test_replication_* redb_test_*
    echo "  ✔ Removed $REDB_COUNT redb test directories"
fi

# MagicMock directory
if [ -d "MagicMock" ]; then
    rm -rf MagicMock
    echo "  ✔ Removed MagicMock directory"
fi

# __pycache__ directories
PYCACHE_COUNT=$(find . -type d -name "__pycache__" -not -path "./.git/*" -not -path "./.venv/*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYCACHE_COUNT" -gt 0 ]; then
    find . -type d -name "__pycache__" -not -path "./.git/*" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
    echo "  ✔ Removed $PYCACHE_COUNT __pycache__ directories"
fi

# .pytest_cache
if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
    echo "  ✔ Removed .pytest_cache"
fi

# .mypy_cache
if [ -d ".mypy_cache" ]; then
    rm -rf .mypy_cache
    echo "  ✔ Removed .mypy_cache"
fi

# .ruff_cache
if [ -d ".ruff_cache" ]; then
    rm -rf .ruff_cache
    echo "  ✔ Removed .ruff_cache"
fi

# Phase 2: Temporary source copies
echo ""
echo "[Phase 2] Removing temporary source copies..."

TMP_SRC_COUNT=$(ls -d out/tmp_src_* 2>/dev/null | wc -l | tr -d ' ')
if [ "$TMP_SRC_COUNT" -gt 0 ]; then
    TMP_SRC_SIZE=$(du -sh out/tmp_src_* 2>/dev/null | tail -1 | cut -f1)
    rm -rf out/tmp_src_*
    echo "  ✔ Removed $TMP_SRC_COUNT tmp_src directories (~$TMP_SRC_SIZE)"
fi

# Phase 3: Rust build artifacts (optional)
echo ""
echo "[Phase 3] Cleaning Rust artifacts..."

if [ -d "rust_core/target" ]; then
    TARGET_SIZE=$(du -sh rust_core/target 2>/dev/null | cut -f1)
    read -p "  Remove rust_core/target ($TARGET_SIZE)? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf rust_core/target
        echo "  ✔ Removed rust_core/target"
    else
        echo "  ⏭ Skipped rust_core/target"
    fi
fi

# Phase 4: Large archives (requires confirmation)
echo ""
echo "[Phase 4] Large directories (manual review recommended):"
echo ""

if [ -d "archives/tarballs" ]; then
    TARBALL_SIZE=$(du -sh archives/tarballs 2>/dev/null | cut -f1)
    echo "  📦 archives/tarballs: $TARBALL_SIZE"
fi

if [ -d "archives/legacy" ]; then
    LEGACY_SIZE=$(du -sh archives/legacy 2>/dev/null | cut -f1)
    echo "  📦 archives/legacy: $LEGACY_SIZE"
fi

if [ -d "out/bridge_eval" ]; then
    BRIDGE_SIZE=$(du -sh out/bridge_eval 2>/dev/null | cut -f1)
    echo "  📦 out/bridge_eval: $BRIDGE_SIZE"
fi

if [ -d "models" ]; then
    MODELS_SIZE=$(du -sh models 2>/dev/null | cut -f1)
    echo "  📦 models: $MODELS_SIZE"
fi

echo ""
echo "==============================================="
echo "🎉 Phase 1-3 cleanup complete!"
echo "Final size: $(du -sh . 2>/dev/null | cut -f1)"
echo ""
echo "To remove large archives (Phase 4), run manually:"
echo "  rm -rf archives/tarballs  # ~107GB"
echo "  rm -rf archives/legacy    # ~43GB"
echo "  rm -rf out/bridge_eval    # ~8GB"
echo "==============================================="
