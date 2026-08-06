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
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from warm_logic.kernel.sys.cryptography import MLDSA, HardwareEnclave
from warm_logic.kernel.sys.hardware import HardwareAttestor
from warm_logic.kernel.sys.memory import SovereignMemoryEngine

# Modules under test
from warm_logic.kernel.sys.persistence import SovereignStore


class TestPersistenceSurgical(unittest.TestCase):
    """
    Cover reconcile_state logic in persistence.py lines 418-468.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test.db"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_reconcile_skipped_no_rust(self):
        """Line 418: Return early if no rust ledger."""
        store = SovereignStore(self.db_path)
        # Force rust off
        store._use_rust = False
        res = store.reconcile_state()
        self.assertFalse(res)
        store.close()

    @patch("warm_logic.kernel.sys.persistence.SovereignStore.get_all_balances")
    def test_reconcile_success(self, mock_get_balances):
        """Test full reconcile flow (lines 427-457)."""
        store = SovereignStore(self.db_path)
        store._use_rust = True

        # Mock rust ledger
        mock_ledger = MagicMock()
        mock_ledger.sync_state = MagicMock()  # Has sync_state
        store._rust_ledger = mock_ledger

        # Mock sqlite cursor returns
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            [("addr1", 100), ("addr2", 200)],  # Balances
            [{"id": 1, "hash": "h1"}, {"id": 2, "hash": "h2"}],  # Blocks
        ]
        store.conn = MagicMock()
        store.conn.execute.return_value = mock_cursor

        # We also need to ensure get_all_balances doesn't error if called?
        # The code calls self.get_all_balances() then overwrites it.
        # But wait, self.get_all_balances relies on _rust_ledger if _use_rust=True.
        # So we mock it to avoid rust interaction there.
        mock_get_balances.return_value = {}

        res = store.reconcile_state()
        self.assertTrue(res)
        mock_ledger.sync_state.assert_called()
        store.close()

    def test_reconcile_fallback_no_sync(self):
        """Test missing sync_state (lines 458-461)."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        store._rust_ledger = MagicMock()
        del store._rust_ledger.sync_state  # Ensure no attribute?
        # Or mock spec?
        # MagicMock has everything by default.
        # We must explicitly ensure hasattr returns False?
        # hasattr(mock, "sync_state") returns True usually.
        # We can set spec.

        # Better: use a simple class
        class MockLedger:
            pass

        store._rust_ledger = MockLedger()

        res = store.reconcile_state()
        self.assertFalse(res)
        store.close()

    def test_reconcile_exception(self):
        """Test exception handler (lines 463-468)."""
        store = SovereignStore(self.db_path)
        store._use_rust = True
        store._rust_ledger = MagicMock()
        # Raise generic exception
        store.get_all_balances = MagicMock(side_effect=RuntimeError("Fail"))

        res = store.reconcile_state()
        self.assertFalse(res)
        store.close()


class TestCryptographySurgicalExceptions(unittest.TestCase):
    """Cover exception and hardware logic in cryptography.py."""

    def test_mldsa_exceptions(self):
        # MLDSA KeyGen Exception (Line 49)
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True), patch(
            "warm_logic.kernel.rust_loader.load_rust_core",
            side_effect=RuntimeError("Core Fail"),
        ):
            signer = MLDSA()
            with self.assertRaises(RuntimeError):
                signer.generate_keypair()
            with self.assertRaises(RuntimeError):
                signer.sign("m", "k")

            # verify returns False on exception
            self.assertFalse(signer.verify("m", "s", "k"))

    def test_hardware_enclave_seed(self):
        # Line 105: get_kinetic_seed
        with patch("warm_logic.kernel.rust_loader.load_rust_core") as mock_core:
            mock_core.return_value.HardwareEntropy.derive_seed.return_value = (
                "AABB",
                "proof",
            )
            seed = HardwareEnclave.get_kinetic_seed()
            self.assertEqual(seed, b"\xaa\xbb")

        # Exception
        with patch(
            "warm_logic.kernel.rust_loader.load_rust_core",
            side_effect=RuntimeError("Fail"),
        ):
            with self.assertRaises(RuntimeError):
                HardwareEnclave.get_kinetic_seed()


class TestMemoryCoverage(unittest.TestCase):
    """Cover sys/memory.py."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_memory_lifecycle(self):
        identity = MagicMock()
        identity.sign.return_value = "SIG123"

        mem = SovereignMemoryEngine(self.tmp_dir, identity)

        # log_event
        mem.log_event("TEST", "Detail", {"k": "v"})

        # Verify file created
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        ephem_file = Path(self.tmp_dir) / "meta/memory/ephemeris" / f"{today}.md"
        self.assertTrue(ephem_file.exists())
        content = ephem_file.read_text()
        self.assertIn("TEST", content)
        self.assertIn("SIG123", content)

        # get_session_summary
        summ = mem.get_session_summary(today)
        self.assertEqual(summ, content)

        # compact_to_chronicle
        mem.compact_to_chronicle(summ)
        chronicle = Path(self.tmp_dir) / "meta/memory/chronicle.md"
        self.assertTrue(chronicle.exists())
        self.assertIn("Session Summary", chronicle.read_text())


class TestHardwareCoverage(unittest.TestCase):
    """Cover sys/hardware.py."""

    @patch("warm_logic.kernel.substrate.hardware.SovereignHAL")
    def test_hardware_attestor(self, MockHAL):
        MockHAL.return_value.get_silicon_id.return_value = "SILICON-ID"

        # get_hardware_uuid
        uuid = HardwareAttestor.get_hardware_uuid()
        self.assertEqual(uuid, "SILICON-ID")

        # verify_attestation
        packet = HardwareAttestor.generate_attestation_packet()
        self.assertTrue(HardwareAttestor.verify_attestation(packet))

        # Exception
        MockHAL.return_value.get_silicon_id.side_effect = RuntimeError("No HAL")
        with self.assertRaises(RuntimeError):
            HardwareAttestor.get_hardware_uuid()
