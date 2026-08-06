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
from pathlib import Path
from unittest import mock

from warm_logic.kernel.ops.audit import (
    AuditLogExporter,
    IntegrityReport,
    SovereignAudit,
    log_event,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestAuditCoverage(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        self.db_path = self.get_temp_path("audit.db")
        # Mocking SovereignStore is easier than creating a real DB with complex schema
        self.store_patcher = mock.patch("warm_logic.kernel.ops.audit.SovereignStore")
        self.mock_store_cls = self.store_patcher.start()
        self.mock_store = mock.MagicMock()
        self.mock_store_cls.return_value = self.mock_store

        # Mock Connection
        self.mock_conn = mock.MagicMock()
        self.mock_store.conn = self.mock_conn

        self.audit = SovereignAudit(db_path=Path(self.db_path))

    def tearDown(self):
        self.store_patcher.stop()
        super().tearDown()

    def test_close(self):
        self.audit.close()
        self.mock_store.close.assert_called()

    def test_run_full_audit_perfect(self):
        # Setup perfect state
        # 1. Chain Continuity
        self.mock_conn.execute.return_value.fetchall.side_effect = [
            # Blocks for continuity check
            [
                {"hash": "h1" * 32, "prev_hash": "0" * 64},
                {"hash": "h2" * 32, "prev_hash": "h1" * 32},
            ],
            # Schema info for state consistency
            [{"name": "tx_ids"}],
            # Blocks for proof integrity
            [
                {
                    "hash": "h1" * 32,
                    "prev_hash": "0" * 64,
                    "tx_ids": "[]",
                    "zk_proof": json.dumps(
                        {
                            "prefix": "zkp_v2_bulletproofs",
                            "proof": "p1",
                            "commitment": "c1",
                        }
                    ),
                },
                {
                    "hash": "h2" * 32,
                    "prev_hash": "h1" * 32,
                    "tx_ids": "[]",
                    "zk_proof": json.dumps(
                        {
                            "prefix": "zkp_v2_bulletproofs",
                            "proof": "p2",
                            "commitment": "c2",
                        }
                    ),
                },
            ],
        ]

        # 2. State Consistency (Balances)
        self.mock_store.get_all_balances.return_value = {"alice": 100, "bob": 50}

        # Run
        with mock.patch(
            "warm_logic.kernel.substrate.proof_zk.ZKProofGenerator.verify_proof",
            return_value=True,
        ):
            with mock.patch(
                "warm_logic.kernel.ops.audit.SovereignAudit._save_report"
            ) as mock_save:
                res = self.audit.run_full_audit()
                self.assertTrue(res)
                mock_save.assert_called()
                args, _ = mock_save.call_args
                report = args[0]
                self.assertEqual(report.score, 10.0)

    def test_audit_empty_chain(self):
        # Empty rows
        self.mock_conn.execute.return_value.fetchall.side_effect = [
            [],  # Continuity: empty
            [{"name": "id"}, {"name": "tx_ids"}],  # Schema (including tx_ids)
            [],  # Blocks for proofs: empty
        ]
        self.mock_store.get_all_balances.return_value = {}
        self.mock_store.get_last_block.return_value = None  # Crucial for Rust path

        with mock.patch(
            "warm_logic.kernel.ops.audit.SovereignAudit._save_report"
        ) as mock_save:
            with mock.patch(
                "warm_logic.kernel.ops.audit.SovereignAudit._verify_autonomy_readiness",
                return_value=True,
            ):
                res = self.audit.run_full_audit()
                self.assertTrue(res)

                args, _ = mock_save.call_args
                report = args[0]
                self.assertEqual(report.score, 10.0)

    def test_audit_failures(self):
        # 1. Broken Chain
        # 2. Negative Supply
        # 3. Bad Proofs
        # 4. convergence Not Ready

        self.mock_conn.execute.return_value.fetchall.side_effect = [
            # Continuity: Broken
            [
                {"hash": "h1", "prev_hash": "0" * 64},
                {"hash": "h3", "prev_hash": "h2"},  # Gap!
            ],
            # Schema
            [{"name": "tx_ids"}],
            # Proofs: Bad
            [
                {
                    "hash": "h1",
                    "prev_hash": "0",
                    "tx_ids": "[]",
                    "zk_proof": None,
                },  # Missing
                {
                    "hash": "h3",
                    "prev_hash": "h2",
                    "tx_ids": "[]",
                    "zk_proof": "{}",
                },  # Malformed
            ],
        ]

        self.mock_store.get_all_balances.return_value = {"alice": -100}

        with mock.patch(
            "warm_logic.kernel.substrate.proof_zk.ZKProofGenerator.verify_proof",
            return_value=False,
        ):
            with mock.patch(
                "warm_logic.kernel.ops.audit.SovereignAudit._save_report"
            ) as mock_save:
                with mock.patch(
                    "warm_logic.kernel.ops.audit.SovereignAudit._verify_autonomy_readiness",
                    return_value=False,
                ):
                    res = self.audit.run_full_audit()
                    self.assertFalse(res)
                    args, _ = mock_save.call_args
                    report = args[0]
                    self.assertEqual(report.score, 0.0)

    def test_audit_proof_exception_path(self):
        # Explicitly trigger Exception on json.loads to cover lines in _verify_proof_integrity
        self.mock_conn.execute.return_value.fetchall.side_effect = [
            [
                {
                    "hash": "trigger_err",
                    "prev_hash": "0",
                    "tx_ids": "[]",
                    "zk_proof": "junk",
                },
            ],
        ]

        # Audit should handle the failure gracefully
        report = IntegrityReport()
        res = self.audit._verify_proof_integrity(report)
        self.assertFalse(res)
        self.assertTrue(any("ZK-Proof INVALID" in d for d in report.details))

    def test_save_report(self):
        report = IntegrityReport()
        with mock.patch("builtins.open", mock.mock_open()) as mock_file:
            self.audit._save_report(report)
            mock_file.assert_called()

    def test_log_event(self):
        with mock.patch("builtins.open", mock.mock_open()) as mock_file:
            log_event("plugin", "kind", {"a": 1})
            mock_file().write.assert_called()

    def test_log_event_fail(self):
        # Test fallback logging
        with mock.patch("builtins.open", side_effect=Exception("Disk Full")):
            with self.assertLogs("SovereignAudit", level="CRITICAL") as cm:
                log_event("plugin", "kind")
                self.assertIn("AUDIT LOG FAILURE", cm.output[0])

    def test_exporter(self):
        p = Path("dummy")
        exp = AuditLogExporter(p)

        with mock.patch("builtins.open", mock.mock_open()) as mock_file:
            with mock.patch.object(Path, "exists", return_value=False):
                exp.start_tailing()
                # Should create file
                mock_file.assert_called()
