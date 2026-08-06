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
Sovereign Invariant Enforcement
Enforces J/K/L series runtime invariants and the Fail-Latch mechanism.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from warm_logic.kernel.sys.cryptography import MLDSA

logger = logging.getLogger("InvariantGuard")

# Thresholds
KINETIC_THRESHOLD_MS = 100


class FailLatch:
    """
    Singleton mechanism to lock the kernel upon invariant violation.
    """

    _instance: Optional[FailLatch] = None
    latched: bool
    reason: Optional[str]

    def __new__(cls) -> FailLatch:
        if cls._instance is None:
            cls._instance = super(FailLatch, cls).__new__(cls)
            cls._instance.latched = False
            cls._instance.reason = None
        return cls._instance

    def trigger(self, reason: str) -> None:
        if not self.latched:
            self.latched = True
            self.reason = reason
            logger.critical(f"[FAIL-LATCH] SYSTEM LOCKED: {reason}")


class JSeriesValidator:
    """
    Justice Invariants: PQC Attestation and Signature Integrity.
    """

    def __init__(self) -> None:
        self.mldsa = MLDSA()

    def validate(self, state_hash: str, attestation: Dict[str, str]) -> bool:
        """Verifies that the current state is signed by the PQC layer."""
        if not attestation:
            return False

        is_valid = self.mldsa.verify(
            state_hash, attestation.get("signature", ""), attestation.get("pub_key", "")
        )
        return is_valid


class KSeriesValidator:
    """
    Kinetic Invariants: Loop Latency and Drift.
    """

    def __init__(self) -> None:
        self.last_tick_time: Optional[float] = None

    def validate(self) -> bool:
        """Ensures tick drift does not exceed KINETIC_THRESHOLD_MS."""
        now = time.time()
        if self.last_tick_time is None:
            self.last_tick_time = now
            return True

        drift = (now - self.last_tick_time) * 1000
        self.last_tick_time = now

        if drift > KINETIC_THRESHOLD_MS:
            logger.critical(
                f"⛔ [K-Series] Drift violation: {drift:.2f}ms (Threshold: {KINETIC_THRESHOLD_MS}ms)"
            )
            # hardware attestation enforcement: No more 5s grace.
            # If the loop is too slow, the system is compromised or unstable.
            return False
        return True


class LSeriesValidator:
    """
    Logic Invariants: Sequence and State Integrity.
    """

    def __init__(self) -> None:
        self.last_tick = -1

    def validate(self, current_tick: int) -> bool:
        """Ensures tick count is strictly monotonic."""
        if current_tick <= self.last_tick:
            return False
        self.last_tick = current_tick
        return True


class InvariantManager:
    """
    Orchestrates J/K/L series validation.
    """

    def __init__(self) -> None:
        self.latch = FailLatch()
        self.j_val = JSeriesValidator()
        self.k_val = KSeriesValidator()
        self.l_val = LSeriesValidator()

    def check_all(
        self, current_tick: int, state_hash: str, attestation: Dict[str, str]
    ) -> bool:
        if self.latch.latched:
            return False

        # 1. Logic Check
        if not self.l_val.validate(current_tick):
            self.latch.trigger(f"L-Series Violation: Non-monotonic tick {current_tick}")
            return False

        # 2. Kinetic Check
        if not self.k_val.validate():
            self.latch.trigger("K-Series Violation: Extreme clock drift")
            return False

        # 3. Justice Check
        if not self.j_val.validate(state_hash, attestation):
            self.latch.trigger("J-Series Violation: Unattested state transition")
            return False

        return True
