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
[Q4 2026] Multi-region Deployment Infrastructure

Provides multi-region deployment capabilities:
- Region management and discovery
- Cross-region replication
- Global load balancing
- Failover and disaster recovery
- Region-aware routing
- Data sovereignty controls
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class RegionStatus(Enum):
    """Region health status"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class ReplicationMode(Enum):
    """Data replication modes"""

    SYNC = "synchronous"  # Strong consistency
    ASYNC = "asynchronous"  # Eventual consistency
    SEMI_SYNC = "semi_synchronous"  # Quorum-based


class RoutingStrategy(Enum):
    """Request routing strategies"""

    LATENCY = "latency"  # Route to lowest latency region
    GEOGRAPHIC = "geographic"  # Route to nearest region
    ROUND_ROBIN = "round_robin"  # Distribute evenly
    WEIGHTED = "weighted"  # Based on capacity weights
    FAILOVER = "failover"  # Primary with fallback


class DataSovereignty(Enum):
    """Data sovereignty requirements"""

    NONE = "none"  # No restrictions
    EU = "eu"  # EU data residency
    US = "us"  # US data residency
    APAC = "apac"  # Asia-Pacific residency
    STRICT = "strict"  # No cross-region transfer


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Region:
    """Represents a deployment region"""

    region_id: str = ""
    name: str = ""
    location: str = ""  # Geographic location
    cloud_provider: str = ""  # aws, gcp, azure
    availability_zones: list[str] = field(default_factory=list)
    status: RegionStatus = RegionStatus.HEALTHY
    is_primary: bool = False
    capacity_weight: float = 1.0
    data_sovereignty: DataSovereignty = DataSovereignty.NONE
    endpoint: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_health_check: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegionHealth:
    """Health status of a region"""

    region_id: str = ""
    status: RegionStatus = RegionStatus.HEALTHY
    latency_ms: float = 0.0
    error_rate: float = 0.0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    active_connections: int = 0
    requests_per_second: float = 0.0
    checked_at: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplicationConfig:
    """Replication configuration between regions"""

    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_region: str = ""
    target_regions: list[str] = field(default_factory=list)
    mode: ReplicationMode = ReplicationMode.ASYNC
    lag_threshold_ms: int = 1000
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReplicationStatus:
    """Current replication status"""

    source_region: str = ""
    target_region: str = ""
    lag_ms: float = 0.0
    last_sync: datetime | None = None
    bytes_transferred: int = 0
    is_healthy: bool = True
    error_message: str = ""


@dataclass
class FailoverEvent:
    """Record of a failover event"""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_region: str = ""
    to_region: str = ""
    reason: str = ""
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    success: bool = False
    duration_ms: float = 0.0
    affected_services: list[str] = field(default_factory=list)


@dataclass
class RoutingRule:
    """Traffic routing rule"""

    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: RoutingStrategy = RoutingStrategy.LATENCY
    regions: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    conditions: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 100


# =============================================================================
# Region Registry
# =============================================================================


class RegionRegistry:
    """
    Registry for deployment regions.

    Manages region configuration and discovery.
    """

    def __init__(self) -> None:
        self.regions: dict[str, Region] = {}
        self._primary_region: str | None = None

    def register_region(
        self,
        region_id: str,
        name: str,
        location: str,
        cloud_provider: str,
        endpoint: str,
        availability_zones: list[str] | None = None,
        is_primary: bool = False,
        capacity_weight: float = 1.0,
        data_sovereignty: DataSovereignty = DataSovereignty.NONE,
    ) -> Region:
        """
        Register a new region.

        Args:
            region_id: Unique region identifier
            name: Human-readable name
            location: Geographic location
            cloud_provider: Cloud provider (aws, gcp, azure)
            endpoint: Region endpoint URL
            availability_zones: AZs in the region
            is_primary: Whether this is the primary region
            capacity_weight: Weight for load balancing
            data_sovereignty: Data residency requirements

        Returns:
            Region
        """
        region = Region(
            region_id=region_id,
            name=name,
            location=location,
            cloud_provider=cloud_provider,
            endpoint=endpoint,
            availability_zones=availability_zones or [],
            is_primary=is_primary,
            capacity_weight=capacity_weight,
            data_sovereignty=data_sovereignty,
        )
        self.regions[region_id] = region

        if is_primary:
            self._primary_region = region_id

        logger.info(f"Region registered: {name} ({region_id})")
        return region

    def get_region(self, region_id: str) -> Region | None:
        """Get a region by ID."""
        return self.regions.get(region_id)

    def get_primary_region(self) -> Region | None:
        """Get the primary region."""
        if self._primary_region:
            return self.regions.get(self._primary_region)
        return None

    def set_primary_region(self, region_id: str) -> bool:
        """Set the primary region."""
        if region_id not in self.regions:
            return False

        # Unset current primary
        if self._primary_region and self._primary_region in self.regions:
            self.regions[self._primary_region].is_primary = False

        self.regions[region_id].is_primary = True
        self._primary_region = region_id
        return True

    def get_healthy_regions(self) -> list[Region]:
        """Get all healthy regions."""
        return [r for r in self.regions.values() if r.status == RegionStatus.HEALTHY]

    def get_regions_by_sovereignty(
        self,
        sovereignty: DataSovereignty,
    ) -> list[Region]:
        """Get regions matching data sovereignty requirements."""
        return [
            r
            for r in self.regions.values()
            if r.data_sovereignty == sovereignty or sovereignty == DataSovereignty.NONE
        ]

    def update_status(self, region_id: str, status: RegionStatus) -> bool:
        """Update region status."""
        if region_id not in self.regions:
            return False

        self.regions[region_id].status = status
        self.regions[region_id].last_health_check = datetime.utcnow()
        return True


# =============================================================================
# Health Monitor
# =============================================================================


class HealthMonitor:
    """
    Monitors health of all regions.

    Performs regular health checks and status updates.
    """

    def __init__(
        self,
        registry: RegionRegistry,
        check_interval_seconds: int = 30,
    ):
        self.registry = registry
        self.check_interval = check_interval_seconds
        self.health_history: dict[str, list[RegionHealth]] = {}
        self._health_check_func: Callable[[Region], RegionHealth] | None = None

    def set_health_check_function(
        self,
        func: Callable[[Region], RegionHealth],
    ) -> None:
        """Set custom health check function."""
        self._health_check_func = func

    def check_region_health(self, region: Region) -> RegionHealth:
        """
        Check health of a single region.

        Args:
            region: Region to check

        Returns:
            RegionHealth status
        """
        if self._health_check_func:
            return self._health_check_func(region)

        # Default health check (simulated)
        start_time = time.time()
        latency_ms = random.uniform(10, 100)  # Simulated latency
        elapsed = (time.time() - start_time) * 1000

        health = RegionHealth(
            region_id=region.region_id,
            status=region.status,
            latency_ms=latency_ms + elapsed,
            error_rate=random.uniform(0, 0.01),  # Simulated
            cpu_utilization=random.uniform(0.2, 0.8),
            memory_utilization=random.uniform(0.3, 0.7),
            active_connections=random.randint(100, 1000),
            requests_per_second=random.uniform(100, 10000),
        )

        # Update health history
        if region.region_id not in self.health_history:
            self.health_history[region.region_id] = []
        self.health_history[region.region_id].append(health)

        # Keep only last 100 entries
        if len(self.health_history[region.region_id]) > 100:
            self.health_history[region.region_id] = self.health_history[
                region.region_id
            ][-100:]

        return health

    def check_all_regions(self) -> dict[str, RegionHealth]:
        """Check health of all regions."""
        results = {}
        for region in self.registry.regions.values():
            if region.status != RegionStatus.OFFLINE:
                results[region.region_id] = self.check_region_health(region)
        return results

    def get_average_latency(self, region_id: str, window: int = 10) -> float:
        """Get average latency for a region over recent checks."""
        history = self.health_history.get(region_id, [])
        if not history:
            return float("inf")

        recent = history[-window:]
        return sum(h.latency_ms for h in recent) / len(recent)

    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary across all regions."""
        all_health = self.check_all_regions()

        healthy = sum(
            1 for h in all_health.values() if h.status == RegionStatus.HEALTHY
        )
        degraded = sum(
            1 for h in all_health.values() if h.status == RegionStatus.DEGRADED
        )
        unhealthy = sum(
            1 for h in all_health.values() if h.status == RegionStatus.UNHEALTHY
        )

        avg_latency = (
            sum(h.latency_ms for h in all_health.values()) / len(all_health)
            if all_health
            else 0
        )

        return {
            "total_regions": len(self.registry.regions),
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "average_latency_ms": round(avg_latency, 2),
            "checked_at": datetime.utcnow().isoformat(),
        }


# =============================================================================
# Replication Manager
# =============================================================================


class ReplicationManager:
    """
    Manages cross-region data replication.

    Supports sync, async, and semi-sync replication modes.
    """

    def __init__(self, registry: RegionRegistry):
        self.registry = registry
        self.configs: dict[str, ReplicationConfig] = {}
        self.statuses: dict[str, ReplicationStatus] = {}

    def create_replication(
        self,
        source_region: str,
        target_regions: list[str],
        mode: ReplicationMode = ReplicationMode.ASYNC,
        lag_threshold_ms: int = 1000,
    ) -> ReplicationConfig:
        """
        Create a replication configuration.

        Args:
            source_region: Source region ID
            target_regions: Target region IDs
            mode: Replication mode
            lag_threshold_ms: Maximum acceptable lag

        Returns:
            ReplicationConfig
        """
        config = ReplicationConfig(
            source_region=source_region,
            target_regions=target_regions,
            mode=mode,
            lag_threshold_ms=lag_threshold_ms,
        )
        self.configs[config.config_id] = config

        # Initialize status for each target
        for target in target_regions:
            key = f"{source_region}->{target}"
            self.statuses[key] = ReplicationStatus(
                source_region=source_region,
                target_region=target,
            )

        logger.info(
            f"Replication created: {source_region} -> {target_regions} ({mode.value})"
        )
        return config

    def get_replication_status(
        self,
        source_region: str,
        target_region: str,
    ) -> ReplicationStatus | None:
        """Get replication status between two regions."""
        key = f"{source_region}->{target_region}"
        return self.statuses.get(key)

    def update_replication_status(
        self,
        source_region: str,
        target_region: str,
        lag_ms: float,
        bytes_transferred: int = 0,
    ) -> bool:
        """Update replication status."""
        key = f"{source_region}->{target_region}"
        if key not in self.statuses:
            return False

        status = self.statuses[key]
        status.lag_ms = lag_ms
        status.last_sync = datetime.utcnow()
        status.bytes_transferred += bytes_transferred

        # Check if lag exceeds threshold
        for config in self.configs.values():
            if (
                config.source_region == source_region
                and target_region in config.target_regions
            ):
                status.is_healthy = lag_ms <= config.lag_threshold_ms
                if not status.is_healthy:
                    status.error_message = (
                        f"Lag {lag_ms}ms exceeds threshold {config.lag_threshold_ms}ms"
                    )
                break

        return True

    def get_all_replication_health(self) -> dict[str, Any]:
        """Get health status of all replications."""
        total = len(self.statuses)
        healthy = sum(1 for s in self.statuses.values() if s.is_healthy)
        avg_lag = (
            sum(s.lag_ms for s in self.statuses.values()) / total if total > 0 else 0
        )

        return {
            "total_replications": total,
            "healthy": healthy,
            "unhealthy": total - healthy,
            "average_lag_ms": round(avg_lag, 2),
            "details": {
                key: {
                    "lag_ms": s.lag_ms,
                    "is_healthy": s.is_healthy,
                    "last_sync": s.last_sync.isoformat() if s.last_sync else None,
                }
                for key, s in self.statuses.items()
            },
        }


# =============================================================================
# Failover Manager
# =============================================================================


class FailoverManager:
    """
    Manages region failover and disaster recovery.

    Handles automatic and manual failovers between regions.
    """

    def __init__(
        self,
        registry: RegionRegistry,
        health_monitor: HealthMonitor,
    ):
        self.registry = registry
        self.health_monitor = health_monitor
        self.failover_history: list[FailoverEvent] = []
        self._failover_callback: Callable[[FailoverEvent], None] | None = None

    def set_failover_callback(
        self,
        callback: Callable[[FailoverEvent], None],
    ) -> None:
        """Set callback for failover events."""
        self._failover_callback = callback

    def trigger_failover(
        self,
        from_region: str,
        to_region: str,
        reason: str,
        affected_services: list[str] | None = None,
    ) -> FailoverEvent:
        """
        Trigger a failover from one region to another.

        Args:
            from_region: Region to failover from
            to_region: Region to failover to
            reason: Reason for failover
            affected_services: List of affected services

        Returns:
            FailoverEvent
        """
        start_time = time.time()

        event = FailoverEvent(
            from_region=from_region,
            to_region=to_region,
            reason=reason,
            affected_services=affected_services or [],
        )

        # Validate regions
        if from_region not in self.registry.regions:
            event.success = False
            return event

        if to_region not in self.registry.regions:
            event.success = False
            return event

        target = self.registry.regions[to_region]
        if target.status not in (RegionStatus.HEALTHY, RegionStatus.DEGRADED):
            event.success = False
            return event

        # Perform failover
        self.registry.update_status(from_region, RegionStatus.OFFLINE)
        self.registry.set_primary_region(to_region)

        event.success = True
        event.completed_at = datetime.utcnow()
        event.duration_ms = (time.time() - start_time) * 1000

        self.failover_history.append(event)

        # Trigger callback
        if self._failover_callback:
            self._failover_callback(event)

        logger.warning(
            f"Failover completed: {from_region} -> {to_region}",
            extra={
                "event_id": event.event_id,
                "duration_ms": event.duration_ms,
            },
        )

        return event

    def auto_failover(self, unhealthy_region: str) -> FailoverEvent | None:
        """
        Automatically failover from an unhealthy region.

        Selects best healthy region based on capacity.
        """
        healthy_regions = self.registry.get_healthy_regions()
        healthy_regions = [
            r for r in healthy_regions if r.region_id != unhealthy_region
        ]

        if not healthy_regions:
            logger.error(
                f"No healthy regions available for failover from {unhealthy_region}"
            )
            return None

        # Select region with highest capacity weight
        best_region = max(healthy_regions, key=lambda r: r.capacity_weight)

        return self.trigger_failover(
            from_region=unhealthy_region,
            to_region=best_region.region_id,
            reason="Automatic failover due to region health failure",
        )

    def get_failover_history(
        self,
        limit: int = 50,
    ) -> list[FailoverEvent]:
        """Get recent failover history."""
        return self.failover_history[-limit:]

    def get_failover_metrics(self) -> dict[str, Any]:
        """Get failover metrics."""
        successful = sum(1 for e in self.failover_history if e.success)
        failed = len(self.failover_history) - successful
        avg_duration = (
            sum(e.duration_ms for e in self.failover_history if e.success) / successful
            if successful > 0
            else 0
        )

        return {
            "total_failovers": len(self.failover_history),
            "successful": successful,
            "failed": failed,
            "average_duration_ms": round(avg_duration, 2),
            "success_rate": (
                successful / len(self.failover_history)
                if self.failover_history
                else 1.0
            ),
        }


# =============================================================================
# Traffic Router
# =============================================================================


class TrafficRouter:
    """
    Routes traffic across regions.

    Implements various routing strategies for optimal distribution.
    """

    def __init__(
        self,
        registry: RegionRegistry,
        health_monitor: HealthMonitor,
    ):
        self.registry = registry
        self.health_monitor = health_monitor
        self.rules: dict[str, RoutingRule] = {}
        self._round_robin_index: dict[str, int] = {}

    def add_routing_rule(
        self,
        name: str,
        strategy: RoutingStrategy,
        regions: list[str],
        weights: dict[str, float] | None = None,
        conditions: dict[str, Any] | None = None,
        priority: int = 100,
    ) -> RoutingRule:
        """
        Add a routing rule.

        Args:
            name: Rule name
            strategy: Routing strategy
            regions: Regions to route to
            weights: Weights for weighted routing
            conditions: Conditions for rule matching
            priority: Rule priority (lower = higher priority)

        Returns:
            RoutingRule
        """
        rule = RoutingRule(
            name=name,
            strategy=strategy,
            regions=regions,
            weights=weights or {},
            conditions=conditions or {},
            priority=priority,
        )
        self.rules[rule.rule_id] = rule
        self._round_robin_index[rule.rule_id] = 0

        logger.info(f"Routing rule added: {name} ({strategy.value})")
        return rule

    def route_request(
        self,
        rule_id: str | None = None,
        client_location: str | None = None,
        sovereignty: DataSovereignty = DataSovereignty.NONE,
    ) -> Region | None:
        """
        Route a request to a region.

        Args:
            rule_id: Specific rule to use (or default)
            client_location: Client's location for geographic routing
            sovereignty: Data sovereignty requirements

        Returns:
            Selected Region or None
        """
        # Get applicable regions
        if sovereignty != DataSovereignty.NONE:
            regions = self.registry.get_regions_by_sovereignty(sovereignty)
        else:
            regions = self.registry.get_healthy_regions()

        if not regions:
            return None

        # Get rule
        rule = None
        if rule_id and rule_id in self.rules:
            rule = self.rules[rule_id]
        else:
            # Get highest priority enabled rule
            enabled_rules = [r for r in self.rules.values() if r.enabled]
            if enabled_rules:
                rule = min(enabled_rules, key=lambda r: r.priority)

        if not rule:
            # Default: return primary or first healthy (respecting sovereignty filter)
            primary = self.registry.get_primary_region()
            if (
                primary
                and primary.status == RegionStatus.HEALTHY
                and primary in regions  # Ensure primary matches sovereignty filter
            ):
                return primary
            return regions[0] if regions else None

        # Filter regions by rule
        rule_regions = [r for r in regions if r.region_id in rule.regions]
        if not rule_regions:
            rule_regions = regions

        # Apply strategy
        return self._apply_strategy(rule, rule_regions, client_location)

    def _apply_strategy(
        self,
        rule: RoutingRule,
        regions: list[Region],
        client_location: str | None,
    ) -> Region | None:
        """Apply routing strategy to select region."""
        if not regions:
            return None

        strategy_handlers = {
            RoutingStrategy.LATENCY: self._strategy_latency,
            RoutingStrategy.ROUND_ROBIN: self._strategy_round_robin,
            RoutingStrategy.WEIGHTED: self._strategy_weighted,
            RoutingStrategy.FAILOVER: self._strategy_failover,
            RoutingStrategy.GEOGRAPHIC: self._strategy_geographic,
        }

        handler = strategy_handlers.get(rule.strategy, self._strategy_geographic)
        return handler(rule, regions, client_location)

    def _strategy_latency(
        self,
        rule: RoutingRule,
        regions: list[Region],
        client_location: str | None,
    ) -> Region:
        """Select lowest latency region."""
        latencies = {
            r.region_id: self.health_monitor.get_average_latency(r.region_id)
            for r in regions
        }
        best_id = min(latencies, key=lambda k: latencies[k])
        return next((r for r in regions if r.region_id == best_id), regions[0])

    def _strategy_round_robin(
        self,
        rule: RoutingRule,
        regions: list[Region],
        client_location: str | None,
    ) -> Region:
        """Round robin selection."""
        idx = self._round_robin_index.get(rule.rule_id, 0)
        selected = regions[idx % len(regions)]
        self._round_robin_index[rule.rule_id] = idx + 1
        return selected

    def _strategy_weighted(
        self,
        rule: RoutingRule,
        regions: list[Region],
        client_location: str | None,
    ) -> Region:
        """Weighted random selection."""
        if not rule.weights:
            return random.choice(regions)

        total_weight = sum(
            rule.weights.get(r.region_id, r.capacity_weight) for r in regions
        )
        rand = random.uniform(0, total_weight)
        cumulative: float = 0.0
        for region in regions:
            cumulative += rule.weights.get(region.region_id, region.capacity_weight)
            if rand <= cumulative:
                return region
        return regions[-1]

    def _strategy_failover(
        self,
        rule: RoutingRule,
        regions: list[Region],
        client_location: str | None,
    ) -> Region | None:
        """Primary with fallback (respecting filtered regions)."""
        region_ids_in_scope = {r.region_id for r in regions}
        for region_id in rule.regions:
            if region_id not in region_ids_in_scope:
                continue
            failover_region = self.registry.get_region(region_id)
            if failover_region and failover_region.status == RegionStatus.HEALTHY:
                return failover_region
        return regions[0] if regions else None

    def _strategy_geographic(
        self,
        rule: RoutingRule,
        regions: list[Region],
        client_location: str | None,
    ) -> Region:
        """Select by location match or first available."""
        if client_location:
            for region in regions:
                if client_location.lower() in region.location.lower():
                    return region
        return regions[0]

    def get_routing_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules.values() if r.enabled),
            "rules_by_strategy": {
                strategy.value: sum(
                    1 for r in self.rules.values() if r.strategy == strategy
                )
                for strategy in RoutingStrategy
            },
        }


# =============================================================================
# Multi-Region Deployment Manager
# =============================================================================


class MultiRegionDeployment:
    """
    Central manager for multi-region deployments.

    Integrates all multi-region components:
    - Region Registry
    - Health Monitoring
    - Replication
    - Failover
    - Traffic Routing
    """

    def __init__(self, organization_name: str = "WarmLogic"):
        self.organization_name = organization_name
        self.registry = RegionRegistry()
        self.health_monitor = HealthMonitor(self.registry)
        self.replication = ReplicationManager(self.registry)
        self.failover = FailoverManager(self.registry, self.health_monitor)
        self.router = TrafficRouter(self.registry, self.health_monitor)

        self._initialized = False

    def initialize(self) -> bool:
        """Initialize multi-region deployment."""
        self._initialized = True
        logger.info(f"Multi-region deployment initialized for {self.organization_name}")
        return True

    def setup_standard_regions(self) -> list[Region]:
        """
        Set up standard multi-region deployment.

        Creates regions in US, EU, and APAC.
        """
        regions = []

        # US East (Primary)
        regions.append(
            self.registry.register_region(
                region_id="us-east-1",
                name="US East",
                location="Virginia, USA",
                cloud_provider="aws",
                endpoint="https://us-east-1.github.com/espressolee/warmlogic-rust-core-artifact",
                availability_zones=["us-east-1a", "us-east-1b", "us-east-1c"],
                is_primary=True,
                capacity_weight=1.0,
                data_sovereignty=DataSovereignty.US,
            )
        )

        # US West
        regions.append(
            self.registry.register_region(
                region_id="us-west-2",
                name="US West",
                location="Oregon, USA",
                cloud_provider="aws",
                endpoint="https://us-west-2.github.com/espressolee/warmlogic-rust-core-artifact",
                availability_zones=["us-west-2a", "us-west-2b"],
                capacity_weight=0.8,
                data_sovereignty=DataSovereignty.US,
            )
        )

        # EU West
        regions.append(
            self.registry.register_region(
                region_id="eu-west-1",
                name="EU West",
                location="Ireland, EU",
                cloud_provider="aws",
                endpoint="https://eu-west-1.github.com/espressolee/warmlogic-rust-core-artifact",
                availability_zones=["eu-west-1a", "eu-west-1b", "eu-west-1c"],
                capacity_weight=1.0,
                data_sovereignty=DataSovereignty.EU,
            )
        )

        # APAC
        regions.append(
            self.registry.register_region(
                region_id="ap-northeast-1",
                name="APAC Tokyo",
                location="Tokyo, Japan",
                cloud_provider="aws",
                endpoint="https://ap-northeast-1.github.com/espressolee/warmlogic-rust-core-artifact",
                availability_zones=["ap-northeast-1a", "ap-northeast-1b"],
                capacity_weight=0.7,
                data_sovereignty=DataSovereignty.APAC,
            )
        )

        # Set up replication from primary
        self.replication.create_replication(
            source_region="us-east-1",
            target_regions=["us-west-2", "eu-west-1", "ap-northeast-1"],
            mode=ReplicationMode.ASYNC,
        )

        # Set up routing
        self.router.add_routing_rule(
            name="default-latency",
            strategy=RoutingStrategy.LATENCY,
            regions=["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"],
            priority=100,
        )

        self.router.add_routing_rule(
            name="failover",
            strategy=RoutingStrategy.FAILOVER,
            regions=["us-east-1", "us-west-2", "eu-west-1"],
            priority=50,
        )

        return regions

    def route_request(
        self,
        client_location: str | None = None,
        sovereignty: DataSovereignty = DataSovereignty.NONE,
    ) -> Region | None:
        """Route a request to the best region."""
        return self.router.route_request(
            client_location=client_location,
            sovereignty=sovereignty,
        )

    def get_deployment_status(self) -> dict[str, Any]:
        """Get comprehensive deployment status."""
        health_summary = self.health_monitor.get_health_summary()
        replication_health = self.replication.get_all_replication_health()
        failover_metrics = self.failover.get_failover_metrics()
        routing_stats = self.router.get_routing_stats()

        return {
            "organization": self.organization_name,
            "initialized": self._initialized,
            "regions": {
                "total": len(self.registry.regions),
                "primary": self.registry._primary_region,
                "by_status": {
                    status.value: sum(
                        1 for r in self.registry.regions.values() if r.status == status
                    )
                    for status in RegionStatus
                },
            },
            "health": health_summary,
            "replication": replication_health,
            "failover": failover_metrics,
            "routing": routing_stats,
            "report_time": datetime.utcnow().isoformat(),
        }

    def check_global_health(self) -> bool:
        """Check if global deployment is healthy."""
        summary = self.health_monitor.get_health_summary()
        return bool(summary["healthy"] > 0 and summary["unhealthy"] == 0)
