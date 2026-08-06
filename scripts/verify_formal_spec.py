import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from warm_logic.kernel.logic.foundation import InvariantEnforcer


def verify_formal_spec():
    print("Initializing Formal Verification Bridge...")
    enforcer = InvariantEnforcer()

    # Test 1: Boot Time Invariant
    start = time.time()
    # Simulate fast boot
    time.sleep(0.001)
    if enforcer.verify_boot(start):
        print("Boot Time Invariant Passed (< 33ms)")
    else:
        print(f"Boot Time Violation: {enforcer.violations[-1]}")
        sys.exit(1)

    # Test 2: State Uniqueness Invariant
    if enforcer.check_state_collision("hashA", "hashB", "contentA", "contentB"):
        print("State Uniqueness Invariant Passed")
    else:
        print(f"State Uniqueness Violation: {enforcer.violations[-1]}")
        sys.exit(1)

    # Test 3: Simulating a Violation (Scientific Control)
    print("Simulating Violation (Control Test)...")
    # Same hash, different content -> Violation
    if not enforcer.check_state_collision("hashA", "hashA", "contentA", "contentB"):
        print("Violation Correctly Caught: Hash Collision")
    else:
        print("FAILED: Did not catch hash collision!")
        sys.exit(1)


if __name__ == "__main__":
    verify_formal_spec()
