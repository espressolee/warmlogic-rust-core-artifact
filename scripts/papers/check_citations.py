#!/usr/bin/env python3
"""Check that markdown citation keys exist in a .bib file."""

from __future__ import annotations

import re
import sys
from pathlib import Path

CITE_RE = re.compile(r"@([A-Za-z0-9_:\-]+)")
BIB_RE = re.compile(r"@\w+\{\s*([^,\s]+)")


def load(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: check_citations.py <paper.md> <master.bib>")
        return 2

    paper = Path(sys.argv[1])
    bib = Path(sys.argv[2])

    try:
        paper_text = load(paper)
        bib_text = load(bib)
    except FileNotFoundError as exc:
        print(f"ERROR: missing file: {exc}")
        return 1

    cited = set(CITE_RE.findall(paper_text))
    keys = set(BIB_RE.findall(bib_text))
    missing = sorted(k for k in cited if k not in keys)

    if missing:
        print(f"ERROR: unresolved citation keys in {paper}: {', '.join(missing)}")
        return 1

    print(f"citations check: OK ({paper})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
