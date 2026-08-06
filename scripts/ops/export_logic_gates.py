import json
import os
import sys

# Dynamic root detection
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from warm_logic.kernel.formal_invariants import ALLOWED_TRANSITIONS

"""
Sovereign Logic Gate Exporter (Era 47).
Extracts Python formal invariants into a portable JSON format.
"""


def export_gates():
    print("Era 47: Exporting Sovereign Logic Gates...")

    # Convert Enum keys to string names for JSON portability
    portable_gates = {}
    for phase, allowed in ALLOWED_TRANSITIONS.items():
        portable_gates[phase.name] = [next_p.name for next_p in allowed]

    output_path = os.path.join(ROOT_DIR, "warm_logic/kernel/sovereign_logic_gates.json")

    # Manifest Metadata for verification
    manifest = {
        "version": "1.1",
        "era": 48,
        "type": "FORMAL_LOGIC_SPEC",
        "description": "Ported TLA+ invariants with Era 48 Sovereign Seal.",
        "logic_gates": portable_gates,
        "signature": "era48_seal_8784af87ebfc8d7f6e39c9fdc3f391c78198443feb748a11aa45943b11198459",
    }

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=4)

    print(f"Exported {len(portable_gates)} logic gates to: {output_path}")


if __name__ == "__main__":
    export_gates()
