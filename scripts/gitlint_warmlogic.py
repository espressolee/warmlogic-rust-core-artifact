#!/usr/bin/env python3
"""Lightweight commit message lint for CI."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SUBJECT_RE = re.compile(r"^P[0-9xX]{3,}:[ ]+.+")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: gitlint_warmlogic.py <commit-message-file>")
        return 2

    message_file = Path(sys.argv[1])
    if not message_file.exists():
        print(f"ERROR: commit message file not found: {message_file}")
        return 1

    lines = [line.rstrip("\n") for line in message_file.read_text(encoding="utf-8").splitlines()]
    subject = next((line.strip() for line in lines if line.strip()), "")

    if not subject:
        print("ERROR: empty commit subject")
        return 1
    if len(subject) > 120:
        print("ERROR: commit subject exceeds 120 chars")
        return 1
    if subject.lower().startswith(("fixup!", "squash!", "wip")):
        print("ERROR: temporary commit subject prefix is not allowed")
        return 1
    if not SUBJECT_RE.match(subject):
        print("ERROR: commit subject must match 'Pxxx: <summary>'")
        return 1

    print("gitlint_warmlogic: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
