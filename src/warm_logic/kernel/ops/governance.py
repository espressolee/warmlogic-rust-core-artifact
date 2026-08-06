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
import math
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

from warm_logic.kernel.sys.consensus import ProposalPipeline

logger = logging.getLogger("Governance")


@dataclass
class Proposal:
    id: str
    proposer: str
    action: str
    params: Dict[str, Any]
    votes_for: float = 0.0
    votes_against: float = 0.0
    deadline: float = 0.0
    status: str = "PENDING"  # PENDING, PASSED, REJECTED, EXECUTED


class QuadraticGovernanceEngine:
    """
    Recursive Law.
    Implements Quadratic Voting to weight consensus by stake while limiting whale dominance.
    Integrated with Speculative BFT Pipeline.
    """

    def __init__(self, token_manager: Any, node_id: str = "local_node"):
        self.token_manager = token_manager
        self.proposals: Dict[str, Proposal] = {}
        self.voters: Dict[str, List[str]] = {}  # prop_id -> list of voter_ids

        # BFT Pipeline
        self.pipeline = ProposalPipeline(node_id)

    def _calculate_voting_power(self, stake_amount: float) -> float:
        """Voting Power = sqrt(Stake). Reduces influence of large holders."""
        if stake_amount <= 0:
            return 0.0
        return math.sqrt(stake_amount)

    def submit_proposal(
        self,
        proposer: str,
        action: str,
        params: Dict[str, Any],
        duration: float = 86400.0,
    ) -> str:
        """
        Submits a new constitutional or protocol amendment.
        Automatically stages it for SPECULATIVE EXECUTION via the BFT Pipeline.
        """
        # 1. Create traditional proposal record
        # Fix collision: timestamp + proposer + random suffix
        prop_id = f"PROP-{int(time.time())}-{proposer[:4]}-{uuid.uuid4().hex[:4]}"
        proposal = Proposal(
            id=prop_id,
            proposer=proposer,
            action=action,
            params=params,
            # Voting window starts after proposal staging succeeds.
            # This prevents immediate expiry when staging/signing is slow.
            deadline=0.0,
        )
        self.proposals[prop_id] = proposal

        # 2. Stage Speculatively (What-If)
        # We assume the 'action' maps to a target key for now.
        target_key = params.get("target_key", f"governance:{action}")
        value = params.get("value", {})

        self.pipeline.propose(target_key, value, proposal_id=prop_id)
        proposal.deadline = time.time() + duration

        logger.info(
            f"📜 [Gov] Proposal {prop_id} submitted & STAGED by {proposer[:8]}: {action}"
        )
        return prop_id

    def cast_vote(self, voter_id: str, prop_id: str, support: bool) -> bool:
        """Casts a quadratic vote based on the voter's current stake."""
        proposal = self.proposals.get(prop_id)
        if not proposal or proposal.status != "PENDING":
            return False

        if time.time() > proposal.deadline:
            proposal.status = "REJECTED"
            return False

        if prop_id not in self.voters:
            self.voters[prop_id] = []

        if voter_id in self.voters[prop_id]:
            logger.warning(f"Voter {voter_id[:8]} already voted on {prop_id}")
            return False

        stake = self.token_manager.get_balance(
            voter_id
        )  # Using liquid for now or staked
        # In reality, we should use 'staked' balance
        power = self._calculate_voting_power(stake)

        if support:
            proposal.votes_for += power
        else:
            proposal.votes_against += power

        self.voters[prop_id].append(voter_id)
        logger.info(
            f"🗳️  [Gov] Node {voter_id[:8]} voted {'FOR' if support else 'AGAINST'} {prop_id} with power {power:.2f}"
        )
        return True

    def tally_and_execute(self, prop_id: str) -> bool:
        """Checks if a proposal passed and prepares it for BFT execution."""
        proposal = self.proposals.get(prop_id)
        if not proposal:
            return False

        if time.time() < proposal.deadline:
            logger.info(f"Proposal {prop_id} is still active.")
            return False

        if proposal.votes_for > proposal.votes_against:
            proposal.status = "PASSED"
            logger.info(
                f"✅ [Gov] Proposal {prop_id} PASSED ({proposal.votes_for:.2f} vs {proposal.votes_against:.2f})"
            )
            return True
        else:
            proposal.status = "REJECTED"
            logger.info(f"[Gov] Proposal {prop_id} REJECTED.")
            return False


class SwarmArbiter:
    """
    Swarm Ethics Arbiter.
    Resolves conflicting proposals by evaluating their 'Ethical Alignment Score'.
    """

    def __init__(self, governance_engine: QuadraticGovernanceEngine):
        self.gov = governance_engine

    def resolve_conflict(self, prop_id_a: str, prop_id_b: str) -> str:
        """
        Compares two conflicting proposals and decides which one to prioritize.
        Returns the winning proposal ID.
        """
        prop_a = self.gov.proposals.get(prop_id_a)
        prop_b = self.gov.proposals.get(prop_id_b)

        if not prop_a or not prop_b:
            return ""

        # Calculate 'Ethical Alignment Score'
        # In a real system, this would query the 'Axiomatic Guard' or 'Constitution'.
        # For Phase 62 verification, we use a simple heuristic based on keywords.

        score_a = self._calculate_ethics_score(prop_a)
        score_b = self._calculate_ethics_score(prop_b)

        logger.info(
            f"⚖️ [Arbiter] Conflict Resolution: {prop_a.action} (Score: {score_a}) vs {prop_b.action} (Score: {score_b})"
        )

        if score_a >= score_b:
            logger.info(f"[Arbiter] Returning Winner: {prop_a.action}")
            return prop_id_a
        else:
            logger.info(f"[Arbiter] Returning Winner: {prop_b.action}")
            return prop_id_b

    def _calculate_ethics_score(self, proposal: Proposal) -> int:
        score = 0
        action = proposal.action.lower()

        # Ethics Heuristics
        if "archive" in action or "save" in action or "protect" in action:
            score += 10  # Preservation is good
        if "delete" in action or "destroy" in action or "purge" in action:
            score -= 5  # Destruction is risky, lower score
        if "optimize" in action or "improve" in action:
            score += 5  # Improvement is good

        # Voting Power influence (the 'Safety Vote')
        score += int(proposal.votes_for - proposal.votes_against)

        return score
