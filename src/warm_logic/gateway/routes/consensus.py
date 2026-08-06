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
Consensus Routes

API endpoints for BFT consensus operations:
- Network status and health
- Validator information
- Vote history
"""

import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/consensus")


# ============================================================================
# Request/Response Models
# ============================================================================


class ValidatorInfo(BaseModel):
    """Information about a BFT validator."""

    node_id: str = Field(..., description="Validator node ID")
    public_key: str = Field(..., description="ML-DSA-65 public key (hex)")
    status: str = Field(
        ..., description="Validator status", examples=["active", "inactive", "slashed"]
    )
    last_vote_round: Optional[int] = Field(None, description="Last round voted in")
    last_seen: Optional[datetime] = Field(None, description="Last activity timestamp")
    stake: int = Field(default=0, description="Staked amount")
    uptime_percent: float = Field(default=100.0, description="Uptime percentage")


class ConsensusStatus(BaseModel):
    """Current consensus network status."""

    current_round: int = Field(..., description="Current BFT round number")
    quorum_size: int = Field(..., description="Required votes for quorum")
    total_validators: int = Field(..., description="Total registered validators")
    active_validators: int = Field(..., description="Currently active validators")
    last_finalized_block: Optional[str] = Field(
        None, description="Last finalized block hash"
    )
    last_finalized_time: Optional[datetime] = Field(
        None, description="Last finalization time"
    )
    network_health: str = Field(
        ...,
        description="Network health status",
        examples=["healthy", "degraded", "critical"],
    )
    byzantine_tolerance: int = Field(..., description="Max tolerable Byzantine nodes")


class Vote(BaseModel):
    """A BFT consensus vote."""

    vote_id: str
    round: int
    block_hash: str
    voter_id: str
    decision: str  # "APPROVE" or "REJECT"
    signature: str
    timestamp: datetime


class VoteHistory(BaseModel):
    """Vote history response."""

    votes: List[Vote]
    total: int
    round: Optional[int]


class NetworkPeer(BaseModel):
    """Information about a network peer."""

    peer_id: str
    address: str
    port: int
    status: str
    latency_ms: Optional[float]
    last_seen: datetime


class NetworkStatus(BaseModel):
    """P2P network status."""

    node_id: str
    peers: List[NetworkPeer]
    total_peers: int
    dht_status: str
    uptime_seconds: float


class ProposeBlockRequest(BaseModel):
    """Request to propose a new block."""

    transactions: List[str] = Field(..., description="Transaction IDs to include")
    parent_hash: Optional[str] = Field(None, description="Parent block hash")


class BlockProposal(BaseModel):
    """A proposed block."""

    block_hash: str
    round: int
    proposer: str
    transactions: List[str]
    timestamp: datetime
    status: str  # "pending", "approved", "rejected"
    votes_received: int
    votes_needed: int


# ============================================================================
# Dependency
# ============================================================================


def get_api_key(request: Request) -> str:
    """Verify API key from request."""
    from warm_logic.gateway.app import verify_api_key

    return verify_api_key(request)


# ============================================================================
# Simulated State (Replace with actual BFT engine integration)
# ============================================================================

_current_round = 1
_validators: Dict[str, ValidatorInfo] = {}
_votes: List[Vote] = []
_start_time = time.time()


def _init_mock_validators():
    """Initialize mock validators for demo."""
    if _validators:
        return

    for i in range(4):
        node_id = hashlib.sha256(f"validator_{i}".encode()).hexdigest()[:16]
        _validators[node_id] = ValidatorInfo(
            node_id=node_id,
            public_key=f"pk_{node_id}",  # Placeholder
            status="active",
            last_vote_round=_current_round - 1,
            last_seen=datetime.now(),
            stake=1000,
            uptime_percent=99.5 - i * 0.5,
        )


# ============================================================================
# Routes
# ============================================================================


@router.get(
    "/status",
    response_model=ConsensusStatus,
    summary="Get consensus status",
    description="Current state of the BFT consensus network.",
)
async def get_status(
    api_key: str = Depends(get_api_key),
) -> ConsensusStatus:
    """Get current consensus status."""
    _init_mock_validators()

    # Try to use Rust BFT engine
    try:
        import warm_logic_rs

        engine = warm_logic_rs.BFTEngine(quorum_size=3)
        quorum_size = 3
    except (ImportError, Exception):
        quorum_size = 3

    active_count = len([v for v in _validators.values() if v.status == "active"])
    total_count = len(_validators)

    # BFT: Can tolerate f failures where N >= 3f + 1
    # For 4 validators: f = 1
    byzantine_tolerance = (total_count - 1) // 3

    return ConsensusStatus(
        current_round=_current_round,
        quorum_size=quorum_size,
        total_validators=total_count,
        active_validators=active_count,
        last_finalized_block=None,
        last_finalized_time=None,
        network_health="healthy" if active_count >= quorum_size else "degraded",
        byzantine_tolerance=byzantine_tolerance,
    )


@router.get(
    "/validators",
    response_model=List[ValidatorInfo],
    summary="List validators",
    description="List all registered BFT validators.",
)
async def list_validators(
    status: Optional[str] = Query(None, description="Filter by status"),
    api_key: str = Depends(get_api_key),
) -> List[ValidatorInfo]:
    """List all validators."""
    _init_mock_validators()

    validators = list(_validators.values())

    if status:
        validators = [v for v in validators if v.status == status]

    return validators


@router.get(
    "/validators/{node_id}",
    response_model=ValidatorInfo,
    summary="Get validator info",
    description="Get information about a specific validator.",
)
async def get_validator(
    node_id: str,
    api_key: str = Depends(get_api_key),
) -> ValidatorInfo:
    """Get validator by node ID."""
    _init_mock_validators()

    if node_id not in _validators:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"Validator not found: {node_id}"},
        )

    return _validators[node_id]


@router.get(
    "/votes",
    response_model=VoteHistory,
    summary="Get vote history",
    description="Query consensus vote history.",
)
async def get_votes(
    round: Optional[int] = Query(None, description="Filter by round"),
    voter_id: Optional[str] = Query(None, description="Filter by voter"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    api_key: str = Depends(get_api_key),
) -> VoteHistory:
    """Get vote history."""
    votes = _votes.copy()

    if round is not None:
        votes = [v for v in votes if v.round == round]
    if voter_id:
        votes = [v for v in votes if v.voter_id == voter_id]

    return VoteHistory(
        votes=votes[:limit],
        total=len(votes),
        round=round,
    )


@router.get(
    "/network",
    response_model=NetworkStatus,
    summary="Get network status",
    description="P2P network and DHT status.",
)
async def get_network(
    api_key: str = Depends(get_api_key),
) -> NetworkStatus:
    """Get P2P network status."""
    # Mock network peers
    peers = [
        NetworkPeer(
            peer_id=hashlib.sha256(f"peer_{i}".encode()).hexdigest()[:16],
            address=f"10.0.0.{i + 1}",
            port=9000 + i,
            status="connected",
            latency_ms=5.0 + i * 2.0,
            last_seen=datetime.now(),
        )
        for i in range(3)
    ]

    return NetworkStatus(
        node_id=hashlib.sha256(b"local_node").hexdigest()[:16],
        peers=peers,
        total_peers=len(peers),
        dht_status="running",
        uptime_seconds=time.time() - _start_time,
    )


@router.get(
    "/quorum",
    summary="Get quorum information",
    description="Detailed quorum requirements and current state.",
)
async def get_quorum(
    api_key: str = Depends(get_api_key),
) -> Dict[str, Any]:
    """Get quorum information."""
    _init_mock_validators()

    total = len(_validators)
    active = len([v for v in _validators.values() if v.status == "active"])

    # Quorum = floor(2N/3) + 1
    quorum_needed = (2 * total) // 3 + 1
    byzantine_tolerance = (total - 1) // 3

    return {
        "total_validators": total,
        "active_validators": active,
        "quorum_needed": quorum_needed,
        "byzantine_tolerance": byzantine_tolerance,
        "formula": "quorum = floor(2N/3) + 1",
        "can_reach_consensus": active >= quorum_needed,
        "safety_threshold": {
            "description": "BFT safety requires N >= 3f + 1 where f = Byzantine nodes",
            "current_n": total,
            "max_f": byzantine_tolerance,
        },
    }


@router.post(
    "/propose",
    response_model=BlockProposal,
    summary="Propose a block",
    description="Propose a new block for consensus (validator only).",
)
async def propose_block(
    request: ProposeBlockRequest,
    api_key: str = Depends(get_api_key),
) -> BlockProposal:
    """Propose a block for consensus."""
    global _current_round

    # Generate block hash
    block_data = f"{_current_round}:{request.transactions}:{time.time()}"
    block_hash = hashlib.sha256(block_data.encode()).hexdigest()

    # Get quorum info
    _init_mock_validators()
    total = len(_validators)
    quorum_needed = (2 * total) // 3 + 1

    proposal = BlockProposal(
        block_hash=block_hash,
        round=_current_round,
        proposer="local_node",
        transactions=request.transactions,
        timestamp=datetime.now(),
        status="pending",
        votes_received=1,  # Self-vote
        votes_needed=quorum_needed,
    )

    _current_round += 1

    return proposal


@router.get(
    "/health",
    summary="Consensus health check",
    description="Quick health check for the consensus layer.",
)
async def health_check(
    api_key: str = Depends(get_api_key),
) -> Dict[str, Any]:
    """Consensus health check."""
    _init_mock_validators()

    active = len([v for v in _validators.values() if v.status == "active"])
    total = len(_validators)
    quorum = (2 * total) // 3 + 1

    return {
        "healthy": active >= quorum,
        "active_validators": active,
        "quorum_needed": quorum,
        "current_round": _current_round,
        "last_check": datetime.now().isoformat(),
    }
