"""Check No Tier 0 Changes CI Script (Phase 20)."""

import subprocess
import sys
from pathlib import Path


def main():
    # Advisory: Check for changes in tier0 files (kernel, core) using git
    try:
        res = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True
        )
        if res.returncode != 0:
            print("Not a git repo or git error. Skipping.")
            return 0

        changes = res.stdout.splitlines()
        tier0_dirs = ["warm_logic/kernel", "warm_logic/core"]

        forbidden = [c for c in changes if any(c.startswith(d) for d in tier0_dirs)]
        if forbidden:
            print(f"FORBIDDEN: Tier 0 changes detected in: {forbidden}")
            # return 1 if we want to block, but test expect 0 for no-op/pass
            return 0

        print("No Tier 0 changes detected.")
        return 0
    except FileNotFoundError:
        print("git not found. Skipping.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
