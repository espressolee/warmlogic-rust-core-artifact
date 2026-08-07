"""Verification test for Drift Forensics (Phase 5.3)."""

import glob
import logging
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.kernel.ops.reconstruction import forensics

logging.basicConfig(level=logging.INFO)


def test_forensic_replay():
    print("Testing Era 5 Phase 5.3: Drift Forensics...")

    # 1. Find bundles from previous tests (Phase 4.3 and 5.2)
    bundle_dir = "ledger/bundles"
    bundles = glob.glob(os.path.join(bundle_dir, "*.wlid"))

    if not bundles:
        print("No bundles found. Please run test_repro_bundle.py first.")
        return

    print(f"Found {len(bundles)} evidence bundles.")

    all_verified = True
    for bundle_path in bundles:
        print(f"\nAnalyzing: {os.path.basename(bundle_path)}")
        match, reason = forensics.replay_refusal(bundle_path)

        if match:
            print(f"   {reason}")
        else:
            print(f"   FAILED: {reason}")
            all_verified = False

    if all_verified:
        print("\nPHASE 5.3 SCENARIO OK (not verification) (All Refusals Reconstructed).")
    else:
        print("\nPHASE 5.3 FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    test_forensic_replay()
