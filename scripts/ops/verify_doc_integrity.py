import os
import re
import sys

# Policy Constants
TIER_PATTERN = re.compile(r"> \*\*TIER\*\*: Tier-(0|1|2)")
LEGACY_TERMS = {
    "Active Legitimacy": "Operationalized Traceability",
    "Dead Weight": "Foundational Context",
    "Governance Veto": "Atomic Veto",
}

CORE_PATHS = ["spec", "docs/01_Core", "docs/research"]


def verify_file(filepath):
    errors = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

        # 1. Check Tier Tag
        if not TIER_PATTERN.search(content):
            errors.append("MISSING_TIER_TAG")

        # 2. Check Legacy Terms
        for term, replacement in LEGACY_TERMS.items():
            if term in content:
                errors.append(f"LEGACY_TERM_DETECTED: '{term}' (Use '{replacement}')")

        # 3. Check Internal Links (Broad match)
        links = re.findall(
            r"\[.*?\]\((./(.*?))\)",
            content,
        )
        for full_url, rel_path in links:
            # Strip anchor
            clean_path = rel_path.split("#")[0]
            abs_path = os.path.join(
                os.getcwd(), clean_path
            )
            if not os.path.exists(abs_path):
                errors.append(f"BROKEN_LINK: {clean_path}")

    return errors


def main():
    root = os.getcwd()
    reports = {}

    for path in CORE_PATHS:
        full_path = os.path.join(root, path)
        if not os.path.isdir(full_path):
            continue

        for dirpath, _, filenames in os.walk(full_path):
            for f in filenames:
                if f.endswith(".md"):
                    fpath = os.path.join(dirpath, f)
                    errors = verify_file(fpath)
                    if errors:
                        reports[fpath] = errors

    if not reports:
        print("A+ Integrity Verified. No issues found.")
        sys.exit(0)
    else:
        print(f"Found errors in {len(reports)} files:")
        for f, errs in reports.items():
            print(f"\n[ {os.path.relpath(f, root)} ]")
            for e in errs:
                print(f"  - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
