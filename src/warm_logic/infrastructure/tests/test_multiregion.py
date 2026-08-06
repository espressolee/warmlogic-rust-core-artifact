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
[Q4 2026] Multi-region Deployment Tests

Tests for multi-region deployment infrastructure including:
- Region Registry
- Health Monitoring
- Replication
- Failover
- Traffic Routing
"""

from __future__ import annotations

import unittest

from warm_logic.infrastructure.multiregion import (
    DataSovereignty,
    FailoverEvent,
    FailoverManager,
    HealthMonitor,
    MultiRegionDeployment,
    Region,
    RegionHealth,
    RegionRegistry,
    RegionStatus,
    ReplicationConfig,
    ReplicationManager,
    ReplicationMode,
    RoutingRule,
    RoutingStrategy,
    TrafficRouter,
)

# =============================================================================
# Region Registry Tests
# =============================================================================


class TestRegionRegistry(unittest.TestCase):
    """Test region registry functionality."""

    def setUp(self):
        self.registry = RegionRegistry()

    def test_register_region(self):
        """Test registering a region."""
        region = self.registry.register_region(
            region_id="us-east-1",
            name="US East",
            location="Virginia, USA",
            cloud_provider="aws",
            endpoint="https://us-east-1.example.com",
        )

        self.assertIsInstance(region, Region)
        self.assertEqual(region.region_id, "us-east-1")
        self.assertIn("us-east-1", self.registry.regions)

    def test_register_primary_region(self):
        """Test registering a primary region."""
        region = self.registry.register_region(
            region_id="us-east-1",
            name="US East",
            location="Virginia",
            cloud_provider="aws",
            endpoint="https://us-east-1.example.com",
            is_primary=True,
        )

        self.assertTrue(region.is_primary)
        self.assertEqual(self.registry._primary_region, "us-east-1")

    def test_get_region(self):
        """Test getting a region by ID."""
        self.registry.register_region(
            region_id="eu-west-1",
            name="EU West",
            location="Ireland",
            cloud_provider="aws",
            endpoint="https://eu-west-1.example.com",
        )

        region = self.registry.get_region("eu-west-1")
        self.assertIsNotNone(region)
        self.assertEqual(region.name, "EU West")

    def test_get_region_not_found(self):
        """Test getting non-existent region."""
        region = self.registry.get_region("nonexistent")
        self.assertIsNone(region)

    def test_set_primary_region(self):
        """Test setting primary region."""
        self.registry.register_region(
            region_id="us-east-1",
            name="US East",
            location="Virginia",
            cloud_provider="aws",
            endpoint="https://us-east-1.example.com",
            is_primary=True,
        )
        self.registry.register_region(
            region_id="us-west-2",
            name="US West",
            location="Oregon",
            cloud_provider="aws",
            endpoint="https://us-west-2.example.com",
        )

        result = self.registry.set_primary_region("us-west-2")

        self.assertTrue(result)
        self.assertEqual(self.registry._primary_region, "us-west-2")
        self.assertTrue(self.registry.regions["us-west-2"].is_primary)
        self.assertFalse(self.registry.regions["us-east-1"].is_primary)

    def test_get_healthy_regions(self):
        """Test getting healthy regions."""
        self.registry.register_region(
            region_id="region-1",
            name="Region 1",
            location="Location",
            cloud_provider="aws",
            endpoint="https://region-1.example.com",
        )
        self.registry.register_region(
            region_id="region-2",
            name="Region 2",
            location="Location",
            cloud_provider="aws",
            endpoint="https://region-2.example.com",
        )
        self.registry.update_status("region-2", RegionStatus.UNHEALTHY)

        healthy = self.registry.get_healthy_regions()
        self.assertEqual(len(healthy), 1)
        self.assertEqual(healthy[0].region_id, "region-1")

    def test_get_regions_by_sovereignty(self):
        """Test filtering by data sovereignty."""
        self.registry.register_region(
            region_id="eu-region",
            name="EU Region",
            location="EU",
            cloud_provider="aws",
            endpoint="https://eu.example.com",
            data_sovereignty=DataSovereignty.EU,
        )
        self.registry.register_region(
            region_id="us-region",
            name="US Region",
            location="US",
            cloud_provider="aws",
            endpoint="https://us.example.com",
            data_sovereignty=DataSovereignty.US,
        )

        eu_regions = self.registry.get_regions_by_sovereignty(DataSovereignty.EU)
        self.assertEqual(len(eu_regions), 1)
        self.assertEqual(eu_regions[0].region_id, "eu-region")

    def test_update_status(self):
        """Test updating region status."""
        self.registry.register_region(
            region_id="region-1",
            name="Region 1",
            location="Location",
            cloud_provider="aws",
            endpoint="https://region-1.example.com",
        )

        result = self.registry.update_status("region-1", RegionStatus.MAINTENANCE)

        self.assertTrue(result)
        self.assertEqual(
            self.registry.regions["region-1"].status,
            RegionStatus.MAINTENANCE,
        )


# =============================================================================
# Health Monitor Tests
# =============================================================================


class TestHealthMonitor(unittest.TestCase):
    """Test health monitoring functionality."""

    def setUp(self):
        self.registry = RegionRegistry()
        self.registry.register_region(
            region_id="us-east-1",
            name="US East",
            location="Virginia",
            cloud_provider="aws",
            endpoint="https://us-east-1.example.com",
        )
        self.monitor = HealthMonitor(self.registry)

    def test_check_region_health(self):
        """Test checking region health."""
        region = self.registry.get_region("us-east-1")
        health = self.monitor.check_region_health(region)

        self.assertIsInstance(health, RegionHealth)
        self.assertEqual(health.region_id, "us-east-1")
        self.assertGreater(health.latency_ms, 0)

    def test_check_all_regions(self):
        """Test checking all regions."""
        self.registry.register_region(
            region_id="eu-west-1",
            name="EU West",
            location="Ireland",
            cloud_provider="aws",
            endpoint="https://eu-west-1.example.com",
        )

        results = self.monitor.check_all_regions()

        self.assertEqual(len(results), 2)
        self.assertIn("us-east-1", results)
        self.assertIn("eu-west-1", results)

    def test_custom_health_check_function(self):
        """Test custom health check function."""

        def custom_check(region: Region) -> RegionHealth:
            return RegionHealth(
                region_id=region.region_id,
                status=RegionStatus.HEALTHY,
                latency_ms=50.0,
            )

        self.monitor.set_health_check_function(custom_check)
        region = self.registry.get_region("us-east-1")
        health = self.monitor.check_region_health(region)

        self.assertEqual(health.latency_ms, 50.0)

    def test_get_average_latency(self):
        """Test getting average latency."""
        region = self.registry.get_region("us-east-1")

        # Generate some health history
        for _ in range(5):
            self.monitor.check_region_health(region)

        avg = self.monitor.get_average_latency("us-east-1", window=5)
        self.assertGreater(avg, 0)

    def test_get_health_summary(self):
        """Test getting health summary."""
        summary = self.monitor.get_health_summary()

        self.assertIn("total_regions", summary)
        self.assertIn("healthy", summary)
        self.assertIn("average_latency_ms", summary)


# =============================================================================
# Replication Manager Tests
# =============================================================================


class TestReplicationManager(unittest.TestCase):
    """Test replication management functionality."""

    def setUp(self):
        self.registry = RegionRegistry()
        self.registry.register_region(
            region_id="primary",
            name="Primary",
            location="US",
            cloud_provider="aws",
            endpoint="https://primary.example.com",
            is_primary=True,
        )
        self.registry.register_region(
            region_id="secondary",
            name="Secondary",
            location="EU",
            cloud_provider="aws",
            endpoint="https://secondary.example.com",
        )
        self.replication = ReplicationManager(self.registry)

    def test_create_replication(self):
        """Test creating replication config."""
        config = self.replication.create_replication(
            source_region="primary",
            target_regions=["secondary"],
            mode=ReplicationMode.ASYNC,
        )

        self.assertIsInstance(config, ReplicationConfig)
        self.assertEqual(config.source_region, "primary")
        self.assertIn("secondary", config.target_regions)

    def test_get_replication_status(self):
        """Test getting replication status."""
        self.replication.create_replication(
            source_region="primary",
            target_regions=["secondary"],
        )

        status = self.replication.get_replication_status("primary", "secondary")

        self.assertIsNotNone(status)
        self.assertEqual(status.source_region, "primary")
        self.assertEqual(status.target_region, "secondary")

    def test_update_replication_status(self):
        """Test updating replication status."""
        self.replication.create_replication(
            source_region="primary",
            target_regions=["secondary"],
            lag_threshold_ms=1000,
        )

        result = self.replication.update_replication_status(
            source_region="primary",
            target_region="secondary",
            lag_ms=500,
            bytes_transferred=1024,
        )

        self.assertTrue(result)
        status = self.replication.get_replication_status("primary", "secondary")
        self.assertEqual(status.lag_ms, 500)
        self.assertTrue(status.is_healthy)

    def test_replication_lag_threshold_exceeded(self):
        """Test replication lag exceeding threshold."""
        self.replication.create_replication(
            source_region="primary",
            target_regions=["secondary"],
            lag_threshold_ms=100,
        )

        self.replication.update_replication_status(
            source_region="primary",
            target_region="secondary",
            lag_ms=500,  # Exceeds 100ms threshold
        )

        status = self.replication.get_replication_status("primary", "secondary")
        self.assertFalse(status.is_healthy)

    def test_get_all_replication_health(self):
        """Test getting all replication health."""
        self.replication.create_replication(
            source_region="primary",
            target_regions=["secondary"],
        )

        health = self.replication.get_all_replication_health()

        self.assertIn("total_replications", health)
        self.assertIn("healthy", health)
        self.assertIn("details", health)


# =============================================================================
# Failover Manager Tests
# =============================================================================


class TestFailoverManager(unittest.TestCase):
    """Test failover management functionality."""

    def setUp(self):
        self.registry = RegionRegistry()
        self.registry.register_region(
            region_id="primary",
            name="Primary",
            location="US",
            cloud_provider="aws",
            endpoint="https://primary.example.com",
            is_primary=True,
            capacity_weight=1.0,
        )
        self.registry.register_region(
            region_id="secondary",
            name="Secondary",
            location="EU",
            cloud_provider="aws",
            endpoint="https://secondary.example.com",
            capacity_weight=0.8,
        )
        self.monitor = HealthMonitor(self.registry)
        self.failover = FailoverManager(self.registry, self.monitor)

    def test_trigger_failover(self):
        """Test triggering failover."""
        event = self.failover.trigger_failover(
            from_region="primary",
            to_region="secondary",
            reason="Manual failover test",
        )

        self.assertIsInstance(event, FailoverEvent)
        self.assertTrue(event.success)
        self.assertEqual(self.registry._primary_region, "secondary")

    def test_failover_to_invalid_region(self):
        """Test failover to invalid region."""
        event = self.failover.trigger_failover(
            from_region="primary",
            to_region="nonexistent",
            reason="Test",
        )

        self.assertFalse(event.success)

    def test_auto_failover(self):
        """Test automatic failover."""
        # Mark primary as unhealthy
        self.registry.update_status("primary", RegionStatus.UNHEALTHY)

        event = self.failover.auto_failover("primary")

        self.assertIsNotNone(event)
        self.assertTrue(event.success)
        self.assertEqual(event.to_region, "secondary")

    def test_auto_failover_no_healthy_regions(self):
        """Test auto failover with no healthy regions."""
        self.registry.update_status("secondary", RegionStatus.OFFLINE)

        event = self.failover.auto_failover("primary")

        self.assertIsNone(event)

    def test_failover_callback(self):
        """Test failover callback."""
        callback_events = []

        def callback(event: FailoverEvent):
            callback_events.append(event)

        self.failover.set_failover_callback(callback)
        self.failover.trigger_failover(
            from_region="primary",
            to_region="secondary",
            reason="Test",
        )

        self.assertEqual(len(callback_events), 1)

    def test_get_failover_metrics(self):
        """Test getting failover metrics."""
        self.failover.trigger_failover(
            from_region="primary",
            to_region="secondary",
            reason="Test",
        )

        metrics = self.failover.get_failover_metrics()

        self.assertEqual(metrics["total_failovers"], 1)
        self.assertEqual(metrics["successful"], 1)


# =============================================================================
# Traffic Router Tests
# =============================================================================


class TestTrafficRouter(unittest.TestCase):
    """Test traffic routing functionality."""

    def setUp(self):
        self.registry = RegionRegistry()
        self.registry.register_region(
            region_id="us-east-1",
            name="US East",
            location="Virginia, USA",
            cloud_provider="aws",
            endpoint="https://us-east-1.example.com",
            is_primary=True,
            data_sovereignty=DataSovereignty.US,
        )
        self.registry.register_region(
            region_id="eu-west-1",
            name="EU West",
            location="Ireland, EU",
            cloud_provider="aws",
            endpoint="https://eu-west-1.example.com",
            data_sovereignty=DataSovereignty.EU,
        )
        self.monitor = HealthMonitor(self.registry)
        self.router = TrafficRouter(self.registry, self.monitor)

    def test_add_routing_rule(self):
        """Test adding routing rule."""
        rule = self.router.add_routing_rule(
            name="default",
            strategy=RoutingStrategy.LATENCY,
            regions=["us-east-1", "eu-west-1"],
        )

        self.assertIsInstance(rule, RoutingRule)
        self.assertEqual(rule.strategy, RoutingStrategy.LATENCY)

    def test_route_request_default(self):
        """Test routing request with no rules."""
        region = self.router.route_request()

        self.assertIsNotNone(region)
        # Should return primary when no rules
        self.assertEqual(region.region_id, "us-east-1")

    def test_route_request_round_robin(self):
        """Test round robin routing."""
        self.router.add_routing_rule(
            name="round-robin",
            strategy=RoutingStrategy.ROUND_ROBIN,
            regions=["us-east-1", "eu-west-1"],
            priority=50,
        )

        region1 = self.router.route_request()
        region2 = self.router.route_request()

        # Should alternate between regions
        self.assertNotEqual(region1.region_id, region2.region_id)

    def test_route_request_failover(self):
        """Test failover routing."""
        self.router.add_routing_rule(
            name="failover",
            strategy=RoutingStrategy.FAILOVER,
            regions=["us-east-1", "eu-west-1"],
            priority=50,
        )

        region = self.router.route_request()
        self.assertEqual(region.region_id, "us-east-1")

        # Mark primary as unhealthy
        self.registry.update_status("us-east-1", RegionStatus.UNHEALTHY)
        region = self.router.route_request()
        self.assertEqual(region.region_id, "eu-west-1")

    def test_route_request_with_sovereignty(self):
        """Test routing with data sovereignty."""
        region = self.router.route_request(sovereignty=DataSovereignty.EU)

        self.assertIsNotNone(region)
        self.assertEqual(region.data_sovereignty, DataSovereignty.EU)

    def test_get_routing_stats(self):
        """Test getting routing statistics."""
        self.router.add_routing_rule(
            name="rule1",
            strategy=RoutingStrategy.LATENCY,
            regions=["us-east-1"],
        )

        stats = self.router.get_routing_stats()

        self.assertEqual(stats["total_rules"], 1)
        self.assertEqual(stats["enabled_rules"], 1)


# =============================================================================
# Multi-Region Deployment Tests
# =============================================================================


class TestMultiRegionDeployment(unittest.TestCase):
    """Test central multi-region deployment manager."""

    def setUp(self):
        self.deployment = MultiRegionDeployment(organization_name="Test Org")

    def test_initialize(self):
        """Test initialization."""
        result = self.deployment.initialize()
        self.assertTrue(result)
        self.assertTrue(self.deployment._initialized)

    def test_setup_standard_regions(self):
        """Test setting up standard regions."""
        self.deployment.initialize()
        regions = self.deployment.setup_standard_regions()

        self.assertEqual(len(regions), 4)

        # Verify primary is set
        primary = self.deployment.registry.get_primary_region()
        self.assertIsNotNone(primary)
        self.assertEqual(primary.region_id, "us-east-1")

    def test_route_request(self):
        """Test routing request."""
        self.deployment.initialize()
        self.deployment.setup_standard_regions()

        region = self.deployment.route_request()
        self.assertIsNotNone(region)

    def test_route_request_with_sovereignty(self):
        """Test routing with sovereignty requirements."""
        self.deployment.initialize()
        self.deployment.setup_standard_regions()

        region = self.deployment.route_request(sovereignty=DataSovereignty.EU)

        self.assertIsNotNone(region)
        self.assertEqual(region.data_sovereignty, DataSovereignty.EU)

    def test_get_deployment_status(self):
        """Test getting deployment status."""
        self.deployment.initialize()
        self.deployment.setup_standard_regions()

        status = self.deployment.get_deployment_status()

        self.assertEqual(status["organization"], "Test Org")
        self.assertTrue(status["initialized"])
        self.assertEqual(status["regions"]["total"], 4)
        self.assertIn("health", status)
        self.assertIn("replication", status)
        self.assertIn("failover", status)
        self.assertIn("routing", status)

    def test_check_global_health(self):
        """Test checking global health."""
        self.deployment.initialize()
        self.deployment.setup_standard_regions()

        is_healthy = self.deployment.check_global_health()
        self.assertTrue(is_healthy)

    def test_full_workflow(self):
        """Test complete multi-region workflow."""
        # Initialize
        self.deployment.initialize()

        # Setup regions
        regions = self.deployment.setup_standard_regions()
        self.assertEqual(len(regions), 4)

        # Route some requests
        for _ in range(10):
            region = self.deployment.route_request()
            self.assertIsNotNone(region)

        # Check replication
        replication_health = self.deployment.replication.get_all_replication_health()
        self.assertEqual(replication_health["total_replications"], 3)

        # Simulate failover
        event = self.deployment.failover.trigger_failover(
            from_region="us-east-1",
            to_region="us-west-2",
            reason="Test failover",
        )
        self.assertTrue(event.success)

        # Verify new primary
        new_primary = self.deployment.registry.get_primary_region()
        self.assertEqual(new_primary.region_id, "us-west-2")

        # Get final status
        status = self.deployment.get_deployment_status()
        self.assertEqual(status["failover"]["total_failovers"], 1)


if __name__ == "__main__":
    unittest.main()
