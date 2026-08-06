# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic Consensus module.

These tests require Rust core to be available.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

# Import directly since Rust core is available
from warm_logic.kernel.sys.consensus import (
    Vote,
    BFTEngine,
    BFTProposal,
    ProposalPipeline,
)


class TestVote:
    """Test Vote class."""

    def test_vote_simple_args(self):
        """Vote accepts 3 positional args (block_hash, voter_id, signature)."""
        vote = Vote("block123", "voter1", "sig123")

        assert vote.block_hash == "block123"
        assert vote.voter_id == "voter1"
        assert vote.signature == "sig123"
        assert vote.region == "GLOBAL"
        assert vote.decision == "APPROVE"

    def test_vote_simple_args_with_kwargs(self):
        """Vote accepts kwargs with simple args."""
        vote = Vote(
            "block123",
            "voter1",
            "sig123",
            region="ASIA",
            decision="REJECT",
            timestamp=1234567890.0,
        )

        assert vote.region == "ASIA"
        assert vote.decision == "REJECT"
        assert vote.timestamp == 1234567890.0

    def test_vote_regional_args(self):
        """Vote accepts 5+ positional args for regional consensus."""
        vote = Vote("block123", "voter1", "EUROPE", "APPROVE", "sig123")

        assert vote.block_hash == "block123"
        assert vote.voter_id == "voter1"
        assert vote.region == "EUROPE"
        assert vote.decision == "APPROVE"
        assert vote.signature == "sig123"

    def test_vote_regional_args_with_timestamp(self):
        """Vote accepts 6 args including timestamp."""
        vote = Vote("block123", "voter1", "EUROPE", "APPROVE", "sig123", 1234567890.0)

        assert vote.timestamp == 1234567890.0

    def test_vote_kwargs_only(self):
        """Vote accepts kwargs only."""
        vote = Vote(
            block_hash="block123",
            voter_id="voter1",
            signature="sig123",
            region="ASIA",
            decision="REJECT",
        )

        assert vote.block_hash == "block123"
        assert vote.voter_id == "voter1"
        assert vote.signature == "sig123"
        assert vote.region == "ASIA"
        assert vote.decision == "REJECT"

    def test_vote_has_inner_rust_object(self):
        """Vote creates inner Rust Vote object."""
        vote = Vote("block123", "voter1", "sig123")

        assert vote._inner is not None


class TestBFTEngine:
    """Test BFTEngine class."""

    def test_engine_default_validators(self):
        """BFTEngine initializes with default validators."""
        engine = BFTEngine()

        assert engine.total_validators == 4
        assert engine.min_regions == 1
        # Quorum = (4 * 2 // 3) + 1 = 3
        assert engine.quorum_size == 3

    def test_engine_custom_validators(self):
        """BFTEngine accepts custom validator count."""
        engine = BFTEngine(total_validators=7, min_regions=2)

        assert engine.total_validators == 7
        assert engine.min_regions == 2
        # Quorum = (7 * 2 // 3) + 1 = 5
        assert engine.quorum_size == 5

    def test_engine_has_inner_rust_object(self):
        """BFTEngine creates inner Rust BFTEngine object."""
        engine = BFTEngine()

        assert engine._inner is not None

    def test_submit_vote_below_quorum(self):
        """submit_vote returns False when below quorum."""
        engine = BFTEngine(total_validators=4)

        vote = Vote("block123", "voter1", "sig123")
        result = engine.submit_vote(vote)

        # First vote, below quorum of 3
        assert result is False
        assert "voter1" in engine.votes

    def test_submit_vote_multiple_voters(self):
        """submit_vote tracks multiple voters."""
        engine = BFTEngine(total_validators=4)

        vote1 = Vote("block123", "voter1", "sig1")
        vote2 = Vote("block123", "voter2", "sig2")

        engine.submit_vote(vote1)
        engine.submit_vote(vote2)

        assert "voter1" in engine.votes
        assert "voter2" in engine.votes

    def test_submit_vote_reaches_quorum(self):
        """submit_vote returns True when quorum reached."""
        engine = BFTEngine(total_validators=4, min_regions=1)

        # Need 3 votes for quorum
        vote1 = Vote("block123", "voter1", "sig1")
        vote2 = Vote("block123", "voter2", "sig2")
        vote3 = Vote("block123", "voter3", "sig3")

        engine.submit_vote(vote1)
        engine.submit_vote(vote2)
        result = engine.submit_vote(vote3)

        assert result is True
        assert engine.is_committed("block123") is True

    def test_submit_vote_regional_diversity(self):
        """submit_vote checks regional diversity."""
        engine = BFTEngine(total_validators=4, min_regions=2)

        # All from same region
        vote1 = Vote("block123", "voter1", "GLOBAL", "APPROVE", "sig1")
        vote2 = Vote("block123", "voter2", "GLOBAL", "APPROVE", "sig2")
        vote3 = Vote("block123", "voter3", "GLOBAL", "APPROVE", "sig3")

        engine.submit_vote(vote1)
        engine.submit_vote(vote2)
        result = engine.submit_vote(vote3)

        # Quorum reached but only 1 region, need 2
        assert result is False

    def test_submit_vote_regional_diversity_satisfied(self):
        """submit_vote succeeds with regional diversity."""
        engine = BFTEngine(total_validators=4, min_regions=2)

        vote1 = Vote("block123", "voter1", "ASIA", "APPROVE", "sig1")
        vote2 = Vote("block123", "voter2", "EUROPE", "APPROVE", "sig2")
        vote3 = Vote("block123", "voter3", "ASIA", "APPROVE", "sig3")

        engine.submit_vote(vote1)
        engine.submit_vote(vote2)
        result = engine.submit_vote(vote3)

        # Quorum reached with 2 regions
        assert result is True

    def test_cast_vote_alias(self):
        """cast_vote is alias for submit_vote."""
        engine = BFTEngine(total_validators=4)

        vote = Vote("block123", "voter1", "sig123")
        result = engine.cast_vote(vote)

        assert result is False
        assert "voter1" in engine.votes

    def test_is_committed_true(self):
        """is_committed returns True for committed blocks."""
        engine = BFTEngine(total_validators=4)

        vote1 = Vote("block123", "voter1", "sig1")
        vote2 = Vote("block123", "voter2", "sig2")
        vote3 = Vote("block123", "voter3", "sig3")

        engine.submit_vote(vote1)
        engine.submit_vote(vote2)
        engine.submit_vote(vote3)

        assert engine.is_committed("block123") is True

    def test_is_committed_false(self):
        """is_committed returns False for uncommitted blocks."""
        engine = BFTEngine()

        assert engine.is_committed("nonexistent") is False

    def test_propose(self):
        """propose delegates to Rust engine."""
        engine = BFTEngine()

        # Should not raise
        engine.propose("block123")


class TestBFTProposal:
    """Test BFTProposal dataclass."""

    def test_proposal_fields(self):
        """BFTProposal has expected fields."""
        proposal = BFTProposal(
            proposal_id="prop1",
            target_key="policy:thresholds:drift_max",
            value=0.05,
            proposer="node1",
            signature="sig123",
            timestamp=1234567890.0,
        )

        assert proposal.proposal_id == "prop1"
        assert proposal.target_key == "policy:thresholds:drift_max"
        assert proposal.value == 0.05
        assert proposal.proposer == "node1"
        assert proposal.signature == "sig123"
        assert proposal.timestamp == 1234567890.0


class TestProposalPipeline:
    """Test ProposalPipeline class."""

    def test_pipeline_init(self):
        """ProposalPipeline initializes with node_id."""
        pipeline = ProposalPipeline(node_id="node1")

        assert pipeline.node_id == "node1"
        assert pipeline.active_proposals == {}

    def test_pipeline_custom_quorum(self):
        """ProposalPipeline accepts custom quorum size."""
        pipeline = ProposalPipeline(node_id="node1", quorum_size=5)

        # quorum_size is passed as total_validators to BFTEngine
        assert pipeline.engine.total_validators == 5

    def test_propose_creates_proposal(self):
        """propose creates and stages a proposal."""
        pipeline = ProposalPipeline(node_id="node1")

        prop_id = pipeline.propose(
            target="policy:test",
            value={"setting": True},
        )

        assert prop_id is not None
        assert len(prop_id) == 16  # SHA256 hex truncated
        assert prop_id in pipeline.active_proposals

    def test_propose_custom_id(self):
        """propose accepts custom proposal_id."""
        pipeline = ProposalPipeline(node_id="node1")

        prop_id = pipeline.propose(
            target="policy:test",
            value=100,
            proposal_id="custom_prop_id",
        )

        assert prop_id == "custom_prop_id"
        assert "custom_prop_id" in pipeline.active_proposals

    def test_propose_registers_in_engine(self):
        """propose registers proposal in BFT engine."""
        pipeline = ProposalPipeline(node_id="node1")

        prop_id = pipeline.propose(
            target="policy:test",
            value={"key": "value"},
        )

        # Proposal should be tracked
        assert pipeline.active_proposals[prop_id].target_key == "policy:test"

    def test_receive_vote_below_quorum(self):
        """receive_vote returns False below quorum."""
        pipeline = ProposalPipeline(node_id="node1", quorum_size=4)

        prop_id = pipeline.propose(target="policy:test", value=123)

        result = pipeline.receive_vote(
            {
                "proposal_id": prop_id,
                "voter_id": "voter1",
                "signature": "sig1",
            }
        )

        assert result is False

    def test_receive_vote_commits_on_quorum(self):
        """receive_vote commits proposal on quorum."""
        pipeline = ProposalPipeline(node_id="node1", quorum_size=3)

        prop_id = pipeline.propose(target="policy:test", value=456)

        pipeline.receive_vote(
            {
                "proposal_id": prop_id,
                "voter_id": "voter1",
                "signature": "sig1",
            }
        )
        pipeline.receive_vote(
            {
                "proposal_id": prop_id,
                "voter_id": "voter2",
                "signature": "sig2",
            }
        )
        result = pipeline.receive_vote(
            {
                "proposal_id": prop_id,
                "voter_id": "voter3",
                "signature": "sig3",
            }
        )

        # Quorum reached, should commit
        assert result is True
        # Proposal should be removed after commit
        assert prop_id not in pipeline.active_proposals

    def test_reject_removes_proposal(self):
        """Reject removes proposal from active list."""
        pipeline = ProposalPipeline(node_id="node1")

        prop_id = pipeline.propose(target="policy:test", value=789)
        assert prop_id in pipeline.active_proposals

        pipeline.Reject(prop_id)

        assert prop_id not in pipeline.active_proposals

    def test_reject_nonexistent_proposal(self):
        """Reject handles nonexistent proposal gracefully."""
        pipeline = ProposalPipeline(node_id="node1")

        # Should not raise
        pipeline.Reject("nonexistent_prop_id")

    def test_commit_nonexistent_proposal(self):
        """_commit handles nonexistent proposal gracefully."""
        pipeline = ProposalPipeline(node_id="node1")

        # Should not raise
        pipeline._commit("nonexistent_prop_id")
