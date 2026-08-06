import json
import os
import sys
from pathlib import Path

import warm_logic_rs

# Setup paths
ROOT = Path(os.getcwd())
OUT_DIR = ROOT / "out/sovereign"
REQUEST_PATH = OUT_DIR / "refusal_test_req.json"
RESPONSE_PATH = OUT_DIR / "refusal_test_resp.json"
LATCH_PATH = OUT_DIR / "FAIL_LATCH"


def setup_files():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if LATCH_PATH.exists():
        os.remove(LATCH_PATH)


def create_request(prefix_val, signatures=[], is_self_designed=False):
    req = {
        "prefix_val": prefix_val,
        "hard_limit": 500,
        "p300_enabled": True,
        "is_hardware_hardened": True,  # Simulate hardware for P300 checks, but we test P400 auth
        "signatures": signatures,
        "is_self_designed": is_self_designed,
    }
    with open(REQUEST_PATH, "w") as f:
        json.dump(req, f)


def test_refusal_p405_no_sigs():
    print("\n--- Testing P405 Refusal (No Signatures) ---")
    setup_files()
    create_request(405, signatures=[])

    # Correct Policy Signature
    policy_sig = "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0"

    try:
        warm_logic_rs.run_sovereign_logic(
            str(REQUEST_PATH), str(RESPONSE_PATH), "prev_hash_dummy", policy_sig
        )
        print("FAIL: Rust did not refuse P405 without signatures!")
        return False
    except Exception as e:
        print(f"SUCCESS: Rust refused P405 as expected. Error: {e}")
        # Verify Latch
        if LATCH_PATH.exists():
            print("SUCCESS: Fail Latch triggered.")
            with open(LATCH_PATH, "r") as f:
                print(f"Latch Content: {f.read().strip()}")
        else:
            print("FAIL: Fail Latch NOT triggered.")
            return False
        return True


def test_refusal_policy_mismatch():
    print("\n--- Testing Policy Signature Mismatch ---")
    setup_files()
    create_request(100)  # Safe prefix

    wrong_sig = "0xDEADBEEF"

    try:
        warm_logic_rs.run_sovereign_logic(
            str(REQUEST_PATH), str(RESPONSE_PATH), "prev_hash_dummy", wrong_sig
        )
        print("FAIL: Rust accepted wrong policy signature!")
        return False
    except Exception as e:
        print(f"SUCCESS: Rust refused wrong policy signature. Error: {e}")
        return True


if __name__ == "__main__":
    success = True
    success &= test_refusal_p405_no_sigs()
    success &= test_refusal_policy_mismatch()

    if success:
        print("\nREFUSAL ENGINE INTEGRATION VERIFIED")
        sys.exit(0)
    else:
        print("\nREFUSAL ENGINE FAILED")
        sys.exit(1)
