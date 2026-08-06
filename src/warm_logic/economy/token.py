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
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("SovereignEconomy")


@dataclass
class SovereignToken:
    """
    Represents the atomic unit of value in the WarmLogic economy.
    Model: 1.0 ST (Sovereign Token) = 1 Standard GPU Hour (Reference)
    """

    amount: float
    currency: str = "ST"


@dataclass
class Transaction:
    """
    An atomic transfer of value.
    """

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: float
    timestamp: float
    signature: Optional[str] = None  # To be implemented with PQC
    memo: str = ""


class TokenLedger:
    """
    A transient (in-memory) ledger for 
    Will evolve into a distributed ledger in a later revision.
    """

    def __init__(self):
        self._balances: Dict[str, float] = {}  # node_id -> amount
        self._history: List[Transaction] = []

        # Genesis Block logic (Grant Kernel infinite supply or pre-mine?)
        # For now, we allow Minting by Root Authority (Kernel)
        self._balances["KERNEL_ROOT"] = 1_000_000_000.0

    def get_balance(self, node_id: str) -> float:
        return self._balances.get(node_id, 0.0)

    def mint(self, node_id: str, amount: float, proof: str = "GENESIS") -> bool:
        """
        Create new tokens.
        In strict mode, this requires Proof of Compute.
        """
        if amount < 0:
            return False

        current = self.get_balance(node_id)
        self._balances[node_id] = current + amount

        # Record Mint TX
        tx = Transaction(
            tx_id=hashlib.sha256(f"MINT-{time.time()}-{node_id}".encode()).hexdigest(),
            sender_id="MINT_AUTHORITY",
            receiver_id=node_id,
            amount=amount,
            timestamp=time.time(),
            memo=f"Proof: {proof}",
        )
        self._history.append(tx)
        logger.info(f"[Economy] Minted {amount} ST for {node_id[:8]}...")
        return True

    def transfer(
        self, sender: str, receiver: str, amount: float, signature: str = ""
    ) -> bool:
        """
        Transfer tokens from sender to receiver.
        """
        if amount <= 0:
            return False

        sender_bal = self.get_balance(sender)
        if sender_bal < amount:
            logger.warning(f"[Economy] TX Failed: Insufficient Funds ({sender[:8]})")
            return False

        # Execute Transfer
        self._balances[sender] -= amount
        self._balances[receiver] = self.get_balance(receiver) + amount

        tx = Transaction(
            tx_id=hashlib.sha256(
                f"TX-{time.time()}-{sender}-{receiver}".encode()
            ).hexdigest(),
            sender_id=sender,
            receiver_id=receiver,
            amount=amount,
            timestamp=time.time(),
            signature=signature,
        )
        self._history.append(tx)
        logger.info(
            f"💸 [Economy] Transfer {amount} ST: {sender[:8]} -> {receiver[:8]}"
        )
        return True

    def verify_payment(self, payer: str, required_amount: float) -> bool:
        return self.get_balance(payer) >= required_amount
