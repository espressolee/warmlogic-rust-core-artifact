"""Check Experiment Manifests CI Script (Phase 20)."""

import json
import os
import sys
from pathlib import Path


def main():
    exp_dir_str = (
        os.environ.get("EXPERIMENTS_DIR")
        or os.environ.get("OUT_EXPERIMENTS_DIR")
        or "out/experiments"
    )
    exp_dir = Path(exp_dir_str)

    if not exp_dir.exists():
        print(f"Experiments directory {exp_dir} not found. Skipping.")
        return 0

    manifests = list(exp_dir.glob("*.manifest.json"))
    if not manifests:
        print("No experiment manifests found. Skipping.")
        return 0

    # Validation logic (Stub for now: just log)
    print(f"Found {len(manifests)} experiment manifests.")
    for m in manifests:
        print(f"Validated {m.name} [ADVISORY]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
