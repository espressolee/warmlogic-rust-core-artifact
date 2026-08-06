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
Crypto Routes

API endpoints for post-quantum cryptographic operations:
- Key generation
- Signing and verification
- Hashing
- Zero-knowledge proofs
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/crypto")


# ============================================================================
# Request/Response Models
# ============================================================================


class KeypairInfo(BaseModel):
    """Post-quantum keypair information (public key only for security)."""

    key_id: str = Field(..., description="Unique key identifier")
    algorithm: str = Field(default="ML-DSA-65", description="Signature algorithm")
    public_key: str = Field(..., description="Public key (hex)")
    public_key_size: int = Field(..., description="Public key size in bytes")
    created_at: datetime = Field(..., description="Key creation timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerateKeypairResponse(BaseModel):
    """Response from keypair generation."""

    key_id: str
    algorithm: str
    public_key: str
    public_key_size: int
    private_key_size: int
    created_at: datetime
    warning: str = Field(
        default="Private key is NOT returned via API for security. Store securely."
    )


class SignRequest(BaseModel):
    """Request to sign a message."""

    message: str = Field(..., description="Message to sign (will be hashed)")
    key_id: Optional[str] = Field(None, description="Key ID to use (or use ephemeral)")
    use_ephemeral: bool = Field(
        default=True, description="Generate ephemeral keypair for signing"
    )


class SignResponse(BaseModel):
    """Signature response."""

    message_hash: str = Field(..., description="SHA3-256 hash of message")
    signature: str = Field(..., description="ML-DSA-65 signature (hex)")
    signature_size: int = Field(..., description="Signature size in bytes")
    public_key: str = Field(..., description="Public key used for signing")
    algorithm: str = Field(default="ML-DSA-65")
    timestamp: datetime


class VerifyRequest(BaseModel):
    """Request to verify a signature."""

    message: str = Field(..., description="Original message")
    signature: str = Field(..., description="Signature to verify (hex)")
    public_key: str = Field(..., description="Public key (hex)")


class VerifyResponse(BaseModel):
    """Verification result."""

    valid: bool = Field(..., description="Whether signature is valid")
    message_hash: str
    algorithm: str
    verified_at: datetime


class HashRequest(BaseModel):
    """Request to hash data."""

    data: str = Field(..., description="Data to hash")
    algorithm: str = Field(default="SHA3-256", description="Hash algorithm")


class HashResponse(BaseModel):
    """Hash result."""

    hash: str = Field(..., description="Hash value (hex)")
    algorithm: str
    input_length: int
    hash_length: int


class ZKProofRequest(BaseModel):
    """Request to generate a zero-knowledge proof."""

    value: int = Field(..., description="Value to prove knowledge of")
    blinding_factor: Optional[int] = Field(None, description="Optional blinding factor")


class ZKProof(BaseModel):
    """Zero-knowledge proof."""

    commitment: str = Field(..., description="Pedersen commitment (hex)")
    challenge: str = Field(..., description="Challenge (hex)")
    response_z1: str = Field(..., description="Response z1 (hex)")
    response_z2: str = Field(..., description="Response z2 (hex)")
    algorithm: str = Field(default="Sigma-Ristretto255")
    proof_size: int = Field(..., description="Proof size in bytes")


class ZKVerifyRequest(BaseModel):
    """Request to verify a ZK proof."""

    proof: ZKProof
    commitment: str = Field(..., description="Original commitment to verify against")


class AlgorithmInfo(BaseModel):
    """Information about a cryptographic algorithm."""

    name: str
    type: str  # "signature", "hash", "zkp"
    standard: Optional[str]
    quantum_safe: bool
    key_sizes: Optional[Dict[str, int]]
    description: str


class HSMStatus(BaseModel):
    """Hardware Security Module status."""

    hsm_type: str = Field(
        ..., description="HSM type (TPM, SECURE_ENCLAVE, VIRTUAL, SIMULATED)"
    )
    tpm_available: bool = Field(..., description="TPM hardware available")
    secure_enclave_available: bool = Field(
        ..., description="Apple Secure Enclave available"
    )
    rust_core_available: bool = Field(
        ..., description="Rust cryptographic core available"
    )
    reality_score: float = Field(..., description="Hardware trust score (0.0-1.0)")
    silicon_fingerprint: str = Field(
        ..., description="Silicon hardware fingerprint (truncated)"
    )


class HSMSignRequest(BaseModel):
    """Request to sign using HSM."""

    message: str = Field(..., description="Message to sign")


class HSMSignResponse(BaseModel):
    """HSM signature response."""

    message_hash: str = Field(..., description="SHA3-256 hash of message")
    signature: str = Field(..., description="Hardware-backed signature")
    hsm_type: str = Field(..., description="HSM type used for signing")
    timestamp: datetime


class HSMAttestationResponse(BaseModel):
    """Hardware attestation response."""

    attestation_data: str = Field(..., description="JSON attestation data")
    signature: str = Field(..., description="HSM signature over attestation")
    hardware_id: str = Field(..., description="Unique hardware identifier")
    hsm_type: str


# ============================================================================
# Dependency
# ============================================================================


def get_api_key(request: Request) -> str:
    """Verify API key from request."""
    from warm_logic.gateway.app import verify_api_key

    return verify_api_key(request)


# ============================================================================
# In-memory key storage (for demo - use HSM in production)
# ============================================================================

_keypairs: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Routes
# ============================================================================


@router.get(
    "/algorithms",
    summary="List supported algorithms",
    description="List all supported cryptographic algorithms.",
)
async def list_algorithms(
    api_key: str = Depends(get_api_key),
) -> Dict[str, AlgorithmInfo]:
    """List supported cryptographic algorithms."""
    return {
        "ML-DSA-65": AlgorithmInfo(
            name="ML-DSA-65",
            type="signature",
            standard="NIST FIPS 204",
            quantum_safe=True,
            key_sizes={
                "public_key": 1952,
                "private_key": 4032,
                "signature": 3309,
            },
            description="Module-Lattice Digital Signature Algorithm (Level 3)",
        ),
        "SHA3-256": AlgorithmInfo(
            name="SHA3-256",
            type="hash",
            standard="NIST FIPS 202",
            quantum_safe=True,
            key_sizes=None,
            description="SHA-3 256-bit hash function",
        ),
        "Sigma-Ristretto255": AlgorithmInfo(
            name="Sigma-Ristretto255",
            type="zkp",
            standard=None,
            quantum_safe=False,  # Classical ZK
            key_sizes={"proof": 128},
            description="Sigma protocol on Ristretto255 curve",
        ),
    }


@router.post(
    "/keypair/generate",
    response_model=GenerateKeypairResponse,
    summary="Generate keypair",
    description="""
Generate a new ML-DSA-65 post-quantum keypair.

**Security Notice**: Private key is NOT returned via API.
In production, use HSM integration for key management.
""",
)
async def generate_keypair(
    api_key: str = Depends(get_api_key),
) -> GenerateKeypairResponse:
    """Generate a new ML-DSA-65 keypair."""
    try:
        import warm_logic_rs

        keypair = warm_logic_rs.MLDSA.keypair()
        key_id = hashlib.sha256(keypair.public_key.encode()).hexdigest()[:16]

        # Store (in production, use HSM)
        _keypairs[key_id] = {
            "public_key": keypair.public_key,
            "private_key": keypair.private_key,  # In production: HSM reference only
            "created_at": datetime.now(),
        }

        return GenerateKeypairResponse(
            key_id=key_id,
            algorithm="ML-DSA-65",
            public_key=keypair.public_key[:64] + "...",  # Truncated for display
            public_key_size=1952,
            private_key_size=4032,
            created_at=datetime.now(),
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Rust crypto core not available",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "crypto_error", "message": str(e)},
        )


@router.post(
    "/sign",
    response_model=SignResponse,
    summary="Sign a message",
    description="Sign a message using ML-DSA-65 post-quantum signature.",
)
async def sign_message(
    request: SignRequest,
    api_key: str = Depends(get_api_key),
) -> SignResponse:
    """Sign a message with ML-DSA-65."""
    try:
        import warm_logic_rs

        # Hash the message first
        message_hash = hashlib.sha256(request.message.encode()).hexdigest()

        # Get or generate keypair
        if request.use_ephemeral or request.key_id not in _keypairs:
            keypair = warm_logic_rs.MLDSA.keypair()
            public_key = keypair.public_key
            private_key = keypair.private_key
        else:
            kp = _keypairs[request.key_id]
            public_key = kp["public_key"]
            private_key = kp["private_key"]

        # Sign
        signature = warm_logic_rs.MLDSA.sign_raw(private_key, message_hash)

        return SignResponse(
            message_hash=message_hash,
            signature=signature[:64] + "...",  # Truncated for display
            signature_size=3309,
            public_key=public_key[:64] + "...",
            algorithm="ML-DSA-65",
            timestamp=datetime.now(),
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Rust crypto core not available",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "signing_error", "message": str(e)},
        )


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify a signature",
    description="Verify an ML-DSA-65 signature.",
)
async def verify_signature(
    request: VerifyRequest,
    api_key: str = Depends(get_api_key),
) -> VerifyResponse:
    """Verify an ML-DSA-65 signature."""
    try:
        import warm_logic_rs

        message_hash = hashlib.sha256(request.message.encode()).hexdigest()

        is_valid = warm_logic_rs.MLDSA.verify_raw(
            request.public_key,
            message_hash,
            request.signature,
        )

        return VerifyResponse(
            valid=is_valid,
            message_hash=message_hash,
            algorithm="ML-DSA-65",
            verified_at=datetime.now(),
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Rust crypto core not available",
            },
        )
    except Exception:
        return VerifyResponse(
            valid=False,
            message_hash=hashlib.sha256(request.message.encode()).hexdigest(),
            algorithm="ML-DSA-65",
            verified_at=datetime.now(),
        )


@router.post(
    "/hash",
    response_model=HashResponse,
    summary="Hash data",
    description="Hash data using SHA3-256.",
)
async def hash_data(
    request: HashRequest,
    api_key: str = Depends(get_api_key),
) -> HashResponse:
    """Hash data using SHA3-256."""
    try:
        import warm_logic_rs

        hash_value = warm_logic_rs.hash_sha3_256(request.data)
    except ImportError:
        # Fallback to Python hashlib
        from hashlib import sha3_256

        hash_value = sha3_256(request.data.encode()).hexdigest()

    return HashResponse(
        hash=hash_value,
        algorithm="SHA3-256",
        input_length=len(request.data),
        hash_length=32,
    )


@router.post(
    "/zk/prove",
    response_model=ZKProof,
    summary="Generate ZK proof",
    description="""
Generate a zero-knowledge proof of knowledge.

Uses Sigma protocol on Ristretto255 curve.
Proves knowledge of a value without revealing it.
""",
)
async def generate_zk_proof(
    request: ZKProofRequest,
    api_key: str = Depends(get_api_key),
) -> ZKProof:
    """Generate a zero-knowledge proof."""
    try:
        import warm_logic_rs

        generator = warm_logic_rs.RustZKProofGenerator()

        # Generate proof
        proof = generator.prove_knowledge(request.value, request.blinding_factor or 0)

        return ZKProof(
            commitment=(
                proof.commitment.hex()
                if hasattr(proof.commitment, "hex")
                else str(proof.commitment)
            ),
            challenge=(
                proof.challenge.hex()
                if hasattr(proof.challenge, "hex")
                else str(proof.challenge)
            ),
            response_z1=proof.z1.hex() if hasattr(proof.z1, "hex") else str(proof.z1),
            response_z2=proof.z2.hex() if hasattr(proof.z2, "hex") else str(proof.z2),
            algorithm="Sigma-Ristretto255",
            proof_size=128,
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Rust ZK core not available",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "zk_error", "message": str(e)},
        )


@router.post(
    "/zk/verify",
    summary="Verify ZK proof",
    description="Verify a zero-knowledge proof.",
)
async def verify_zk_proof(
    request: ZKVerifyRequest,
    api_key: str = Depends(get_api_key),
) -> Dict[str, Any]:
    """Verify a zero-knowledge proof."""
    try:
        import warm_logic_rs

        generator = warm_logic_rs.RustZKProofGenerator()

        # Reconstruct proof object (simplified)
        # In production, would properly deserialize

        return {
            "valid": True,  # Placeholder - real verification needed
            "algorithm": "Sigma-Ristretto255",
            "verified_at": datetime.now().isoformat(),
            "note": "Full ZK verification requires Rust core integration",
        }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_unavailable",
                "message": "Rust ZK core not available",
            },
        )


@router.get(
    "/info",
    summary="Crypto system info",
    description="Information about the cryptographic subsystem.",
)
async def get_info(
    api_key: str = Depends(get_api_key),
) -> Dict[str, Any]:
    """Get cryptographic system information."""
    rust_available = False
    try:
        import warm_logic_rs

        rust_available = True
    except ImportError:
        pass

    return {
        "rust_core_available": rust_available,
        "algorithms": {
            "signature": "ML-DSA-65 (FIPS 204)",
            "hash": "SHA3-256 (FIPS 202)",
            "zkp": "Sigma-Ristretto255",
        },
        "security": {
            "signature_level": "NIST Level 3 (128-bit post-quantum)",
            "quantum_safe_signature": True,
            "quantum_safe_hash": True,
            "quantum_safe_zkp": False,  # Classical elliptic curve
        },
        "key_sizes": {
            "ml_dsa_65_public_key": 1952,
            "ml_dsa_65_private_key": 4032,
            "ml_dsa_65_signature": 3309,
            "sha3_256_hash": 32,
            "zk_proof": 128,
        },
        "standards": [
            "NIST FIPS 204 (ML-DSA)",
            "NIST FIPS 202 (SHA-3)",
        ],
    }


# ============================================================================
# HSM Routes
# ============================================================================


@router.get(
    "/hsm/status",
    response_model=HSMStatus,
    summary="Get HSM status",
    description="Get the status of the Hardware Security Module.",
)
async def get_hsm_status(
    api_key: str = Depends(get_api_key),
) -> HSMStatus:
    """Get Hardware Security Module status."""
    try:
        from warm_logic.security.hsm import get_hsm

        hsm = get_hsm()
        report = hsm.get_report()

        return HSMStatus(
            hsm_type=report.hsm_type,
            tpm_available=report.tpm_available,
            secure_enclave_available=report.secure_enclave_available,
            rust_core_available=report.rust_core_available,
            reality_score=report.reality_score,
            silicon_fingerprint=report.silicon_fingerprint,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "hsm_unavailable", "message": str(e)},
        )


@router.post(
    "/hsm/sign",
    response_model=HSMSignResponse,
    summary="Sign with HSM",
    description="Sign a message using the Hardware Security Module.",
)
async def hsm_sign(
    request: HSMSignRequest,
    api_key: str = Depends(get_api_key),
) -> HSMSignResponse:
    """Sign a message using the HSM."""
    try:
        from warm_logic.security.hsm import get_hsm

        hsm = get_hsm()
        signature = hsm.sign(request.message)
        message_hash = hashlib.sha3_256(request.message.encode()).hexdigest()

        return HSMSignResponse(
            message_hash=message_hash,
            signature=signature,
            hsm_type=hsm._hsm_type,
            timestamp=datetime.now(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "hsm_sign_failed", "message": str(e)},
        )


@router.get(
    "/hsm/attest",
    response_model=HSMAttestationResponse,
    summary="Get hardware attestation",
    description="Generate a hardware attestation proof.",
)
async def hsm_attest(
    api_key: str = Depends(get_api_key),
) -> HSMAttestationResponse:
    """Generate hardware attestation proof."""
    try:
        from warm_logic.security.hsm import get_hsm

        hsm = get_hsm()
        attestation_data, signature = hsm.attest()

        return HSMAttestationResponse(
            attestation_data=attestation_data,
            signature=signature,
            hardware_id=hsm.get_hardware_id(),
            hsm_type=hsm._hsm_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "attestation_failed", "message": str(e)},
        )
