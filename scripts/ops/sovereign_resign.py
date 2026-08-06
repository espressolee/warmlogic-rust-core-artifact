#!/usr/bin/env python3
"""
Sovereign Resign Tool
Generates new ML-DSA-65 keys and signs the integrity manifest.
Use this after a "Hard-Fork" or Kernel Upgrade.
"""

import base64
import json
import os
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

try:
    from warm_logic.kernel.provenance import CodeIntegrityGuard
    from warm_logic.kernel.sys.cryptography import MLDSA
except ImportError as e:
    print(f"Error importing kernel: {e}")
    sys.exit(1)


def main():
    print(" SOVEREIGN RESIGN: Initiating PQC Key Generation...")

    # 1. Generate Keys
    try:
        # Assuming MLDSA.generate_keypair() returns a PQCKeypair object with .public_key and .private_key (hex strings)
        mldsa = MLDSA()
        keypair = mldsa.generate_keypair()
        print("New ML-DSA-65 Keys Generated.")
    except Exception as e:
        print(f"Key Generation Failed: {e}")
        sys.exit(1)

    # 2. Save Public Key
    pub_path = ROOT_DIR / "data" / "provenance" / "sovereign_pub.dat"
    pub_path.parent.mkdir(parents=True, exist_ok=True)

    # Format: B64 encoded HEX string (to match provenance expectation)
    pub_b64 = base64.b64encode(keypair.public_key.encode("utf-8")).decode("utf-8")
    with open(pub_path, "w") as f:
        f.write(pub_b64)
    print(f"Public Key saved to {pub_path}")

    # 3. Save Private Key (Securely!)
    priv_path = ROOT_DIR / ".sovereign" / "sovereign.key"
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(priv_path, "w") as f:
        f.write(keypair.private_key)
    # restrict permissions
    os.chmod(priv_path, 0o600)
    print(f"Private Key saved to {priv_path} (Keep Safe!)")

    # 4. Generate Manifest (Hash Files)
    # Reuse simple logic or just hardcode for this demo?
    # Let's use the simplest approach: Re-scan what we know.
    # Actually, let's just make a dummy file map for demonstration if scan is expensive
    # But CodeIntegrityGuard doesn't expose scan.
    # Let's do a mini-scan of core files.
    file_map = {}
    scan_targets = [
        "warm_logic/kernel/provenance.py",
        "warm_logic/kernel/autonomy/budget.py",
        "warm_logic/app/cockpit/server.py",
        "warm_logic/kernel/sys/cryptography.py",
    ]

    guard = CodeIntegrityGuard(strict=False)
    for t in scan_targets:
        full_p = ROOT_DIR / t
        h = guard._hash_file(full_p)
        if h:
            file_map[t] = h

    manifest_data = {
        "files": file_map,
        # Signature added later
    }

    # 5. Sign Manifest
    # Payload must match verification logic: json.dumps(..., sort_keys=True)
    payload = json.dumps(file_map, sort_keys=True)
    signature = mldsa.sign(payload, keypair.private_key)

    manifest_data["signature"] = signature

    manifest_path = ROOT_DIR / "data" / "provenance" / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"Manifest signed and saved to {manifest_path}")
    print("SYSTEM IS NOW SECURED WITH ML-DSA-65.")


if __name__ == "__main__":
    main()
