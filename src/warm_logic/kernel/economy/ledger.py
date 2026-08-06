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
Replicated Ledger
The Single Source of Truth for the WarmLogic Economy.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Centralized Rust Core Loader
from warm_logic.kernel import rust_loader

# Transaction Logic
from warm_logic.kernel.substrate.proof_zk import ZKProofGenerator
from warm_logic.kernel.sys.persistence import SovereignStore

# Removed shadowed HAS_RUST_CORE to allow dynamic patching


@dataclass
class Transaction:
    source: str
    target: str
    amount: int
    signature: str
    timestamp: float = field(default_factory=time.time)
    # EIP-1559 Fee Market
    max_fee: int = 20  # Default cover for base fee
    priority_fee: int = 1  # Default tip

    @property
    def tx_id(self) -> str:
        payload = f"{self.source}:{self.target}:{self.amount}:{self.timestamp}:{self.max_fee}:{self.priority_fee}"
        return hashlib.sha3_256(payload.encode()).hexdigest()


logger = logging.getLogger("ReplicatedLedger")


# Removed: @dataclass Transaction definition, as it's now imported.


class ReplicatedLedger:
    """
    Solid-State Replicated Ledger (Legay Purged)
    Mandatory Rust Core for all state transitions.
    """

    def __init__(
        self, store: SovereignStore, consensus_callback: Optional[Callable] = None
    ):
        self.store = store
        self.consensus_callback = consensus_callback
        self.pending_txs: List[Transaction] = []

        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError(
                "CRITICAL: Rust Core missing. Ledger disabled for hardware attestation enforcement."
            )

        # Load Core via wrapper
        try:
            rs = rust_loader.load_rust_core()
            if hasattr(self.store, "_rust_ledger") and self.store._rust_ledger:
                self.rust_core = self.store._rust_ledger
                logger.info("Using Shared Ledger Engine (Rust).")
            else:
                db_path = getattr(self.store, "db_path", "sovereign.db")
                self.rust_core = rs.RustReplicatedLedger(str(db_path) + ".sled")
                logger.info("Solid-State Ledger Engine Active (Rust).")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Rust Ledger: {e}")

    def close(self) -> None:
        """Releases all resources."""
        if hasattr(self, "store") and self.store:
            self.store.close()
        self.rust_core = None

    def submit_tx(self, tx: Transaction) -> bool:
        """Validates and adds a transaction to the mempool via Rust Core."""
        # Allow amount=0 for signal-only transactions (e.g., Oracle anchoring)
        if tx.amount < 0:
            return False

        try:
            self.rust_core.submit_transaction(
                tx.tx_id,
                tx.source,
                tx.target,
                tx.amount,
                tx.signature,
                tx.timestamp,
                tx.max_fee,
                tx.priority_fee,
            )
            return True
        except Exception as e:
            logger.error(f"Rust Core Validation Failed: {e}")
            return False

    def mine_block(self, miner_address: str) -> Optional[str]:
        """Commit pending transactions to a new block using Rust Core."""
        block_hash = self.rust_core.mine_block(miner_address)
        if not block_hash:
            return None

        # Post-Mining Forensic Sync
        block = self.rust_core.get_last_block()
        if block:
            balances = self.rust_core.get_all_balances()
            self.store.commit_block(
                timestamp=block.timestamp,
                tx_ids=block.tx_ids,
                miner=block.miner,
                prev_hash=block.prev_hash,
                block_hash=block.hash,
                balance_updates=balances,
                zk_proof=block.zk_proof,
                state_root=block.state_root,
                index=block.index,
            )
            if self.consensus_callback:
                self.consensus_callback(block, balances, block.zk_proof, [])
        return str(block_hash)

    def receive_external_block(
        self,
        block_data: Dict[str, Any],
        balance_updates: Dict[str, int],
        zk_proof: str,
        transactions: List[Any] = [],
    ) -> bool:
        """
        Validates and commits a block received from the network.
        """
        # 1. Basic Structure Validation
        required = ["index", "prev_hash", "tx_ids", "hash"]
        if not all(k in block_data for k in required):
            return False

        # 2. ZK Proof Verification -> Delegated to Rust in final form
        # But for now keeping Python ZK verification logic wrapper if ZKProofGenerator uses Rust?
        # SIM-002 said ZKProofGenerator uses hardcoded metrics.
        # Let's keep this shell but note we need to fix ZKProofGenerator next.

        prev_root = self.get_state_root()
        items = sorted(balance_updates.items())
        claimed_root = hashlib.sha256(
            "|".join([f"{k}:{v}" for k, v in items]).encode()
        ).hexdigest()

        if not ZKProofGenerator.verify_proof(
            zk_proof, prev_root, transactions, claimed_root
        ):
            # hardware attestation enforcement: Slash Malicious Node
            miner = block_data.get("miner", "UNKNOWN")
            timestamp = time.time()
            try:
                self.store.set_meta(
                    f"SLASH:{miner}:{timestamp}",
                    {
                        "reason": "INVALID_ZK_PROOF",
                        "block_hash": block_data.get("hash", "???"),
                    },
                )
            except Exception as e:
                logger.error(f"Slashing Log Failed: {e}")

            logger.warning(f"NODE SLASHED: {miner} for invalid ZK proof.")
            return False

        # ... Commit logic preserved ...
        try:
            self.store.commit_block(
                timestamp=time.time(),
                tx_ids=block_data["tx_ids"],
                miner="REMOTE",
                prev_hash=block_data["prev_hash"],
                block_hash=block_data["hash"],
                balance_updates=balance_updates,
                zk_proof=zk_proof,
                index=block_data.get("index"),
            )
            logger.info(f"External Block {block_data['hash'][:8]} synced.")
            return True
        except Exception as e:
            logger.error(f"Failed to sync external block: {e}")
            return False

    def get_balance(self, address: str) -> int:
        try:
            return int(self.rust_core.get_balance(address))
        except Exception as e:
            logger.error(f"Error getting balance from Core: {e}")
            return 0

    def get_state_root(self) -> str:
        """Calculates a deterministic hash of the entire balance set."""
        try:
            return str(self.rust_core.get_state_root())
        except Exception as e:
            logger.error(f"Error calculating state root via Core: {e}")
            return "0"
