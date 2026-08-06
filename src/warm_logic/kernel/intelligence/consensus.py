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
[Phase 104.2] Multi-Agent Consensus Protocol.
Implements Byzantine-fault-tolerant consensus for agent decisions.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Consensus")


class VoteType(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass
class Vote:
    """A vote from an agent."""

    agent_id: str
    vote_type: VoteType
    reason: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConsensusRound:
    """A single consensus round."""

    round_id: str
    proposal: str
    proposer: str
    votes: List[Vote] = field(default_factory=list)
    outcome: Optional[str] = None
    finalized: bool = False


class ConsensusProtocol:
    """
    [Phase 104.2] Multi-Agent Consensus.

    Implements:
    1. Proposal submission
    2. Voting mechanism
    3. Quorum requirements
    4. Byzantine fault tolerance (2/3 majority)
    5. Finality
    """

    def __init__(self, agents: List[str] = None, quorum_ratio: float = 0.67):
        self.agents = agents or ["Scholar", "Engineer", "Auditor", "Architect"]
        self.quorum_ratio = quorum_ratio
        self.rounds: Dict[str, ConsensusRound] = {}
        self._round_counter = 0
        logger.info(f"[Consensus] Protocol Active with {len(self.agents)} agents.")

    def _generate_round_id(self, proposal: str) -> str:
        """Generate unique round ID."""
        self._round_counter += 1
        hash_input = f"{proposal}:{self._round_counter}:{datetime.now().isoformat()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:12]

    def propose(self, proposal: str, proposer: str) -> ConsensusRound:
        """Submit a proposal for consensus."""
        round_id = self._generate_round_id(proposal)

        consensus_round = ConsensusRound(
            round_id=round_id, proposal=proposal, proposer=proposer
        )
        self.rounds[round_id] = consensus_round

        logger.info(f"[Consensus] Proposal submitted: {proposal[:50]}...")
        return consensus_round

    def vote(
        self,
        round_id: str,
        agent_id: str,
        vote_type: VoteType,
        reason: str = "",
        confidence: float = 0.8,
    ) -> bool:
        """Cast a vote in a consensus round."""
        if round_id not in self.rounds:
            logger.error(f"Round {round_id} not found")
            return False

        round_obj = self.rounds[round_id]
        if round_obj.finalized:
            logger.warning(f"Round {round_id} already finalized")
            return False

        # Check if agent already voted
        existing_votes = [v for v in round_obj.votes if v.agent_id == agent_id]
        if existing_votes:
            logger.warning(f"Agent {agent_id} already voted")
            return False

        vote = Vote(
            agent_id=agent_id, vote_type=vote_type, reason=reason, confidence=confidence
        )
        round_obj.votes.append(vote)

        logger.debug(f"Vote cast: {agent_id} -> {vote_type.value}")
        return True

    def check_quorum(self, round_id: str) -> Dict[str, Any]:
        """Check if quorum is reached."""
        if round_id not in self.rounds:
            return {"reached": False, "reason": "round_not_found"}

        round_obj = self.rounds[round_id]
        total_agents = len(self.agents)
        votes_cast = len(round_obj.votes)

        quorum_needed = int(total_agents * self.quorum_ratio)
        quorum_reached = votes_cast >= quorum_needed

        return {
            "reached": quorum_reached,
            "votes_cast": votes_cast,
            "quorum_needed": quorum_needed,
            "total_agents": total_agents,
            "participation": votes_cast / total_agents,
        }

    def finalize(self, round_id: str) -> Dict[str, Any]:
        """Finalize a consensus round and determine outcome."""
        if round_id not in self.rounds:
            return {"success": False, "error": "round_not_found"}

        round_obj = self.rounds[round_id]
        if round_obj.finalized:
            return {
                "success": False,
                "error": "already_finalized",
                "outcome": round_obj.outcome,
            }

        quorum = self.check_quorum(round_id)
        if not quorum["reached"]:
            return {"success": False, "error": "quorum_not_reached", **quorum}

        # Count votes
        approvals = sum(1 for v in round_obj.votes if v.vote_type == VoteType.APPROVE)
        rejections = sum(1 for v in round_obj.votes if v.vote_type == VoteType.REJECT)
        abstentions = sum(1 for v in round_obj.votes if v.vote_type == VoteType.ABSTAIN)

        # Byzantine fault tolerance: need 2/3 majority
        total_decisive = approvals + rejections
        if total_decisive == 0:
            outcome = "no_decision"
        elif approvals / max(total_decisive, 1) >= self.quorum_ratio:
            outcome = "approved"
        elif rejections / max(total_decisive, 1) >= self.quorum_ratio:
            outcome = "rejected"
        else:
            outcome = "inconclusive"

        round_obj.outcome = outcome
        round_obj.finalized = True

        logger.info(f"[Consensus] Round {round_id} finalized: {outcome}")

        return {
            "success": True,
            "round_id": round_id,
            "outcome": outcome,
            "votes": {
                "approve": approvals,
                "reject": rejections,
                "abstain": abstentions,
            },
            "participation": quorum["participation"],
        }

    def quick_consensus(
        self, proposal: str, agent_opinions: Dict[str, VoteType]
    ) -> Dict[str, Any]:
        """Run a quick consensus with predefined agent opinions."""
        # Create round
        round_obj = self.propose(proposal, "System")

        # Cast votes
        for agent_id, opinion in agent_opinions.items():
            self.vote(
                round_obj.round_id,
                agent_id,
                opinion,
                reason=f"Agent {agent_id} opinion",
            )

        # Finalize
        return self.finalize(round_obj.round_id)

    def simulate_consensus(self, proposal: str) -> Dict[str, Any]:
        """Simulate a full consensus round with default agent behaviors."""
        round_obj = self.propose(proposal, "Architect")

        # Simulate each agent voting based on their role
        role_behaviors = {
            "Scholar": (VoteType.APPROVE, 0.8),  # Researchers tend to approve
            "Engineer": (VoteType.APPROVE, 0.85),  # Engineers approve if feasible
            "Auditor": (VoteType.ABSTAIN, 0.6),  # Auditors are cautious
            "Architect": (VoteType.APPROVE, 0.9),  # Proposer supports
        }

        for agent in self.agents:
            vote_type, confidence = role_behaviors.get(agent, (VoteType.APPROVE, 0.7))
            self.vote(round_obj.round_id, agent, vote_type, confidence=confidence)

        return self.finalize(round_obj.round_id)

    def get_history(self) -> List[Dict]:
        """Get history of consensus rounds."""
        return [
            {
                "round_id": r.round_id,
                "proposal": r.proposal[:50],
                "outcome": r.outcome,
                "votes": len(r.votes),
            }
            for r in self.rounds.values()
            if r.finalized
        ]


def get_consensus(agents: List[str] = None) -> ConsensusProtocol:
    """Get a new Consensus Protocol."""
    return ConsensusProtocol(agents)
