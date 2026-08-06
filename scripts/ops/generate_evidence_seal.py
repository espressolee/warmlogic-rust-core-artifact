import hashlib
import json
import os
import platform
import subprocess
import sys


def generate_evidence_seal():
    print("Generating System Evidence Seal...")

    # 1. Capture Environment
    seal = {
        "system": {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "toolchain": {
            "python_version": sys.version,
            "rustc_version": subprocess.check_output(["rustc", "--version"])
            .decode()
            .strip(),
            "maturin_version": subprocess.check_output(["maturin", "--version"])
            .decode()
            .strip(),
        },
        "artifacts": {
            "telemetry_v2_hash": hashlib.sha256(
                open("out/bridge_eval/bridge_eval_v2/full_telemetry.json", "rb").read()
            ).hexdigest(),
            "lib_rs_hash": hashlib.sha256(
                open("warm_logic_rs/src/lib.rs", "rb").read()
            ).hexdigest(),
        },
    }

    # 2. Save Seal
    out_path = "out/bridge_eval/bridge_eval_v2/SYSTEM_PROOF_SEAL.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(seal, f, indent=2)

    print(f"System Evidence Hash SEALED at {out_path}")
    print(f"   Artifact Hash: {seal['artifacts']['telemetry_v2_hash'][:16]}...")


if __name__ == "__main__":
    generate_evidence_seal()
