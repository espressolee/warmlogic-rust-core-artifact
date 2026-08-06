#!/usr/bin/env bash
# Human-run proof checker for CT-safe MDP theorems (TLAPS/SMT).
# approval_policy=never: do NOT auto-run from agents.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${REPO_ROOT}/out/formal/ct_safe_mdp"
mkdir -p "${OUT_DIR}"

echo "[info] expected models: sim/ct_safe_mdp/core_sim.tla, sim/t_operator/trajectory_explorer.tla, sim/drift/drift_counterexamples.tla"
echo "[info] place TLAPS/SMT logs into ${OUT_DIR}/THM-*.tlaps.log"

# Example TLAPS invocations (edit for your environment):
# tlapm --dump-config "${OUT_DIR}/tlaps_config" sim/ct_safe_mdp/core_sim.tla > "${OUT_DIR}/THM-CTSAFE-EXISTENCE.tlaps.log"
# tlapm sim/t_operator/trajectory_explorer.tla > "${OUT_DIR}/THM-TOP-CONTRACTION.tlaps.log"
# tlapm sim/drift/drift_counterexamples.tla > "${OUT_DIR}/THM-DRIFT-003.tlaps.log"

echo "[info] update docs/research/proofs/CT_Safe_MDP_proof_manifest_v1.json with status/log hashes after runs."
