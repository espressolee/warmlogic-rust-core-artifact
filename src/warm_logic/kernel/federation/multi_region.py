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
Multi-Region Federation

Geographic distribution with region-aware routing:
- Region-local consensus for low-latency decisions
- Cross-region synchronization with eventual consistency
- Partition tolerance with automatic failover
- Latency-aware request routing
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from warm_logic.kernel.federation.sovereign_federation import (
    FederationConsensus,
    FederationState,
    SovereignFederation,
)
from warm_logic.kernel.federation.state_sync import (
    RegionStateSynchronizer,
)

logger = logging.getLogger("MultiRegion")


class Region(Enum):
    """Geographic regions for federation distribution."""

    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    ASIA_PACIFIC = "asia-pacific"
    ASIA_SOUTH = "asia-south"
    SOVEREIGN_LOCAL = "sovereign-local"  # On-premise


@dataclass
class RegionConfig:
    """Configuration for a region."""

    region: Region
    display_name: str
    primary_endpoint: str
    backup_endpoints: List[str] = field(default_factory=list)
    max_nodes: int = 10
    min_nodes: int = 1
    latency_threshold_ms: int = 100
    is_primary: bool = False
    # Cross-region settings
    sync_interval_sec: int = 30
    sync_batch_size: int = 100


@dataclass
class RegionHealth:
    """Health status of a region."""

    region: Region
    is_healthy: bool
    node_count: int
    active_nodes: int
    avg_latency_ms: float
    last_sync_timestamp: float
    pending_sync_count: int
    partition_detected: bool = False


@dataclass
class CrossRegionSync:
    """Cross-region synchronization state."""

    origin_region: Region
    target_region: Region
    sync_id: str
    decision_ids: List[str]  # Decision IDs to sync
    timestamp: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "pending"  # pending, in_progress, completed, failed


class RegionSelector:
    """
    Selects optimal region for request handling based on:
    - Latency measurements
    - Region health
    - Load balancing
    """

    def __init__(self) -> None:
        self._latencies: Dict[Region, List[float]] = {r: [] for r in Region}
        self._max_samples = 100

    def record_latency(self, region: Region, latency_ms: float) -> None:
        """Record a latency measurement for a region."""
        samples = self._latencies[region]
        samples.append(latency_ms)
        if len(samples) > self._max_samples:
            samples.pop(0)

    def get_avg_latency(self, region: Region) -> float:
        """Get average latency for a region."""
        samples = self._latencies[region]
        if not samples:
            return float("inf")
        return sum(samples) / len(samples)

    def select_region(
        self,
        available_regions: List[Region],
        prefer_local: bool = True,
        local_region: Optional[Region] = None,
    ) -> Optional[Region]:
        """
        Select the optimal region from available regions.

        Args:
            available_regions: List of healthy regions
            prefer_local: Whether to prefer local region if latency is acceptable
            local_region: The local region (if known)

        Returns:
            Best region or None if no regions available
        """
        if not available_regions:
            return None

        # If only one region, return it
        if len(available_regions) == 1:
            return available_regions[0]

        # If prefer local and local region is available and fast enough
        if prefer_local and local_region and local_region in available_regions:
            local_latency = self.get_avg_latency(local_region)
            if local_latency < 100:  # 100ms threshold
                return local_region

        # Sort by latency
        sorted_regions = sorted(
            available_regions, key=lambda r: self.get_avg_latency(r)
        )

        return sorted_regions[0]


class MultiRegionFederation:
    """
    Multi-Region Federation Manager

    Orchestrates sovereign federation across multiple geographic regions
    with support for:
    - Region-local consensus
    - Cross-region synchronization
    - Partition tolerance
    - Automatic failover
    """

    def __init__(
        self,
        local_node_id: str,
        local_region: Region,
        quorum_threshold: float = 0.67,
    ):
        self.local_node_id = local_node_id
        self.local_region = local_region
        self.quorum_threshold = quorum_threshold

        # State
        self.state = FederationState.INITIALIZING
        self._region_configs: Dict[Region, RegionConfig] = {}
        self._region_federations: Dict[Region, SovereignFederation] = {}
        self._region_health: Dict[Region, RegionHealth] = {}
        self._pending_syncs: Dict[str, CrossRegionSync] = {}
        self._region_selector = RegionSelector()
        self._state_sync = RegionStateSynchronizer(
            local_region=local_region.value,
            node_id=local_node_id,
        )

        # Callbacks
        self._on_partition_detected: Optional[Callable[[Region], None]] = None
        self._on_sync_completed: Optional[Callable[[CrossRegionSync], None]] = None

        logger.info(
            f"[MultiRegion] Initialized node {local_node_id} in region {local_region.value}"
        )

    def configure_region(self, config: RegionConfig) -> None:
        """Configure a region for federation."""
        self._region_configs[config.region] = config

        # Initialize health tracking
        self._region_health[config.region] = RegionHealth(
            region=config.region,
            is_healthy=False,
            node_count=0,
            active_nodes=0,
            avg_latency_ms=0.0,
            last_sync_timestamp=0.0,
            pending_sync_count=0,
        )

        logger.info(
            f"[MultiRegion] Configured region: {config.display_name} "
            f"(endpoint: {config.primary_endpoint})"
        )

    def bootstrap_local(self) -> bool:
        """Bootstrap the local region federation."""
        if self.local_region not in self._region_configs:
            logger.error(
                f"[MultiRegion] Local region {self.local_region} not configured"
            )
            return False

        try:
            # Create local federation
            local_fed = SovereignFederation(
                local_node_id=self.local_node_id,
                quorum_threshold=self.quorum_threshold,
            )

            if not local_fed.bootstrap():
                return False

            self._region_federations[self.local_region] = local_fed
            self.state = FederationState.ACTIVE

            # Update health
            health = self._region_health[self.local_region]
            health.is_healthy = True
            health.node_count = 1
            health.active_nodes = 1
            health.last_sync_timestamp = time.time()

            logger.info(
                f"[MultiRegion] Local region {self.local_region.value} bootstrapped"
            )
            return True

        except Exception as e:
            logger.error(f"[MultiRegion] Bootstrap failed: {e}")
            self.state = FederationState.HALTED
            return False

    def connect_region(self, region: Region) -> bool:
        """
        Establish connection to a remote region.

        Returns True if connection successful.
        """
        if region not in self._region_configs:
            logger.error(f"[MultiRegion] Region {region} not configured")
            return False

        # Simulate connection (in production, would establish actual network connection)
        start_time = time.time()

        try:
            # Create remote federation stub
            remote_fed = SovereignFederation(
                local_node_id=f"{self.local_node_id}-proxy-{region.value}",
                quorum_threshold=self.quorum_threshold,
            )

            # Record latency
            latency_ms = (time.time() - start_time) * 1000
            self._region_selector.record_latency(region, latency_ms)

            self._region_federations[region] = remote_fed

            # Update health
            health = self._region_health[region]
            health.is_healthy = True
            health.avg_latency_ms = latency_ms

            logger.info(
                f"[MultiRegion] Connected to region {region.value} "
                f"(latency: {latency_ms:.1f}ms)"
            )
            return True

        except Exception as e:
            logger.error(f"[MultiRegion] Failed to connect to {region}: {e}")
            self._region_health[region].is_healthy = False
            return False

    def get_healthy_regions(self) -> List[Region]:
        """Get list of healthy regions."""
        return [
            region
            for region, health in self._region_health.items()
            if health.is_healthy and not health.partition_detected
        ]

    def select_region_for_request(self) -> Optional[Region]:
        """Select optimal region for handling a request."""
        healthy = self.get_healthy_regions()
        return self._region_selector.select_region(
            healthy, prefer_local=True, local_region=self.local_region
        )

    def propose_decision(
        self,
        decision_data: Dict[str, Any],
        scope: str = "regional",  # "regional" or "global"
    ) -> Optional[FederationConsensus]:
        """
        Propose a governance decision.

        Args:
            decision_data: Decision payload
            scope: "regional" for local-only or "global" for all regions

        Returns:
            FederationConsensus if proposal created
        """
        if self.state != FederationState.ACTIVE:
            logger.error(f"[MultiRegion] Cannot propose in state {self.state}")
            return None

        local_fed = self._region_federations.get(self.local_region)
        if not local_fed:
            return None

        # Add scope metadata
        decision_data["_scope"] = scope
        decision_data["_origin_region"] = self.local_region.value

        consensus = local_fed.propose_decision(decision_data)

        if consensus and scope == "global":
            # Use RegionStateSynchronizer for global decisions
            import json

            payload = json.dumps(decision_data).encode("utf-8")

            # The local consensus already has the proposer's signature (ML-DSA-65)
            signature = consensus.approvals.get(self.local_node_id, "")

            self._state_sync.add_local_decision(
                decision_id=consensus.decision_id, payload=payload, signature=signature
            )
            # Schedule cross-region sync
            self._schedule_global_sync(consensus.decision_id)

        return consensus

    def _schedule_global_sync(self, decision_id: str) -> None:
        """Schedule synchronization of a decision to all regions."""
        for region in self._region_configs:
            if region == self.local_region:
                continue

            # Create sync batch via RegionStateSynchronizer
            batch = self._state_sync.create_sync_batch(
                target_region=region.value, decision_ids=[decision_id]
            )

            sync = CrossRegionSync(
                sync_id=batch.batch_id,
                origin_region=self.local_region,
                target_region=region,
                decision_ids=[decision_id],
                timestamp=time.time(),
            )
            self._pending_syncs[sync.sync_id] = sync
            logger.info(
                f"[MultiRegion] Scheduled global sync {sync.sync_id} to {region.value}"
            )
            # Update health
            self._region_health[region].pending_sync_count += 1

        logger.info(
            f"[MultiRegion] Scheduled global sync for decision {decision_id} "
            f"to {len(self._pending_syncs)} regions"
        )

    def execute_pending_syncs(self) -> int:
        """
        Execute pending cross-region synchronizations.

        Returns number of syncs completed.
        """
        completed = 0

        for sync_id, sync in list(self._pending_syncs.items()):
            if sync.status != "pending":
                continue

            sync.status = "in_progress"

            try:
                target_fed = self._region_federations.get(sync.target_region)
                if not target_fed:
                    continue

                # In production, would actually sync decision data
                # For now, mark as completed
                sync.status = "completed"
                sync.completed_at = time.time()
                completed += 1

                # Update health
                self._region_health[sync.target_region].pending_sync_count -= 1
                self._region_health[sync.target_region].last_sync_timestamp = (
                    time.time()
                )

                if self._on_sync_completed:
                    self._on_sync_completed(sync)

            except Exception as e:
                logger.error(f"[MultiRegion] Sync {sync_id} failed: {e}")
                sync.status = "failed"

        return completed

    def detect_partitions(self) -> List[Region]:
        """
        Detect network partitions.

        Returns list of partitioned regions.
        """
        partitioned = []

        for region, health in self._region_health.items():
            if region == self.local_region:
                continue

            # Check last sync time
            sync_age = time.time() - health.last_sync_timestamp
            config = self._region_configs.get(region)

            if config and sync_age > config.sync_interval_sec * 3:
                # More than 3x sync interval without update = partition
                if not health.partition_detected:
                    health.partition_detected = True
                    partitioned.append(region)

                    if self._on_partition_detected:
                        self._on_partition_detected(region)

                    logger.warning(
                        f"[MultiRegion] Partition detected: {region.value} "
                        f"(last sync: {sync_age:.0f}s ago)"
                    )

        return partitioned

    def heal_partition(self, region: Region) -> bool:
        """
        Attempt to heal a network partition.

        Returns True if partition healed.
        """
        health = self._region_health.get(region)
        if not health or not health.partition_detected:
            return False

        # Try to reconnect
        if self.connect_region(region):
            health.partition_detected = False
            logger.info(f"[MultiRegion] Partition healed: {region.value}")
            return True

        return False

    def get_region_health(self, region: Region) -> Optional[RegionHealth]:
        """Get health status for a region."""
        return self._region_health.get(region)

    def get_all_health(self) -> Dict[Region, RegionHealth]:
        """Get health status for all regions."""
        return dict(self._region_health)

    def set_partition_callback(self, callback: Callable[[Region], None]) -> None:
        """Set callback for partition detection."""
        self._on_partition_detected = callback

    def set_sync_callback(self, callback: Callable[[CrossRegionSync], None]) -> None:
        """Set callback for sync completion."""
        self._on_sync_completed = callback

    def get_state(self) -> Dict[str, Any]:
        """Get current multi-region state summary."""
        return {
            "state": self.state.value,
            "local_node_id": self.local_node_id,
            "local_region": self.local_region.value,
            "configured_regions": len(self._region_configs),
            "connected_regions": len(self._region_federations),
            "healthy_regions": len(self.get_healthy_regions()),
            "pending_syncs": len(
                [s for s in self._pending_syncs.values() if s.status == "pending"]
            ),
            "partitioned_regions": [
                r.value for r, h in self._region_health.items() if h.partition_detected
            ],
        }


def create_default_region_configs() -> List[RegionConfig]:
    """Create default region configurations."""
    return [
        RegionConfig(
            region=Region.US_EAST,
            display_name="US East (Virginia)",
            primary_endpoint="us-east.github.com/espressolee/WarmLogic:8443",
            backup_endpoints=["us-east-2.github.com/espressolee/WarmLogic:8443"],
            is_primary=True,
        ),
        RegionConfig(
            region=Region.US_WEST,
            display_name="US West (Oregon)",
            primary_endpoint="us-west.github.com/espressolee/WarmLogic:8443",
        ),
        RegionConfig(
            region=Region.EU_WEST,
            display_name="EU West (Ireland)",
            primary_endpoint="eu-west.github.com/espressolee/WarmLogic:8443",
        ),
        RegionConfig(
            region=Region.EU_CENTRAL,
            display_name="EU Central (Frankfurt)",
            primary_endpoint="eu-central.github.com/espressolee/WarmLogic:8443",
        ),
        RegionConfig(
            region=Region.ASIA_PACIFIC,
            display_name="Asia Pacific (Tokyo)",
            primary_endpoint="ap-northeast.github.com/espressolee/WarmLogic:8443",
        ),
        RegionConfig(
            region=Region.SOVEREIGN_LOCAL,
            display_name="Sovereign (On-Premise)",
            primary_endpoint="localhost:8443",
            max_nodes=100,
        ),
    ]
