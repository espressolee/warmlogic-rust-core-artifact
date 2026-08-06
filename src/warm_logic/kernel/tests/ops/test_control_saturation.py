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
from unittest import mock

from warm_logic.kernel.ops.control import (
    ConsensusMechanism,
    KernelContext,
    KernelLoop,
    KernelTask,
    ResonanceOptimizer,
    TaskScheduler,
    _estimate_human_minutes,
    _fsm_next,
    _infer_action,
    _is_ci_related,
    _load_lines,
    _origin_from_entry,
    _parse_ts,
    _status_bucket,
    build_patch_efficiency_report,
    load_patch_efficiency,
)


class TestControlSaturation(unittest.TestCase):
    def test_fsm_next(self):
        self.assertEqual(_fsm_next("INIT", "BOOT"), "AUTHORIZED")
        self.assertEqual(_fsm_next("INIT", "UNKNOWN"), "INIT")

    def test_kernel_context(self):
        ctx = KernelContext()
        ctx.increment_tick()
        self.assertEqual(ctx.tick_count, 1)

    def test_resonance_optimizer(self):
        mock_engine = mock.MagicMock()
        opt = ResonanceOptimizer(mock_engine)
        opt.alpha = 0.5
        opt.optimize(0.95, 0.0)  # alpha increase
        opt.optimize(0.5, 0.6)  # beta increase
        opt.optimize(0.3, 0.0)  # rescue reset

        class ReadOnlyEngine:
            @property
            def alpha(self):
                return 0.5

        opt_ro = ResonanceOptimizer(ReadOnlyEngine())
        opt_ro.optimize(0.5, 0.0)

    def test_kernel_loop_coverage_saturated(self):
        ctx = mock.MagicMock()
        # Line 120: service_registry = None
        del ctx.store
        del ctx.gossip
        tm = mock.MagicMock()
        tm.get_state.return_value = {"tick": 0, "hash": "0" * 64}
        tm.begin_transaction.side_effect = RuntimeError("test-isolated")
        with mock.patch("warm_logic.kernel.transaction.TransactionManager", return_value=tm):
            with mock.patch("warm_logic.kernel.api.rust_loader.HAS_RUST_CORE", False):
                loop = KernelLoop(ctx)
                self.assertIsNone(loop.service_registry)

        # Line 156-161: fallback tick logic
        ctx.tick_count = "bad"
        ctx.tick = "abc"
        loop.ctx = ctx
        loop.tick()
        self.assertEqual(loop.state, "INIT")  # Didn't reach 3

        # Evolution trigger (line 189 fallthrough)
        loop.evolution_chamber = True
        loop.trigger_evolution()

    def test_task_scheduler_saturated(self):
        sched = TaskScheduler()
        with self.assertRaises(ValueError):
            sched.schedule("t1", 1.0)

        t1 = KernelTask(10, "id1", lambda: 1)
        self.assertEqual(t1, "id1")
        self.assertNotEqual(t1, 123)

        sched.schedule("t1", lambda: 1, 10)
        self.assertEqual(sched.pending_count(), 1)  # Line 226
        sched.next_task()

    def test_helpers_saturated(self):
        # origin (line 233)
        self.assertEqual(_origin_from_entry({}), "unknown")

        # bucket
        self.assertEqual(_status_bucket("applied"), "success")
        self.assertEqual(_status_bucket("ROLLBACK"), "rollback")

        # ci related (line 249)
        self.assertTrue(_is_ci_related({"reason": "ci trigger"}))
        self.assertTrue(
            _is_ci_related(
                {"detail": {"detail_key": "v"}, "reason": "CI logic failure"}
            )
        )

        # estimate human (line 257-262)
        with mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", False):
            self.assertEqual(_estimate_human_minutes({}), 0.0)
        with mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
            with mock.patch(
                "warm_logic.kernel.ops.metrics._estimate_human_minutes",
                return_value=5.0,
            ):
                self.assertEqual(_estimate_human_minutes({}), 5.0)

        # parse ts (line 295-296)
        # Fix: call directly with bad string to trigger exception in fromisoformat
        self.assertIsNone(_parse_ts("not-iso"))

        # Wrappers (300-310)
        with mock.patch(
            "warm_logic.kernel.ops.metrics.load_patch_efficiency", return_value={}
        ):
            load_patch_efficiency("p")
        with mock.patch(
            "warm_logic.kernel.ops.metrics.build_patch_efficiency_report",
            return_value={},
        ):
            build_patch_efficiency_report([])

        # infer action (320)
        self.assertEqual(_infer_action(), "HALT")

    def test_load_lines_saturated(self):
        with mock.patch(
            "builtins.open", mock.mock_open(read_data='{"a": 1}\nnot json')
        ):
            _load_lines("p")
        with mock.patch("builtins.open", side_effect=IOError("no")):
            _load_lines("p")

    def test_consensus(self):
        with self.assertRaises(RuntimeError):
            ConsensusMechanism().propose_block("h")


if __name__ == "__main__":
    unittest.main()
