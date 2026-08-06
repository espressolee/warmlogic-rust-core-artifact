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
Provenance Ledger
Immutable, append-only log of Sovereign State transitions.
Provides 'Proof of History' via hash chaining.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger("warm_logic.kernel.provenance.ledger")


@dataclass
class LedgerEntry:
    index: int
    timestamp: float
    previous_hash: str
    state_hash: str  # Hash of the Global System State (Kernel + Constitution)
    signature: Optional[str] = None  # PQC Signature

    def compute_hash(self) -> str:
        """Computes the hash of this entry (Link in the chain)."""
        payload = f"{self.index}:{self.timestamp}:{self.previous_hash}:{self.state_hash}:{self.signature}"
        return hashlib.sha3_256(payload.encode()).hexdigest()


class GlobalLedger:
    """
    [Phase 90.2] Formal Sovereignty: Global Ledger.
    Maintains an unbroken chain of custody for the Sovereign State.
    """

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, storage_path: str = "ledger.jsonl"):
        self.chain: List[LedgerEntry] = []
        self.storage_path = storage_path
        self._init_genesis()

    def _init_genesis(self) -> None:
        """Creates the Genesis Block (Anchor of Reality)."""
        genesis = LedgerEntry(
            index=0,
            timestamp=0.0,
            previous_hash=self.GENESIS_HASH,
            state_hash="GENESIS_STATE_ERA_88000",
            signature="ROOT_AUTHORITY",
        )
        self.chain.append(genesis)
        # In a real persistence scenario, we'd load here.

    def append_state(self, state_hash: str, signature: Optional[str] = None) -> str:
        """
        Record a new state transition.
        Returns the new block hash.
        """
        last_block = self.chain[-1]
        last_hash = last_block.compute_hash()

        new_entry = LedgerEntry(
            index=len(self.chain),
            timestamp=time.time(),
            previous_hash=last_hash,
            state_hash=state_hash,
            signature=signature,
        )
        self.chain.append(new_entry)

        block_hash = new_entry.compute_hash()
        logger.info(
            f"📜 [Ledger] New Block #{new_entry.index} anchored. Hash: {block_hash[:8]}..."
        )
        return block_hash

    def verify_chain(self) -> bool:
        """
        Verifies the integrity of the entire hash chain.
        Returns True if history is unbroken.
        """
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            # Recompute previous hash
            expected_prev_hash = previous.compute_hash()

            if current.previous_hash != expected_prev_hash:
                logger.critical(
                    f"🛑 [Ledger] BROKEN CHAIN at index {i}. Prev: {current.previous_hash[:8]}, Expected: {expected_prev_hash[:8]}"
                )
                return False

        return True
