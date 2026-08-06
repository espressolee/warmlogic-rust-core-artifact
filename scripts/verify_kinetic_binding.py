import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from warm_logic.kernel.sys.security import KineticSovereign


def verify_kinetic():
    print("Initializing Kinetic Sovereign...")

    # attempt binding
    binding = KineticSovereign.bind_genesis()
    uuid = KineticSovereign.get_hardware_uuid()

    print(f"  Hardware UUID: {uuid}")
    print(f"  Genesis Binding: {binding}")

    if uuid == "00000000-0000-0000-0000-000000000000":
        print("Warning: Using Phantom/VM Fallback UUID.")
    else:
        print("Correctly bound to Physical Silicon.")

    if len(binding) == 64:  # SHA-256 hex digest length
        print("Binding Hash Validity Confirmed.")
    else:
        print("Invalid Binding Hash.")
        sys.exit(1)


if __name__ == "__main__":
    verify_kinetic()
