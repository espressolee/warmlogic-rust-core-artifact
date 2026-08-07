""" ACID Persistence Verification.
Tests Atomic Writes and Concurrency Safety using threads.
"""

import shutil
import sys
import threading
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from warm_logic.kernel.justice.audit_ledger import AuditLedger

# Global Ledger
ledger = None


def worker(thread_id: int, count: int):
    """Writes 'count' events to the ledger."""
    for i in range(count):
        ledger.record_event(
            f"THREAD_{thread_id}",
            {"seq": i, "message": f"Concurrent write {i} from thread {thread_id}"},
        )
        time.sleep(0.001)  # Small yielding delay


def test_acid_persistence():
    print(" Testing ACID Persistence (SQLite Wal)...")

    # 1. Setup - Fresh DB
    root_dir = Path("warm_logic/kernel")
    sovereign_dir = Path(".sovereign")
    if sovereign_dir.exists():
        shutil.rmtree(sovereign_dir)

    # Initialize Ledger (Creates DB)
    global ledger
    ledger = AuditLedger()
    print("SovereignStore Initialized.")

    # 2. Concurrency Attack
    NUM_THREADS = 10
    WRITES_PER_THREAD = 50
    TOTAL_WRITES = NUM_THREADS * WRITES_PER_THREAD

    print(
        f"🌪️  Launching {NUM_THREADS} threads x {WRITES_PER_THREAD} writes ({TOTAL_WRITES} total)..."
    )

    threads = []
    for t_id in range(NUM_THREADS):
        t = threading.Thread(target=worker, args=(t_id, WRITES_PER_THREAD))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("All threads completed.")

    # 3. Verification
    print("Verifying Chain Integrity...")

    # Check Count (Genesis + Total Writes)
    events = ledger.store.get_all_events()
    expected_count = 1 + TOTAL_WRITES
    actual_count = len(events)

    print(f"   Count: Expected {expected_count} | Actual {actual_count}")

    if actual_count != expected_count:
        print("Data Loss Detected! Missing events.")
        sys.exit(1)

    # Check Hash Chain
    if not ledger.verify_chain():
        print("hash Chain Broken! Integrity compromised.")
        sys.exit(1)

    print("Hash Chain Valid.")
    print("\nACID PERSISTENCE SCENARIO OK (not verification)")


if __name__ == "__main__":
    test_acid_persistence()
