"""
Sovereign Pilot Simulation (Red Team Scenario).
Orchestrates the full lifecycle: Attack -> Refusal -> Bundle -> Forensics.
"""

import json
import logging
import os
import sys
import time

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.intelligence.provenance_graph import provenance_db
from warm_logic.kernel.justice.gov_inputs import GovernanceInputs
from warm_logic.kernel.justice.gvm import eval_vm
from warm_logic.kernel.ops.reconstruction import forensics
from warm_logic.kernel.ops.repro_bundler import repro_bundler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("PilotSim")


def run_pilot_scenario():
    print("\n STARTING SOVEREIGN PILOT SIMULATION (RED TEAM) \n")

    # ---------------------------------------------------------
    # SCENARIO 1: The "Untrusted Model" Attack
    # ---------------------------------------------------------
    print("[Scenario 1] Attempting to deploy model with BROKEN provenance...")

    # 1. Setup: Register known artifacts
    provenance_db.register_artifact("TRUSTED_ROOT_DATA", "dataset", {}, trusted=True)
    provenance_db.register_artifact(
        "SHADOW_WEIGHTS_v666", "weights", {}, trusted=False
    )  # Isolated node

    print("   Artifact 'SHADOW_WEIGHTS_v666' registered (Untrusted Lineage).")

    # 2. Attack: Submit Governance Request with Mode 4 (Research Integrity)
    print("   Submitting Governance Request for 'SHADOW_WEIGHTS_v666'...")

    witness_bundle_json = json.dumps(
        {
            "run_id": "PILOT_ATTACK_001",
            "target_hash": "deadbeef",
            "threshold": 3,
            "signatures": [
                {"witness_id": f"NODE_{i}", "signature": "s", "timestamp": 0}
                for i in range(3)
            ],
        }
    )

    inputs_attack = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF",
        autonomy_mode=4,  # Research Integrity
        witness_bundle=witness_bundle_json,
        metadata={
            "target_artifact_id": "SHADOW_WEIGHTS_v666",
            "run_id": "PILOT_ATTACK_001",
        },
    )

    # 3. Execution (Expect Refusal)
    outputs = eval_vm(inputs_attack)

    if outputs.govSAT == "SatBlock":
        print(f"    GVM INTERCEPTION SUCCESSFUL: {outputs.reason}")
    else:
        print(f"   GVM FAILED TO BLOCK: {outputs.govSAT}")
        sys.exit(1)

    # ---------------------------------------------------------
    # SCENARIO 2: Evidence Bundling
    # ---------------------------------------------------------
    print("\n[Scenario 2] Verifying Sovereign Repro Bundle...")

    # Check if bundle was created
    # We need to find the specific bundle for this run_id
    import glob

    bundles = glob.glob(os.path.join(repro_bundler.bundle_dir, "*.wlid"))
    target_bundle = None

    for b_path in bundles:
        with open(b_path, "r") as f:
            content = json.load(f)
            if (
                content.get("evidence", {}).get("context", {}).get("artifact")
                == "SHADOW_WEIGHTS_v666"
            ):
                target_bundle = b_path
                break

    if target_bundle:
        print(f"   Bundle Generated: {os.path.basename(target_bundle)}")
        print(f"   path: {target_bundle}")
    else:
        print("   Bundle Generation FAILED.")
        sys.exit(1)

    # ---------------------------------------------------------
    # SCENARIO 3: Forensic Replay
    # ---------------------------------------------------------
    print("\n‍[Scenario 3] Executing Drift Forensics (Time Travel)...")

    match, reason = forensics.replay_refusal(target_bundle)

    if match:
        print(f"   Forensics Confirmation: {reason}")
        print("   The refusal was INEVITABLE and MATHEMATICALLY PROVEN.")
    else:
        print(f"   Forensics Mismatch: {reason}")
        sys.exit(1)

    print("\nPILOT SIMULATION COMPLETE: ALL SYSTEMS GREEN.")
    print("   The Sovereign Refusal Engine is ready for deployment.")


if __name__ == "__main__":
    run_pilot_scenario()
