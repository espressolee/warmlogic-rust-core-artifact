"""
Logic Portability Verification (Era 47).
Verifies that the JSON logic spec is correctly loaded and matches Python expectations.
"""

import json
import os
import sys

# Dynamic root detection
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from warm_logic.kernel.core.state_root import KernelPhase


def test_logic_portability():
    print("Era 47: Logic Portability Verification...")

    gates_path = os.path.join(ROOT_DIR, "warm_logic/kernel/sovereign_logic_gates.json")

    with open(gates_path, "r") as f:
        manifest = json.load(f)

    gates = manifest["logic_gates"]
    print(f"Loaded {len(gates)} logic gates from portable manifest.")

    # Cross-check specific transitions
    expected = {
        "BOOT_INIT": ["AUTHORIZED", "HALTED"],
        "AUTHORIZED": ["ALIGNING", "HALTED"],
        "HALTED": [],
    }

    for phase, allowed in expected.items():
        print(f"Checking {phase}...")
        manifest_allowed = set(gates.get(phase, []))
        expected_allowed = set(allowed)

        assert manifest_allowed == expected_allowed, (
            f"Mismatch in {phase}: {manifest_allowed} != {expected_allowed}"
        )
        print(f"{phase} matches.")

    print(
        "\n✅ Era 47 Logic Portability Verified: Host-independent specs are consistent."
    )


if __name__ == "__main__":
    test_logic_portability()
