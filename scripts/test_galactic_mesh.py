import json
import os
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def clear_latch():
    if os.path.exists("out/sovereign/FAIL_LATCH"):
        os.remove("out/sovereign/FAIL_LATCH")


def test_galactic_mesh():
    print("[TEST] Phase 22: distributed Mesh (Multi-TEE Portability)")
    print(f"[PYTHON] Current Working Directory: {os.getcwd()}")

    os.makedirs("test_data", exist_ok=True)
    os.makedirs("out/sovereign", exist_ok=True)
    clear_latch()

    # 1. Case 1: mesh_sync without attestation (Should FAIL)
    print("\nCase 1: mesh_sync WITHOUT attestation...")
    ctx_missing = {
        "prefix_val": 100,
        "hard_limit": 500,
        "p300_enabled": True,
        "is_hardware_hardened": True,
        "signatures": [],
        "is_self_designed": False,
        "data_payload": "Syncing state...",
        "mesh_latch_active": False,
        "requested_tool": "mesh_sync",
        "remote_attestation": None,
    }

    with open("test_data/mesh_missing_req.json", "w") as f:
        json.dump(ctx_missing, f)

    # [Python] Use SovereignSieve
    from warm_logic.kernel.justice.sovereign_sieve import SovereignSieve

    sieve = SovereignSieve()

    try:
        sieve.run_sovereign_logic(
            "test_data/mesh_missing_req.json",
            "test_data/mesh_missing_out.json",
            "genesis",
            "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0",
        )
        print("FAILED: mesh_sync without attestation was not blocked.")
    except Exception as e:
        if "ATTESTATION_REQUIRED" in str(e):
            print(f"PASSED: Blocked as expected: {e}")
        else:
            print(f"FAILED: Unexpected error: {e}")

    clear_latch()

    # 2. Case 2: mesh_sync with VALID attestation (Should PASS)
    print("\nCase 2: mesh_sync WITH valid AWS Nitro attestation...")
    nitro_token = {
        "tee_type": "AWSNitro",
        "pcr0": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
        "unique_id": "NITRO_ENCLAVE_12345",
        "measurement": "7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a7f8e",
        "signature": "TRUSTED_NITRO_ROOT_SIG",
    }

    ctx_valid = {
        "prefix_val": 100,
        "hard_limit": 500,
        "p300_enabled": True,
        "is_hardware_hardened": True,
        "signatures": [],
        "is_self_designed": False,
        "data_payload": "Syncing state to Nitro...",
        "mesh_latch_active": False,
        "requested_tool": "mesh_sync",
        "remote_attestation": nitro_token,
    }

    with open("test_data/mesh_valid_req.json", "w") as f:
        json.dump(ctx_valid, f)

    try:
        sieve.run_sovereign_logic(
            "test_data/mesh_valid_req.json",
            "test_data/mesh_valid_out.json",
            "genesis",
            "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0",
        )
        print("PASSED: mesh_sync allowed with valid token.")
    except Exception as e:
        print(f"FAILED: Valid mesh_sync was blocked: {e}")

    # Cleanup
    if os.path.exists("test_data"):
        shutil.rmtree("test_data")


if __name__ == "__main__":
    test_galactic_mesh()
