# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.persistence import SovereignStore


# Mocking the Rust Loader constant
@pytest.fixture
def mock_no_rust():
    with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
        yield


@pytest.fixture
def store(tmp_path, mock_no_rust):
    db_path = tmp_path / "test.db"
    return SovereignStore(db_path)


def test_persistence_init_schema_migration(tmp_path, mock_no_rust):
    """Test that schema migration adds missing columns."""
    db_path = tmp_path / "migration.db"

    # 1. Create OLD schema (missing columns)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE ledger (id INTEGER PRIMARY KEY, timestamp REAL, event_type TEXT, payload JSON, prev_hash TEXT, hash TEXT)"
    )
    conn.execute(
        "CREATE TABLE blocks (id INTEGER PRIMARY KEY, timestamp REAL, miner TEXT, prev_hash TEXT, hash TEXT)"
    )  # Missing index, zk_proof, state_root, tx_ids
    conn.commit()
    conn.close()

    # 2. Initialize Store (should trigger migration)
    store = SovereignStore(db_path)

    # 3. Verify columns exist
    cursor = store.conn.execute("PRAGMA table_info(ledger)")
    cols = {row["name"] for row in cursor.fetchall()}
    assert "state_root" in cols
    assert "zk_proof" in cols

    cursor = store.conn.execute("PRAGMA table_info(blocks)")
    cols = {row["name"] for row in cursor.fetchall()}
    assert "index" in cols
    assert "zk_proof" in cols
    assert "state_root" in cols
    assert "tx_ids" in cols


def test_persistence_not_initialized_error():
    """Test RuntimeError when conn is None."""
    store = SovereignStore(":memory:")
    store.conn = None

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        store.log_event(0.0, "test", {}, "", "")


def test_persistence_put_blob_rust(store):
    """Test put_blob with Rust store active."""
    store._use_rust = True
    store._rust_store = MagicMock()

    # Success case
    store.put_blob("key", b"value")
    store._rust_store.put.assert_called_with("key", "76616c7565")  # hex of "value"

    # Failure case
    store._rust_store.put.side_effect = Exception("Rust Put Blob Failed")
    store.put_blob(
        "key", b"value"
    )  # Should log error and fallback (or pass silently if fallback not implemented)


def test_persistence_conn_none_guards():
    """Test that methods return gracefully (or Safe None) when conn is None."""
    store = SovereignStore(":memory:")
    # Force close and clear
    if store.conn:
        store.conn.close()
    store.conn = None
    store._use_rust = False  # Ensure we hit the pure python guards

    # Void methods (should return None/void)
    assert store.set_meta("k", "v") is None
    assert store.update_balance("a", 10) is None
    assert store.put_blob("k", b"v") is None
    assert store.commit_block(0, [], "", "", "", {}) is None

    # Return safe defaults
    assert store.get_last_event() is None
    assert store.get_all_events() == []
    assert store.get_meta("k") is None
    assert store.get_blob("k") is None
    assert store.get_balance("a") == 0
    assert store.get_all_balances() == {}
    assert store.get_last_block() is None


def test_persistence_rust_loader_failure():
    """Test expected behavior when Rust loader fails."""
    with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
        with patch(
            "warm_logic.kernel.rust_loader.load_rust_core",
            side_effect=ImportError("Rust core missing"),
        ):
            with pytest.raises(
                RuntimeError, match="Persistence Hardening: redb Init Failed"
            ):
                SovereignStore(":memory:")


def test_persistence_rust_method_failures(store):
    """Test graceful failure handling when Rust methods raise exceptions."""
    # Force enable rust mode for the instance
    store._use_rust = True
    store._rust_store = MagicMock()
    store._rust_ledger = MagicMock()

    # Mock failures
    store._rust_store.put.side_effect = Exception("Rust Put Failed")
    store._rust_store.get.side_effect = Exception("Rust Get Failed")
    store._rust_ledger.get_balance.side_effect = Exception("Rust Balance Failed")
    store._rust_ledger.update_balance.side_effect = Exception(
        "Rust Update Failed"
    )  # Although update_balance just passes currently
    store._rust_ledger.get_last_block.side_effect = Exception("Rust Block Failed")

    # Exec & Verify Log Errors (captured by logger but shouldn't crash)
    store.set_meta("key", "val")  # Rust fails but SQL fallback succeeds

    val = store.get_meta("key")  # Rust fails but SQL fallback returns value
    assert val == "val"  # SQL fallback returns the stored value

    bal = store.get_balance("addr")  # Should log error and fallback to SQL
    assert bal == 0

    store.update_balance("addr", 100)  # Should log error and continue to SQL

    blk = store.get_last_block()
    assert blk is None


def test_persistence_blob_handling(store):
    """Test get_blob fallback logic."""
    store._use_rust = True
    store._rust_store = MagicMock()
    store._rust_store.get.return_value = None  # Rust miss

    # Store explicit non-hex string in SQL to test fallback
    store.conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("blob_key", json.dumps("not_hex")),
    )

    val = store.get_blob("blob_key")
    assert val == b"not_hex"

    # Test Rust failure
    store._rust_store.get.side_effect = Exception("Rust Blob Fail")
    val = store.get_blob("blob_key")  # Should match SQL fallback
    assert val == b"not_hex"


def test_persistence_rust_update_balance_failure(store):
    """Explicit test for update_balance rust failure to hit the catch block."""
    store._use_rust = True
    store._rust_ledger = MagicMock()
    store._rust_ledger.update_balance.side_effect = Exception("Rust Update Fail")

    # Should log error and NOT raise
    store.update_balance("addr", 100)


def test_persistence_reconcile_failures(store):
    """Test reconcile state failure modes."""
    store._use_rust = False
    assert store.reconcile_state() is False  # Skipped warning

    store._use_rust = True
    store._rust_ledger = MagicMock()
    del store._rust_ledger.sync_state  # Simulate missing method

    # Should log error about missing sync_state
    assert store.reconcile_state() is False

    store._rust_ledger.sync_state = MagicMock(side_effect=Exception("Sync Explosion"))
    assert store.reconcile_state() is False  # Exception caught


def test_persistence_lastrowid_failure():
    """Test rare case where lastrowid is None."""
    store = SovereignStore(":memory:")
    # Replace conn with a full mock to avoid context manager issues and side effects
    store.conn = MagicMock()

    # Setup context manager mock
    store.conn.__enter__.return_value = store.conn
    store.conn.__exit__.return_value = None

    # Setup execute & cursor
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = None  # Trigger the error condition
    store.conn.execute.return_value = mock_cursor

    with pytest.raises(RuntimeError, match="Failed to log event: lastrowid is None"):
        store.log_event(0.0, "t", {}, "", "")


def test_persistence_rust_get_last_block_none(store):
    """Test get_last_block returning None from Rust."""
    store._use_rust = True
    store._rust_ledger = MagicMock()

    # Case: Rust returns None (empty ledger)
    store._rust_ledger.get_last_block.return_value = None
    assert store.get_last_block() is None
