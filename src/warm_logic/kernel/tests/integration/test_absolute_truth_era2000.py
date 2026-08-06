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
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from warm_logic.kernel import policy
from warm_logic.kernel.hardware.confidential import HardwareGuard
from warm_logic.kernel.lineage import LineageTracker, PolicyZone
from warm_logic.kernel.ops.audit import IntegrityReport, SovereignAudit
from warm_logic.kernel.ops.control import (
    TaskScheduler,
)
from warm_logic.kernel.ops.metrics import SystemMetrics
from warm_logic.kernel.ops.quorum_manager import QuorumManager
from warm_logic.kernel.protocol import load_ct_spec
from warm_logic.kernel.sys.shield import (
    SyscallShield,
    SyscallViolation,
    kernel_exec,
    kernel_open,
)


class TestAbsoluteTruthEra2000(unittest.IsolatedAsyncioTestCase):
    def test_shield_reality(self):
        shield = SyscallShield("restricted")
        # Blocked
        with self.assertRaises(SyscallViolation):
            shield.enforce("execve")

        # Kernel functions raise RuntimeError
        with self.assertRaises(RuntimeError):
            kernel_open("test", 1)

        with self.assertRaises(SyscallViolation):
            kernel_exec("ls", [])

    def test_quorum_reality(self):
        # StitchServer stubs in quorum_manager now raise RuntimeError
        from warm_logic.kernel.ops.quorum_manager import StitchServer

        with self.assertRaises(RuntimeError):
            StitchServer.broadcast("EVT", {})

        # QuorumManager initialization
        mock_ledger = MagicMock()
        qm = QuorumManager(mock_ledger)

        # cast_vote Propagates RuntimeError from StitchServer
        with patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with patch("warm_logic.kernel.rust_loader.load_rust_core") as m_load:
                m_load.return_value.sign.return_value = "sig"
                with self.assertRaises(RuntimeError):
                    qm.cast_vote("H1", "APPROVE")

    def test_lineage_reality(self):
        lt = LineageTracker()
        # Deny by default (SIM-040)
        self.assertFalse(lt.check_flow("untracked", PolicyZone.PUBLIC))

    def test_metrics_reality(self):
        sys_m = SystemMetrics()
        # Default to critical (drift=1.0)
        self.assertTrue(sys_m.is_critical())
        sys_m.drift_score = 0.1
        sys_m.governance_health = 0.9
        sys_m.network_stability = 0.9
        self.assertFalse(sys_m.is_critical())

    def test_policy_reality(self):
        # Strict loading
        with self.assertRaises(FileNotFoundError):
            policy._load_yaml_policy(Path("nonexistent"))

        # Decision logic
        res = policy.evaluate_os_policy(None)
        self.assertFalse(res.approved)
        self.assertIn("CRITICAL: OS State is None", res.reason)

    def test_protocol_reality(self):
        spec = load_ct_spec()
        self.assertEqual(spec["version"], "0.1")
        self.assertFalse(spec["allow_anonymous"])

    def test_hardware_reality(self):
        guard = HardwareGuard()
        # Should return a report (mock or real) rather than raising
        report = guard.get_hardware_report()
        self.assertTrue(hasattr(report, "pcr_hash"))

    def test_scheduler_reality(self):
        ts = TaskScheduler()
        # Requires action (SIM-041)
        with self.assertRaises(ValueError):
            ts.schedule("T1", 10)
        ts.schedule("T1", lambda: print("OK"), priority=10)
        self.assertEqual(ts.pending_count(), 1)

    def test_audit_reality(self):
        audit = SovereignAudit(db_path=":memory:")
        report = IntegrityReport()
        # Empty chain should be valid (Genesis pending)
        self.assertTrue(audit._verify_proof_integrity(report))


if __name__ == "__main__":
    unittest.main()
