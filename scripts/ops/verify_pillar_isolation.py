#!/usr/bin/env python3
import re
import sys
from pathlib import Path

# Explicitly allowed bridges between pillars
ALLOWED_BRIDGES = {
    "core": ["governance", "research"],
    "ops": ["core", "audit"],
    "management": ["core", "history"],
    "audit": ["core", "ops", "governance"],
    "governance": ["core"],
    "research": ["core"],
    "history": [],
    "archive": [],
}


def check_imports():
    print(" Starting Hard Pillar Isolation Scan...")
    docs_dir = Path("docs")
    violations = 0

    for pillar in ALLOWED_BRIDGES.keys():
        pillar_path = docs_dir / pillar
        if not pillar_path.exists():
            continue

        for file in pillar_path.rglob("*.md"):
            with open(file, "r") as f:
                content = f.read()
                # Find links to other pillars
                links = re.findall(
                    r"\(./docs/([^/]+)/",
                    content,
                )
                for linked_pillar in links:
                    if (
                        linked_pillar != pillar
                        and linked_pillar not in ALLOWED_BRIDGES[pillar]
                    ):
                        print(
                            f"❌ Violation: {file.relative_to(Path.cwd())} links to illegal pillar '{linked_pillar}'"
                        )
                        violations += 1

    if violations == 0:
        print("PASS: No illegal cross-pillar leakage detected.")
        return True
    else:
        print(f"FAIL: {violations} architectural violations found.")
        return False


if __name__ == "__main__":
    if check_imports():
        sys.exit(0)
    else:
        sys.exit(1)
