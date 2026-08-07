""" Forensics Verification
Tests the Audit Ledger integrity and event recording.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.justice.audit_ledger import AuditLedger
from warm_logic.kernel.justice.refusal import RefusalEngine


def test_forensics():
    print("Testing Audit Ledger (Forensics)...")

    # 0. Initialize Ledger
    ledger = AuditLedger()
    print("Ledger Initialized.")

    # 1. Generate REFUSAL Event
    refusal = RefusalEngine()
    try:
        print("\n--- Generating Refusal Event ---")
        refusal.enforce_sovereignty({"mesh_latch_active": True})
    except ValueError:
        print("Refusal Triggered (Mesh Lockdown).")

    # 2. Generate ACCESS Event
    print("\n--- Generating Access Event ---")
    refusal.enforce_sovereignty({"mesh_latch_active": False})
    print("Access Granted.")

    # 3. Verify Chain Integrity
    print("\n--- Verifying Chain Integrity ---")
    if ledger.verify_chain():
        print("Cryptographic Chain is VALID.")
    else:
        print("Chain Validation FAILED!")
        sys.exit(1)

    # 4. Inspect Content
    print("\n--- Inspecting Ledger Content ---")
    with open(ledger.ledger_path, "r") as f:
        lines = f.readlines()
        print(f"Total Entries: {len(lines)}")
        last_entry = json.loads(lines[-1])
        print(f"Last Event: {last_entry['event']} (Index: {last_entry['index']})")

        if last_entry["event"] != "ACCESS_GRANTED":
            print("Last event mismatch.")
            sys.exit(1)

    print("\nFORENSICS SCENARIO OK (not verification)")


if __name__ == "__main__":
    try:
        test_forensics()
    except Exception as e:
        print(f"Test Failed: {e}")
        sys.exit(1)
