import json
import sys
from pathlib import Path

import warm_logic_rs

# Constants
REQ_PATH = "out/sovereign/request_forge.json"
RESP_PATH = "out/sovereign/evidence_forge.json"
POLICY_SIG = "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0"


def reset_latch():
    latch_path = Path("out/sovereign/FAIL_LATCH")
    if latch_path.exists():
        latch_path.unlink()


def run_test(name, payload_str, expect_pass):
    print(f"\n--- Testing Forge: {name} ---")
    reset_latch()

    context = {
        "prefix_val": 100,
        "hard_limit": 200,
        "p300_enabled": False,
        "is_hardware_hardened": True,
        "signatures": [],
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
            print(f"SUCCESS: Payload allowed.")
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
            if "DATA_LEAK_PREVENTION" in error_msg:
                print(
                    f"✅ SUCCESS: Rust refused dynamic sensitive data as expected.\n   Error: {error_msg}"
                )
            else:
                print(f"FAIL: Blocked but unexpected reason: {error_msg}")
                sys.exit(1)


def main():
    print("STARTING SOVEREIGN FORGE INTEGRATION TEST")

    # Check if forge file exists
    if not Path("out/sovereign/constitution.signed.yaml").exists():
        print("FAIL: Forge file missing. Run forge_constitution.py first.")
        sys.exit(1)

    # 1. Test Dynamic Keyword (BANANA was forged)
    run_test(
        "Dynamic Keyword (BANANA)", "I love eating BANANA bread.", expect_pass=False
    )

    # 2. Test Hardcoded Keyword (STILL active)
    run_test(
        "Hardcoded Keyword (CONFIDENTIAL)",
        "This is a CONFIDENTIAL file.",
        expect_pass=False,
    )

    # 3. Test Benign
    run_test("Benign", "I love eating APPLE bread.", expect_pass=True)

    print("\nFORGE CONSTITUTION SCENARIO OK (not verification)")


if __name__ == "__main__":
    main()
