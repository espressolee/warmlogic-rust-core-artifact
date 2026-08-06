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
Galaxy Layer
Manages multi-region federation topology and high-latency bridging.
"""

import logging
from typing import Dict, List, Optional

from warm_logic.kernel.mesh.dht import Contact, SovereignDHT

logger = logging.getLogger("Galaxy")


class DynamicLatencyOracle:
    """
    Dynamic Latency Oracle
    Uses real-time RTT measurements with Exponential Moving Average (EMA).
    """

    def __init__(self) -> None:
        self._rtt_cache: Dict[str, float] = {}  # peer_id_hex -> estimated_ms
        self._alpha: float = 0.2  # EMA smoothing factor

    def record_ping(self, peer_id: bytes, rtt_ms: float) -> None:
        pid = peer_id.hex()
        if pid not in self._rtt_cache:
            self._rtt_cache[pid] = rtt_ms
        else:
            # Apply EMA: New = Alpha * RTT + (1 - Alpha) * Old
            self._rtt_cache[pid] = (self._alpha * rtt_ms) + (
                (1 - self._alpha) * self._rtt_cache[pid]
            )

    def get_estimated_latency(self, peer_id: bytes, default: float = 100.0) -> float:
        return self._rtt_cache.get(peer_id.hex(), default)

    # Static compatibility for initial bootstrap (optional)
    @staticmethod
    def estimate_static(region_a: str, region_b: str) -> float:
        if region_a == region_b:
            return 10.0
        return 1200.0


class GalaxyNode:
    """
    A Sovereign Node with Region Awareness.
    Wraps SovereignDHT to provide location-aware routing context.
    """

    def __init__(
        self,
        node_id: bytes,
        region_id: str,
        address: str,
        port: int,
        public_key: Optional[bytes] = None,
        private_key: Optional[str] = None,
        db_path: str = "sovereign_db",
    ):
        self.region_id = region_id
        self.oracle = DynamicLatencyOracle()

        self.dht = SovereignDHT(
            node_id=node_id,
            address=address,
            port=port,
            public_key=public_key,
            private_key=private_key,
            db_path=db_path,
        )
        self._known_regions: Dict[str, List[Contact]] = {}

    async def start(self) -> None:
        logger.info(
            f"🌌 [Galaxy] Node {self.dht.node_id.hex()[:8]} initializing in region '{self.region_id}'"
        )
        await self.dht.start()

    async def stop(self) -> None:
        await self.dht.stop()

    def is_local(self, other_region_id: str) -> bool:
        return self.region_id == other_region_id

    def register_peer_region(self, contact: Contact, region_id: str) -> None:
        """Manual registration of a peer's region (simulated discovery)."""
        if region_id not in self._known_regions:
            self._known_regions[region_id] = []
        self._known_regions[region_id].append(contact)

    def record_rtt(self, peer_id: bytes, rtt_ms: float) -> None:
        """Feed RTT data to the oracle."""
        self.oracle.record_ping(peer_id, rtt_ms)

    def get_topology_score(
        self, contact: Contact, other_region_id: Optional[str] = None
    ) -> float:
        """
        Returns a routing score. Lower is better (closer).
        """
        # Base XOR distance
        xor_dist = int.from_bytes(contact.node_id, "big") ^ int.from_bytes(
            self.dht.node_id, "big"
        )

        # Dynamic Latency from Oracle
        latency = self.oracle.get_estimated_latency(contact.node_id)

        # If unknown (default 100), try static fallback if region known
        if latency == 100.0 and other_region_id:
            latency = DynamicLatencyOracle.estimate_static(
                self.region_id, other_region_id
            )

        # Normalization (simplified)
        return (xor_dist / (2**256)) * 1000 + latency
