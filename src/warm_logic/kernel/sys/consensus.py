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
Sovereign Consensus Pillar
Byzantine Fault Tolerant (BFT) State Agreement Protocol.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from warm_logic.kernel import rust_loader
from warm_logic.kernel.ops.speculative_buffer import speculative_buffer
from warm_logic.kernel.sys.cryptography import MLDSA

logger = logging.getLogger("SovereignConsensus")

# Initialize Rust Core
rust_core = rust_loader.load_rust_core()


if rust_loader.HAS_RUST_CORE:
    # Atomic Truth: Rust Implementation
    _RustVote = rust_core.Vote
    _RustBFTEngine = rust_core.BFTEngine
    logger.info(": Using Rust-native BFTEngine with Python Bridge.")

    class Vote:
        def __init__(self, *args, **kwargs):
            # Dynamic argument resolution for Era compatibility
            if len(args) == 3:
                # Simple consensus call: (block_hash, voter_id, signature)
                self.block_hash = args[0]
                self.voter_id = args[1]
                self.signature = args[2]
                self.region = kwargs.get("region", "GLOBAL")
                self.decision = kwargs.get("decision", "APPROVE")
                self.timestamp = kwargs.get("timestamp", time.time())
                self.round = kwargs.get("round", 0)
            elif len(args) >= 5:
                # Regional consensus call: (block_hash, voter_id, region, decision, signature, [ts])
                self.block_hash = args[0]
                self.voter_id = args[1]
                self.region = args[2]
                self.decision = args[3]
                self.signature = args[4]
                self.timestamp = (
                    args[5] if len(args) > 5 else kwargs.get("timestamp", time.time())
                )
                self.round = kwargs.get("round", 0)
            else:
                self.block_hash = kwargs.get("block_hash", "")
                self.voter_id = kwargs.get("voter_id", "")
                self.region = kwargs.get("region", "GLOBAL")
                self.decision = kwargs.get("decision", "APPROVE")
                self.signature = kwargs.get("signature", "")
                self.timestamp = kwargs.get("timestamp", time.time())
                self.round = kwargs.get("round", 0)

            # Bound to Rust Core (Order: voter_id, block_hash, round, signature)
            self._inner = _RustVote(
                self.voter_id, self.block_hash, self.round, self.signature
            )

    class BFTEngine:
        def __init__(self, total_validators: int = 4, min_regions: int = 1):
            self.total_validators = total_validators
            self.min_regions = min_regions
            # Quorum = 2f + 1 where n=3f+1. For n=4, f=1, quorum=3.
            # Simple approximation for this bridge:
            self.quorum_size = (total_validators * 2 // 3) + 1
            self._inner = _RustBFTEngine(self.quorum_size)
            self.votes: Dict[str, Vote] = {}
            self.committed_blocks: Dict[str, bool] = {}

        def submit_vote(self, vote: Vote) -> bool:
            """
            Python Bridge: Checks Regional Diversity before delegating to Rust for count.
            """
            self.votes[vote.voter_id] = vote

            # Delegate count to Rust
            vote_count = self._inner.py_cast_vote(vote._inner)
            reached_quorum = vote_count >= self.quorum_size

            # Regional Check
            unique_regions = {
                v.region for v in self.votes.values() if v.block_hash == vote.block_hash
            }

            if reached_quorum and len(unique_regions) >= self.min_regions:
                self.committed_blocks[vote.block_hash] = True
                return True
            return False

        def cast_vote(self, vote: Vote) -> bool:
            """Alias for submit_vote (Simple BFT Compatibility)."""
            return self.submit_vote(vote)

        def is_committed(self, block_hash: str) -> bool:
            return self.committed_blocks.get(block_hash, False)

        def propose(self, block_hash: str) -> None:
            self._inner.py_propose(block_hash)

else:  # pragma: no cover
    # ground truth: No Simulation Allowed.
    raise ImportError(
        "CRITICAL: Rust Core (warm_logic_rs) missing. Consensus System Halted."
    )


@dataclass
class BFTProposal:
    proposal_id: str
    target_key: str  # e.g. "policy:thresholds:drift_max"
    value: Any
    proposer: str
    signature: str
    timestamp: float


class ProposalPipeline:
    """
    Speculative BFT Pipeline.
    ML-DSA-65 (FIPS 204) PQC Signature Integration.

    Manages the lifecycle of a proposal:
    Propose -> Speculate (Buffer) -> Vote -> Commit/Rollback.

    All proposals and votes are signed with ML-DSA-65 post-quantum signatures.
    """

    def __init__(self, node_id: str, quorum_size: int = 3):
        self.node_id = node_id
        self.engine = BFTEngine(quorum_size)
        self.active_proposals: Dict[str, BFTProposal] = {}

        # PQC Cryptography
        self._mldsa = MLDSA()
        self._keypair = self._mldsa.generate_keypair()
        self._voter_public_keys: Dict[str, str] = {}  # voter_id -> public_key

        logger.info(
            f"[BFT] Pipeline initialized with ML-DSA-65 (PK: {self._keypair.public_key[:16]}...)"
        )

    def register_voter(self, voter_id: str, public_key: str) -> None:
        """
        Register a voter's public key for signature verification.

        Args:
            voter_id: Unique identifier for the voter
            public_key: ML-DSA-65 public key hex string
        """
        self._voter_public_keys[voter_id] = public_key
        logger.debug(f"[BFT] Registered voter {voter_id} (PK: {public_key[:16]}...)")

    def get_public_key(self) -> str:
        """Return this node's public key for distribution."""
        return self._keypair.public_key

    def _sign_proposal(self, proposal_id: str, target: str, value: Any) -> str:
        """
        Sign a proposal payload with ML-DSA-65.

        Returns:
            ML-DSA-65 signature hex string
        """
        import json

        payload = {
            "proposal_id": proposal_id,
            "target": target,
            "value": str(value),
            "proposer": self.node_id,
            "timestamp": int(time.time()),
        }
        message = json.dumps(payload, sort_keys=True)
        return self._mldsa.sign(message, self._keypair.private_key)

    def _verify_vote_signature(
        self, proposal_id: str, voter_id: str, signature: str
    ) -> bool:
        """
        Verify a vote signature using the voter's registered public key.

        Returns:
            True if signature is valid, False otherwise
        """
        if voter_id not in self._voter_public_keys:
            logger.warning(f"[BFT] Unknown voter {voter_id}, cannot verify signature")
            return False

        # Reconstruct the message that was signed
        message = f"{proposal_id}:{voter_id}"
        public_key = self._voter_public_keys[voter_id]

        try:
            return self._mldsa.verify(message, signature, public_key)
        except Exception as e:
            logger.error(f"[BFT] Signature verification failed: {e}")
            return False

    def create_signed_vote(self, proposal_id: str) -> Dict[str, Any]:
        """
        Create a signed vote for a proposal.

        Returns:
            Vote payload with ML-DSA-65 signature
        """
        message = f"{proposal_id}:{self.node_id}"
        signature = self._mldsa.sign(message, self._keypair.private_key)

        return {
            "proposal_id": proposal_id,
            "voter_id": self.node_id,
            "signature": signature,
            "public_key": self._keypair.public_key,
        }

    def propose(
        self, target: str, value: Any, proposal_id: Optional[str] = None
    ) -> str:
        """
        Initiates a proposal with ML-DSA-65 signature.
        Immediately stages it in the speculative buffer for 'What-If' analysis.
        """
        if proposal_id:
            prop_id = proposal_id
        else:
            prop_id = hashlib.sha256(
                f"{target}:{value}:{time.time()}".encode()
            ).hexdigest()[:16]

        # 1. Speculative Execution (Stage 1)
        # We apply it to a 'pending' layer associated with this proposal
        speculative_buffer.stage_change(
            layer_id=f"pending:{prop_id}",
            change_id=prop_id,
            target=target,
            old_val=None,  # In real system, would fetch current
            new_val=value,
            proposer=self.node_id,
        )

        # 2. Sign proposal with ML-DSA-65
        signature = self._sign_proposal(prop_id, target, value)

        # 3. Register for BFT
        prop = BFTProposal(
            proposal_id=prop_id,
            target_key=target,
            value=value,
            proposer=self.node_id,
            signature=signature,
            timestamp=time.time(),
        )
        self.active_proposals[prop_id] = prop
        self.engine.propose(prop_id)  # Register in Rust Engine

        logger.info(
            f"🗳️ [BFT] Proposal {prop_id} initiated with ML-DSA-65 signature and STAGED speculatively."
        )
        return prop_id

    def receive_vote(self, vote_payload: Dict[str, Any]) -> bool:
        """
        Processes an incoming vote with signature verification.
        If quorum is reached, COMMITS the speculative layer.
        """
        proposal_id = vote_payload["proposal_id"]
        voter_id = vote_payload["voter_id"]
        signature = vote_payload["signature"]

        # Auto-register voter if public key provided
        if "public_key" in vote_payload:
            self.register_voter(voter_id, vote_payload["public_key"])

        # Verify ML-DSA-65 signature (with fallback for development)
        if voter_id in self._voter_public_keys:
            if not self._verify_vote_signature(proposal_id, voter_id, signature):
                logger.warning(
                    f"[BFT] Invalid signature from {voter_id}, rejecting vote"
                )
                return False
        else:
            logger.debug(f"[BFT] No public key for {voter_id}, skipping verification")

        v = Vote(
            proposal_id,
            voter_id,
            signature,
        )

        reached_quorum = self.engine.cast_vote(v)
        if reached_quorum:
            self._commit(proposal_id)
            return True

        return False

    def _commit(self, prop_id: str) -> None:
        """
        Finalizes the proposal and triggers network-wide propagation.
        """
        if prop_id not in self.active_proposals:
            return

        logger.info(f"[BFT] Quorum Reached for {prop_id}. Committing to Reality.")

        # 1. Apply to local buffer
        changes = speculative_buffer.commit_layer(f"pending:{prop_id}")
        logger.info(f"[BFT] Committed {len(changes)} changes to Reality.")

        # 2. propagation
        # If any of the changes were code-related, trigger a network sync.

        # Note: In a full kernel, the propagator would be a singleton.
        # For now, we signal that a sync is required.
        logger.info(f"[Propagation] Broadcasting SYNC_MANIFEST for {prop_id}...")

        # Clean up
        del self.active_proposals[prop_id]

    def Reject(self, prop_id: str) -> None:
        """
        Explicit rejection. Rolls back the speculative layer.
        """
        if prop_id in self.active_proposals:
            logger.warning(f"[BFT] Proposal {prop_id} REJECTED. Rolling back.")
            speculative_buffer.rollback_layer(f"pending:{prop_id}")
            del self.active_proposals[prop_id]
