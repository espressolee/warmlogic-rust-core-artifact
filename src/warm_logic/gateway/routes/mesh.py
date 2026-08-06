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
Mesh Network Routes

API endpoints for DHT/Kademlia mesh network operations:
- Network health status
- Peer information
- Routing table inspection
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/mesh")

logger = logging.getLogger(__name__)


# ============================================================================
# Response Models
# ============================================================================


class PeerInfo(BaseModel):
    """Information about a network peer."""

    node_id: str = Field(..., description="Node ID (hex)")
    address: str = Field(..., description="IP address")
    port: int = Field(..., description="Port number")
    silicon_id: Optional[str] = Field(None, description="Hardware silicon ID")
    capabilities: Optional[Dict[str, int]] = Field(
        None, description="Node capabilities"
    )


class RoutingTableStatus(BaseModel):
    """Status of the Kademlia routing table."""

    using_rust: bool = Field(
        ..., description="Whether Rust accelerated routing is active"
    )
    bucket_count: int = Field(..., description="Number of k-buckets")
    total_contacts: int = Field(..., description="Total known contacts")
    revoked_nodes: int = Field(..., description="Byzantine revoked nodes count")


class MeshStatus(BaseModel):
    """Overall mesh network status."""

    node_id: str = Field(..., description="Local node ID (hex)")
    address: str = Field(..., description="Local address")
    port: int = Field(..., description="Local port")
    public_address: Optional[str] = Field(
        None, description="NAT-discovered public address"
    )
    public_port: Optional[int] = Field(None, description="NAT-discovered public port")
    silicon_id: str = Field(..., description="Hardware silicon ID")
    routing_table: RoutingTableStatus
    gossip_stats: Dict[str, Any] = Field(
        default_factory=dict, description="Gossip protocol stats"
    )
    rust_dht_available: bool = Field(..., description="Rust DHT core available")


class GossipStats(BaseModel):
    """Gossip protocol statistics."""

    announcements_sent: int = 0
    announcements_received: int = 0
    unique_manifests_seen: int = 0
    verification_failures: int = 0
    peer_count: int = 0
    running: bool = False
    temperature: float = 25.0


# ============================================================================
# Dependency: API Key Verification
# ============================================================================


def get_api_key(request: Request) -> str:
    """Verify API key from request."""
    from warm_logic.gateway.app import verify_api_key

    return verify_api_key(request)


# ============================================================================
# Global DHT instance (lazily initialized)
# ============================================================================

_dht_instance = None


def _get_or_create_dht():
    """Get or create the global DHT instance."""
    global _dht_instance

    if _dht_instance is not None:
        return _dht_instance

    try:
        import hashlib

        import warm_logic_rs as rs

        # Generate node ID from hardware info
        hw_info = rs.get_hardware_info()
        node_id = hashlib.sha3_256(hw_info.encode()).digest()

        from warm_logic.kernel.mesh.dht import SovereignDHT

        _dht_instance = SovereignDHT(
            node_id=node_id,
            address="0.0.0.0",
            port=9000,
        )
        logger.info(f"DHT instance created: {node_id.hex()[:16]}")
        return _dht_instance
    except Exception as e:
        logger.warning(f"Failed to create DHT instance: {e}")
        return None


# ============================================================================
# Routes
# ============================================================================


@router.get(
    "/status",
    response_model=MeshStatus,
    summary="Get mesh network status",
    description="Returns the status of the local DHT node and mesh network.",
)
async def get_mesh_status(api_key: str = Depends(get_api_key)) -> MeshStatus:
    """Get current mesh network status."""
    dht = _get_or_create_dht()

    if dht is None:
        # Return minimal status when DHT not available
        return MeshStatus(
            node_id="not_initialized",
            address="0.0.0.0",
            port=0,
            public_address=None,
            public_port=None,
            silicon_id="UNAVAILABLE",
            routing_table=RoutingTableStatus(
                using_rust=False,
                bucket_count=0,
                total_contacts=0,
                revoked_nodes=0,
            ),
            gossip_stats={},
            rust_dht_available=False,
        )

    # Gather routing table stats
    routing_status = RoutingTableStatus(
        using_rust=dht.routing._use_rust,
        bucket_count=len(dht.routing.buckets),
        total_contacts=sum(len(b.contacts) for b in dht.routing.buckets),
        revoked_nodes=len(dht.routing.revoked_nodes),
    )

    # Gather gossip stats if available
    gossip_stats = {}
    if dht.gossip_agent:
        gossip_stats = dht.gossip_agent.get_stats()

    # Check Rust DHT availability
    rust_available = False
    try:
        import warm_logic_rs as rs

        rust_available = hasattr(rs, "RustDHT")
    except ImportError:
        pass

    return MeshStatus(
        node_id=dht.node_id.hex(),
        address=dht.address,
        port=dht.port,
        public_address=getattr(dht, "public_address", None),
        public_port=getattr(dht, "public_port", None),
        silicon_id=dht.silicon_id,
        routing_table=routing_status,
        gossip_stats=gossip_stats,
        rust_dht_available=rust_available,
    )


@router.get(
    "/peers",
    response_model=List[PeerInfo],
    summary="List known peers",
    description="Returns all known peers in the routing table.",
)
async def list_peers(
    limit: int = 20,
    api_key: str = Depends(get_api_key),
) -> List[PeerInfo]:
    """List known peers in the routing table."""
    dht = _get_or_create_dht()

    if dht is None:
        return []

    contacts = dht.routing.get_all_contacts()[:limit]

    return [
        PeerInfo(
            node_id=c.node_id.hex(),
            address=c.address,
            port=c.port,
            silicon_id=c.silicon_id,
            capabilities=c.capabilities,
        )
        for c in contacts
    ]


@router.get(
    "/neighbors/{target_id}",
    response_model=List[PeerInfo],
    summary="Find neighbors for target",
    description="Find the K closest neighbors to a target node ID.",
)
async def find_neighbors(
    target_id: str,
    count: int = 20,
    api_key: str = Depends(get_api_key),
) -> List[PeerInfo]:
    """Find K closest neighbors to target ID."""
    dht = _get_or_create_dht()

    if dht is None:
        raise HTTPException(status_code=503, detail="DHT not available")

    try:
        target_bytes = bytes.fromhex(target_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target_id hex")

    contacts = dht.routing.find_neighbors(target_bytes, count=count)

    return [
        PeerInfo(
            node_id=c.node_id.hex(),
            address=c.address,
            port=c.port,
            silicon_id=c.silicon_id,
            capabilities=c.capabilities,
        )
        for c in contacts
    ]


@router.get(
    "/gossip",
    response_model=GossipStats,
    summary="Get gossip protocol stats",
    description="Returns statistics from the gossip protocol.",
)
async def get_gossip_stats(api_key: str = Depends(get_api_key)) -> GossipStats:
    """Get gossip protocol statistics."""
    dht = _get_or_create_dht()

    if dht is None or dht.gossip_agent is None:
        return GossipStats()

    stats = dht.gossip_agent.get_stats()
    return GossipStats(**stats)


@router.post(
    "/revoke/{node_id}",
    summary="Revoke a node (BRL)",
    description="Add a node to the Byzantine Revocation List.",
)
async def revoke_node(
    node_id: str,
    api_key: str = Depends(get_api_key),
) -> Dict[str, Any]:
    """Revoke a node and add to BRL."""
    dht = _get_or_create_dht()

    if dht is None:
        raise HTTPException(status_code=503, detail="DHT not available")

    try:
        node_bytes = bytes.fromhex(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node_id hex")

    dht.routing.revoke_node(node_bytes)

    return {
        "status": "revoked",
        "node_id": node_id,
        "revoked_count": len(dht.routing.revoked_nodes),
    }
