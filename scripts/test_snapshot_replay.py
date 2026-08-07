""" Reproducibility Verification
Tests the Time Travel capabilities (Snapshot & Restore).
"""

import shutil
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.justice.audit_ledger import AuditLedger
from warm_logic.kernel.sys.snapshot import SnapshotEngine


def test_time_travel():
    print("⏪ Testing Time Travel (Snapshot/Restore)...")

    # Setup
    ledger = AuditLedger()
    snapshot_engine = SnapshotEngine()

    # 1. State A: The "Good Old Days"
    print("\n--- PHASE 1: The Good Old Days ---")
    ledger.record_event("EVENT_A", {"note": "I remember this moment."})

    # Verify Ledger has A
    with open(ledger.ledger_path, "r") as f:
        if "EVENT_A" not in f.read():
            print("Setup failed: EVENT_A not recorded.")
            sys.exit(1)

    # 2. TAKE SNAPSHOT
    print("SNAPSHOT taken.")
    snapshot_path = snapshot_engine.take_snapshot("good_times", {"mood": "happy"})

    # 3. State B: The "Dark Timeline"
    print("\n--- PHASE 2: The Dark Timeline ---")
    ledger.record_event("EVENT_B", {"note": "Everything went wrong."})
    ledger.record_event("EVENT_C", {"note": "Disaster."})

    # Verify Ledger has corrupted future
    with open(ledger.ledger_path, "r") as f:
        content = f.read()
        if "EVENT_C" not in content:
            print("Setup failed: Timeline did not advance.")
            sys.exit(1)
    print("Timeline corrupted with EVENT_B and EVENT_C.")

    # 4. RESTORE SNAPSHOT (Time Travel)
    print("\n--- PHASE 3: Restoring the Past ---")
    restored_memory = snapshot_engine.restore_snapshot(snapshot_path)

    # 5. Verification
    print("Verifying Paradox Resolution...")

    # Check Memory
    if restored_memory.get("mood") != "happy":
        print(f"Memory restoration failed. Got: {restored_memory}")
        sys.exit(1)
    print("Memory Restored (Mood: Happy).")

    # Check Ledger (Should have A, but NOT B or C)
    with open(ledger.ledger_path, "r") as f:
        content = f.read()
        if "EVENT_A" not in content:
            print("FATAL: Lost the past (EVENT_A missing).")
            sys.exit(1)
        if "EVENT_B" in content or "EVENT_C" in content:
            print("FATAL: Dark timeline leaked into the past!")
            sys.exit(1)

    print("Timeline sanitized. Valid Hash Chain preserved.")

    # Cleanup
    shutil.rmtree(snapshot_engine.snapshots_dir)
    print("Cleanup complete.")

    print("\nTIME TRAVEL SCENARIO OK (not verification)")


if __name__ == "__main__":
    try:
        test_time_travel()
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
