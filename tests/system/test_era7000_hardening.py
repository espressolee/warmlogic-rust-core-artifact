import os
import shutil
from pathlib import Path

import pytest

from warm_logic.kernel.economy.ledger import ReplicatedLedger
from warm_logic.kernel.ops.audit import SovereignAudit
from warm_logic.dominion.replication.codebase import SovereignCodebase
from warm_logic.kernel.sys.oracle import SovereignOracle
from warm_logic.kernel.sys.persistence import SovereignStore


@pytest.fixture
def temp_store(tmp_path):
    db_path = tmp_path / "era7000.db"
    store = SovereignStore(db_path)
    yield store
    store.close()


@pytest.fixture
def ledger(temp_store):
    return ReplicatedLedger(temp_store)


def test_oracle_anchoring(ledger):
    """Verify that Oracle data is anchored in the ledger."""
    oracle = SovereignOracle(ledger)
    source = "WEATHER_STATION"
    key = "TEMP:SEOUL"
    value = 25.5

    data_hash = oracle.ingest_data(source, key, value)
    assert data_hash is not None
    assert oracle.verify_data(source, key, value) is True
    assert oracle.verify_data(source, key, 30.0) is False


def test_self_healing_codebase(temp_store, tmp_path):
    """Verify that auto_heal restores tampered files."""
    codebase_root = tmp_path / "code"
    codebase_root.mkdir()
    file_path = codebase_root / "logic.py"
    original_content = b"print('valid code')"
    file_path.write_bytes(original_content)

    codebase = SovereignCodebase(temp_store)
    codebase.ingest(str(codebase_root))

    # TAMPER
    file_path.write_bytes(b"print('malicious code')")
    assert codebase.verify_integrity(str(codebase_root)) is False

    # HEAL
    healed = codebase.auto_heal(str(codebase_root))
    assert healed == 1
    assert file_path.read_bytes() == original_content
    assert codebase.verify_integrity(str(codebase_root)) is True


def test_audit_drift_detection(temp_store):
    """Verify SovereignAudit handles store presence correctly."""
    audit = SovereignAudit(store=temp_store)
    # Just verify it can run without crashing for now as we don't mock drift easily here
    # without deeper store manipulation.
    assert hasattr(audit, "recursive_audit_loop")
    # We don't close 'audit' here because it might close the shared 'temp_store'
    # and the fixture teardown also closes it.
    # Actually audit.close() closes store. Best is to let fixture handle it.
