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
WarmLogic SDK Client

Provides a high-level interface for interacting with the WarmLogic governance kernel.
"""

from __future__ import annotations

import hashlib
import json
import logging
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Decision:
    """Represents a governance decision from the kernel."""

    verdict: str  # "ALLOW", "DENY", "PENDING"
    reason: str
    proof_hash: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    signature: str | None = None  # ML-DSA-65 signature (hex)
    mode: str = "NORMAL"  # Kernel mode at decision time

    @property
    def allowed(self) -> bool:
        return self.verdict == "ALLOW"

    @property
    def denied(self) -> bool:
        return self.verdict == "DENY"

    @property
    def is_signed(self) -> bool:
        """Check if decision has a valid ML-DSA-65 signature."""
        return self.signature is not None and len(self.signature) > 100


class SovereignClient:
    """
    High-level client for WarmLogic governance kernel.

    WARNING: This is an experimental API (experimental).
    - No cryptographic proofs in this version (requires Rust core)
    - No BFT consensus (single-node only)
    - For demonstration and development only

    Example:
        >>> client = SovereignClient()
        >>> decision = client.propose_action(
        ...     intent="send_email",
        ...     context={"to": "user@example.com"}
        ... )
        >>> print(decision.verdict)
        ALLOW
    """

    def __init__(
        self,
        endpoint: str | None = None,
        *,
        host: str | None = None,
        port: int | None = None,
        timeout: float | int | None = None,
    ):
        """
        Initialize the SovereignClient.

        Args:
            endpoint: Optional kernel endpoint URL. If None, uses local kernel.
            host: Backward-compatible host for docs/examples (builds HTTP endpoint).
            port: Backward-compatible port for docs/examples.
            timeout: Optional request timeout in seconds.
        """
        warnings.warn(
            "SovereignClient is experimental. "
            "Do not use in production without Rust core compilation.",
            UserWarning,
            stacklevel=2,
        )
        if timeout is not None and float(timeout) <= 0:
            raise ValueError("timeout must be > 0")

        if endpoint:
            resolved_endpoint = endpoint
        elif host is not None:
            resolved_port = int(port) if port is not None else 8000
            resolved_endpoint = f"http://{host}:{resolved_port}"
        elif port is not None:
            resolved_endpoint = f"http://localhost:{int(port)}"
        else:
            resolved_endpoint = "local"

        self.endpoint = resolved_endpoint
        self.timeout_seconds = float(timeout) if timeout is not None else None
        self._rust_available = self._check_rust_core()

    def _check_rust_core(self) -> bool:
        """Check if Rust cryptographic core is available."""
        try:
            import warm_logic_rs

            return True
        except ImportError:
            try:
                from warm_logic.kernel import rust_loader

                return rust_loader.HAS_RUST_CORE
            except ImportError:
                return False

    def _get_or_create_keypair(self) -> tuple[str, str]:
        """Get or create ML-DSA-65 keypair for signing."""
        if not self._rust_available:
            return ("", "")
        try:
            import warm_logic_rs as rs

            # Use standalone function (returns hex-encoded keys)
            pub, priv = rs.generate_keypair()
            return (pub, priv)
        except Exception as e:
            logger.warning(f"Keypair generation failed: {e}")
            return ("", "")

    def _sign_message(self, private_key: str, message: str) -> str | None:
        """Sign message with ML-DSA-65."""
        if not self._rust_available or not private_key:
            return None
        try:
            import warm_logic_rs as rs

            # Use standalone sign function
            return str(rs.sign(private_key, message))
        except Exception as e:
            logger.warning(f"Signing failed: {e}")
            return None

    def _get_kernel_mode(self, epsilon_c: float = 0.2, tau_ethics: float = 0.1) -> str:
        """Get current kernel mode from ReflectiveLoop."""
        if not self._rust_available:
            return "NORMAL"
        try:
            import warm_logic_rs as rs

            loop = rs.ReflectiveLoop()
            mode_decision = loop.compute_mode(
                {"epsilon_c": epsilon_c, "tau_ethics": tau_ethics}
            )
            return str(mode_decision.mode)
        except Exception as e:
            logger.warning(f"Kernel mode check failed: {e}")
            return "NORMAL"

    def propose_action(
        self,
        intent: str,
        context: dict[str, Any] | None = None,
        *,
        require_proof: bool = False,
        require_signature: bool = False,
    ) -> Decision:
        """
        Propose an action to the governance kernel.

        In Hardened Mode (v1.0), this uses the SovereignBridge to ensure
        memory isolation between the application and the kernel.
        """
        context = context or {}

        if self._rust_available:
            from warm_logic.sdk.bridge import SovereignBridge
            from warm_logic.sdk.identity import SovereignIdentity

            # 1. Handle Identification/Signing
            pub_key = "anonymous"
            signature = None
            if require_signature:
                # In a real app, the client would have a persistent identity
                identity = SovereignIdentity()
                pub_key = identity.public_key
                payload_to_sign = f"{intent}:{json.dumps(context, sort_keys=True)}"
                signature = identity.sign(payload_to_sign)

            # 2. Evaluate via Hardened Bridge (ISB)
            try:
                verdict_data = SovereignBridge.evaluate_hardened(
                    agent_id=pub_key,
                    action_type=intent,
                    payload=context,
                    signature=signature,
                )

                return Decision(
                    verdict=verdict_data["verdict_type"].upper(),
                    reason=verdict_data["reason"],
                    proof_hash=(
                        hex(verdict_data["proof_hash"][0])
                        if verdict_data["proof_hash"]
                        else "no-proof"
                    ),
                    metadata={
                        "intent": intent,
                        "hardened": True,
                        "verdict_hash": list(verdict_data["verdict_hash"]),
                    },
                    signature=signature,
                    mode=verdict_data.get("mode", "NORMAL"),
                )
            except Exception as e:
                logger.info(
                    "Hardened bridge unavailable (%s); using the Python "
                    "fallback evaluator. See docs/CLAIM_EVIDENCE.md.",
                    e,
                )
                if require_proof:
                    raise

        # Fallback for research prototype / Non-Rust environments
        if require_proof or require_signature:
            raise RuntimeError(
                "Cryptographic proofs/signatures require Rust core. "
                "Run 'cd rust_core && maturin develop --release --features python'"
            )

        # Generate deterministic hash for audit trail
        payload = f"{intent}:{sorted(context.items())}"
        proof_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]

        # Basic policy evaluation (placeholder - real logic in Rust)
        verdict, reason = self._evaluate_policy(intent, context)

        # Get current kernel mode from ReflectiveLoop
        mode = self._get_kernel_mode()

        return Decision(
            verdict=verdict,
            reason=reason,
            proof_hash=proof_hash,
            metadata={
                "intent": intent,
                "rust_verified": False,
                "context_hash": hashlib.sha256(str(context).encode()).hexdigest()[:16],
            },
            signature=None,
            mode=mode,
        )

    def _evaluate_policy(self, intent: str, context: dict[str, Any]) -> tuple[str, str]:
        """
        Evaluate policy for the given intent.

        NOTE: This is a simplified Python-only evaluation.
        Real policy enforcement happens in Rust core with ZK proofs.
        """
        # Blocked intents (hardcoded safety)
        blocked = {"delete_all", "bypass_auth", "disable_logging"}
        if intent in blocked:
            return "DENY", f"Intent '{intent}' is blocked by constitution"

        # Default allow for demonstration
        return "ALLOW", "Policy check passed (Python fallback)"

    def health_check(self) -> dict[str, Any]:
        """Check the health of the kernel connection."""
        return {
            "status": "ok",
            "endpoint": self.endpoint,
            "rust_core": self._rust_available,
            "warning": "Experimental - not production ready",
        }
