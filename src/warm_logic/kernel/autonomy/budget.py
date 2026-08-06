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
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from warm_logic.kernel.sys.persistence import SovereignStore

logger = logging.getLogger("SovereignBudget")


class PatchBudgeter:
    """
    [] The Architect of Scarcity.
    Manages the 'kernel Energy' budget for autonomous evolution.
    """

    def __init__(
        self, daily_limit: float = 1000.0, store: Optional[SovereignStore] = None
    ) -> None:
        # Persistent Budgeting to prevent Phoenix Drain
        import time

        from warm_logic.kernel.sys.persistence import SovereignStore

        self.store = store or SovereignStore()
        self.daily_limit = daily_limit
        self.total_expenditure = 0.0  # Session tracking only

        # Load from Store
        now = time.time()
        last_reset = self.store.get_meta("budget_last_reset")

        if last_reset and (now - float(last_reset) < 86400):
            # Same day, restore energy
            saved_energy = self.store.get_meta("budget_energy")
            restored_energy = (
                float(saved_energy) if saved_energy is not None else daily_limit
            )
            self.remaining_energy = max(0.0, min(restored_energy, daily_limit))
            logger.info(
                f"💾 [Budget] Restored from persistence: {self.remaining_energy:.2f}/{daily_limit}"
            )
        else:
            # New day or first run
            self.remaining_energy = daily_limit
            self.store.set_meta("budget_last_reset", now)
            self.store.set_meta("budget_energy", daily_limit)
            logger.info(f"[Budget] New cycle started. Energy: {daily_limit}")

    def calculate_cost(self, patch_code: str, strategy: str) -> float:
        """
        Calculates the energy cost of a patch.
        """
        base_cost = 10.0
        if strategy == "semantic":
            base_cost = 50.0  # Higher reasoning cost

        line_cost = len(patch_code.splitlines()) * 1.5
        return base_cost + line_cost

    def pre_approve(self, cost: float) -> bool:
        """
        Checks if the budget allows for the cost.
        """
        if self.remaining_energy >= cost:
            logger.info(
                f"💰 [Budget] Pre-approved expenditure: {cost:.2f} (Remaining: {self.remaining_energy - cost:.2f})"
            )
            return True
        logger.warning(
            f"📉 [Budget] INSOLVENT: Required {cost:.2f}, but only {self.remaining_energy:.2f} available."
        )
        return False

    def finalize_expenditure(self, cost: float) -> None:
        """
        Deducts the cost from the remaining budget.
        """
        self.remaining_energy -= cost
        self.total_expenditure += cost

        # Persist Update
        self.store.set_meta("budget_energy", self.remaining_energy)

        logger.info(
            f"📊 [Budget] Total Expenditure today: {self.total_expenditure:.2f}"
            f" (Remaining Persisted: {self.remaining_energy:.2f})"
        )

    def replenish(self) -> None:
        """
        Resets the budget (e.g., daily cycle).
        """
        import time

        logger.info(f"[Budget] Replenishing kernel Energy to {self.daily_limit}")
        self.remaining_energy = self.daily_limit
        self.store.set_meta("budget_energy", self.daily_limit)
        self.store.set_meta("budget_last_reset", time.time())
