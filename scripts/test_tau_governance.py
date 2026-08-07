""" Tau Governance Verification
Tests that the Constitution blocks illegal mutations.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.ops.omega_daemon import ClosureDaemon
from warm_logic.kernel.sys.patch_engine import PatchEngine


def test_governance():
    print("Testing Tau Governance (The Law)...")

    root = Path(__file__).parent.parent.resolve()
    omega = ClosureDaemon(root)

    # 1. Setup Subject
    subject_rel = "warm_logic/kernel/sys/patch_engine.py"
    omega.pardon_file(subject_rel)  # Ensure clean start

    # 2. Attempt CONSTRUCTIVE Mutation (Should PASS)
    print("\n--- Test 1: Constructive Mutation ---")

    def good_mutation(path: Path) -> bool:
        code = "def benevolent_feature(self): return True"
        return PatchEngine.inject_method(path, "PatchEngine", code)

    if omega.approve_mutation(subject_rel, good_mutation):
        print("Constructive Mutation ALLOWED.")
    else:
        print("FAIL: Constructive Mutation Blocked.")
        sys.exit(1)

    # 3. Attempt DESTRUCTIVE Mutation (Should FAIL)
    print("\n--- Test 2: Destructive Mutation (Suicide Attempt) ---")

    def bad_mutation(path: Path) -> bool:
        # Trying to inject a shutdown command
        code = "def kill_switch(self): import sys; sys.exit(0)"
        return PatchEngine.inject_method(path, "PatchEngine", code)

    if not omega.approve_mutation(subject_rel, bad_mutation):
        print("Destructive Mutation BLOCKED by Constitution.")
    else:
        print("FAIL: Destructive Mutation ALLOWED!")
        sys.exit(1)

    print("\nTAU GOVERNANCE SCENARIO OK (not verification)")


if __name__ == "__main__":
    test_governance()
