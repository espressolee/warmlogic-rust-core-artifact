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
import sys
import unittest
from datetime import datetime
from unittest import mock

# Import api to patch it directly
from warm_logic.kernel import api

# Target modules
from warm_logic.kernel.ops import control, metrics


class TestSaturationGapCloser(unittest.TestCase):
    def setUp(self):
        self.mock_ctx = mock.MagicMock()

    # --- control.py gaps ---

    def test_control_init_with_rust_core(self):
        """Cover control.py lines 88-94"""
        # Patch the real objects on the imported api module
        with mock.patch.object(api.rust_loader, "HAS_RUST_CORE", True):
            with mock.patch.object(api, "compute_mode") as mock_compute:
                with mock.patch.object(api, "_RUST_LOOP", mock.MagicMock()):
                    loop = control.KernelLoop(self.mock_ctx)

                    # Verify optimization was called
                    mock_compute.assert_called()
                    self.assertIsNotNone(loop.optimizer)

    def test_control_service_registry_full(self):
        """Cover control.py lines 116-118"""
        self.mock_ctx.store = mock.MagicMock()
        self.mock_ctx.gossip = mock.MagicMock()
        self.mock_ctx.gossip.dht = mock.MagicMock()

        # Mock local import of ServiceQuorum
        mock_sr_module = mock.MagicMock()
        mock_service_quorum = mock_sr_module.ServiceQuorum

        with mock.patch.dict(
            sys.modules,
            {
                "warm_logic.kernel.ops.service_registry": mock_sr_module,
                "warm_logic.kernel.ops.collective_evolution": mock.MagicMock(),
            },
        ):
            loop = control.KernelLoop(self.mock_ctx)

            # Line 116 reached?
            mock_service_quorum.assert_called()
            self.assertIsNotNone(loop.service_registry)
            # Line 118
            self.assertEqual(
                self.mock_ctx.gossip.dht.service_registry, loop.service_registry
            )

    def test_control_tick_exceptions_and_branches(self):
        """Cover control.py 140-141, 145-151, 163, 171-172"""
        loop = control.KernelLoop(self.mock_ctx)
        loop.optimizer = mock.MagicMock()

        # 1. 140-141: logic exception
        self.mock_ctx.increment_tick.side_effect = Exception("TickFail")
        loop.tick()  # Should log error and continue

        # 2. 145-151: Evolution trigger
        loop.evolution_chamber = True
        loop.trigger_evolution = mock.MagicMock()
        loop.tick({"epsilon_c": 0.99, "tau_ethics": 0.0})
        loop.trigger_evolution.assert_called()

        # 3. 163: INIT -> AUTHORIZED
        loop.state = "INIT"
        self.mock_ctx.tick_count = 5
        loop.tick()
        self.assertEqual(loop.state, "AUTHORIZED")

        # 4. 171-172: Prometheus fail
        with mock.patch("warm_logic.kernel.ops.control.prom_metrics") as mock_prom:
            mock_prom.update_uptime.side_effect = Exception("PromFail")
            loop.tick()  # Should log warning

    def test_task_scheduler_eq_and_empty(self):
        """Cover control.py 205, 222"""
        t1 = control.KernelTask(10, "A", lambda: 1)
        t2 = control.KernelTask(10, "A", lambda: 1)
        t3 = control.KernelTask(20, "A", lambda: 1)
        t4 = control.KernelTask(10, "B", lambda: 1)

        self.assertTrue(t1 == t2)
        self.assertFalse(t1 == t3)  # Priority diff
        self.assertFalse(t1 == t4)  # ID diff
        self.assertFalse(t1 == "C")

        sched = control.TaskScheduler()
        self.assertIsNone(sched.next_task())

    # --- metrics.py gaps ---

    def test_metrics_parse_ts_overflow(self):
        """Cover metrics.py 53-54"""
        # Natural overflow
        val = 1e30  # Huge float timestamp
        self.assertIsNone(metrics._parse_ts(val))

    def test_metrics_json_load_fail(self):
        """Cover metrics.py 77-79"""
        p = mock.MagicMock()
        p.exists.return_value = True
        p.read_text.return_value = '{"good": 1}\n{bad json'

        res = metrics._load_lines(p, 100)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], {"good": 1})

    def test_metrics_helpers_deep(self):
        """Cover metrics.py 98, 101, 116-118, etc"""
        # _origin_from_entry nested
        e1 = {"meta": {"source": "S1"}}
        self.assertEqual(metrics._origin_from_entry(e1), "S1")

        # Use a string that GUARANTEES a match with CI_MARKERS
        e2 = {"detail": {"ci_logs": ["ci failure occurred"]}}
        self.assertTrue(metrics._is_ci_related(e2))

        self.assertFalse(
            metrics._is_ci_related({"detail": {"error": ["nothing important"]}})
        )

    def test_metrics_snapshot_overflow(self):
        """Cover metrics.py 298-299"""
        sm = metrics.SystemMetrics()
        sm._max_buffer_size = 1
        sm.record_snapshot()
        sm.record_snapshot()
        self.assertEqual(len(sm._trend_buffer), 1)

    def test_control_parse_ts_branches(self):
        """Cover control.py 287-291"""
        # 287: isinstance datetime
        dt = datetime.now()
        self.assertEqual(control._parse_ts(dt), dt)
        # 289: None
        self.assertIsNone(control._parse_ts(None))
        # 291: int/float
        self.assertIsNotNone(control._parse_ts(1234567890))

    def test_control_evolution_elif(self):
        """Cover control.py 189"""
        loop = control.KernelLoop(self.mock_ctx)
        loop.mutation_quorum = None
        loop.evolution_chamber = True
        loop.trigger_evolution()  # Should hit elif self.evolution_chamber

    def test_control_helpers_final(self):
        """Cover control.py 231-232, 241, 248"""
        # 231-232
        self.assertEqual(control._origin_from_entry({"meta": {"origin": "O1"}}), "O1")
        # 241
        self.assertEqual(control._status_bucket("unknown_status"), "failed")
        # 248
        self.assertTrue(control._is_ci_related({"detail": {"tests_failing": True}}))

    def test_metrics_helpers_final(self):
        """Cover metrics.py 114, 134, 136, 141, 143"""
        # 114: error as string
        self.assertTrue(metrics._is_ci_related({"detail": {"error": "ci failure"}}))

        # 134: manual origin
        with mock.patch.dict(
            sys.modules
        ):  # Ensure no rust core interference or use mock
            # Actually _estimate_human_minutes in metrics.py doesn't check RUST_CORE, control.py wrapper does.
            # We are testing metrics.py directly.
            self.assertEqual(
                metrics._estimate_human_minutes({"origin": "manual"}), 6.0
            )  # default 6

        # 136: human_in_loop
        self.assertEqual(
            metrics._estimate_human_minutes({"human_in_loop": True}), 5.0
        )  # default 5

        # 141: meta human_in_loop
        self.assertEqual(
            metrics._estimate_human_minutes({"meta": {"human_in_loop": True}}), 5.0
        )

        # 143: reason token
        self.assertEqual(
            metrics._estimate_human_minutes({"reason": "manual review required"}), 5.0
        )

    def test_metrics_file_read_fail(self):
        """Cover metrics.py 70-72"""
        p = mock.MagicMock()
        p.exists.return_value = True
        p.read_text.side_effect = Exception("ReadFail")
        self.assertEqual(metrics._load_lines(p, 10), [])

    def test_metrics_final_saturation(self):
        """Cover 206, 209, 307, 318, 361-366"""
        # 206: pattern/ts missing
        metrics._compute_ci_fix_stats([{"status": "applied"}])  # No pattern
        metrics._compute_ci_fix_stats([{"pattern": "P2"}])  # No ts

        # 209: failed but NOT CI related
        e2 = {
            "pattern": "P1",
            "ts": "2024-01-01T00:00:00Z",
            "status": "error",
            "reason": "normal failure",
        }
        metrics._compute_ci_fix_stats([e2])

        # 307/318: SystemMetrics buffer size < 2 and division
        sm = metrics.SystemMetrics()
        self.assertEqual(sm.get_derivative("drift_score"), 0.0)  # size 0
        sm.record_snapshot()
        self.assertEqual(sm.get_derivative("drift_score"), 0.0)  # size 1

        # 318: successful derivative calculation
        sm.drift_score = 1.0
        sm.record_snapshot()
        # Ensure delta_time > 0 by mocking time.time or just trusting real time (risky in fast tests)
        with mock.patch(
            "time.time", side_effect=[100.0, 200.0, 300.0, 400.0]
        ):  # record calls time.time
            sm2 = metrics.SystemMetrics()  # start_time=100
            sm2.drift_score = 1.0
            sm2.record_snapshot()  # snapshot.ts=200
            sm2.drift_score = 2.0
            sm2.record_snapshot()  # snapshot.ts=300
            # derivative = (2.0 - 1.0) / (300 - 200) = 0.01
            self.assertAlmostEqual(sm2.get_derivative("drift_score"), 0.01)

        # 361-366: ingest_batch
        records = [
            {"origin": "O1", "status": "applied"},
            {"origin": "O2", "status": "applied"},
        ]
        sm.ingest_batch(records)
        self.assertEqual(sm.governance_health, 1.0)


if __name__ == "__main__":
    unittest.main()
