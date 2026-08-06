#!/usr/bin/env bash
set -euo pipefail

# TLAPS runner for the drift/lagmax theorem (THM-DRIFT-003).
# Runs tlapm2 against the current TLA spec and writes the log next to the spec.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SPEC="$REPO_ROOT/proof/drift/DRIFT_IMPOSSIBILITY_005.tla"
LOG="$REPO_ROOT/proof/drift/tlaps_THM-DRIFT-003.log"

if ! command -v tlapm2 >/dev/null 2>&1; then
  echo "tlapm2 not found in PATH. Ensure TLAPS is installed (opam switch tlaps-4.x, tlapm2 in PATH)." >&2
  exit 1
fi

echo "Running tlapm2 on $SPEC"
tlapm2 "$SPEC" | tee "$LOG"
echo "Log written to $LOG"
