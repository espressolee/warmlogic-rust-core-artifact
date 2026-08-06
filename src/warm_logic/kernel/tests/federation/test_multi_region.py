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
"""
Tests for Multi-Region Federation module.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.federation.multi_region import (
    CrossRegionSync,
    MultiRegionFederation,
    Region,
    RegionConfig,
    RegionHealth,
    RegionSelector,
    create_default_region_configs,
)
from warm_logic.kernel.federation.sovereign_federation import FederationState


class TestRegion(unittest.TestCase):
    """Test Region enum."""

    def test_region_values(self):
        """Test region enum values."""
        self.assertEqual(Region.US_EAST.value, "us-east")
        self.assertEqual(Region.EU_WEST.value, "eu-west")
        self.assertEqual(Region.SOVEREIGN_LOCAL.value, "sovereign-local")


class TestRegionConfig(unittest.TestCase):
    """Test RegionConfig dataclass."""

    def test_config_creation(self):
        """Test basic config creation."""
        config = RegionConfig(
            region=Region.US_EAST,
            display_name="US East",
            primary_endpoint="us-east.example.com:8443",
        )
        self.assertEqual(config.region, Region.US_EAST)
        self.assertEqual(config.display_name, "US East")
        self.assertEqual(config.max_nodes, 10)
        self.assertFalse(config.is_primary)

    def test_config_with_backup_endpoints(self):
        """Test config with backup endpoints."""
        config = RegionConfig(
            region=Region.US_WEST,
            display_name="US West",
            primary_endpoint="us-west.example.com",
            backup_endpoints=["us-west-2.example.com", "us-west-3.example.com"],
        )
        self.assertEqual(len(config.backup_endpoints), 2)


class TestRegionHealth(unittest.TestCase):
    """Test RegionHealth dataclass."""

    def test_health_creation(self):
        """Test health status creation."""
        health = RegionHealth(
            region=Region.EU_CENTRAL,
            is_healthy=True,
            node_count=5,
            active_nodes=4,
            avg_latency_ms=25.5,
            last_sync_timestamp=time.time(),
            pending_sync_count=2,
        )
        self.assertTrue(health.is_healthy)
        self.assertEqual(health.node_count, 5)
        self.assertFalse(health.partition_detected)


class TestCrossRegionSync(unittest.TestCase):
    """Test CrossRegionSync dataclass."""

    def test_sync_creation(self):
        """Test sync creation."""
        sync = CrossRegionSync(
            source_region=Region.US_EAST,
            target_region=Region.EU_WEST,
            sync_id="sync-123",
            decisions=["dec-1", "dec-2"],
        )
        self.assertEqual(sync.source_region, Region.US_EAST)
        self.assertEqual(sync.status, "pending")
        self.assertIsNone(sync.completed_at)


class TestRegionSelector(unittest.TestCase):
    """Test RegionSelector."""

    def test_record_latency(self):
        """Test recording latency."""
        selector = RegionSelector()
        selector.record_latency(Region.US_EAST, 50.0)
        selector.record_latency(Region.US_EAST, 60.0)

        avg = selector.get_avg_latency(Region.US_EAST)
        self.assertEqual(avg, 55.0)

    def test_get_avg_latency_no_samples(self):
        """Test avg latency with no samples."""
        selector = RegionSelector()
        avg = selector.get_avg_latency(Region.EU_WEST)
        self.assertEqual(avg, float("inf"))

    def test_select_region_single(self):
        """Test selecting from single region."""
        selector = RegionSelector()
        result = selector.select_region([Region.US_EAST])
        self.assertEqual(result, Region.US_EAST)

    def test_select_region_empty(self):
        """Test selecting from empty list."""
        selector = RegionSelector()
        result = selector.select_region([])
        self.assertIsNone(result)

    def test_select_region_prefer_local(self):
        """Test preferring local region."""
        selector = RegionSelector()
        selector.record_latency(Region.US_EAST, 10.0)
        selector.record_latency(Region.US_WEST, 5.0)

        result = selector.select_region(
            [Region.US_EAST, Region.US_WEST],
            prefer_local=True,
            local_region=Region.US_EAST,
        )
        # Should prefer local since latency < 100ms
        self.assertEqual(result, Region.US_EAST)

    def test_select_region_lowest_latency(self):
        """Test selecting lowest latency."""
        selector = RegionSelector()
        selector.record_latency(Region.US_EAST, 100.0)
        selector.record_latency(Region.US_WEST, 50.0)
        selector.record_latency(Region.EU_WEST, 200.0)

        result = selector.select_region(
            [Region.US_EAST, Region.US_WEST, Region.EU_WEST],
            prefer_local=False,
        )
        self.assertEqual(result, Region.US_WEST)


class TestMultiRegionFederation(unittest.TestCase):
    """Test MultiRegionFederation."""

    def test_init(self):
        """Test federation initialization."""
        fed = MultiRegionFederation(
            local_node_id="node-1",
            local_region=Region.US_EAST,
        )
        self.assertEqual(fed.local_node_id, "node-1")
        self.assertEqual(fed.local_region, Region.US_EAST)
        self.assertEqual(fed.state, FederationState.INITIALIZING)

    def test_configure_region(self):
        """Test configuring a region."""
        fed = MultiRegionFederation("node-1", Region.US_EAST)

        config = RegionConfig(
            region=Region.US_EAST,
            display_name="US East",
            primary_endpoint="us-east.example.com",
        )
        fed.configure_region(config)

        state = fed.get_state()
        self.assertEqual(state["configured_regions"], 1)

    @patch("warm_logic.kernel.federation.multi_region.SovereignFederation")
    def test_bootstrap_local(self, mock_fed_class):
        """Test bootstrapping local region."""
        mock_fed = MagicMock()
        mock_fed.bootstrap.return_value = True
        mock_fed_class.return_value = mock_fed

        fed = MultiRegionFederation("node-1", Region.US_EAST)
        fed.configure_region(
            RegionConfig(
                region=Region.US_EAST,
                display_name="US East",
                primary_endpoint="localhost",
            )
        )

        result = fed.bootstrap_local()
        self.assertTrue(result)
        self.assertEqual(fed.state, FederationState.ACTIVE)

    def test_bootstrap_local_unconfigured(self):
        """Test bootstrapping unconfigured region fails."""
        fed = MultiRegionFederation("node-1", Region.US_EAST)
        result = fed.bootstrap_local()
        self.assertFalse(result)

    def test_get_healthy_regions(self):
        """Test getting healthy regions."""
        fed = MultiRegionFederation("node-1", Region.US_EAST)

        # Configure and set health
        fed.configure_region(RegionConfig(Region.US_EAST, "US East", "localhost"))
        fed.configure_region(RegionConfig(Region.EU_WEST, "EU West", "localhost"))

        fed._region_health[Region.US_EAST].is_healthy = True
        fed._region_health[Region.EU_WEST].is_healthy = False

        healthy = fed.get_healthy_regions()
        self.assertEqual(len(healthy), 1)
        self.assertIn(Region.US_EAST, healthy)

    def test_detect_partitions(self):
        """Test partition detection."""
        fed = MultiRegionFederation("node-1", Region.US_EAST)

        fed.configure_region(
            RegionConfig(Region.EU_WEST, "EU West", "localhost", sync_interval_sec=10)
        )

        # Set last sync time to long ago
        fed._region_health[Region.EU_WEST].last_sync_timestamp = time.time() - 100

        partitioned = fed.detect_partitions()
        self.assertEqual(len(partitioned), 1)
        self.assertEqual(partitioned[0], Region.EU_WEST)
        self.assertTrue(fed._region_health[Region.EU_WEST].partition_detected)

    def test_partition_callback(self):
        """Test partition detection callback."""
        fed = MultiRegionFederation("node-1", Region.US_EAST)

        callback_called = []

        def on_partition(region):
            callback_called.append(region)

        fed.set_partition_callback(on_partition)
        fed.configure_region(
            RegionConfig(Region.EU_WEST, "EU West", "localhost", sync_interval_sec=1)
        )
        fed._region_health[Region.EU_WEST].last_sync_timestamp = time.time() - 100

        fed.detect_partitions()
        self.assertEqual(len(callback_called), 1)

    def test_get_state(self):
        """Test getting federation state."""
        fed = MultiRegionFederation("node-1", Region.US_EAST)

        state = fed.get_state()
        self.assertEqual(state["local_node_id"], "node-1")
        self.assertEqual(state["local_region"], "us-east")
        self.assertEqual(state["state"], "initializing")


class TestCreateDefaultRegionConfigs(unittest.TestCase):
    """Test create_default_region_configs."""

    def test_creates_configs(self):
        """Test default configs are created."""
        configs = create_default_region_configs()
        self.assertGreaterEqual(len(configs), 5)

        # Check US East is primary
        us_east = next((c for c in configs if c.region == Region.US_EAST), None)
        self.assertIsNotNone(us_east)
        self.assertTrue(us_east.is_primary)

        # Check sovereign local exists
        local = next((c for c in configs if c.region == Region.SOVEREIGN_LOCAL), None)
        self.assertIsNotNone(local)


if __name__ == "__main__":
    unittest.main()
