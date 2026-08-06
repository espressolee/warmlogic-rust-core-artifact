#!/usr/bin/env bash
# Run SMT proof checks (research) using z3 if available.

set -euo pipefail

SMT_DIR=${SMT_DIR:-docs/math/proofs/smt}

if ! command -v z3 >/dev/null 2>&1; then
  echo "[PROOF] z3 not found; skipping SMT checks" >&2
  exit 0
fi

if [ ! -d "${SMT_DIR}" ]; then
  echo "[PROOF] SMT dir not found at ${SMT_DIR}; skipping" >&2
  exit 0
fi

rc=0
for f in "${SMT_DIR}"/*.smt2; do
  [ -e "$f" ] || continue
  echo "[PROOF] running z3 on $f"
  out=$(z3 -smt2 -in < "$f")
  echo "${out}"
  status=$(echo "${out}" | tr -d '\r' | tail -n1 | tr -d '[:space:]')
  if [ "$status" != "unsat" ]; then
    echo "[PROOF] SMT check failed (status=${status:-unknown}) for $f" >&2
    rc=1
  fi
done
exit $rc
