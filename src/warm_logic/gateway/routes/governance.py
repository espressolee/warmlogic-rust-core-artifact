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
Governance Routes

API endpoints for AI governance operations:
- Propose actions for governance evaluation
- Evaluate policies
- Manage governance rules
"""

import hashlib
import time
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/governance")

DEFAULT_ALPHA = 0.5
DEFAULT_BETA = 0.5
DEFAULT_EPSILON_C = 0.2
DEFAULT_TAU_ETHICS = 0.1


def _compute_e_stab(
    epsilon_c: float,
    tau_ethics: float,
    *,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
) -> float:
    return alpha * epsilon_c + beta * (1.0 - tau_ethics)


def _fallback_mode(e_stab: float, tau_ethics: float) -> str:
    if tau_ethics > 0.85:
        return "VETO_LOCK"
    if e_stab < 0.3:
        return "CRITICAL_HALT"
    if e_stab < 0.7:
        return "SUSPICIOUS"
    return "NORMAL"


def _compute_mode_snapshot(
    epsilon_c: float = DEFAULT_EPSILON_C,
    tau_ethics: float = DEFAULT_TAU_ETHICS,
) -> tuple[str, float, float]:
    e_stab = _compute_e_stab(epsilon_c, tau_ethics)
    mode = _fallback_mode(e_stab, tau_ethics)

    try:
        import warm_logic_rs

        loop = warm_logic_rs.ReflectiveLoop()
        mode_decision = loop.compute_mode(
            {"epsilon_c": epsilon_c, "tau_ethics": tau_ethics}
        )
        mode = mode_decision.mode
    except (ImportError, Exception):
        pass

    return mode, e_stab, tau_ethics


# ============================================================================
# Request/Response Models
# ============================================================================


class ProposeActionRequest(BaseModel):
    """Request to propose an action for governance evaluation."""

    intent: str = Field(
        ...,
        description="The intent of the action (e.g., 'execute_trade', 'send_email')",
        examples=["execute_trade", "deploy_model", "send_notification"],
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual data for the action",
        examples=[{"symbol": "AAPL", "quantity": 100, "action": "buy"}],
    )
    require_proof: bool = Field(
        default=False,
        description="Whether to generate a cryptographic proof",
    )
    require_consensus: bool = Field(
        default=False,
        description="Whether to require BFT consensus",
    )


class Decision(BaseModel):
    """Governance decision response."""

    decision_id: str = Field(..., description="Unique decision identifier")
    verdict: str = Field(
        ...,
        description="Decision verdict",
        examples=["ALLOW", "DENY", "PENDING"],
    )
    reason: str = Field(..., description="Explanation for the decision")
    proof_hash: Optional[str] = Field(None, description="SHA3-256 hash of evidence")
    signature: Optional[str] = Field(None, description="ML-DSA-65 signature (hex)")
    timestamp: datetime = Field(..., description="Decision timestamp")
    mode: str = Field(
        ...,
        description="Governance mode at decision time",
        examples=["NORMAL", "SUSPICIOUS", "CRITICAL_HALT", "VETO_LOCK"],
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyRule(BaseModel):
    """A governance policy rule."""

    rule_id: str
    name: str
    description: str
    intent_pattern: str
    conditions: Dict[str, Any]
    action: str  # "ALLOW", "DENY", "REQUIRE_APPROVAL"
    priority: int = 0
    enabled: bool = True


class PolicyListResponse(BaseModel):
    """List of active policies."""

    policies: List[PolicyRule]
    total: int
    active: int


class EvaluatePolicyRequest(BaseModel):
    """Request to evaluate a policy without executing."""

    intent: str
    context: Dict[str, Any] = Field(default_factory=dict)


class EvaluatePolicyResponse(BaseModel):
    """Policy evaluation result."""

    would_allow: bool
    matching_rules: List[str]
    mode: str
    e_stab: float = Field(..., description="Stability score (0.0-1.0)")
    tau_ethics: float = Field(..., description="Ethics tension score (0.0-1.0)")


class GovernanceStatus(BaseModel):
    """Current governance system status."""

    mode: str
    e_stab: float
    tau_ethics: float
    pending_decisions: int
    total_decisions_today: int
    last_veto_lock: Optional[datetime]


# ============================================================================
# Dependency: API Key Verification
# ============================================================================


def get_api_key(request: Request) -> str:
    """Verify API key from request."""
    from warm_logic.gateway.app import verify_api_key

    return verify_api_key(request)


# ============================================================================
# Routes
# ============================================================================


@router.post(
    "/propose",
    response_model=Decision,
    summary="Propose an action for governance",
    description="""
Submit an action proposal for governance evaluation.

The governance kernel evaluates the action against:
- Constitutional policies
- Ethical constraints (tau_ethics)
- Stability thresholds (e_stab)

Returns a decision with optional cryptographic proof.
""",
)
async def propose_action(
    request: ProposeActionRequest,
    api_key: str = Depends(get_api_key),
) -> Decision:
    """Propose an action for governance evaluation."""
    # Generate decision ID
    decision_id = hashlib.sha256(
        f"{request.intent}:{time.time()}:{id(request)}".encode()
    ).hexdigest()[:16]

    # Try to use SDK with Rust Core integration
    try:
        from warm_logic.sdk import SovereignClient

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="SovereignClient is experimental \\(research prototype\\).*",
                category=UserWarning,
            )
            client = SovereignClient()
        sdk_decision = client.propose_action(
            intent=request.intent,
            context=request.context,
            require_proof=request.require_proof,
            require_signature=request.require_proof,  # Sign if proof requested
        )

        return Decision(
            decision_id=decision_id,
            verdict=sdk_decision.verdict,
            reason=sdk_decision.reason,
            proof_hash=sdk_decision.proof_hash,
            signature=sdk_decision.signature,  # ML-DSA-65 signature from Rust Core
            timestamp=sdk_decision.timestamp,
            mode=sdk_decision.mode,  # Kernel mode from ReflectiveLoop
            metadata=sdk_decision.metadata,
        )
    except ImportError:
        pass
    except Exception as e:
        # Log but continue with fallback
        import logging

        logging.getLogger(__name__).warning(f"SDK error: {e}")

    # Fallback: Simple policy evaluation with kernel mode
    mode, e_stab, tau_ethics = _compute_mode_snapshot()

    verdict = "ALLOW"
    reason = "No policy violations detected"

    # Check governance mode first
    if mode == "VETO_LOCK":
        verdict = "DENY"
        reason = "Governance kernel in VETO_LOCK mode - ethics violation detected"
    elif mode == "CRITICAL_HALT":
        verdict = "DENY"
        reason = "Governance kernel in CRITICAL_HALT mode - system instability"

    # Check for blocked intents
    blocked_intents = ["delete_all", "shutdown_system", "bypass_governance"]
    if request.intent in blocked_intents:
        verdict = "DENY"
        reason = f"Intent '{request.intent}' is blocked by constitutional policy"

    # Generate proof hash if requested
    proof_hash = None
    signature = None
    if request.require_proof:
        proof_data = f"{decision_id}:{request.intent}:{verdict}:{time.time()}"
        proof_hash = hashlib.sha256(proof_data.encode()).hexdigest()

        # Try to sign with Rust Core (ML-DSA-65)
        try:
            import warm_logic_rs as rs

            pub, priv = rs.generate_keypair()
            sign_payload = f"{proof_hash}:{verdict}:{mode}:{request.intent}"
            signature = rs.sign(priv, sign_payload)
        except (ImportError, Exception):
            pass  # Signature optional in fallback mode

    return Decision(
        decision_id=decision_id,
        verdict=verdict,
        reason=reason,
        proof_hash=proof_hash,
        signature=signature,
        timestamp=datetime.now(),
        mode=mode,
        metadata={
            "intent": request.intent,
            "context_hash": hashlib.sha256(str(request.context).encode()).hexdigest()[
                :16
            ],
            "e_stab": e_stab,
            "tau_ethics": tau_ethics,
            "fallback": True,
        },
    )


@router.post(
    "/evaluate",
    response_model=EvaluatePolicyResponse,
    summary="Evaluate policy without executing",
    description="Dry-run policy evaluation to check what would happen.",
)
async def evaluate_policy(
    request: EvaluatePolicyRequest,
    api_key: str = Depends(get_api_key),
) -> EvaluatePolicyResponse:
    """Evaluate policy without executing the action."""
    mode, e_stab, tau_ethics = _compute_mode_snapshot()

    # Simple policy matching
    blocked_intents = ["delete_all", "shutdown_system", "bypass_governance"]
    would_allow = request.intent not in blocked_intents
    matching_rules = []

    if request.intent in blocked_intents:
        matching_rules.append("constitutional_block")

    return EvaluatePolicyResponse(
        would_allow=would_allow,
        matching_rules=matching_rules,
        mode=mode,
        e_stab=e_stab,
        tau_ethics=tau_ethics,
    )


@router.get(
    "/policies",
    response_model=PolicyListResponse,
    summary="List governance policies",
    description="Retrieve all active governance policies.",
)
async def list_policies(
    enabled_only: bool = Query(True, description="Only return enabled policies"),
    api_key: str = Depends(get_api_key),
) -> PolicyListResponse:
    """List all governance policies."""
    # Default policies
    policies = [
        PolicyRule(
            rule_id="constitutional_block",
            name="Constitutional Block List",
            description="Blocks dangerous intents",
            intent_pattern="delete_all|shutdown_system|bypass_governance",
            conditions={},
            action="DENY",
            priority=100,
            enabled=True,
        ),
        PolicyRule(
            rule_id="high_value_approval",
            name="High Value Approval",
            description="Requires approval for high-value transactions",
            intent_pattern="execute_trade|transfer_funds",
            conditions={"amount": "> 10000"},
            action="REQUIRE_APPROVAL",
            priority=50,
            enabled=True,
        ),
        PolicyRule(
            rule_id="default_allow",
            name="Default Allow",
            description="Allow all other actions",
            intent_pattern=".*",
            conditions={},
            action="ALLOW",
            priority=0,
            enabled=True,
        ),
    ]

    if enabled_only:
        policies = [p for p in policies if p.enabled]

    return PolicyListResponse(
        policies=policies,
        total=len(policies),
        active=len([p for p in policies if p.enabled]),
    )


@router.get(
    "/status",
    response_model=GovernanceStatus,
    summary="Get governance status",
    description="Current state of the governance system.",
)
async def get_status(
    api_key: str = Depends(get_api_key),
) -> GovernanceStatus:
    """Get current governance system status."""
    mode, e_stab, tau_ethics = _compute_mode_snapshot()

    return GovernanceStatus(
        mode=mode,
        e_stab=e_stab,
        tau_ethics=tau_ethics,
        pending_decisions=0,
        total_decisions_today=0,
        last_veto_lock=None,
    )


@router.get(
    "/modes",
    summary="List governance modes",
    description="Explain available governance modes and their thresholds.",
)
async def list_modes(
    api_key: str = Depends(get_api_key),
) -> Dict[str, Any]:
    """List available governance modes with explanations."""
    return {
        "modes": [
            {
                "name": "NORMAL",
                "description": "Standard operation, all actions permitted",
                "condition": "e_stab >= 0.7 AND tau_ethics <= 0.85",
                "behavior": "Full functionality",
            },
            {
                "name": "SUSPICIOUS",
                "description": "Elevated monitoring, some restrictions",
                "condition": "0.3 <= e_stab < 0.7",
                "behavior": "Enhanced logging, restricted high-risk operations",
            },
            {
                "name": "CRITICAL_HALT",
                "description": "System instability detected",
                "condition": "e_stab < 0.3",
                "behavior": "Pause autonomous operations, require manual override",
            },
            {
                "name": "VETO_LOCK",
                "description": "Ethical constraint violation",
                "condition": "tau_ethics > 0.85",
                "behavior": "Complete system freeze, governance committee required",
            },
        ],
        "formula": {
            "e_stab": "alpha * epsilon_c + beta * (1 - tau_ethics)",
            "alpha": DEFAULT_ALPHA,
            "beta": DEFAULT_BETA,
            "description": "Stability score combining ethical and computational factors",
        },
    }
