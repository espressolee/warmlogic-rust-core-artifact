import base64
import binascii
import json
from pathlib import Path

import yaml
from cryptography.hazmat.primitives.asymmetric import ed25519

OUT_DIR = Path("data/provenance")
CONSTITUTION_PATH = OUT_DIR / "constitution.signed.yaml"
KEY_PATH = OUT_DIR / "owner_priv.dat"
PUB_PATH = OUT_DIR / "owner_pub.dat"


def get_owner_key():
    if KEY_PATH.exists():
        # Decode B64
        key_bytes = base64.b64decode(KEY_PATH.read_bytes())
        return ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)

    # Generate new key
    print(f"[*] No Owner key found. Generating new key at {KEY_PATH}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    private_key = ed25519.Ed25519PrivateKey.generate()
    # Obfuscate with B64
    KEY_PATH.write_bytes(base64.b64encode(private_key.private_bytes_raw()))

    # Also save public key
    public_key = private_key.public_key()
    PUB_PATH.write_bytes(base64.b64encode(public_key.public_bytes_raw()))

    return private_key


def forge_constitution(keywords, defense_level=100, entropy_threshold=5.5):
    private_key = get_owner_key()
    public_key = private_key.public_key()
    pubkey_hex = binascii.hexlify(public_key.public_bytes_raw()).decode()

    # Data to be signed (Matches Rust struct order)
    data_dict = {
        "sensitive_keywords": keywords,
        "defense_level": defense_level,
        "owner_pubkey": pubkey_hex,
        "entropy_threshold": entropy_threshold,
    }

    # Stable serialization to match Rust's serde_json behavior
    # NOTE: Rust's serde_json::to_string usually has no spaces
    serialized_data = json.dumps(data_dict, separators=(",", ":"), sort_keys=False)

    # Sign
    signature = private_key.sign(serialized_data.encode())
    sig_hex = binascii.hexlify(signature).decode()

    # Final Signed Constitution (YAML)
    signed_constitution = {"data": data_dict, "signature": sig_hex}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONSTITUTION_PATH, "w") as f:
        yaml.dump(signed_constitution, f, sort_keys=False)

    print(f"Constitution FORGED and SIGNED at {CONSTITUTION_PATH}")
    print(f"   Keywords: {keywords}")
    print(f"   Owner PubKey: {pubkey_hex}")


if __name__ == "__main__":
    # Example usage: Add "BANANA" to the list of forbidden seeds
    forge_constitution(["BANANA", "TOP_SECRET_X", "MALWARE_MD5"])
