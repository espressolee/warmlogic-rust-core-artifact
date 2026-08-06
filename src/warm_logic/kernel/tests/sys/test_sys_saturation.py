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
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from warm_logic.kernel.sys.exceptions import (
    ConstitutionalBreach,
    IntegrityError,
    MeshNetworkingError,
    PersistenceError,
    RateLimitExceeded,
    SovereignError,
    WarmLogicError,
)
from warm_logic.kernel.sys.persistence import SovereignStore
from warm_logic.kernel.sys.shield import (
    SyscallShield,
    SyscallViolation,
    kernel_exec,
    kernel_open,
    kernel_socket,
    shield,
    shield_syscall,
)


class TestSysExceptions(unittest.TestCase):
    def test_exception_instantiation(self):
        # Coverage for exceptions.py
        exceptions = [
            WarmLogicError("err"),
            SovereignError("err"),
            ConstitutionalBreach("err"),
            MeshNetworkingError("err"),
            PersistenceError("err"),
            IntegrityError("err"),
            RateLimitExceeded("err"),
        ]
        for e in exceptions:
            self.assertEqual(str(e), "err")


class TestSyscallShield(unittest.TestCase):
    def test_shield_enforcement(self):
        s = SyscallShield(agent_profile="restricted")

        # 1. Allowed
        self.assertTrue(s.enforce("read"))

        # 2. Blocked with Panic
        with self.assertRaises(SyscallViolation):
            s.enforce("execve")

        # 3. Blocked without Panic
        s.policies["restricted"]["panic"] = False
        self.assertFalse(s.enforce("execve"))

        # 4. Strict Allow-list (not in allowed list)
        self.assertFalse(s.enforce("mkdir"))

        # 5. Non-existent profile (should fallback to restricted)
        s_bad = SyscallShield(agent_profile="unknown")
        self.assertEqual(s_bad.profile, "unknown")
        self.assertTrue(s_bad.enforce("read"))

    def test_shield_decorator(self):
        # We patch the global shield's enforce method
        with patch.object(shield, "enforce") as mock_enforce:

            @shield_syscall("test_call")
            def my_func(a, b):
                return a + b

            res = my_func(1, 2)
            self.assertEqual(res, 3)
            mock_enforce.assert_called_with("test_call", (1, 2))

    def test_kernel_syscall_barriers(self):
        # 'open' is allowed in restricted profile -> reaches function body -> RuntimeError
        with self.assertRaises(RuntimeError):
            kernel_open("path", 0)

        # 'execve' and 'socket' are blocked in restricted profile -> SyscallViolation (panic=True by default)
        with self.assertRaises(SyscallViolation):
            kernel_exec("path", ("arg",))
        with self.assertRaises(SyscallViolation):
            kernel_socket(1, 1)


class TestPersistenceSaturation(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "persistence.db"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_store_init_rust_fail(self):
        # Force Rust to be enabled but fail init
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core",
                side_effect=Exception("Rust crash"),
            ):
                with self.assertRaises(RuntimeError) as cm:
                    SovereignStore(self.db_path)
                self.assertIn("redb Init Failed", str(cm.exception))

    def test_store_init_rust_success(self):
        mock_rs = MagicMock()
        mock_store = MagicMock()
        mock_ledger = MagicMock()
        mock_rs.SovereignStore.return_value = mock_store
        mock_rs.RustReplicatedLedger.return_value = mock_ledger

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch(
                "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
            ):
                store = SovereignStore(self.db_path)
                self.assertTrue(store._use_rust)
                self.assertEqual(store._rust_store, mock_store)
                self.assertEqual(store._rust_ledger, mock_ledger)

                # Test Rust methods
                store.set_meta("k", "v")
                mock_store.put.assert_called()

                mock_store.get.return_value = json.dumps("v")
                self.assertEqual(store.get_meta("k"), "v")

                mock_ledger.get_balance.return_value = 100
                self.assertEqual(store.get_balance("addr"), 100)

                mock_ledger.get_all_balances.return_value = {"a": 1}
                self.assertEqual(store.get_all_balances(), {"a": 1})

                # Rust get_last_block conversion
                mock_block = MagicMock()
                mock_block.timestamp = 1.0
                mock_block.tx_ids = ["t1"]
                mock_block.miner = "m"
                mock_block.prev_hash = "p"
                mock_block.hash = "h"
                mock_block.zk_proof = "zk"
                mock_ledger.get_last_block.return_value = mock_block

                lb = store.get_last_block()
                self.assertEqual(lb["hash"], "h")

    def test_log_event_no_conn(self):
        store = SovereignStore(self.db_path)
        store.conn = None
        with self.assertRaises(RuntimeError):
            store.log_event(1.0, "E", {}, "p", "c")

    def test_persistence_edge_cases(self):
        store = SovereignStore(self.db_path)

        # get_last_event empty
        self.assertIsNone(store.get_last_event())

        # get_all_events empty
        self.assertEqual(store.get_all_events(), [])

        # log_event
        store.log_event(1.0, "E", {"p": 1}, "prev", "curr", "root", "zk")
        ev = store.get_last_event()
        self.assertEqual(ev["event_type"], "E")
        self.assertEqual(json.loads(ev["payload"]), {"p": 1})
        self.assertEqual(ev["state_root"], "root")
        self.assertEqual(ev["zk_proof"], "zk")

    def test_blob_storage(self):
        store = SovereignStore(self.db_path)

        # 1. String blob
        store.put_blob("text", "hello world")
        self.assertEqual(store.get_blob("text"), b"hello world")

        # 2. Bytes blob
        blob_data = b"\xde\xad\xbe\xef"
        store.put_blob("bytes", blob_data)
        self.assertEqual(store.get_blob("bytes"), blob_data)

        # 3. Missing blob
        self.assertIsNone(store.get_blob("missing"))

    def test_schema_migration_coverage(self):
        # Re-initialize to trigger migration checks on existing DB
        store1 = SovereignStore(self.db_path)
        store1.close()

        # Init again
        store2 = SovereignStore(self.db_path)
        # Should not crash
        store2.close()


if __name__ == "__main__":
    unittest.main()
