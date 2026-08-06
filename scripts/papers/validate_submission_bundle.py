#!/usr/bin/env python3
"""Validate generated submission bundle zip artifacts."""

from __future__ import annotations

import glob
import sys
import zipfile
from pathlib import Path


def resolve(pattern: str) -> list[Path]:
    matches = [Path(p) for p in glob.glob(pattern)]
    if matches:
        return matches
    return [Path(pattern)]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_submission_bundle.py <bundle.zip|glob>")
        return 2

    targets: list[Path] = []
    for arg in sys.argv[1:]:
        targets.extend(resolve(arg))

    errors = []
    for path in targets:
        if not path.exists():
            errors.append(f"missing bundle: {path}")
            continue
        if not zipfile.is_zipfile(path):
            errors.append(f"not a zip file: {path}")
            continue
        with zipfile.ZipFile(path) as zf:
            if not zf.namelist():
                errors.append(f"empty zip archive: {path}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1

    print("bundle validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
