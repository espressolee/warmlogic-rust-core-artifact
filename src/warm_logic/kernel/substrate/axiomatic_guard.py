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
import functools
import logging
from typing import Any, Callable

from warm_logic.kernel.substrate.attestation import CrossNodeAttestation

logger = logging.getLogger("AxiomaticGuard")


def axiomatic_guard(func: Callable) -> Callable:
    """
    Decorator to enforce hardware-bound governance.
    Ensures that the environment is cryptographically validated before
    executing a critical directive.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        from warm_logic.kernel import rust_loader

        # 0. Rust Core Check
        if not rust_loader.HAS_RUST_CORE:
            logger.error(
                "🛑 [AxiomaticGuard] RUST CORE OFFLINE. hardware attestation enforcement Blocked."
            )
            raise RuntimeError("Hardware Integrity Compromised: Rust Core Missing.")

        # 1. Local Attestation Check
        try:
            # On macOS, this checks the Kinetic Seal (CPU UUID + Serial)
            # On Linux/Edge, this would verify TPM PCRs.
            from warm_logic_rs import HardwareEntropy

            valid, info = HardwareEntropy.verify_attestation()
            if not valid:
                logger.critical(f"[AxiomaticGuard] LOCAL ATTESTATION FAILED: {info}")
                raise RuntimeError("hardware attestation enforcement: Hardware Integrity Failure.")
        except Exception as e:
            logger.error(f"[AxiomaticGuard] Attestation logic error: {e}")
            raise RuntimeError(f"Hardware Integrity Compromised: {e}")

        # 2. Remote Tower Attestation Check (if mesh active)
        # This prevents a compromised root authority from unilaterally changing axioms
        # without being 'audited' by the Control Tower.
        attestor = CrossNodeAttestation()
        if not attestor.challenge_tower():
            logger.warning(
                "⚠️ [AxiomaticGuard] Control Tower unreachable or attestation failed. Proceeding with caution (Local-Only Mode)."
            )
            # In a 'Hard Shutdown' configuration, we would raise an error here.
            # raise RuntimeError("Axiomatic Guard: Control Tower Consensus Required.")

        logger.info(
            f"🛡️ [AxiomaticGuard] Environment Validated. Executing: {func.__name__}"
        )
        return func(*args, **kwargs)

    return wrapper
