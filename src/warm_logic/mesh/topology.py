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
Network Topology
Defines the geographic simulation rules for the Global Mesh.
"""

from typing import Dict


class NetworkTopology:
    _instance = None

    # Regions
    US_EAST = "US-EAST"
    EU_WEST = "EU-WEST"
    AP_NORTH = "AP-NORTH"

    # Latency Matrix (ms)
    # Source -> {Target: Latency}
    LATENCY_MATRIX: Dict[str, Dict[str, int]] = {
        US_EAST: {US_EAST: 5, EU_WEST: 100, AP_NORTH: 200},
        EU_WEST: {US_EAST: 100, EU_WEST: 5, AP_NORTH: 250},
        AP_NORTH: {US_EAST: 200, EU_WEST: 250, AP_NORTH: 5},
    }

    # Node ID to Region Mapping (Production Inventory)
    _node_region_cache: Dict[bytes, str] = {}

    local_region: str

    def __new__(cls) -> "NetworkTopology":
        if cls._instance is None:
            cls._instance = super(NetworkTopology, cls).__new__(cls)
            import os

            # Enforce explicit region configuration
            cls._instance.local_region = os.environ.get("SOVEREIGN_REGION", "UNKNOWN")
            if cls._instance.local_region == "UNKNOWN":
                print(" [Topology] SOVEREIGN_REGION not set. Defaulting to UNKNOWN.")
        return cls._instance

    @classmethod
    def register_node(cls, node_id: bytes, region: str) -> None:
        """Register a node's region for simulation."""
        if region not in cls.LATENCY_MATRIX:
            raise ValueError(f"Unknown region: {region}")
        cls._node_region_cache[node_id] = region

    @classmethod
    def get_region_for_id(cls, node_id: bytes) -> str:
        """Determines the region for a node ID. Simulation fallback uses port mapping."""
        return cls._node_region_cache.get(node_id, cls.US_EAST)

    @classmethod
    def set_local_region(cls, region: str) -> None:
        instance = cls()
        if region not in cls.LATENCY_MATRIX:
            raise ValueError(f"Unknown region: {region}")
        instance.local_region = region
        print(f"[Topology] Local Region set to: {region}")

    @classmethod
    def get_latency_between_nodes(cls, id_a: bytes, id_b: bytes) -> int:
        """Estimate latency between two arbitrary nodes."""
        reg_a = cls.get_region_for_id(id_a)
        reg_b = cls.get_region_for_id(id_b)
        return cls.get_latency_between_regions(reg_a, reg_b)

    @classmethod
    def get_latency_between_regions(cls, reg_a: str, reg_b: str) -> int:
        """Lookup latency between two regions."""
        return cls.LATENCY_MATRIX.get(reg_a, {}).get(reg_b, 0)

    @classmethod
    def get_latency(cls, id_a: bytes, id_b: bytes) -> int:
        """Alias for get_latency_between_nodes."""
        return cls.get_latency_between_nodes(id_a, id_b)
