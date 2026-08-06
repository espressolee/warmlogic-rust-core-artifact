#!/usr/bin/env python3
import yaml
import os
import sys
from pathlib import Path

MANIFEST_PATH = "ROOT_MANIFEST.yaml"


def check_manifest():
    if not os.path.exists(MANIFEST_PATH):
        print(f"Manifest not found at {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r") as f:
        data = yaml.safe_load(f)

    print(f"Checking manifest: {MANIFEST_PATH}")
    errors = []

    # Check Pillars
    if "pillars" in data:
        for name, info in data["pillars"].items():
            path = info.get("path")
            if not path:
                errors.append(f"Pillar '{name}' missing 'path' field.")
                continue
            if not os.path.exists(path):
                errors.append(f"❌ Pillar '{name}' path not found: {path}")
            else:
                print(f"Pillar '{name}': {path}")

    # Check Key Files
    if "key_files" in data:
        for name, path in data["key_files"].items():
            if not os.path.exists(path):
                errors.append(f"❌ Key File '{name}' path not found: {path}")
            else:
                print(f"Key File '{name}': {path}")

    # Check System
    if "system" in data:
        for name, path in data["system"].items():
            if not os.path.exists(path):
                errors.append(f"❌ System '{name}' path not found: {path}")
            else:
                print(f"System '{name}': {path}")

    if errors:
        print("\nERRORS FOUND:")
        for e in errors:
            print(e)
        sys.exit(1)

    print("\nAll manifest paths verified successfully.")


if __name__ == "__main__":
    check_manifest()
