import json
import os
import shutil

import warm_logic_rs


def test_formal_verification():
    print("[TEST] Phase 21: Formal Verification Loop (Certified Logic)")
    print(f"[PYTHON] Current Working Directory: {os.getcwd()}")

    # Check if moral_constraints.yaml exists
    yaml_path = "warm_logic/kernel/agency/moral_constraints.yaml"
    if os.path.exists(yaml_path):
        print(f"[PYTHON] Found {yaml_path}")
    else:
        print(f"[PYTHON] Missing {yaml_path}")

    # Ensure out/sovereign exists
    os.makedirs("out/sovereign", exist_ok=True)

    # 1. Test Lethal Keyword Detection
    print("\nCase 1: Lethal Keyword Detection ('wipe')...")
    ctx_lethal = {
        "prefix_val": 100,
        "hard_limit": 500,
        "p300_enabled": True,
        "is_hardware_hardened": True,
        "signatures": [],
        "is_self_designed": False,
        "data_payload": "SYSTEM_COMMAND: wipe /dev/sda1",
        "mesh_latch_active": False,
        "requested_tool": None,
    }

    os.makedirs("test_data", exist_ok=True)
    with open("test_data/lethal_req.json", "w") as f:
        json.dump(ctx_lethal, f)

    try:
        warm_logic_rs.run_sovereign_logic(
            "test_data/lethal_req.json",
            "test_data/lethal_out.json",
            "genesis",
            "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0",
        )
        print("FAILED: Lethal keyword 'wipe' was not blocked.")
    except Exception as e:
        if "FORMAL_VIOLATION" in str(e) and "wipe" in str(e):
            print(f"PASSED: Blocked with reason: {e}")
        else:
            print(f"FAILED: Unexpected error: {e}")

    # Clear Latch for next test
    if os.path.exists("out/sovereign/FAIL_LATCH"):
        os.remove("out/sovereign/FAIL_LATCH")

    # 2. Test Prohibited Tool Detection
    print("\nCase 2: Prohibited Tool Detection ('mint_token')...")
    ctx_tool = {
        "prefix_val": 100,
        "hard_limit": 500,
        "p300_enabled": True,
        "is_hardware_hardened": True,
        "signatures": [],
        "is_self_designed": False,
        "data_payload": "Requesting funds...",
        "mesh_latch_active": False,
        "requested_tool": "mint_token",
    }

    with open("test_data/tool_req.json", "w") as f:
        json.dump(ctx_tool, f)

    try:
        warm_logic_rs.run_sovereign_logic(
            "test_data/tool_req.json",
            "test_data/tool_out.json",
            "genesis",
            "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0",
        )
        print("FAILED: Prohibited tool 'mint_token' was not blocked.")
    except Exception as e:
        if "FORMAL_VIOLATION" in str(e) and "mint_token" in str(e):
            print(f"PASSED: Blocked with reason: {e}")
        else:
            print(f"FAILED: Unexpected error: {e}")

    # Clear Latch for next test
    if os.path.exists("out/sovereign/FAIL_LATCH"):
        os.remove("out/sovereign/FAIL_LATCH")

    # 3. Test Compliant Request
    print("\nCase 3: Compliant Request...")
    ctx_pass = {
        "prefix_val": 100,
        "hard_limit": 500,
        "p300_enabled": True,
        "is_hardware_hardened": True,
        "signatures": [],
        "is_self_designed": False,
        "data_payload": "Status check...",
        "mesh_latch_active": False,
        "requested_tool": "get_status",
    }

    with open("test_data/pass_req.json", "w") as f:
        json.dump(ctx_pass, f)

    try:
        warm_logic_rs.run_sovereign_logic(
            "test_data/pass_req.json",
            "test_data/pass_out.json",
            "genesis",
            "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0",
        )
        print("PASSED: Compliant request allowed.")
    except Exception as e:
        print(f"FAILED: Compliant request was blocked: {e}")

    # Cleanup
    if os.path.exists("test_data"):
        shutil.rmtree("test_data")


if __name__ == "__main__":
    test_formal_verification()
