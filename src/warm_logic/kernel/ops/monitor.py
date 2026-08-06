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
Sovereign Law Monitor.
Active enforcement of TLA+ Constitutional Invariants.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from warm_logic.kernel.lineage import PolicyZone
from warm_logic.kernel.lineage import tracker as lineage_tracker
from warm_logic.kernel.zanzibar import zanzibar

logger = logging.getLogger("LawMonitor")


@dataclass
class OSState:
    """Snapshot of the OS state for invariant checking."""

    execution_state: str = "IDLE"
    ledger_len: int = 0
    current_artifact: Optional[str] = None
    user_id: str = "anonymous"
    target_zone: PolicyZone = PolicyZone.PUBLIC


class InvariantViolation(Exception):
    """Raised when a formal invariant is violated at runtime."""

    pass


class LawMonitor:
    """
    The Active Guardian of the Constitution.
    Enforces 'Methodological Integrity' using TLA+ derived logic.
    """

    def __init__(self, tla_path: str = "warm_logic/constitution/core_invariants.tla"):
        self.tla_path = tla_path
        self.last_state: Optional[OSState] = None
        logger.info(f"LawMonitor Active. Anchored to: {self.tla_path}")

    def verify_transition(self, current_state: OSState):
        """Checks if the current state violates any global invariants."""

        # 1. TypeOK Check
        if current_state.execution_state not in ["IDLE", "RUNNING", "BLOCKED"]:
            raise InvariantViolation(
                f"TypeOK Violation: Invalid state {current_state.execution_state}"
            )

        # 2. MethodologicalIntegrity (Lineage + Auth)
        if current_state.execution_state == "RUNNING":
            artifact = current_state.current_artifact
            if not artifact:
                raise InvariantViolation(
                    "MethodologicalIntegrity Violation: RUNNING without artifact."
                )

            # Check Authorization (Zanzibar)
            if not zanzibar.check(
                "artifact", artifact, "execute", current_state.user_id
            ):
                raise InvariantViolation(
                    f"Auth Violation: User {current_state.user_id} unauthorized for {artifact}"
                )

            # Check Lineage Policy (PAI)
            if not lineage_tracker.check_flow(artifact, current_state.target_zone):
                raise InvariantViolation(
                    f"Lineage Violation: {artifact} cannot flow to {current_state.target_zone.name}"
                )

        # 3. LedgerImmutable
        if self.last_state and current_state.ledger_len < self.last_state.ledger_len:
            raise InvariantViolation(
                "LedgerImmutable Violation: Ledger size decreased."
            )

        self.last_state = current_state
        return True


# Global Monitor Instance
law_monitor = LawMonitor()
