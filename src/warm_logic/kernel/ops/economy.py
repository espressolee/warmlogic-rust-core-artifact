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
from typing import Any, Dict, Optional

logger = logging.getLogger("KineticEconomy")


class CreditManager:
    """
    Credit Manager.
    Manages node credit balances and transaction integrity.
    In a full implementation, this would be backed by the ReplicatedLedger.
    """

    def __init__(
        self, node_id: str, store: Optional[Any] = None, initial_balance: float = 1000.0
    ):
        self.node_id = node_id
        self.store = store

        # In-memory transaction list for tracking
        self.transactions: list = []

        # Ensure initial balance in store if not present
        if self.store:
            # SovereignStore uses integer balances
            val = self.store.get_balance(node_id)
            current = float(val)
            if current == 0 and initial_balance > 0:
                self.store.update_balance(node_id, int(initial_balance))
        else:
            # Fallback for transient nodes
            self.balances: Dict[str, float] = {node_id: initial_balance}

    def get_balance(self, node_id: str) -> float:
        if self.store:
            return float(self.store.get_balance(node_id))
        return self.balances.get(node_id, 0.0)

    def transfer(self, from_id: str, to_id: str, amount: float, reason: str) -> bool:
        current_from = self.get_balance(from_id)
        if current_from < amount:
            logger.warning(
                f"💸 [Economy] Transfer FAILED: {from_id} has insufficient funds ({amount} requested)."
            )
            return False

        if self.store:
            current_to = self.get_balance(to_id)
            # Update source
            self.store.update_balance(from_id, int(current_from - amount))
            # Update dest
            self.store.update_balance(to_id, int(current_to + amount))
        else:
            self.balances[from_id] -= amount
            self.balances[to_id] = self.balances.get(to_id, 0.0) + amount

        tx = {"from": from_id, "to": to_id, "amount": amount, "reason": reason}
        self.transactions.append(tx)
        logger.info(
            f"💰 [Economy] Transfer SUCCESS: {amount} credits from {from_id[:8]} to {to_id[:8]} ({reason})."
        )
        return True

    def deduct(self, node_id: str, amount: float, reason: str) -> bool:
        """Deducts credits for a service or tax."""
        current = self.get_balance(node_id)
        if current < amount:
            return False

        if self.store:
            self.store.update_balance(node_id, int(current - amount))
        else:
            self.balances[node_id] -= amount

        logger.info(
            f"📉 [Economy] Deducted {amount} from {node_id[:8]} for {reason}. New Balance: {self.get_balance(node_id)}"
        )
        return True


class ResourceAccountant:
    """
    Resource Accountant.
    Converts physical resource usage into credit costs.
    """

    MUTATION_BASE_TAX = 50.0
    COMPUTE_UNIT_COST = 0.1  # Per specialized 'compute unit'

    @staticmethod
    def calculate_mutation_cost(file_size: int, complexity_score: float = 1.0) -> float:
        """Calculates the tax for a code mutation proposal."""
        # Simple formula: Base Tax + (Size / 1024) * Complexity
        return (
            ResourceAccountant.MUTATION_BASE_TAX
            + (file_size / 1024.0) * complexity_score
        )

    @staticmethod
    def calculate_compute_cost(duration_ms: float, cpu_load: float) -> float:
        """Calculates the cost of a compute task."""
        return (duration_ms / 100.0) * cpu_load * ResourceAccountant.COMPUTE_UNIT_COST
