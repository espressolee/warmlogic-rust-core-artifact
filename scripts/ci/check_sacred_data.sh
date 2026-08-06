#!/bin/bash
# protected Data Protection Check
# Prevents accidental commits that could destroy out/bridge_eval protection

set -e

# Check if staged changes contain dangerous rm -rf out/ patterns
if git diff --cached --name-only 2>/dev/null | grep -qE "(justfile|Makefile)" ; then
    if git diff --cached 2>/dev/null | grep -qE "^\+.*rm.*-rf.*out/[^a-z]" ; then
        echo ""
        echo "⛔ SACRED DATA PROTECTION TRIGGERED"
        echo "   Staged changes contain 'rm -rf out/' in justfile or Makefile"
        echo "   This would destroy 17GB of irreplaceable benchmark evidence."
        echo ""
        echo "   See: docs/SACRED_DATA.md"
        echo "   Bypass: git commit --no-verify (NOT RECOMMENDED)"
        echo ""
        exit 1
    fi
fi

exit 0
