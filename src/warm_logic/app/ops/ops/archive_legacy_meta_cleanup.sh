#!/usr/bin/env bash
# archive_legacy_meta_cleanup.sh
# Executes the cleanup contract for Resonance/meta legacy files.
# Moves P-series checkpoints to Resonance/ARCHIVE/meta_v1_checkpoints.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WARMLOGIC_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESONANCE_ROOT="$(cd "$WARMLOGIC_ROOT/.." && pwd)"
META_DIR="$RESONANCE_ROOT/meta"
ARCHIVE_DIR="$RESONANCE_ROOT/ARCHIVE/meta_v1_checkpoints"

echo "=============================================="
echo " WarmLogic Legacy Meta Cleanup"
echo "=============================================="
echo " Source: $META_DIR"
echo " Target: $ARCHIVE_DIR"

if [ ! -d "$META_DIR" ]; then
    echo "Error: Resonance/meta directory not found at $META_DIR"
    exit 1
fi

mkdir -p "$ARCHIVE_DIR"

echo "[1/2] Moving P_Checkpoint files..."
# dry run with ls first to avoid errors if empty
count=$(find "$META_DIR" -maxdepth 1 -name "WarmLogic_P_Checkpoint_*.md" | wc -l)
if [ "$count" -gt 0 ]; then
    mv "$META_DIR"/WarmLogic_P_Checkpoint_*.md "$ARCHIVE_DIR"/
    echo "   Moved $count files."
else
    echo "   No P_Checkpoint files found."
fi

echo "[2/2] Moving P_Roadmap and Status files..."
mv "$META_DIR"/WarmLogic_P_Roadmap_P*.md "$ARCHIVE_DIR"/ 2>/dev/null || true
mv "$META_DIR"/WL_PROGRAM_PROGRESS_CHECKLIST_v1.0.md "$ARCHIVE_DIR"/ 2>/dev/null || true
mv "$META_DIR"/WarmLogic_P_Status_v*.json "$ARCHIVE_DIR"/ 2>/dev/null || true
mv "$META_DIR"/WarmLogic_Runbook_P_Series_v*.md "$ARCHIVE_DIR"/ 2>/dev/null || true

echo "=============================================="
echo " Cleanup Complete."
echo " Manifest: meta/ARCHIVE_MANIFEST_v1.json"
echo "=============================================="
