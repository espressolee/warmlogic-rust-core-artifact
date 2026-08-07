import base64
import json
import os
import sys
from pathlib import Path

import warm_logic_rs

# Constants
REQ_PATH = "out/sovereign/request_entropy.json"
RESP_PATH = "out/sovereign/evidence_entropy.json"
POLICY_SIG = "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0"


def reset_latch():
    latch_path = Path("out/sovereign/FAIL_LATCH")
    if latch_path.exists():
        latch_path.unlink()


def run_test(name, payload_str, expect_pass):
    print(f"\n--- Testing Entropy: {name} ---")
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
            if "HIGH_ENTROPY_DETECTED" in error_msg:
                print(
                    f"✅ SUCCESS: Rust refused high-entropy blob as expected.\n   Error: {error_msg}"
                )
            elif (
                "DATA_LEAK_PREVENTION" in error_msg or "SOVEREIGN_REFUSAL" in error_msg
            ):
                print(
                    f"✅ SUCCESS: Rust refused sensitive data as expected.\n   Error: {error_msg}"
                )
            else:
                print(f"FAIL: Blocked but unexpected reason: {error_msg}")
                sys.exit(1)


def main():
    print("STARTING SOVEREIGN ENTROPY GUARD INTEGRATION TEST")

    # 1. Test Benign English Text (Low entropy ~4.5)
    run_test(
        "Benign Text",
        "This is a normal sentence about the weather. It has low entropy and should pass easily.",
        expect_pass=True,
    )

    # 2. Test High Entropy Blob (High entropy ~7.9)
    # 256 random bytes encoded in base64
    high_entropy_blob = base64.b64encode(os.urandom(256)).decode()
    run_test("High Entropy Blob (Random Data)", high_entropy_blob, expect_pass=False)

    # 3. Test Keyword Match (Phase 12 fallback)
    run_test(
        "Keyword Match (CONFIDENTIAL)",
        "This is a CONFIDENTIAL file.",
        expect_pass=False,
    )

    print("\nENTROPY GUARD SCENARIO OK (not verification)")


if __name__ == "__main__":
    main()
