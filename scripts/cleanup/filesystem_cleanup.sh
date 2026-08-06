#!/usr/bin/env bash
# WarmLogic Filesystem Cleanup Script
# Usage: bash scripts/cleanup/filesystem_cleanup.sh [--dry-run|--execute]
#
# WARNING: This script deletes files. Always run --dry-run first!

set -e

MODE="${1:---dry-run}"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}WarmLogic Filesystem Cleanup${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo "Mode: $MODE"
echo "Project: $PROJECT_ROOT"
echo ""

# Get initial size
INITIAL_SIZE=$(du -sh . 2>/dev/null | cut -f1)
log_info "Initial size: $INITIAL_SIZE"
echo ""

# Track what will be deleted
TOTAL_FILES=0
TOTAL_DIRS=0

# ============================================
# Phase 1: MagicMock Files (CRITICAL)
# ============================================
echo -e "${YELLOW}=== Phase 1: MagicMock Files ===${NC}"

MAGICMOCK_FILES=$(find . -maxdepth 1 -name "*MagicMock*" 2>/dev/null | wc -l | tr -d ' ')
log_info "Found: $MAGICMOCK_FILES MagicMock files"

if [[ "$MAGICMOCK_FILES" -gt 0 ]]; then
    if [[ "$MODE" == "--execute" ]]; then
        find . -maxdepth 1 -name "*MagicMock*" -exec rm -rf {} \; 2>/dev/null || true
        log_success "Deleted $MAGICMOCK_FILES MagicMock files"
    else
        find . -maxdepth 1 -name "*MagicMock*" 2>/dev/null | head -5
        echo "  ... (showing first 5)"
    fi
    TOTAL_FILES=$((TOTAL_FILES + MAGICMOCK_FILES))
fi
echo ""

# ============================================
# Phase 2: Duplicate Numbered Files
# ============================================
echo -e "${YELLOW}=== Phase 2: Duplicate Numbered Files ===${NC}"

# Pattern: "filename N.ext" or "filename N"
DUPLICATE_FILES=$(find . -maxdepth 1 \( -name "* [0-9].py" -o -name "* [0-9].md" -o -name "* [0-9].ini" -o -name "* [0-9].lock" -o -name "* [0-9].baseline" -o -name "* [0-9]" -o -name "*.[0-9]" \) 2>/dev/null | wc -l | tr -d ' ')
log_info "Found: $DUPLICATE_FILES duplicate files"

if [[ "$DUPLICATE_FILES" -gt 0 ]]; then
    if [[ "$MODE" == "--execute" ]]; then
        # Delete files with space+number pattern
        find . -maxdepth 1 -name "* [0-9].py" -delete 2>/dev/null || true
        find . -maxdepth 1 -name "* [0-9].md" -delete 2>/dev/null || true
        find . -maxdepth 1 -name "* [0-9].ini" -delete 2>/dev/null || true
        find . -maxdepth 1 -name "* [0-9].lock" -delete 2>/dev/null || true
        find . -maxdepth 1 -name "* [0-9].baseline" -delete 2>/dev/null || true
        find . -maxdepth 1 -name "* [0-9]" -type f -delete 2>/dev/null || true
        find . -maxdepth 1 -name "*.[0-9]" -type f -delete 2>/dev/null || true
        # Also handle conftest 2.py through conftest 9.py
        rm -f "conftest "[0-9].py 2>/dev/null || true
        rm -f "__init__ "[0-9].py 2>/dev/null || true
        log_success "Deleted duplicate files"
    else
        find . -maxdepth 1 \( -name "* [0-9].py" -o -name "* [0-9].md" -o -name "* [0-9]" \) 2>/dev/null | head -10
        echo "  ... (showing first 10)"
    fi
    TOTAL_FILES=$((TOTAL_FILES + DUPLICATE_FILES))
fi
echo ""

# ============================================
# Phase 3: Test Database Directories
# ============================================
echo -e "${YELLOW}=== Phase 3: Test Database Directories ===${NC}"

SLED_DIRS=$(find . -maxdepth 1 -type d -name "sled_db_*" 2>/dev/null | wc -l | tr -d ' ')
REDB_DIRS=$(find . -maxdepth 1 -type d -name "redb_*" 2>/dev/null | wc -l | tr -d ' ')
TEST_DB_TOTAL=$((SLED_DIRS + REDB_DIRS))

log_info "Found: $SLED_DIRS sled_db_* directories"
log_info "Found: $REDB_DIRS redb_* directories"

if [[ "$TEST_DB_TOTAL" -gt 0 ]]; then
    # Calculate size
    TEST_DB_SIZE=$(du -sh sled_db_* redb_* 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")
    log_info "Total size: ~${TEST_DB_SIZE}MB"

    if [[ "$MODE" == "--execute" ]]; then
        rm -rf sled_db_* redb_* 2>/dev/null || true
        log_success "Deleted $TEST_DB_TOTAL test database directories"
    else
        find . -maxdepth 1 -type d \( -name "sled_db_*" -o -name "redb_*" \) 2>/dev/null | head -5
        echo "  ... (showing first 5)"
    fi
    TOTAL_DIRS=$((TOTAL_DIRS + TEST_DB_TOTAL))
fi
echo ""

# ============================================
# Phase 4: Abandoned Virtual Environments
# ============================================
echo -e "${YELLOW}=== Phase 4: Abandoned Virtual Environments ===${NC}"

ABANDONED_VENVS=(
    ".venv_cockpit"
    ".venv_dp"
    ".venv_lock"
    ".venv_new"
    ".venv_autonomy"
    ".bench_venv"
    ".rust_venv"
)

VENV_COUNT=0
for venv in "${ABANDONED_VENVS[@]}"; do
    if [[ -d "$venv" ]]; then
        SIZE=$(du -sh "$venv" 2>/dev/null | cut -f1)
        log_info "Found: $venv ($SIZE)"
        VENV_COUNT=$((VENV_COUNT + 1))

        if [[ "$MODE" == "--execute" ]]; then
            rm -rf "$venv"
        fi
    fi
done

if [[ "$VENV_COUNT" -gt 0 ]] && [[ "$MODE" == "--execute" ]]; then
    log_success "Deleted $VENV_COUNT abandoned virtual environments"
fi
TOTAL_DIRS=$((TOTAL_DIRS + VENV_COUNT))
echo ""

# ============================================
# Phase 5: --out-dir Artifacts
# ============================================
echo -e "${YELLOW}=== Phase 5: Build Artifacts ===${NC}"

OUTDIR_FILES=$(find . -maxdepth 1 -name "--out-dir*" 2>/dev/null | wc -l | tr -d ' ')
log_info "Found: $OUTDIR_FILES --out-dir files"

if [[ "$OUTDIR_FILES" -gt 0 ]]; then
    if [[ "$MODE" == "--execute" ]]; then
        rm -rf "./--out-dir"* 2>/dev/null || true
        log_success "Deleted --out-dir artifacts"
    else
        find . -maxdepth 1 -name "--out-dir*" 2>/dev/null
    fi
    TOTAL_FILES=$((TOTAL_FILES + OUTDIR_FILES))
fi
echo ""

# ============================================
# Phase 6: Python Cache
# ============================================
echo -e "${YELLOW}=== Phase 6: Python Cache ===${NC}"

PYCACHE_DIRS=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
PYC_FILES=$(find . -name "*.pyc" -o -name "*.pyo" 2>/dev/null | wc -l | tr -d ' ')

log_info "Found: $PYCACHE_DIRS __pycache__ directories"
log_info "Found: $PYC_FILES .pyc/.pyo files"

if [[ "$MODE" == "--execute" ]]; then
    find . -type d -name "__pycache__" -exec rm -rf {} \; 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "*.pyo" -delete 2>/dev/null || true
    log_success "Cleaned Python cache"
fi
echo ""

# ============================================
# Phase 7: Update .gitignore
# ============================================
echo -e "${YELLOW}=== Phase 7: Verify .gitignore ===${NC}"

GITIGNORE_PATTERNS=(
    "sled_db_*"
    "redb_*"
    "__pycache__/"
    "*.pyc"
    ".venv_*"
    "--out-dir*"
)

MISSING_PATTERNS=0
for pattern in "${GITIGNORE_PATTERNS[@]}"; do
    if ! grep -q "^${pattern}$" .gitignore 2>/dev/null; then
        log_warn "Missing from .gitignore: $pattern"
        MISSING_PATTERNS=$((MISSING_PATTERNS + 1))

        if [[ "$MODE" == "--execute" ]]; then
            echo "$pattern" >> .gitignore
        fi
    fi
done

if [[ "$MISSING_PATTERNS" -gt 0 ]] && [[ "$MODE" == "--execute" ]]; then
    log_success "Added $MISSING_PATTERNS patterns to .gitignore"
fi
echo ""

# ============================================
# Summary
# ============================================
echo -e "${BLUE}======================================${NC}"
echo "Summary"
echo -e "${BLUE}======================================${NC}"

if [[ "$MODE" == "--execute" ]]; then
    FINAL_SIZE=$(du -sh . 2>/dev/null | cut -f1)
    echo -e "Initial size:  ${RED}$INITIAL_SIZE${NC}"
    echo -e "Final size:    ${GREEN}$FINAL_SIZE${NC}"
    echo ""
    log_success "Cleanup complete!"
else
    echo "Files to delete:       $TOTAL_FILES"
    echo "Directories to delete: $TOTAL_DIRS"
    echo ""
    echo -e "${YELLOW}This was a DRY RUN. No files were deleted.${NC}"
    echo ""
    echo "To execute cleanup, run:"
    echo "  bash scripts/cleanup/filesystem_cleanup.sh --execute"
fi
echo ""
