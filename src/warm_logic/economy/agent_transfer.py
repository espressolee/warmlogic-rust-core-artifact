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
Agent Transfer Protocol
The economic root for AI-to-AI sovereign interactions.
Handles PQC-signed value transfer between mesh nodes.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, List

logger = logging.getLogger("EconomicProtocol")


@dataclass
class Transaction:
    tx_id: str
    sender_did: str
    receiver_did: str
    amount: float
    asset_type: str  # "COMPUTE_CREDIT", "DATA_ACCESS", "TRUST_TOKEN"
    timestamp: float = field(default_factory=time.time)
    signature: str = ""  # ML-DSA-65 signature


class AgentEconomics:
    """
    Manages resource and value exchange between mesh nodes.
    """

    def __init__(self, kernel_api: Any):
        self.kernel = kernel_api
        self.ledger: List[Transaction] = []

    async def transfer_value(
        self, sender: str, receiver: str, amount: float, asset: str
    ) -> Transaction:
        """
        Creates and signs an economic transaction.
        """
        tx_id = hashlib.sha256(
            f"{sender}:{receiver}:{amount}:{time.time()}".encode()
        ).hexdigest()[:16]

        tx = Transaction(
            tx_id=f"TXN-{tx_id}",
            sender_did=sender,
            receiver_did=receiver,
            amount=amount,
            asset_type=asset,
        )

        # In a real system, this would use the node's private key
        tx.signature = "ML-DSA-65-ECONOMIC-SIG-PLACEHOLDER"

        logger.info(
            f"💰 [Economy] Transferring {amount} {asset} from {sender[:8]} to {receiver[:8]}"
        )

        # Submit to Mesh Ledger (BFT Consensus)
        await self._submit_to_ledger(tx)
        return tx

    async def _submit_to_ledger(self, tx: Transaction):
        """
        Appends to the distributed ledger after consensus.
        """
        self.ledger.append(tx)
        # Simulation: In-memory persist
        logger.debug(
            f"Transaction {tx.tx_id} committed to local ledger index {len(self.ledger)}"
        )

    def get_balance(self, agent_did: str, asset: str) -> float:
        """
        Calculates balance from the ledger. (O(N) for sim, O(1) in production via State Roots)
        """
        balance = 0.0
        for tx in self.ledger:
            if tx.receiver_did == agent_did and tx.asset_type == asset:
                balance += tx.amount
            if tx.sender_did == agent_did and tx.asset_type == asset:
                balance -= tx.amount
        return balance
