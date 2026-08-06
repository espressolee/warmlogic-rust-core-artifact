#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

DIST_DIR = "dist"
MANIFEST_FILE = "RELEASE_MANIFEST.md"


def run_command(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error:\n{result.stderr}")
        sys.exit(1)
    print(result.stdout)


def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def main():
    print("WarmLogic Genesis Packager ")
    print("==================================")

    # 1. Clean dist
    if os.path.exists(DIST_DIR):
        print(f"Cleaning {DIST_DIR}...")
        for f in os.listdir(DIST_DIR):
            os.remove(os.path.join(DIST_DIR, f))
    else:
        os.makedirs(DIST_DIR)

    # 2. Build Wheel and Sdist
    print("Building Source and Wheel artifacts...")
    # Using 'build' module if available, otherwise fallback could be implemented but we assume modern env
    try:
        import build
    except ImportError:
        print(" 'build' module not found. Installing...")
        run_command("pip install build")

    run_command("python3 -m build")

    # 3. Generate Manifest
    print("Generating Release Manifest...")

    artifacts = []
    for f in os.listdir(DIST_DIR):
        path = os.path.join(DIST_DIR, f)
        if os.path.isfile(path):
            sha = calculate_sha256(path)
            size = os.path.getsize(path)
            artifacts.append({"filename": f, "sha256": sha, "size_bytes": size})

    # Write Manifest
    with open(MANIFEST_FILE, "w") as f:
        f.write(f"# 🦅 WarmLogic Genesis Manifest\n\n")
        f.write(f"**Date**: {datetime.utcnow().isoformat()}Z\n")
        f.write(f"**Version**: 1.0.0-omega\n")
        f.write(f"**Builder**: Sovereign Packager\n\n")
        f.write("## Artifacts\n\n")
        f.write("| Filename | Size (Bytes) | SHA256 Checksum |\n")
        f.write("| :--- | :--- | :--- |\n")
        for art in artifacts:
            f.write(
                f"| `{art['filename']}` | {art['size_bytes']} | `{art['sha256']}` |\n"
            )

        f.write("\n## Integrity Statement\n")
        f.write(
            "> These artifacts represent the compiled state of the WarmLogic Sovereign Kernel at the closure.\n"
        )
        f.write("> Use `sha256sum -c` to verify integrity before deployment.\n")

    print(f"\nGenesis Release Complete!")
    print(f"   Artifacts: {DIST_DIR}/")
    print(f"   Manifest:  {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
