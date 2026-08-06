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
from unittest.mock import MagicMock, mock_open, patch

from warm_logic.kernel.api import (
    ModeDecisionContext,
    _normalize_ct_action,
    _normalize_gov_action,
    compute_mode,
)
from warm_logic.kernel.bootloader import Bootloader, boot_system
from warm_logic.kernel.ops.control import (
    KernelLoop,
    TaskScheduler,
    _estimate_human_minutes,
    _fsm_next,
    _is_ci_related,
    _load_lines,
    _origin_from_entry,
    _parse_ts,
    _status_bucket,
    load_patch_efficiency,
)
from warm_logic.kernel.ops.metrics import SystemMetrics
from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey


class TestOpsCluster(unittest.TestCase):
    # --- Chaos Monkey ---
    def test_chaos_monkey(self):
        # Reset singleton
        ChaosMonkey._instance = None

        # 1. Config
        ChaosMonkey.configure(
            enabled=True, drop_rate=1.0, latency_ms=10, corruption_rate=1.0
        )
        self.assertTrue(ChaosMonkey._instance.enabled)

        # 2. Middleware - Drop
        handler = MagicMock()
        wrapped = ChaosMonkey.apply_middleware(handler)
        wrapped("payload")
        handler.assert_not_called()

        # 3. Middleware - Pass (disabled)
        ChaosMonkey.configure(enabled=False)
        wrapped("payload")
        handler.assert_called_with("payload")

        # 4. Latency & Corruption
        ChaosMonkey.configure(
            enabled=True, drop_rate=0.0, latency_ms=1, corruption_rate=1.0
        )
        payload = {"data": 1, "hash": "ok", "signature": "ok"}
        with patch("time.sleep"):  # Don't actually sleep in test
            wrapped(payload)
        self.assertEqual(payload["hash"], "DEADBEEF" * 8)
        self.assertEqual(payload["signature"], "INVALID")

    # --- Bootloader ---
    @patch("warm_logic.kernel.bootloader.HAS_RUST_CORE", True)
    @patch("warm_logic.kernel.bootloader.load_rust_core")
    @patch("warm_logic.kernel.bootloader.enforce_hardware_lock")
    @patch("warm_logic.kernel.bootloader.HardwareGuard.verify_system_integrity")
    def test_bootloader(self, mock_verify, mock_lock, mock_load):
        mock_verify.return_value = (True, "SECURE_BOOT_VERIFIED")
        rs = MagicMock()
        mock_load.return_value = rs

        b = Bootloader()
        self.assertEqual(b.state, "OFFLINE")
        self.assertTrue(b.run_init())
        self.assertEqual(b.state, "INITIALIZED")
        self.assertTrue(b.verify_secure_boot())
        self.assertEqual(b.state, "SECURE_BOOT_VERIFIED")
        self.assertTrue(b.jump_to_kernel())
        self.assertEqual(b.state, "RUNNING")

        self.assertTrue(boot_system())

        mock_verify.return_value = (False, "Fail")
        with self.assertRaises(RuntimeError):
            boot_system()

    # --- API ---
    @patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True)
    @patch("warm_logic.kernel.rust_loader.load_rust_core")
    def test_api_layer(self, mock_load):
        mock_rs = MagicMock()
        mock_rs.ReflectiveLoop.return_value.compute_mode.return_value = MagicMock(
            mode="NORMAL", reason="test"
        )
        mock_load.return_value = mock_rs

        # Reset global state to force reload
        import warm_logic.kernel.api as api

        api._RUST_LOOP = None

        ctx = ModeDecisionContext("NORMAL", {})
        res = compute_mode(ctx)
        self.assertEqual(res.mode, "NORMAL")

        from warm_logic.kernel import api

        self.assertTrue(api._drift_alarm(None))

        self.assertEqual(_normalize_gov_action(123), "123")
        self.assertIsNone(_normalize_gov_action(None))
        self.assertEqual(_normalize_ct_action(123), "123")

    # --- Control Ops ---
    def test_system_metrics(self):
        m = SystemMetrics()
        self.assertIsInstance(m, SystemMetrics)

    def test_fsm(self):
        self.assertEqual(_fsm_next("INIT", "BOOT"), "AUTHORIZED")
        self.assertEqual(_fsm_next("INIT", "UNK"), "INIT")

    def test_kernel_loop(self):
        ctx = MagicMock()
        ctx.tick_count = 0
        loop = KernelLoop(ctx)
        loop.tick()  # 0 -> 1 (via mock call if wired? no, ctx.increment_tick call)
        # Mock logic
        ctx.increment_tick = MagicMock()
        loop.tick()
        ctx.increment_tick.assert_called()

        # State transition
        ctx.tick_count = 3
        loop.state = "INIT"
        loop.tick()
        self.assertEqual(loop.state, "AUTHORIZED")

        # Exception resilience
        ctx.increment_tick.side_effect = Exception("Tick Fail")
        loop.tick()  # Should pass

    def test_scheduler(self):
        sch = TaskScheduler()
        sch.schedule("t1", lambda: None, priority=1)
        sch.schedule("t2", lambda: None, priority=0)

        t = sch.next_task()
        self.assertEqual(t.task_id, "t2")
        self.assertEqual(sch.pending_count(), 1)

        with self.assertRaises(ValueError):
            sch.schedule("t3", 5)  # priority overload
        t = sch.next_task()
        self.assertEqual(t.task_id, "t1")

    def test_helpers(self):
        self.assertEqual(_origin_from_entry({"meta": {"origin": "o"}}), "o")
        self.assertEqual(_origin_from_entry({"origin": "o"}), "o")

        self.assertEqual(_status_bucket("applied"), "success")
        self.assertEqual(_status_bucket("ROLLBACK"), "rollback")
        self.assertEqual(_status_bucket("fail"), "failed")

        self.assertTrue(_is_ci_related({"detail": {"error": 1}}))
        self.assertTrue(_is_ci_related("CI failed"))

        self.assertTrue(_is_ci_related("CI failed"))

        with (
            patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True),
            patch(
                "warm_logic.kernel.ops.metrics._estimate_human_minutes",
                return_value=6.0,
            ),
        ):
            self.assertEqual(_estimate_human_minutes({"origin": "manual"}), 6.0)

    def test_load_lines(self):
        with patch("builtins.open", mock_open(read_data='{"a": 1}\nbad\n{"b": 2}')):
            res = _load_lines("p")
            self.assertEqual(len(res), 2)
        with patch("builtins.open", side_effect=Exception("No file")):
            self.assertEqual(_load_lines("p"), [])

    def test_ts_parsing(self):
        from datetime import datetime

        self.assertIsNone(_parse_ts(None))
        self.assertIsInstance(_parse_ts(1000), datetime)
        self.assertIsInstance(_parse_ts("2021-01-01T00:00:00Z"), datetime)
        self.assertIsNone(_parse_ts("bad"))

    def test_reports(self):
        # reports logic in control.py now delegates to metrics.py
        # We assume delegation works if import error doesn't happen.
        # Ideally we'd patch metrics.load_patch_efficiency, but here we just ensure no RuntimeError.
        try:
            load_patch_efficiency("p")
        except (ImportError, FileNotFoundError, OSError):
            pass
