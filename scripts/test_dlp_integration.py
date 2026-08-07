import json
import os
import sys
from pathlib import Path

import warm_logic_rs

# Setup paths (Mocking the app environment)
ROOT = Path(os.getcwd())
REQ_PATH = ROOT / "out/sovereign/dlp_test_req.json"
RESP_PATH = ROOT / "out/sovereign/dlp_test_resp.json"
REQ_PATH.parent.mkdir(parents=True, exist_ok=True)

POLICY_SIG = "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0"


def run_test(name, payload_str, signatures, expect_pass):
    print(f"\n--- Testing {name} ---")

    context = {
        "prefix_val": 100,  # Low stakes, normally allowed
        "hard_limit": 200,
        "p300_enabled": False,
        "is_hardware_hardened": True,
        "signatures": signatures,
        "is_self_designed": False,
        "data_payload": payload_str,
    }

    with open(REQ_PATH, "w") as f:
        json.dump(context, f)

    try:
        # Call Rust Core
        result_hash = warm_logic_rs.run_sovereign_logic(
            str(REQ_PATH), str(RESP_PATH), "genesis_hash", POLICY_SIG
        )
        if expect_pass:
            print("SUCCESS: Payload allowed.")
        else:
            print(
                f"❌ FAIL: Payload should have been BLOCKED but passed. Hash: {result_hash}"
            )
            sys.exit(1)

    except Exception as e:
        error_msg = str(e)
        if expect_pass:
            print(
                f"❌ FAIL: Payload should have passed but was BLOCKED. Error: {error_msg}"
            )
            sys.exit(1)
        else:
            # We expect a block, check reason
            if "DATA_LEAK_PREVENTION" in error_msg:
                print(
                    f"✅ SUCCESS: Rust refused sensitive data as expected.\n   Error: {error_msg}"
                )
            else:
                print(f" WARNING: Blocked but unexpected reason: {error_msg}")
                # Still a block, so partial success? No, strict check.
                if "SOVEREIGN_LATCH_ACTIVE" in error_msg:
                    print(
                        "   (Latch is active from previous run, reset latch to test logic)"
                    )
                sys.exit(1)


def reset_latch():
    # Helper to clear latch if needed (simulated by deleting persistent file or just verifying logic)
    latch_path = Path("out/sovereign/FAIL_LATCH")
    if latch_path.exists():
        latch_path.unlink()
        print("   [Reset] Cleared out/sovereign/FAIL_LATCH")


def main():
    reset_latch()

    # Case 1: Benign payload, No signature -> PASS
    run_test("Benign Payload", "Hello World", [], expect_pass=True)

    # Case 2: Sensitive Payload, No signature -> FAIL (Strict Refusal)
    reset_latch()
    run_test(
        "Sensitive Leak Attempt", "This is CONFIDENTIAL data.", [], expect_pass=False
    )

    # Check Latch
    if not Path("out/sovereign/FAIL_LATCH").exists():
        print("FAIL: Fail Latch NOT triggered after sensitive leak attempt.")
        sys.exit(1)
    else:
        print("SUCCESS: Fail Latch triggered.")

    # Case 3: Sensitive Payload, Owner Signature -> PASS
    reset_latch()
    # Mock Owner Signature: ("Owner", [], []) - Rust logic just checks role enum
    run_test(
        "Authorized Sensitive Transfer",
        "This is CONFIDENTIAL but Authorized.",
        [("Owner", [], [])],
        expect_pass=True,
    )

    print("\nDATA SOVEREIGNTY SCENARIO OK (not verification)")


if __name__ == "__main__":
    main()
