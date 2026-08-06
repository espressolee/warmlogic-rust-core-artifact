#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f "formal/ctsafe_mdp/proof_checks.txt" ]]; then
  echo "[proof] missing formal/ctsafe_mdp/proof_checks.txt" >&2
  exit 1
fi

while IFS= read -r cmd; do
  if [[ -z "$cmd" ]]; then
    continue
  fi
  echo "[proof] $cmd"
  eval "$cmd"
done < formal/ctsafe_mdp/proof_checks.txt

# T_SAFE (T-operator safe-set preservation) proof run
scripts/proofs/check_t_safe.sh
scripts/proofs/check_t_operator_safety.sh
scripts/proofs/check_smt.sh
# Drift impossibility (placeholder)
scripts/proofs/check_drift_impossibility.sh
