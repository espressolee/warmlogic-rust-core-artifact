#!/usr/bin/env python3
import hashlib
import json
import os
from datetime import datetime


def hash_file(filepath):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_baseline():
    print(" WARMLOGIC FINAL INTEGRITY BASELINING")
    print("=" * 50)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    # Components to include in the baseline
    critical_paths = [
        "warm_logic/kernel",
        "scripts/ops",
        "docs/papers",
        "pyproject.toml",
    ]

    component_hashes = {}

    for path in critical_paths:
        abs_path = os.path.join(project_root, path)
        if os.path.isfile(abs_path):
            component_hashes[path] = hash_file(abs_path)
        elif os.path.isdir(abs_path):
            # Sort files for deterministic hashing
            files = []
            for root, _, filenames in os.walk(abs_path):
                for f in filenames:
                    if not f.startswith(".") and not f.endswith(".pyc"):
                        files.append(os.path.join(root, f))

            dir_hasher = hashlib.sha256()
            for f in sorted(files):
                dir_hasher.update(hash_file(f).encode())
            component_hashes[path] = dir_hasher.hexdigest()

    # The Grand Sovereignty Root
    root_string = json.dumps(component_hashes, sort_keys=True)
    gs_root = hashlib.sha256(root_string.encode()).hexdigest()

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    baseline = {
        "program": "WarmLogic P990",
        "milestone": "Month 6 (Consolidation)",
        "timestamp": timestamp,
        "grand_sovereignty_root": gs_root,
        "components": component_hashes,
    }

    baseline_path = os.path.join(project_root, "SOVEREIGN_BASELINE.json")
    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=4)

    print(f"Final Baseline Hash: {gs_root}")
    print(f"Baseline Document: {baseline_path}")
    return gs_root


if __name__ == "__main__":
    generate_baseline()
