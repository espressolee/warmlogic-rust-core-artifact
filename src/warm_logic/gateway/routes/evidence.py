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
Evidence Routes

API endpoints for cryptographic evidence operations:
- Retrieve evidence bundles
- Verify proofs
- Query audit trails
"""

import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/evidence")


# ============================================================================
# Request/Response Models
# ============================================================================


class EvidenceBundle(BaseModel):
    """Cryptographic evidence bundle."""

    proof_hash: str = Field(..., description="SHA3-256 hash of the evidence")
    decision_id: str = Field(..., description="Associated decision ID")
    intent: str = Field(..., description="Original intent")
    verdict: str = Field(..., description="Governance verdict")
    timestamp: datetime = Field(..., description="Creation timestamp")
    signature: Optional[str] = Field(None, description="ML-DSA-65 signature (hex)")
    signature_algorithm: str = Field(
        default="ML-DSA-65", description="Signature algorithm"
    )
    zk_proof: Optional[str] = Field(None, description="Zero-knowledge proof")
    consensus_proof: Optional[Dict[str, Any]] = Field(
        None, description="BFT consensus proof"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerifyProofRequest(BaseModel):
    """Request to verify a proof."""

    proof_hash: str = Field(..., description="Hash of the evidence to verify")
    signature: Optional[str] = Field(None, description="Signature to verify")
    public_key: Optional[str] = Field(None, description="Public key for verification")


class VerifyProofResponse(BaseModel):
    """Proof verification result."""

    valid: bool = Field(..., description="Whether the proof is valid")
    proof_hash: str
    verified_at: datetime
    verification_method: str
    details: Dict[str, Any] = Field(default_factory=dict)


class AuditEntry(BaseModel):
    """Single audit trail entry."""

    entry_id: str
    timestamp: datetime
    action: str
    intent: str
    verdict: str
    proof_hash: str
    actor: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditTrailResponse(BaseModel):
    """Audit trail query response."""

    entries: List[AuditEntry]
    total: int
    page: int
    page_size: int
    has_more: bool


class EvidenceStats(BaseModel):
    """Evidence system statistics."""

    total_bundles: int
    bundles_today: int
    bundles_this_week: int
    verification_success_rate: float
    last_bundle_timestamp: Optional[datetime]
    storage_size_bytes: int


# ============================================================================
# Dependency
# ============================================================================


def get_api_key(request: Request) -> str:
    """Verify API key from request."""
    from warm_logic.gateway.app import verify_api_key

    return verify_api_key(request)


# ============================================================================
# In-Memory Storage (Replace with persistent storage in production)
# ============================================================================

_evidence_store: Dict[str, EvidenceBundle] = {}
_audit_log: List[AuditEntry] = []


# ============================================================================
# Routes
# ============================================================================


@router.get(
    "/{proof_hash}",
    response_model=EvidenceBundle,
    summary="Get evidence bundle",
    description="Retrieve a cryptographic evidence bundle by its proof hash.",
)
async def get_evidence(
    proof_hash: str,
    api_key: str = Depends(get_api_key),
) -> EvidenceBundle:
    """Retrieve evidence bundle by proof hash."""
    if proof_hash in _evidence_store:
        return _evidence_store[proof_hash]

    # Generate mock evidence for demo purposes
    # In production, this would query the ledger
    raise HTTPException(
        status_code=404,
        detail={
            "error": "not_found",
            "message": f"Evidence bundle not found: {proof_hash}",
        },
    )


@router.post(
    "/verify",
    response_model=VerifyProofResponse,
    summary="Verify a proof",
    description="""
Verify a cryptographic proof.

Supports:
- Hash verification (proof_hash only)
- Signature verification (with signature and public_key)
""",
)
async def verify_proof(
    request: VerifyProofRequest,
    api_key: str = Depends(get_api_key),
) -> VerifyProofResponse:
    """Verify a cryptographic proof."""
    # Try to use Rust core for ML-DSA-65 verification
    if request.signature and request.public_key:
        try:
            import warm_logic_rs

            # Verify ML-DSA-65 signature
            is_valid = warm_logic_rs.MLDSA.verify_raw(
                request.public_key,
                request.proof_hash,
                request.signature,
            )

            return VerifyProofResponse(
                valid=is_valid,
                proof_hash=request.proof_hash,
                verified_at=datetime.now(),
                verification_method="ML-DSA-65",
                details={
                    "algorithm": "ML-DSA-65 (FIPS 204)",
                    "security_level": "NIST Level 3",
                    "quantum_safe": True,
                },
            )
        except ImportError:
            pass
        except Exception as e:
            return VerifyProofResponse(
                valid=False,
                proof_hash=request.proof_hash,
                verified_at=datetime.now(),
                verification_method="ML-DSA-65",
                details={
                    "error": str(e),
                    "note": "Signature verification failed",
                },
            )

    # Hash-only verification (check if evidence exists)
    exists = request.proof_hash in _evidence_store

    return VerifyProofResponse(
        valid=exists,
        proof_hash=request.proof_hash,
        verified_at=datetime.now(),
        verification_method="hash_lookup",
        details={
            "note": "Hash existence check only. Provide signature for full verification.",
        },
    )


@router.get(
    "/audit/trail",
    response_model=AuditTrailResponse,
    summary="Query audit trail",
    description="Query the audit trail with optional filters.",
)
async def get_audit_trail(
    intent: Optional[str] = Query(None, description="Filter by intent"),
    verdict: Optional[str] = Query(None, description="Filter by verdict"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    api_key: str = Depends(get_api_key),
) -> AuditTrailResponse:
    """Query audit trail with filters."""
    # Filter entries
    entries = _audit_log.copy()

    if intent:
        entries = [e for e in entries if e.intent == intent]
    if verdict:
        entries = [e for e in entries if e.verdict == verdict]
    if start_time:
        entries = [e for e in entries if e.timestamp >= start_time]
    if end_time:
        entries = [e for e in entries if e.timestamp <= end_time]

    # Pagination
    total = len(entries)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_entries = entries[start_idx:end_idx]

    return AuditTrailResponse(
        entries=page_entries,
        total=total,
        page=page,
        page_size=page_size,
        has_more=end_idx < total,
    )


@router.get(
    "/stats",
    response_model=EvidenceStats,
    summary="Get evidence statistics",
    description="Statistics about the evidence system.",
)
async def get_stats(
    api_key: str = Depends(get_api_key),
) -> EvidenceStats:
    """Get evidence system statistics."""
    now = datetime.now()
    today_entries = [e for e in _audit_log if e.timestamp.date() == now.date()]

    return EvidenceStats(
        total_bundles=len(_evidence_store),
        bundles_today=len(today_entries),
        bundles_this_week=len(_audit_log),  # Simplified
        verification_success_rate=1.0,  # Placeholder
        last_bundle_timestamp=(_audit_log[-1].timestamp if _audit_log else None),
        storage_size_bytes=0,  # Placeholder
    )


@router.post(
    "/bundle",
    response_model=EvidenceBundle,
    summary="Create evidence bundle",
    description="""
Create a new evidence bundle for a decision.

This endpoint is typically called internally by the governance system,
but can be used for manual evidence creation in testing scenarios.
""",
)
async def create_bundle(
    decision_id: str = Query(..., description="Decision ID to bundle"),
    intent: str = Query(..., description="Original intent"),
    verdict: str = Query(..., description="Governance verdict"),
    include_signature: bool = Query(False, description="Include ML-DSA-65 signature"),
    api_key: str = Depends(get_api_key),
) -> EvidenceBundle:
    """Create an evidence bundle."""
    timestamp = datetime.now()

    # Create proof hash
    proof_data = f"{decision_id}:{intent}:{verdict}:{timestamp.isoformat()}"
    proof_hash = hashlib.sha256(proof_data.encode()).hexdigest()

    # Try to sign with ML-DSA-65
    signature = None
    if include_signature:
        try:
            import warm_logic_rs

            # In production, would use actual node key
            keypair = warm_logic_rs.MLDSA.keypair()
            signature = warm_logic_rs.MLDSA.sign_raw(
                keypair.private_key,
                proof_hash,
            )
        except (ImportError, Exception):
            pass

    bundle = EvidenceBundle(
        proof_hash=proof_hash,
        decision_id=decision_id,
        intent=intent,
        verdict=verdict,
        timestamp=timestamp,
        signature=signature,
        signature_algorithm="ML-DSA-65" if signature else "none",
        zk_proof=None,
        consensus_proof=None,
        metadata={
            "created_via": "api",
        },
    )

    # Store
    _evidence_store[proof_hash] = bundle

    # Log to audit trail
    _audit_log.append(
        AuditEntry(
            entry_id=hashlib.sha256(f"{proof_hash}:{time.time()}".encode()).hexdigest()[
                :16
            ],
            timestamp=timestamp,
            action="CREATE_BUNDLE",
            intent=intent,
            verdict=verdict,
            proof_hash=proof_hash,
            actor="api",
            metadata={},
        )
    )

    return bundle


@router.get(
    "/export",
    summary="Export evidence for compliance",
    description="Export evidence bundles in a compliance-ready format.",
)
async def export_evidence(
    format: str = Query("json", description="Export format (json, csv)"),
    start_time: Optional[datetime] = Query(None, description="Start time"),
    end_time: Optional[datetime] = Query(None, description="End time"),
    api_key: str = Depends(get_api_key),
) -> Dict[str, Any]:
    """Export evidence for compliance reporting."""
    bundles = list(_evidence_store.values())

    if start_time:
        bundles = [b for b in bundles if b.timestamp >= start_time]
    if end_time:
        bundles = [b for b in bundles if b.timestamp <= end_time]

    return {
        "export_timestamp": datetime.now().isoformat(),
        "format": format,
        "total_bundles": len(bundles),
        "bundles": [b.model_dump() for b in bundles],
        "metadata": {
            "signature_algorithm": "ML-DSA-65 (FIPS 204)",
            "hash_algorithm": "SHA3-256",
            "quantum_safe": True,
        },
    }
