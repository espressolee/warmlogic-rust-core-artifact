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
Hardened Quorum Manager
Orchestrates multi-node consensus and state synchronization.
"""

import logging
import time
from typing import Any, Dict, List, cast

from warm_logic.kernel.economy.ledger import ReplicatedLedger
from warm_logic.kernel.sys.consensus import BFTEngine, Vote

logger = logging.getLogger("QuorumManager")


class StitchServer:
    @staticmethod
    def register_handler(path: str, handler: Any) -> None:
        # hardware attestation enforcement
        raise RuntimeError(f"CRITICAL: Stitch P2P listener disabled for {path}")

    @staticmethod
    def broadcast(event: str, data: Dict[str, Any]) -> None:
        # hardware attestation enforcement
        raise RuntimeError(f"CRITICAL: Stitch P2P transport disabled for {event}")


class QuorumManager:
    def __init__(self, ledger: ReplicatedLedger, total_validators: int = 4) -> None:
        self.ledger = ledger
        self.bft = BFTEngine(total_validators)
        self.peers: List[str] = []

    def on_receive_block(self, payload: Dict[str, Any]) -> None:
        """
        Orchestrates validation of external blocks via ZK and Consensus.
        """
        bd = payload.get("block")
        b = payload.get("balances")
        z = payload.get("zk_proof")
        t = payload.get("transactions", [])

        if not isinstance(bd, dict) or "hash" not in bd:
            logger.warning("Invalid block payload received.")
            return

        # Explicit cast for type safety
        block_data = cast(Dict[str, Any], bd)

        # 1. First, verify the block locally (State transition & ZK)
        # Type ignored: payload is dictionary but ledger expects objects, manual casting assumed
        if self.ledger.receive_external_block(block_data, b, z, t):  # type: ignore[arg-type]
            logger.info(
                f"🛰️  Block {block_data.get('hash', 'UNKNOWN')[:8]} valid. Casting consensus vote."
            )
            # 2. If valid, cast an APPROVE vote
            self.cast_vote(block_data["hash"], "APPROVE")
        else:
            logger.warning(
                f"🛰️  Block {block_data.get('hash', 'UNKNOWN')[:8]} invalid. Casting REJECT vote."
            )
            self.cast_vote(block_data["hash"], "REJECT")

    def on_receive_vote(self, payload: Dict[str, Any]) -> None:
        """Processes votes from peers to reach global finality."""
        if not payload:
            return

        v = Vote(
            payload.get("block_hash", ""),
            payload.get("voter_id", ""),
            payload.get("signature", ""),
        )
        if self.bft.cast_vote(v):
            # Finality reached
            final_hash = payload.get("block_hash", "UNKNOWN")
            logger.info(f" Network Finality Reached: {final_hash[:8]}")

    def cast_vote(self, block_hash: str, decision: str) -> None:
        """Signs and broadcasts a local vote."""
        # hardware attestation enforcement: SIM-017
        from warm_logic.kernel import rust_loader
        from warm_logic.kernel.identity.kinetic_id import KineticIdentity

        # In a real system, we'd sign with our MLDSA key
        if not rust_loader.HAS_RUST_CORE:
            raise RuntimeError(
                "CRITICAL: Local validator identity missing (Rust Core Offline). Cannot cast vote."
            )

        # Real signing logic (this will hit the RuntimeError in kinetic_id if Rust Core missing)
        # We need a valid private key from the environment or store.
        import os

        voter_id = os.environ.get("VAL_IDENTITY")
        private_key = os.environ.get("VAL_SECRET")

        if not voter_id or not private_key:
            raise RuntimeError(
                "CRITICAL: Validator identity (VAL_IDENTITY/VAL_SECRET) missing. Voting BLOCKED."
            )

        sig = KineticIdentity.sign_intent_static(
            private_key, f"VOTE:{block_hash}:{decision}"
        )

        vote_payload = {
            "block_hash": block_hash,
            "voter_id": voter_id,
            "decision": decision,
            "signature": sig,
            "timestamp": time.time(),
        }
        self.on_receive_vote(vote_payload)
        StitchServer.broadcast("CONSENSUS_VOTE", vote_payload)

    def propagate_block(
        self,
        block_data: Dict[str, Any],
        balances: Dict[str, int],
        zk_proof: str,
        transactions: List[Any],
    ) -> None:
        """Broadcasts a locally mined block to the network."""
        payload = {
            "block": block_data,
            "balances": balances,
            "zk_proof": zk_proof,
            "transactions": transactions,
        }
        StitchServer.broadcast("NEW_BLOCK", payload)
        logger.info(
            f"📡 Propagating mined block {block_data.get('hash', 'UNKNOWN')[:8]}"
        )
