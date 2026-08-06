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

from warm_logic.kernel.economy.ledger import ReplicatedLedger, Transaction
from warm_logic.kernel.identity.kinetic_id import KineticIdentity
from warm_logic.kernel.ops.audit import IntegrityReport, SovereignAudit
from warm_logic.kernel.ops.invariants import InvariantManager
from warm_logic.kernel.ops.policy import (
    PluginRecord,
    installed_plugins,
    load_registry,
    verify_plugin,
)
from warm_logic.kernel.sys.persistence import SovereignStore


class TestClusterDLost(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test.db"
        self.store = MagicMock(spec=SovereignStore)
        self.store.db_path = self.db_path
        self.store._use_rust = False

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.tmp_dir)

    # --- Ledger ---
    def test_ledger_ops(self):
        with (
            patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True),
            patch("warm_logic.kernel.rust_loader.rust_core") as mock_rs,
            patch("warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs),
        ):
            mock_ledger_instance = mock_rs.RustReplicatedLedger.return_value
            mock_ledger_instance.get_state_root.return_value = "root"

            ledger = ReplicatedLedger(self.store)

            # 1. Transaction
            with patch("time.time", return_value=1234567890.0):
                tx = Transaction("src", "dst", 10, "sig")
            self.assertIsInstance(tx.tx_id, str)
            self.assertEqual(len(tx.tx_id), 64)

            tx = Transaction("A", "B", 100, "sig")
            self.assertTrue(ledger.submit_tx(tx))
            mock_ledger_instance.submit_transaction.assert_called()

            # Mine block
            mock_ledger_instance.mine_block.return_value = "hash1"
            mock_ledger_instance.get_last_block.return_value = MagicMock(
                hash="hash1",
                prev_hash="0",
                tx_ids=["tx1"],
                miner="m1",
                timestamp=1.0,
                zk_proof="p1",
                state_root="root1",
            )
            mock_ledger_instance.get_all_balances.return_value = {"A": 50, "B": 150}

            ledger.mine_block("m1")
            self.store.commit_block.assert_called()

            # 4. State/Balance
            ledger.get_balance("addr")
            mock_ledger_instance.get_balance.assert_called()
            ledger.get_state_root()
            mock_ledger_instance.get_state_root.assert_called()

    # --- Identity ---
    def test_kinetic_id(self):
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            # Init now raises RuntimeError if core missing (hardware attestation enforcement)
            with self.assertRaises(RuntimeError):
                KineticIdentity()

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            mock_rs = MagicMock()
            with patch("warm_logic.kernel.rust_loader.rust_core", mock_rs):
                with patch(
                    "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
                ):
                    mock_rs.generate_keypair.return_value = ("pk", "sk")
                    mock_rs.sign.return_value = "sig"
                    mock_rs.verify.return_value = True

                    kid = KineticIdentity()
                    self.assertEqual(kid.public_key, "pk")
                    self.assertEqual(
                        KineticIdentity.sign_intent_static("sk", "d"), "sig"
                    )
                    self.assertTrue(KineticIdentity.verify_intent("pk", "d", "sig"))

    # --- Audit ---
    def test_audit(self):
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            audit = SovereignAudit(store=self.store)
            report = IntegrityReport()

            # Mock store methods used by audit
            self.store._use_rust = True
            self.store.get_last_block.return_value = {"hash": "h1", "prev_hash": "0"}
            self.store.get_block.return_value = {
                "hash": "h1",
                "prev_hash": "0" * 64,
                "tx_ids": [],
                "zk_proof": "p1",
            }

            with patch(
                "warm_logic.kernel.substrate.proof_zk.ZKProofGenerator.verify_proof",
                return_value=True,
            ):
                with patch.object(
                    audit, "_verify_autonomy_readiness", return_value=True
                ):
                    res = audit._run_atomic_truth_audit(report)
                    self.assertTrue(res)

    # --- Invariants ---
    def test_invariants(self):
        from warm_logic.kernel.ops.invariants import FailLatch

        FailLatch().latched = False  # Reset singleton

        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            mock_rs = MagicMock()
            with patch("warm_logic.kernel.rust_loader.rust_core", mock_rs):
                with patch(
                    "warm_logic.kernel.rust_loader.load_rust_core", return_value=mock_rs
                ):
                    im = InvariantManager()
                    self.assertTrue(im.l_val.validate(1))
                    self.assertTrue(im.l_val.validate(2))
                    self.assertFalse(im.l_val.validate(2))
                    self.assertTrue(im.k_val.validate())
                    self.assertTrue(im.k_val.validate())
                    with patch(
                        "warm_logic.kernel.sys.cryptography.MLDSA.verify",
                        return_value=True,
                    ):
                        self.assertTrue(
                            im.j_val.validate("h", {"signature": "s", "pub_key": "k"})
                        )
                    im.check_all(3, "h", {"signature": "s", "pub_key": "k"})
                    im.latch.trigger("UnitTest")
                    self.assertTrue(im.latch.latched)
                    self.assertFalse(im.check_all(4, "h", {}))

    # --- Policy (Ops) ---
    def test_plugin_policy(self):
        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "pathlib.Path.read_text",
                return_value=json.dumps(
                    {
                        "plugins": [
                            {"name": "p1", "package": "pkg1", "entry_point": "ep1"}
                        ]
                    }
                ),
            ):
                reg = load_registry(Path("fake.json"))
                self.assertIn("p1", reg)

        flags = MagicMock()
        flags.edition = "pro"
        flags.modules = {"mod1"}
        rec = PluginRecord("p1", editions_allowed={"pro"}, modules_required={"mod1"})
        registry = {"p1": rec}

        with patch(
            "warm_logic.kernel.ops.policy._load_entry_points",
            return_value={"ep1": "obj"},
        ):
            with patch("importlib.metadata.version", return_value="1.0.0"):
                rec.entry_point = "ep1"
                rec.package = "pkg1"
                installed = installed_plugins(registry)
                self.assertEqual(installed, ["p1"])
                errors = verify_plugin("p1", flags, registry)
                self.assertEqual(len(errors), 0)
                flags.edition = "home"
                errors = verify_plugin("p1", flags, registry)
                self.assertIn("edition home not allowed", errors[0])

    # --- Core Policy (kernel/policy.py) ---
    def test_core_policy(self):
        # We must import inside test to avoid module-level execution issues if any
        from warm_logic.kernel.policy import (
            PolicyResult,
            TenantPolicy,
            _guard_safe_window,
            _load_yaml_policy,
            apply_guard_policy,
            configure_guard_thresholds,
            ct_policy_decision,
            evaluate_os_policy,
            get_tenant_policy,
            load_guard_thresholds,
            normalize_govsat,
        )

        pr = PolicyResult(True, "reason")
        self.assertTrue(pr.approved)
        normalize_govsat()
        with self.assertRaises(RuntimeError):
            configure_guard_thresholds(path="non/existent/path/policy.yaml")
        tp = TenantPolicy("t1", {})
        self.assertEqual(tp.tenant_id, "t1")
        with patch("warm_logic.kernel.zanzibar.zanzibar.check", return_value=True):
            self.assertEqual(
                ct_policy_decision("ns", "obj", "rel", "user"),
                (True, "ZANZIBAR_APPROVED"),
            )
        self.assertEqual(evaluate_os_policy("state").reason, "INVARIANT_CHECK_PASSED")
        self.assertEqual(
            apply_guard_policy({}, load_guard_thresholds()).reason, "GUARD_CHECK_PASSED"
        )
        self.assertEqual(get_tenant_policy("org", "t").tenant_id, "t")
        defaults = load_guard_thresholds()
        self.assertIn("drift_max", defaults)
        with self.assertRaises(RuntimeError):
            _guard_safe_window([])
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value="a: 1"):
                with patch("yaml.safe_load", return_value={"a": 1}):
                    self.assertEqual(_load_yaml_policy(Path("p")), {"a": 1})
        with patch("pathlib.Path.exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                _load_yaml_policy(Path("p"))
        with patch("pathlib.Path.exists", side_effect=Exception("Read Err")):
            with self.assertRaises(RuntimeError):
                _load_yaml_policy(Path("p"))
