#!/usr/bin/env python3
"""Check markdown front matter presence and required keys."""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = ("title:", "authors:", "abstract:")


def validate(path: Path) -> list[str]:
    if not path.exists():
        return [f"missing file: {path}"]
    text = path.read_text(encoding="utf-8")
    errors = []
    if not text.startswith("---\n"):
        errors.append(f"{path}: missing front matter delimiter")
    for key in REQUIRED:
        if key not in text:
            errors.append(f"{path}: missing '{key}'")
    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: check_front_matter.py <paper.md> [<paper.md> ...]")
        return 2

    errors: list[str] = []
    for arg in sys.argv[1:]:
        errors.extend(validate(Path(arg)))

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1

    print("front matter checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
