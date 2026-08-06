"""Tests for QuadraticGovernanceEngine and SwarmArbiter.

Comprehensive tests for:
- Proposal submission and lifecycle
- Quadratic voting mechanics
- Vote casting and tallying
- SwarmArbiter conflict resolution
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


# Mock TokenManager for testing
@dataclass
class MockTokenManager:
    """Mock token manager for testing."""

    balances: Dict[str, float]

    def get_balance(self, address: str) -> float:
        return self.balances.get(address, 0.0)


# Import after mock setup to avoid import errors
from warm_logic.kernel.ops.governance import (
    Proposal,
    QuadraticGovernanceEngine,
    SwarmArbiter,
)

# ============================================================================
# Tests for Proposal Model
# ============================================================================


class TestProposal:
    """Tests for Proposal dataclass."""

    def test_proposal_creation(self):
        """Test proposal creation with defaults."""
        proposal = Proposal(
            id="PROP-001",
            proposer="alice",
            action="upgrade_contract",
            params={"version": "2.0"},
        )

        assert proposal.id == "PROP-001"
        assert proposal.proposer == "alice"
        assert proposal.action == "upgrade_contract"
        assert proposal.votes_for == 0.0
        assert proposal.votes_against == 0.0
        assert proposal.status == "PENDING"

    def test_proposal_with_votes(self):
        """Test proposal with vote counts."""
        proposal = Proposal(
            id="PROP-002",
            proposer="bob",
            action="mint_tokens",
            params={"amount": 1000},
            votes_for=10.5,
            votes_against=5.2,
        )

        assert proposal.votes_for == 10.5
        assert proposal.votes_against == 5.2


# ============================================================================
# Tests for Quadratic Voting Power Calculation
# ============================================================================


class TestQuadraticVotingPower:
    """Tests for quadratic voting power calculation."""

    def test_voting_power_sqrt(self):
        """Test voting power is sqrt of stake."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)

        power = engine._calculate_voting_power(100.0)
        assert power == pytest.approx(10.0)

    def test_voting_power_zero_stake(self):
        """Test zero stake gives zero power."""
        token_manager = MockTokenManager(balances={})
        engine = QuadraticGovernanceEngine(token_manager)

        power = engine._calculate_voting_power(0.0)
        assert power == 0.0

    def test_voting_power_negative_stake(self):
        """Test negative stake gives zero power."""
        token_manager = MockTokenManager(balances={})
        engine = QuadraticGovernanceEngine(token_manager)

        power = engine._calculate_voting_power(-50.0)
        assert power == 0.0

    def test_quadratic_reduces_whale_influence(self):
        """Test quadratic voting reduces whale dominance."""
        token_manager = MockTokenManager(balances={})
        engine = QuadraticGovernanceEngine(token_manager)

        # Small holder with 100 tokens
        small_power = engine._calculate_voting_power(100.0)
        # Whale with 10000 tokens (100x more)
        whale_power = engine._calculate_voting_power(10000.0)

        # Whale has 10x power, not 100x (sqrt relationship)
        assert whale_power / small_power == pytest.approx(10.0)


# ============================================================================
# Tests for Proposal Submission
# ============================================================================


class TestProposalSubmission:
    """Tests for proposal submission."""

    def test_submit_proposal_creates_id(self):
        """Test submitting a proposal creates unique ID."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)

        prop_id = engine.submit_proposal(
            proposer="alice",
            action="upgrade",
            params={"target_key": "governance:upgrade", "value": {}},
        )

        assert prop_id.startswith("PROP-")
        assert prop_id in engine.proposals

    def test_submit_proposal_stores_details(self):
        """Test proposal details are stored correctly."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)

        prop_id = engine.submit_proposal(
            proposer="alice",
            action="mint",
            params={"amount": 1000},
            duration=3600.0,
        )

        proposal = engine.proposals[prop_id]
        assert proposal.proposer == "alice"
        assert proposal.action == "mint"
        assert proposal.params["amount"] == 1000
        assert proposal.status == "PENDING"

    def test_submit_multiple_proposals(self):
        """Test submitting multiple proposals creates unique IDs."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)

        prop_ids = []
        for i in range(5):
            prop_id = engine.submit_proposal(
                proposer=f"proposer_{i}",
                action=f"action_{i}",
                params={},
            )
            prop_ids.append(prop_id)

        # All IDs should be unique
        assert len(set(prop_ids)) == 5

    def test_duration_window_starts_after_staging_delay(self):
        """Slow staging must not cause immediate proposal expiry."""
        token_manager = MockTokenManager(balances={"alice": 100.0, "bob": 64.0})
        engine = QuadraticGovernanceEngine(token_manager)
        original_propose = engine.pipeline.propose

        def delayed_propose(*args, **kwargs):
            time.sleep(0.12)
            return original_propose(*args, **kwargs)

        with patch.object(engine.pipeline, "propose", side_effect=delayed_propose):
            prop_id = engine.submit_proposal(
                proposer="alice",
                action="test",
                params={},
                duration=0.05,
            )

        assert engine.cast_vote("bob", prop_id, support=True) is True


# ============================================================================
# Tests for Vote Casting
# ============================================================================


class TestVoteCasting:
    """Tests for vote casting mechanics."""

    def test_cast_vote_for(self):
        """Test casting a vote for a proposal."""
        token_manager = MockTokenManager(balances={"alice": 100.0, "bob": 64.0})
        engine = QuadraticGovernanceEngine(token_manager)

        prop_id = engine.submit_proposal(
            proposer="alice",
            action="test",
            params={},
            duration=3600.0,
        )

        result = engine.cast_vote("bob", prop_id, support=True)

        assert result is True
        proposal = engine.proposals[prop_id]
        assert proposal.votes_for == pytest.approx(8.0)  # sqrt(64) = 8

    def test_cast_vote_against(self):
        """Test casting a vote against a proposal."""
        token_manager = MockTokenManager(balances={"alice": 100.0, "charlie": 25.0})
        engine = QuadraticGovernanceEngine(token_manager)

        prop_id = engine.submit_proposal(
            proposer="alice",
            action="test",
            params={},
            duration=3600.0,
        )

        result = engine.cast_vote("charlie", prop_id, support=False)

        assert result is True
        proposal = engine.proposals[prop_id]
        assert proposal.votes_against == pytest.approx(5.0)  # sqrt(25) = 5

    def test_duplicate_vote_rejected(self):
        """Test duplicate votes are rejected."""
        token_manager = MockTokenManager(balances={"alice": 100.0, "bob": 64.0})
        engine = QuadraticGovernanceEngine(token_manager)

        prop_id = engine.submit_proposal(
            proposer="alice",
            action="test",
            params={},
            duration=3600.0,
        )

        # First vote succeeds
        result1 = engine.cast_vote("bob", prop_id, support=True)
        assert result1 is True

        # Second vote fails
        result2 = engine.cast_vote("bob", prop_id, support=False)
        assert result2 is False

        # Vote count unchanged
        proposal = engine.proposals[prop_id]
        assert proposal.votes_for == pytest.approx(8.0)

    def test_vote_on_nonexistent_proposal(self):
        """Test voting on non-existent proposal fails."""
        token_manager = MockTokenManager(balances={"bob": 64.0})
        engine = QuadraticGovernanceEngine(token_manager)

        result = engine.cast_vote("bob", "PROP-NONEXISTENT", support=True)

        assert result is False

    def test_vote_on_expired_proposal(self):
        """Test voting on expired proposal fails."""
        token_manager = MockTokenManager(balances={"alice": 100.0, "bob": 64.0})
        engine = QuadraticGovernanceEngine(token_manager)

        prop_id = engine.submit_proposal(
            proposer="alice",
            action="test",
            params={},
            duration=0.0,  # Expires immediately
        )

        # Wait a tiny bit to ensure expiration
        time.sleep(0.01)

        result = engine.cast_vote("bob", prop_id, support=True)

        assert result is False

    def test_multiple_voters(self):
        """Test multiple voters accumulate votes."""
        token_manager = MockTokenManager(
            balances={
                "alice": 100.0,
                "bob": 64.0,
                "charlie": 25.0,
                "dave": 16.0,
            }
        )
        engine = QuadraticGovernanceEngine(token_manager)

        prop_id = engine.submit_proposal(
            proposer="alice",
            action="test",
            params={},
            duration=3600.0,
        )

        engine.cast_vote("bob", prop_id, support=True)  # 8
        engine.cast_vote("charlie", prop_id, support=True)  # 5
        engine.cast_vote("dave", prop_id, support=False)  # 4

        proposal = engine.proposals[prop_id]
        assert proposal.votes_for == pytest.approx(13.0)  # 8 + 5
        assert proposal.votes_against == pytest.approx(4.0)


# ============================================================================
# Tests for Proposal Tallying
# ============================================================================


class TestProposalTallying:
    """Tests for proposal tallying and execution."""

    def test_tally_active_proposal(self):
        """Test tallying returns false for active proposals."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)

        prop_id = engine.submit_proposal(
            proposer="alice",
            action="test",
            params={},
            duration=3600.0,  # 1 hour
        )

        result = engine.tally_and_execute(prop_id)

        assert result is False
        assert engine.proposals[prop_id].status == "PENDING"

    def test_tally_nonexistent_proposal(self):
        """Test tallying non-existent proposal returns false."""
        token_manager = MockTokenManager(balances={})
        engine = QuadraticGovernanceEngine(token_manager)

        result = engine.tally_and_execute("PROP-NONEXISTENT")

        assert result is False


# ============================================================================
# Tests for SwarmArbiter
# ============================================================================


class TestSwarmArbiter:
    """Tests for SwarmArbiter conflict resolution."""

    def test_arbiter_initialization(self):
        """Test arbiter initialization with governance engine."""
        token_manager = MockTokenManager(balances={})
        engine = QuadraticGovernanceEngine(token_manager)
        arbiter = SwarmArbiter(engine)

        assert arbiter.gov is engine

    def test_ethics_score_preservation_bonus(self):
        """Test preservation actions get bonus score."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)
        arbiter = SwarmArbiter(engine)

        archive_prop = Proposal(
            id="PROP-1",
            proposer="alice",
            action="archive_data",
            params={},
        )
        delete_prop = Proposal(
            id="PROP-2",
            proposer="alice",
            action="delete_data",
            params={},
        )

        archive_score = arbiter._calculate_ethics_score(archive_prop)
        delete_score = arbiter._calculate_ethics_score(delete_prop)

        assert archive_score > delete_score

    def test_ethics_score_improvement_bonus(self):
        """Test improvement actions get bonus score."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)
        arbiter = SwarmArbiter(engine)

        optimize_prop = Proposal(
            id="PROP-1",
            proposer="alice",
            action="optimize_system",
            params={},
        )
        normal_prop = Proposal(
            id="PROP-2",
            proposer="alice",
            action="normal_action",
            params={},
        )

        optimize_score = arbiter._calculate_ethics_score(optimize_prop)
        normal_score = arbiter._calculate_ethics_score(normal_prop)

        assert optimize_score > normal_score

    def test_resolve_conflict_with_votes(self):
        """Test conflict resolution considers vote difference."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)
        arbiter = SwarmArbiter(engine)

        prop_id_a = engine.submit_proposal(
            proposer="alice",
            action="action_a",
            params={},
        )
        prop_id_b = engine.submit_proposal(
            proposer="alice",
            action="action_b",
            params={},
        )

        # Give prop_a more votes
        engine.proposals[prop_id_a].votes_for = 100.0
        engine.proposals[prop_id_b].votes_for = 50.0

        winner = arbiter.resolve_conflict(prop_id_a, prop_id_b)

        assert winner == prop_id_a

    def test_resolve_conflict_nonexistent_proposal(self):
        """Test conflict resolution with non-existent proposal."""
        token_manager = MockTokenManager(balances={"alice": 100.0})
        engine = QuadraticGovernanceEngine(token_manager)
        arbiter = SwarmArbiter(engine)

        prop_id_a = engine.submit_proposal(
            proposer="alice",
            action="action_a",
            params={},
        )

        winner = arbiter.resolve_conflict(prop_id_a, "PROP-NONEXISTENT")

        assert winner == ""


# ============================================================================
# Integration Tests
# ============================================================================


class TestGovernanceIntegration:
    """Integration tests for governance workflow."""

    def test_full_proposal_lifecycle(self):
        """Test complete proposal lifecycle."""
        token_manager = MockTokenManager(
            balances={
                "proposer": 100.0,
                "voter1": 64.0,
                "voter2": 36.0,
                "voter3": 16.0,
            }
        )
        engine = QuadraticGovernanceEngine(token_manager)

        # 1. Submit proposal
        prop_id = engine.submit_proposal(
            proposer="proposer",
            action="upgrade_protocol",
            params={"version": "2.0"},
            duration=0.1,  # Short duration for test
        )

        # 2. Cast votes
        engine.cast_vote("voter1", prop_id, support=True)  # +8
        engine.cast_vote("voter2", prop_id, support=True)  # +6
        engine.cast_vote("voter3", prop_id, support=False)  # -4

        # 3. Verify vote counts
        proposal = engine.proposals[prop_id]
        assert proposal.votes_for == pytest.approx(14.0)  # 8 + 6
        assert proposal.votes_against == pytest.approx(4.0)

        # 4. Wait for deadline and tally
        time.sleep(0.15)
        passed = engine.tally_and_execute(prop_id)

        assert passed is True
        assert engine.proposals[prop_id].status == "PASSED"

    def test_rejected_proposal(self):
        """Test proposal rejection workflow."""
        token_manager = MockTokenManager(
            balances={
                "proposer": 100.0,
                "voter1": 16.0,  # 4 votes
                "voter2": 64.0,  # 8 votes
                "voter3": 100.0,  # 10 votes
            }
        )
        engine = QuadraticGovernanceEngine(token_manager)

        # Submit proposal
        prop_id = engine.submit_proposal(
            proposer="proposer",
            action="controversial_action",
            params={},
            duration=0.1,
        )

        # More votes against
        engine.cast_vote("voter1", prop_id, support=True)  # +4
        engine.cast_vote("voter2", prop_id, support=False)  # -8
        engine.cast_vote("voter3", prop_id, support=False)  # -10

        # Wait and tally
        time.sleep(0.15)
        passed = engine.tally_and_execute(prop_id)

        assert passed is False
        assert engine.proposals[prop_id].status == "REJECTED"
