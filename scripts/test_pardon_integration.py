import binascii
import json
import sys
import time
from pathlib import Path

import warm_logic_rs
from cryptography.hazmat.primitives.asymmetric import ed25519

# Constants
REQ_PATH = Path("out/sovereign/request_pardon_test.json")
RESP_PATH = Path("out/sovereign/evidence_pardon_test.json")
LATCH_PATH = Path("out/sovereign/FAIL_LATCH")
KEY_PATH = Path("config/sovereign_owner.key")
POLICY_SIG = "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0"


def reset_latch():
    if LATCH_PATH.exists():
        LATCH_PATH.unlink()


def trigger_latch():
    print("[*] Triggering FAIL_LATCH with sensitive data...")
    reset_latch()
    context = {
        "prefix_val": 100,
        "hard_limit": 200,
        "p300_enabled": False,
        "is_hardware_hardened": True,
        "signatures": [],
        "is_self_designed": False,
        "data_payload": "This is a CONFIDENTIAL file.",
    }
    with open(REQ_PATH, "w") as f:
        json.dump(context, f)

    try:
        warm_logic_rs.run_sovereign_logic(
            str(REQ_PATH), str(RESP_PATH), "genesis", POLICY_SIG
        )
    except Exception as e:
        print(f"[*] Blocked as expected: {e}")

    if not LATCH_PATH.exists():
        raise RuntimeError("FAIL_LATCH was not created!")
    print("Latch created.")


def test_pardon_flow():
    print("\n--- Testing Sovereign Pardon Flow ---")

    # 1. Parse Latch
    content = LATCH_PATH.read_text()
    reason = "Unknown"
    for line in content.split("\n"):
        if line.startswith("REASON: "):
            reason = line.replace("REASON: ", "")
            break

    # 2. Sign Pardon
    print(f"[*] Signing pardon for reason: {reason}")
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(KEY_PATH.read_bytes())
    public_key = private_key.public_key()
    pubkey_hex = binascii.hexlify(public_key.public_bytes_raw()).decode()

    timestamp = int(time.time())
    data_to_sign = f"{timestamp}:{reason}"
    signature = private_key.sign(data_to_sign.encode())
    sig_hex = binascii.hexlify(signature).decode()

    token = {
        "timestamp": timestamp,
        "latch_reason": reason,
        "owner_pubkey": pubkey_hex,
        "signature": sig_hex,
    }

    # 3. Apply Pardon
    token_json = json.dumps(token)
    print("[*] Applying pardon via Rust bridge...")
    warm_logic_rs.apply_sovereign_pardon(token_json)

    # 4. Verify
    if LATCH_PATH.exists():
        print("FAIL: FAIL_LATCH still exists after pardon.")
        sys.exit(1)
    else:
        print("SUCCESS: FAIL_LATCH cleared by signed pardon.")

    # 5. Verify system is unblocked
    print("[*] Verifying system is unblocked...")
    context = {
        "prefix_val": 100,
        "hard_limit": 200,
        "p300_enabled": False,
        "is_hardware_hardened": True,
        "signatures": [],
        "is_self_designed": False,
        "data_payload": "Hello World",
    }
    with open(REQ_PATH, "w") as f:
        json.dump(context, f)

    warm_logic_rs.run_sovereign_logic(
        str(REQ_PATH), str(RESP_PATH), "genesis", POLICY_SIG
    )
    print("SUCCESS: System accepting requests again.")


def main():
    if not KEY_PATH.exists():
        print("Owner key missing. Run forge_constitution.py first.")
        return

    trigger_latch()
    test_pardon_flow()
    print("\nPARDON PROTOCOL VERIFIED")


if __name__ == "__main__":
    main()
