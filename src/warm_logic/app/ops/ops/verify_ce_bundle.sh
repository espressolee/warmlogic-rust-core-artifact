#!/usr/bin/env bash
set -euo pipefail

# Verifies that CE ledger/index are present in releases and that their hashes
# are recorded in CHECKSUMS_SHA256.txt. Designed for CI/pre-release.
#
# Usage: bash scripts/ops/verify_ce_bundle.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REL_DIR="${ROOT}/releases"
LEDGER="${REL_DIR}/docs/research/Error_and_Counterexample_Ledger_v1.md"
LEDGER_ALT="${REL_DIR}/Error_and_Counterexample_Ledger_v1.md"
INDEX="${REL_DIR}/Error_and_Counterexamples_Index.md"
CHECKSUMS="${REL_DIR}/CHECKSUMS_SHA256.txt"

fail() { echo "[verify_ce_bundle] $*" >&2; exit 1; }

# Prefer ledger under releases/docs/research if present, else top-level copy.
if [[ -f "$LEDGER" ]]; then
  LEDGER_USE="$LEDGER"
elif [[ -f "$LEDGER_ALT" ]]; then
  LEDGER_USE="$LEDGER_ALT"
else
  fail "Missing ledger: expected at $LEDGER or $LEDGER_ALT"
fi

[[ -f "$INDEX" ]] || fail "Missing index: $INDEX"
[[ -f "$CHECKSUMS" ]] || fail "Missing checksums file: $CHECKSUMS"

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

hash_in_file() {
  local h="$1" f="$2"
  if ! grep -q "$h" "$f"; then
    return 1
  fi
}

ledger_hash="$(hash_file "$LEDGER_USE")"
index_hash="$(hash_file "$INDEX")"

hash_in_file "$ledger_hash" "$CHECKSUMS" || fail "Ledger hash not recorded in $CHECKSUMS"
hash_in_file "$index_hash" "$CHECKSUMS" || fail "Index hash not recorded in $CHECKSUMS"

echo "[verify_ce_bundle] OK: ledger/index present and hashes recorded"
