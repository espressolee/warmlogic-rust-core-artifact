#!/usr/bin/env python3
import re
import sys
from pathlib import Path

# Authoritative Pillar Definitions
PILLARS = [
    "core",
    "ops",
    "management",
    "audit",
    "governance",
    "research",
    "history",
    "archive",
]

# Hard-coded allowable bridges (Inbound/Outbound)
ALLOWABLE_BRIDGES = {
    "core": ["governance", "research"],
    "ops": ["core", "audit"],
    "management": ["core", "history"],
    "audit": ["core", "ops", "governance"],
    "governance": ["core"],
    "research": ["core"],
    "history": [],
    "archive": [],
}


def enforce_isolation():
    print("[GATEKEEPER] Starting Hard Pillar Isolation Enforcement...")
    docs_dir = Path("docs")
    violations = []

    # 1. Scan Python files for cross-pillar import leaks (if any structured patterns exist)
    # 2. Scan Markdown files for cross-pillar link leaks
    for pillar in PILLARS:
        pillar_path = docs_dir / pillar
        if not pillar_path.exists():
            continue

        for file in pillar_path.rglob("*.md"):
            with open(file, "r") as f:
                content = f.read()
                # Pattern: find file:///.../docs/[pillar]/
                # We specifically target the 'docs' directory structure
                links = re.findall(r"file:///.*?/docs/([^/]+)/", content)
                for target_pillar in links:
                    if target_pillar in PILLARS and target_pillar != pillar:
                        if target_pillar not in ALLOWABLE_BRIDGES.get(pillar, []):
                            violations.append(
                                f"ILLEGAL LINK: {file.relative_to(Path.cwd())} -> docs/{target_pillar}/"
                            )

    if violations:
        print("\nARCHITECTURAL VIOLATIONS DETECTED:")
        for v in violations:
            print(f"  - {v}")
        print(
            "\n❌ ENFORCEMENT FAILED. Fix the architectural leakage before proceeding."
        )
        return False

    print("ENFORCEMENT PASSED: Architectural integrity verified.")
    return True


if __name__ == "__main__":
    if enforce_isolation():
        sys.exit(0)
    else:
        sys.exit(1)
