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
from unittest import mock

from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestChaosMonkeyCoverage(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        # Reset singleton state
        ChaosMonkey._instance = None
        self.chaos = ChaosMonkey()

    def test_singleton_and_configure(self):
        cm2 = ChaosMonkey()
        self.assertIs(self.chaos, cm2)

        ChaosMonkey.configure(
            enabled=True, drop_rate=0.5, latency_ms=100, corruption_rate=0.1
        )
        self.assertTrue(self.chaos.enabled)
        self.assertEqual(self.chaos.drop_rate, 0.5)
        self.assertEqual(self.chaos.latency_ms, 100)
        self.assertEqual(self.chaos.corruption_rate, 0.1)

    def test_middleware_disabled(self):
        ChaosMonkey.configure(enabled=False)
        mock_handler = mock.Mock()
        wrapped = ChaosMonkey.apply_middleware(mock_handler)

        payload = {"data": "ok"}
        wrapped(payload)
        mock_handler.assert_called_once_with(payload)

    def test_middleware_drop(self):
        ChaosMonkey.configure(enabled=True, drop_rate=1.0)
        mock_handler = mock.Mock()
        wrapped = ChaosMonkey.apply_middleware(mock_handler)

        # With drop_rate=1.0, it should always drop
        # But we mock random to be sure
        with mock.patch("random.random", return_value=0.0):  # 0.0 < 1.0 (Drop)
            with self.assertLogs("ChaosMonkey", level="WARNING") as cm:
                wrapped({"msg": "drop_me"})
                self.assertIn("Packet DROPPED", cm.output[0])
                mock_handler.assert_not_called()

    def test_middleware_latency(self):
        ChaosMonkey.configure(enabled=True, latency_ms=1000)
        mock_handler = mock.Mock()
        wrapped = ChaosMonkey.apply_middleware(mock_handler)

        # 1. No drop (random=0.9 > 0.0)
        # 2. Explicit Latency (latency_ms=1000 -> 1.0s)
        # 3. No corruption (random=0.9 > 0.0)

        # Mock random to avoid drop and corruption
        # Mock time.sleep to verify it's called
        with mock.patch("random.random", return_value=0.9):
            with mock.patch("time.sleep") as mock_sleep:
                wrapped({"msg": "slow_me"})
                mock_sleep.assert_called()
                args, _ = mock_sleep.call_args
                # Actual delay = 1.0 + jitter. Jitter is +/- 0.2.
                # So should be in [0.8, 1.2]
                self.assertGreater(args[0], 0.7)
                mock_handler.assert_called()

    def test_middleware_corruption_dict(self):
        ChaosMonkey.configure(enabled=True, corruption_rate=1.0)
        mock_handler = mock.Mock()
        wrapped = ChaosMonkey.apply_middleware(mock_handler)

        payload = {"hash": "VAL", "signature": "VAL"}

        # Mock random (Drop fail: random=0.9 > 0.0, Corruption success: random=0.0 < 1.0)
        with mock.patch("random.random", side_effect=[0.9, 0.0]):
            with self.assertLogs("ChaosMonkey", level="WARNING") as cm:
                wrapped(payload)
                self.assertIn("Payload CORRUPTED", cm.output[0])
                self.assertEqual(payload["hash"], "DEADBEEF" * 8)
                self.assertEqual(payload["signature"], "INVALID")
                mock_handler.assert_called()

    def test_middleware_corruption_non_dict(self):
        # Coverage for line 87: if isinstance(payload, dict)
        ChaosMonkey.configure(enabled=True, corruption_rate=1.0)
        mock_handler = mock.Mock()
        wrapped = ChaosMonkey.apply_middleware(mock_handler)

        payload = "string_payload"
        with mock.patch("random.random", side_effect=[0.9, 0.0]):
            wrapped(payload)
            # Should log corruption but not modify string (strings are immutable anyway in Py)
            mock_handler.assert_called_once_with(payload)
