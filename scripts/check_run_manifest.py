"""Checks run manifest JSON files for basic validity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple


def check_manifest(manifest_path: Path) -> Tuple[bool, str]:
    """Check a manifest file for minimum JSON validity constraints."""
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive guard
        return False, f"{manifest_path}: invalid JSON ({exc})"
    if not isinstance(payload, dict):
        return False, f"{manifest_path}: top-level payload must be an object"
    return True, f"{manifest_path}: ok"


def validate_manifest(manifest_path: Path) -> bool:
    """Compatibility helper for callers that only need a boolean."""
    ok, _ = check_manifest(manifest_path)
    return ok


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str)
    parser.add_argument("--require", action="store_true")
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Exit with non-zero status if any manifest is invalid JSON.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    manifest_dir = Path(args.dir) if args.dir else None

    print("Checking run manifest...")

    if manifest_dir is None:
        print("No --dir provided; nothing to validate.")
        sys.exit(0)

    if not manifest_dir.exists():
        if args.require:
            print(f"ERROR: manifest directory does not exist: {manifest_dir}")
            sys.exit(1)
        print(f"WARNING: manifest directory does not exist: {manifest_dir}")
        sys.exit(0)

    manifest_files = sorted(manifest_dir.glob("*.json"))
    if args.require and not manifest_files:
        print("ERROR: No manifests found and --require was set.")
        sys.exit(1)
    if not manifest_files:
        print(f"No manifest JSON files found under: {manifest_dir}")
        sys.exit(0)

    invalid = []
    for manifest_path in manifest_files:
        ok, message = check_manifest(manifest_path)
        print(message)
        if not ok:
            invalid.append(str(manifest_path))

    if invalid:
        print(f"Found {len(invalid)} invalid manifest(s).")
        if args.fail_on_invalid:
            sys.exit(1)

    print("Run manifest validated successfully.")
    sys.exit(0)
