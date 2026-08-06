import binascii
import json
import time
from pathlib import Path

import warm_logic_rs
from cryptography.hazmat.primitives.asymmetric import ed25519

LATCH_PATH = Path("out/sovereign/FAIL_LATCH")
KEY_PATH = Path("config/sovereign_owner.key")


def get_owner_key():
    if not KEY_PATH.exists():
        raise FileNotFoundError(
            f"Owner key not found at {KEY_PATH}. Run forge_constitution.py first."
        )
    return ed25519.Ed25519PrivateKey.from_private_bytes(KEY_PATH.read_bytes())


def parse_latch():
    if not LATCH_PATH.exists():
        return None
    content = LATCH_PATH.read_text()
    lines = content.split("\n")
    data = {}
    for line in lines:
        if ": " in line:
            k, v = line.split(": ", 1)
            data[k] = v
    return data


def apply_pardon():
    print("SOVEREIGN PARDON PROTOCOL")

    latch_data = parse_latch()
    if not latch_data:
        print("System is not latched. No pardon needed.")
        return

    reason = latch_data.get("REASON", "Unknown")
    policy = latch_data.get("POLICY", "Unknown")

    print(f"[FORENSICS] System is LATCHED due to: {reason} [{policy}]")

    confirm = input(
        "\nDo you wish to Pardon this event and restore the system? (y/N): "
    )
    if confirm.lower() != "y":
        print("Operation cancelled. System remains in FAIL state.")
        return

    private_key = get_owner_key()
    public_key = private_key.public_key()
    pubkey_hex = binascii.hexlify(public_key.public_bytes_raw()).decode()

    timestamp = int(time.time())

    # Data to be signed: timestamp:reason
    data_to_sign = f"{timestamp}:{reason}"
    signature = private_key.sign(data_to_sign.encode())
    sig_hex = binascii.hexlify(signature).decode()

    token = {
        "timestamp": timestamp,
        "latch_reason": reason,
        "owner_pubkey": pubkey_hex,
        "signature": sig_hex,
    }

    token_json = json.dumps(token)

    try:
        warm_logic_rs.apply_sovereign_pardon(token_json)
        print("\n[PARDON] Signature verified. System restored to P-100 SAFE.")
    except Exception as e:
        print(f"\n[ERROR] Pardon rejected by Rust Core: {e}")


if __name__ == "__main__":
    apply_pardon()
