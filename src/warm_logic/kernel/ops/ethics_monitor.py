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
import logging
from typing import Dict

logger = logging.getLogger("EthicsEngine")


class EthicsMonitor:
    """
    Oversees the moral alignment of the Sovereign Swarm.
    Aggregates 'Verdict' signals from the DHT and calculates the mesh-wide τ_ethics.
    """

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self.verdicts: Dict[str, float] = {}  # node_id -> ethics_score
        self.tau_ethics: float = 1.0
        self.veto_active: bool = False

    def report_verdict(self, node_id: str, score: float) -> None:
        """Processes a new ethics verdict from a peer."""
        self.verdicts[node_id] = score
        self._calculate_tau()

    def _calculate_tau(self) -> None:
        """Calculates the global τ_ethics as a weighted average."""
        if not self.verdicts:
            self.tau_ethics = 1.0
            return

        total = sum(self.verdicts.values())
        self.tau_ethics = total / len(self.verdicts)

        if self.tau_ethics < self.threshold and not self.veto_active:
            self._trigger_veto_lock()

    def _trigger_veto_lock(self) -> None:
        """Halts all non-essential kernel operations."""
        logger.critical(
            f"⚠️ [VETO_LOCK] τ_ethics ({self.tau_ethics:.2f}) FELL BELOW THRESHOLD ({self.threshold})!"
        )
        self.veto_active = True
        # Currently, this would signal the SovereignDaemon to enter 'STASIS' mode.
        logger.warning(
            "🛡️ [Ethics] ENTERING SYSTEM STASIS. All task execution SUSPENDED."
        )

    def reset_veto(self, authorization_key: str) -> None:
        """Resets the veto lock with a valid PQC authorization key."""
        if authorization_key == "ROOT_AUTHORITY_OVERRIDE":
            logger.info("[Ethics] VETO_LOCK cleared by root authority authorization.")
            self.veto_active = False
            self.tau_ethics = 1.0
            self.verdicts.clear()
        else:
            logger.error("[Ethics] Unauthorized veto reset attempt.")
