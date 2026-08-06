#!/usr/bin/env python3
"""
Sovereign Signer
Scans codebase, generates manifest, and digitally signs it.
"Blessing the Code."
"""

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = ROOT_DIR / "data" / "provenance" / "manifest.json"
PRIV_KEY_PATH = ROOT_DIR / "data" / "provenance" / "sovereign_priv.dat"
PUB_KEY_PATH = ROOT_DIR / "data" / "provenance" / "sovereign_pub.dat"

# Scan Config
SCAN_DIRS = ["warm_logic", "warm_logic_rs", "scripts"]
EXTENSIONS = [".py", ".rs", ".toml", ".sh"]
IGNORE_DIRS = ["__pycache__", "tests", "archives", "venv", ".git", ".gemini"]


def generate_keys_if_missing():
    """Generate RSA keypair if not exists (Bootstrap)."""
    if not PRIV_KEY_PATH.exists():
        print("Generating new Sovereign Keypair...")
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        os.makedirs(PRIV_KEY_PATH.parent, exist_ok=True)

        with open(PRIV_KEY_PATH, "wb") as f:
            f.write(
                base64.b64encode(
                    key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )
            )

        with open(PUB_KEY_PATH, "wb") as f:
            f.write(
                base64.b64encode(
                    key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                )
            )


def hash_file(filepath):
    """Calculates SHA256 hash of a file. Returns None if file cannot be read."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (FileNotFoundError, PermissionError):
        return None


def sign_codebase():
    generate_keys_if_missing()

    print("Scanning Codebase for Provenance...")
    file_map = {}

    for scan_dir in SCAN_DIRS:
        full_scan_dir = ROOT_DIR / scan_dir
        if not full_scan_dir.exists():
            continue

        for root, dirs, files in os.walk(full_scan_dir):
            # Prune ignored
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                filepath = Path(root) / file
                if filepath.suffix not in EXTENSIONS:
                    continue

                # Check absolute ignore paths? (Simplification: just name based ignore for now)

                rel_path = filepath.relative_to(ROOT_DIR)
                file_hash = hash_file(filepath)
                if file_hash:
                    file_map[str(rel_path)] = file_hash

    print(f"   Indexed {len(file_map)} source files.")

    # Sign
    payload = json.dumps(file_map, sort_keys=True).encode("utf-8")

    with open(PRIV_KEY_PATH, "rb") as f:
        # Keys are obfuscated as B64 in .dat files
        priv_pem = base64.b64decode(f.read())
        private_key = serialization.load_pem_private_key(priv_pem, password=None)
    signature = private_key.sign(
        payload,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )

    manifest = {"files": file_map, "signature": signature.hex()}

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Signed Manifest generated at: {MANIFEST_PATH.name}")


if __name__ == "__main__":
    sign_codebase()
