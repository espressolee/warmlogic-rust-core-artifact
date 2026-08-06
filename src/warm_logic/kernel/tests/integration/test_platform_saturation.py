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
"""
Platform Mocking Tests for 100% Coverage (Phase 18)
Hardened for 
"""

import hashlib
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.economy.ledger import ReplicatedLedger, Transaction
from warm_logic.kernel.identity.kinetic_id import KineticIdentity
from warm_logic.kernel.sys.persistence import SovereignStore


class TestKineticIdentitySaturation(unittest.TestCase):
    """Saturate all branches in kinetic_id.py"""

    def test_rust_core_missing_path(self):
        """Force HAS_RUST_CORE=False to hit all stub paths."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            # All operations should raise RuntimeError
            with self.assertRaises(RuntimeError):
                KineticIdentity()
            with self.assertRaises(RuntimeError):
                KineticIdentity.generate_keypair()
            with self.assertRaises(RuntimeError):
                KineticIdentity.sign_intent_static("sk", "payload")
            with self.assertRaises(RuntimeError):
                KineticIdentity.verify_intent("pk", "payload", "sig")

    def test_kinetic_identity_with_provided_keypair(self):
        """Hit the keypair branch in __init__."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            ki = KineticIdentity(keypair=("provided_pk", "provided_sk"))
            self.assertEqual(ki.public_key, "provided_pk")
            self.assertEqual(ki.private_key, "provided_sk")

    def test_sign_intent_without_private_key_raises(self):
        """Hit the RuntimeError path in sign_intent_static."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with self.assertRaises(RuntimeError):
                KineticIdentity.sign_intent_static(None, "payload")


class TestDHTSaturationExtended(unittest.TestCase):
    """Saturate remaining DHT branches."""

    def test_routing_table_bucket_split(self):
        """Force bucket split by filling a bucket."""
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            from warm_logic.kernel.mesh.dht import Contact, RoutingTable

            # Create a routing table with a local_id near 0
            local_id = b"\x00" * 32
            rt = RoutingTable(local_id)

            # Add enough contacts to trigger a split
            # K_PARAM = 20, so we need > 20 contacts in the same bucket range
            for i in range(25):
                pk = f"key_{i}".encode()
                nid = hashlib.sha3_256(pk).digest()
                c = Contact(
                    nid,
                    "127.0.0.1",
                    9000 + i,
                    public_key=pk,
                    silicon_id=f"S{i}",
                )
                asyncio.run(rt.update(c))

            # Bucket should have been split
            self.assertGreater(len(rt.buckets), 1)

    def test_verify_binding_trigger_fail(self):
        """Hit the trigger_binding_fail path."""
        from warm_logic.kernel.mesh.dht import Contact, RoutingTable

        rt = RoutingTable(b"local" * 8)
        # address="trigger_binding_fail" causes verify_binding to return False
        c = Contact(b"node" * 8, "trigger_binding_fail", 80, public_key=b"pk")
        asyncio.run(rt.update(c))
        # Contact should NOT be added
        self.assertEqual(len(rt.buckets[0].contacts), 0)


class TestLedgerSaturationExtended(unittest.TestCase):
    """Saturate remaining ledger.py branches."""

    def test_submit_tx_negative_amount(self):
        """Hit the amount <= 0 guard."""
        import shutil
        import tempfile
        from pathlib import Path

        tmp = tempfile.mkdtemp()
        try:
            db_path = Path(tmp) / "test.db"
            with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
                with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_load:
                    mock_rs = MagicMock()
                    mock_load.return_value.RustReplicatedLedger.return_value = mock_rs
                    store = SovereignStore(db_path)
                    ledger = ReplicatedLedger(store)
                    tx = Transaction(
                        source="A", target="B", amount=-100, signature="sig"
                    )
                    result = ledger.submit_tx(tx)
                    self.assertFalse(result)
        finally:
            shutil.rmtree(tmp)

    def test_submit_tx_insufficient_balance(self):
        """Hit the balance check path (now handled primarily by Rust Core)."""
        import shutil
        import tempfile
        from pathlib import Path

        tmp = tempfile.mkdtemp()
        try:
            db_path = Path(tmp) / "test.db"
            with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
                with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_load:
                    mock_rs = MagicMock()
                    mock_load.return_value.RustReplicatedLedger.return_value = mock_rs
                    # Simulate Rust Core rejecting the transaction
                    mock_rs.submit_transaction.side_effect = Exception("Low Balance")

                    store = SovereignStore(db_path)
                    ledger = ReplicatedLedger(store)
                    tx = Transaction(
                        source="POOR", target="B", amount=100, signature="sig"
                    )
                    result = ledger.submit_tx(tx)
                    self.assertFalse(result)
        finally:
            shutil.rmtree(tmp)

    def test_mine_block_empty_mempool(self):
        """Hit the empty mempool early return."""
        import shutil
        import tempfile
        from pathlib import Path

        tmp = tempfile.mkdtemp()
        try:
            db_path = Path(tmp) / "test.db"
            with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
                with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_load:
                    mock_rs = MagicMock()
                    mock_load.return_value.RustReplicatedLedger.return_value = mock_rs
                    # Simulate Rust Core returning None for empty mempool
                    mock_rs.mine_block.return_value = None
                    mock_rs.get_last_block.return_value = None

                    store = SovereignStore(db_path)
                    ledger = ReplicatedLedger(store)
                    result = ledger.mine_block("miner")
                    self.assertIsNone(result)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
