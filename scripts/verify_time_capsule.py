#!/usr/bin/env python3
"""
Time Capsule Verification
Unpacks and audits a sealed archive.
"""

import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT_DIR / "archives" / "time_capsules"
VERIFY_DIR = ROOT_DIR / "archives" / "verify_sandbox"


def hash_file(filepath):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_latest_capsule():
    # Find latest archive
    archives = sorted(list(ARCHIVE_DIR.glob("*.tar.gz")))
    if not archives:
        print("No capsules found.")
        sys.exit(1)

    latest_archive = archives[-1]
    print(f"Verifying: {latest_archive.name}")

    if os.path.exists(VERIFY_DIR):
        import shutil

        shutil.rmtree(VERIFY_DIR)
    os.makedirs(VERIFY_DIR)

    # Unpack
    try:
        with tarfile.open(latest_archive, "r:gz") as tar:
            tar.extractall(path=VERIFY_DIR)
    except Exception as e:
        print(f"EXTRACTION FAILED: {e}")
        sys.exit(1)

    # Locate Manifest
    # The tarball creates a subdir matching the capsule name
    extracted_root = list(VERIFY_DIR.iterdir())[0]
    manifest_path = extracted_root / "TIME_CAPSULE_MANIFEST.json"

    if not manifest_path.exists():
        print("MANIFEST MISSING")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    print(f"Era: {manifest['era']}")
    print(f"Timestamp: {manifest['timestamp']}")

    # Audit Files
    errors = 0
    for rel_path, expected_hash in manifest["files"].items():
        # skip manifest itself
        if "TIME_CAPSULE_MANIFEST.json" in rel_path:
            continue

        file_path = extracted_root / rel_path
        if not file_path.exists():
            print(f"MISSING: {rel_path}")
            errors += 1
            continue

        actual_hash = hash_file(file_path)
        if actual_hash != expected_hash:
            print(f"CORRUPTED: {rel_path}")
            errors += 1

    if errors == 0:
        print("INTEGRITY CONFIRMED (100%)")
        # Cleanup
        import shutil

        shutil.rmtree(VERIFY_DIR)
    else:
        print(f"VERIFICATION FAILED with {errors} errors")
        sys.exit(1)


if __name__ == "__main__":
    verify_latest_capsule()
