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
from unittest.mock import MagicMock, patch

from warm_logic.observability import metrics


class TestPromMetrics(unittest.TestCase):
    def test_metrics_definitions(self):
        """Verify that Prometheus metrics are defined and callable."""
        # Check definitions
        self.assertIsNotNone(metrics.UPTIME_SECONDS)
        self.assertIsNotNone(metrics.KERNEL_INFO)
        self.assertIsNotNone(metrics.PEER_COUNT)
        self.assertIsNotNone(metrics.MESSAGE_SENT)
        self.assertIsNotNone(metrics.MESSAGE_RECEIVED)
        self.assertIsNotNone(metrics.BLOCK_HEIGHT)
        self.assertIsNotNone(metrics.QUORUM_ROUNDS)
        self.assertIsNotNone(metrics.JITTER)

    def test_update_uptime(self):
        """Verify update_uptime sets the gauge."""
        with patch.object(metrics.UPTIME_SECONDS, "set") as mock_set:
            metrics.update_uptime()
            mock_set.assert_called_once()

    def test_set_info(self):
        """Verify set_info sets the gauge with labels."""
        with patch.object(metrics.KERNEL_INFO, "labels") as mock_labels:
            mock_gauge = MagicMock()
            mock_labels.return_value = mock_gauge

            metrics.set_info("1.0.0", "test-era")

            mock_labels.assert_called_with(version="1.0.0", era="test-era")
            mock_gauge.set.assert_called_with(1)
