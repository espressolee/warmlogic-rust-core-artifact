#!/bin/bash
# check_prohibited_symbols.sh
# Verifies that markdown files do not contain forbidden symbols.

DIRECTORY=$1

if [ -z "$DIRECTORY" ]; then
  DIRECTORY="."
fi

# Find all md files and grep for ✓, △, ✗
# Note: Excluding archives and docs to avoid legacy documentation noise.
grep -rnE "[✓△✗]" "$DIRECTORY" --include="*.md" --exclude-dir={"*docs*","*archives*","*archive*","*brain*"}

if [ $? -eq 0 ]; then
  echo "❌ Error: Forbidden symbols (✓, △, ✗) found in markdown files. Please use words instead."
  exit 1
else
  echo "✅ No forbidden symbols found."
  exit 0
fi
