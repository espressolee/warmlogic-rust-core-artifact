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
import os

from warm_logic.kernel.ops.control import (
    KernelContext,
    KernelLoop,
    TaskScheduler,
    _fsm_next,
    _load_lines,
    _origin_from_entry,
)
from warm_logic.kernel.ops.metrics import SystemMetrics
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestControlCoverage(WarmLogicTestCase):
    def test_system_metrics(self):
        m = SystemMetrics()
        self.assertIsInstance(m, SystemMetrics)
        # Deny by Default: health starts at 0.0, drift at 1.0
        self.assertAlmostEqual(m.governance_health, 0.0)
        self.assertAlmostEqual(m.drift_score, 1.0)
        self.assertIn("-", m.hardware_id)  # Verify platform-specific separator exists

    def test_fsm_transitions(self):
        self.assertEqual(_fsm_next("INIT", "BOOT"), "AUTHORIZED")
        self.assertEqual(_fsm_next("AUTHORIZED", "ALIGN"), "ALIGNING")

    def test_kernel_loop(self):
        ctx = KernelContext()
        loop = KernelLoop(ctx)
        self.assertEqual(loop.state, "INIT")

    def test_task_scheduler(self):
        sched = TaskScheduler()
        sched.schedule("t1", lambda: "a1", priority=5)
        sched.schedule("t2", lambda: "a2", priority=1)

    def test_helpers(self):
        # 1. Origin
        self.assertEqual(_origin_from_entry({"meta": {"origin": "o1"}}), "o1")

    def test_load_lines(self):
        path = os.path.join(self.test_dir, "lines.json")
        with open(path, "w") as f:
            f.write('{"a": 1}\nINVALID\n{"b": 2}')

        lines = _load_lines(path)
        self.assertEqual(len(lines), 2)

    def test_stubs(self):
        # run_kernel_tick was removed
        pass
