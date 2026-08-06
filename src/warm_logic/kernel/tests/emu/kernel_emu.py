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
[Phase 200] High-Fidelity Kernel Emulator.
Provides a pure-Python implementation of core Rust Kernel logic for stable testing.
"""

import hashlib
import json
from typing import Dict


class RustZKProofGenerator:
    """Mimics the Rust ZK generator/verifier."""

    def generate_state_proof(self, val, blinding):
        from types import SimpleNamespace

        return SimpleNamespace(commitment_hex="c_hex", proof_hex="p_hex")

    def verify_state_proof(self, proof, commitment):
        return True


class KernelEmulator:
    """
    Emulates RustReplicatedLedger and SovereignStore behaviors.
    """

    def __init__(self):
        self.state = {"balances": {}}
        self.blocks = []
        self.mempool = []
        self.last_hash = "0" * 64
        self.last_state_root = "0" * 64

    def RustReplicatedLedger(self, path: str):
        """Mimics the Rust factory method."""
        return self

    def RustZKProofGenerator(self):
        """Mimics the Rust ZK generator factory."""
        return RustZKProofGenerator()

    def submit_transaction(
        self, tx_id, source, target, amount, signature, timestamp, max_fee, priority_fee
    ):
        """Mimics the Rust submission logic."""
        # Check source balance
        if source != "GENESIS" and self.get_balance(source) < amount:
            return False

        self.mempool.append(
            {"tx_id": tx_id, "source": source, "target": target, "amount": amount}
        )
        return True

    def get_balance(self, address: str) -> int:
        return self.state["balances"].get(address, 0)

    def get_all_balances(self) -> Dict[str, int]:
        return self.state["balances"].copy()

    def get_state_root(self) -> str:
        # Deterministic state root based on sorted balances
        sorted_bal = sorted(self.state["balances"].items())
        state_str = "|".join([f"{k}:{v}" for k, v in sorted_bal])
        if not state_str:
            return "0" * 64
        return hashlib.sha256(state_str.encode()).hexdigest()

    def mine_block(self, miner: str) -> str:
        # Calculate balance updates from mempool
        updates = self.get_all_balances()
        tx_ids = []
        for tx in self.mempool:
            src, tgt, amt = tx["source"], tx["target"], tx["amount"]
            if src != "GENESIS":
                updates[src] = updates.get(src, 0) - amt
            updates[tgt] = updates.get(tgt, 0) + amt
            tx_ids.append(tx["tx_id"])

        # Apply updates
        self.state["balances"].update(updates)
        self.mempool = []  # Clear mempool

        current_state_root = self.get_state_root()

        block_idx = len(self.blocks)
        new_hash = hashlib.sha256(
            f"{self.last_hash}{block_idx}{miner}".encode()
        ).hexdigest()

        block = {
            "index": block_idx,
            "timestamp": 123456789.0,  # constant for test determinism
            "tx_ids": tx_ids,
            "miner": miner,
            "prev_hash": self.last_hash,
            "hash": new_hash,
            "state_root": current_state_root,
            "zk_proof": json.dumps(
                {
                    "prefix": "zkp_v2_bulletproofs",  # Use real prefix to satisfy ZKProofGenerator
                    "commitment": "emu_c",
                    "proof": "emu_p",
                    "meta": {
                        "prev_root": self.last_state_root,
                        "orig_commitment": "emu_orig",  # Mock
                    },
                }
            ),
        }

        self.blocks.append(block)
        self.last_hash = new_hash
        self.last_state_root = current_state_root
        return new_hash

    def get_last_block(self):
        if not self.blocks:
            return None
        # Wrap in a SimpleNamespace to mimic Rust object access
        from types import SimpleNamespace

        return SimpleNamespace(**self.blocks[-1])

    def verify(self, sender: str, content: str, signature: str) -> bool:
        # Basic signature presence check
        return bool(signature)
