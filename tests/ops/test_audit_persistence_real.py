import json
import time
from pathlib import Path

import pytest

from warm_logic.kernel.ops.audit import AUDIT_LOG_PATH, log_event


def test_audit_persistence_real():
    """
    Phase 53.2: Verify Audit Logging writes to out/audit/audit.jsonl.
    SIM-012: Audit Log No-op -> Real Persistence.
    """
    # 1. Setup - Clear previous log if exists (or just append and seek)
    # We want to verify *our* event is there.
    test_id = f"TEST_AUDIT_{time.time()}"

    # 2. Log Event
    log_event("TEST_PLUGIN", "AUDIT_TEST", {"test_id": test_id})

    # 3. Verify File Exists
    assert AUDIT_LOG_PATH.exists()

    # 4. Read File and Find Event
    found = False
    with open(AUDIT_LOG_PATH, "r") as f:
        for line in f:
            try:
                msg = json.loads(line)
                if msg.get("detail", {}).get("test_id") == test_id:
                    found = True
                    assert msg["plugin"] == "TEST_PLUGIN"
                    assert msg["kind"] == "AUDIT_TEST"
                    break
            except json.JSONDecodeError:
                continue

    assert found, f"Audit event with test_id {test_id} not found in {AUDIT_LOG_PATH}"
    print(f"✅ Audit Event Persisted to {AUDIT_LOG_PATH}")


if __name__ == "__main__":
    test_audit_persistence_real()
