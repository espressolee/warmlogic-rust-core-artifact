//! Conviction Voting System
//!
//! Implements weighted voting with time-locked conviction multipliers.
//! Inspired by Polkadot's conviction voting but adapted for AI governance.
//!
//! Key features:
//! - Stake-weighted voting power
//! - Conviction multipliers (0.1x to 6x based on lock period)
//! - Time-weighted early voting bonus
//! - Delegation support for representative democracy
//! - Integration with BFT consensus for finalization

use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_256};

#[cfg(feature = "std")]
use std::collections::HashMap;

#[cfg(not(feature = "std"))]
use alloc::{collections::BTreeMap as HashMap, string::String, vec::Vec};

/// Conviction level determines the voting power multiplier and lock period.
/// Higher conviction = more voting power but longer lock period.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum Conviction {
    /// No lock, 0.1x voting power
    None = 0,
    /// 1 epoch lock, 1x voting power
    Locked1x = 1,
    /// 2 epoch lock, 2x voting power
    Locked2x = 2,
    /// 4 epoch lock, 3x voting power
    Locked3x = 3,
    /// 8 epoch lock, 4x voting power
    Locked4x = 4,
    /// 16 epoch lock, 5x voting power
    Locked5x = 5,
    /// 32 epoch lock, 6x voting power
    Locked6x = 6,
}

impl Conviction {
    /// Get the voting power multiplier for this conviction level.
    #[must_use]
    pub fn multiplier(&self) -> f64 {
        match self {
            Conviction::None => 0.1,
            Conviction::Locked1x => 1.0,
            Conviction::Locked2x => 2.0,
            Conviction::Locked3x => 3.0,
            Conviction::Locked4x => 4.0,
            Conviction::Locked5x => 5.0,
            Conviction::Locked6x => 6.0,
        }
    }

    /// Get the lock period in epochs for this conviction level.
    #[must_use]
    pub fn lock_period(&self) -> u64 {
        match self {
            Conviction::None => 0,
            Conviction::Locked1x => 1,
            Conviction::Locked2x => 2,
            Conviction::Locked3x => 4,
            Conviction::Locked4x => 8,
            Conviction::Locked5x => 16,
            Conviction::Locked6x => 32,
        }
    }

    /// Parse conviction from u8 value.
    #[must_use]
    pub fn from_u8(value: u8) -> Option<Self> {
        match value {
            0 => Some(Conviction::None),
            1 => Some(Conviction::Locked1x),
            2 => Some(Conviction::Locked2x),
            3 => Some(Conviction::Locked3x),
            4 => Some(Conviction::Locked4x),
            5 => Some(Conviction::Locked5x),
            6 => Some(Conviction::Locked6x),
            _ => None,
        }
    }
}

/// Vote direction
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VoteDirection {
    /// Vote in favor of the proposal
    Aye,
    /// Vote against the proposal
    Nay,
    /// Abstain but count towards quorum
    Abstain,
}

/// A single vote cast by a voter
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vote {
    /// Voter's public key hash
    pub voter_id: [u8; 32],
    /// Direction of the vote
    pub direction: VoteDirection,
    /// Stake amount (in smallest unit)
    pub stake: u64,
    /// Conviction level for lock period
    pub conviction: Conviction,
    /// Epoch when vote was cast
    pub cast_epoch: u64,
    /// Optional delegation chain (empty if direct vote)
    pub delegated_from: Vec<[u8; 32]>,
}

impl Vote {
    /// Calculate the effective voting power.
    /// Formula: stake * conviction_multiplier * early_voting_bonus
    #[must_use]
    pub fn voting_power(&self, current_epoch: u64, voting_end_epoch: u64) -> f64 {
        let base_power = self.stake as f64 * self.conviction.multiplier();

        // Early voting bonus: linear decay from 1.2x at start to 1.0x at end
        let voting_duration = voting_end_epoch.saturating_sub(self.cast_epoch);
        let time_remaining = voting_end_epoch.saturating_sub(current_epoch);

        let early_bonus = if voting_duration > 0 {
            1.0 + 0.2 * (time_remaining as f64 / voting_duration as f64)
        } else {
            1.0
        };

        base_power * early_bonus
    }

    /// Calculate the unlock epoch for this vote.
    #[must_use]
    pub fn unlock_epoch(&self, voting_end_epoch: u64) -> u64 {
        voting_end_epoch + self.conviction.lock_period()
    }
}

/// Proposal status in the governance lifecycle
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProposalStatus {
    /// Proposal is being drafted (not yet submitted)
    Draft,
    /// Proposal submitted and awaiting second
    Pending,
    /// Proposal seconded and in voting period
    Voting,
    /// Voting ended, proposal passed
    Passed,
    /// Voting ended, proposal rejected
    Rejected,
    /// Proposal was vetoed by governance authority
    Vetoed,
    /// Proposal executed successfully
    Executed,
    /// Proposal execution failed
    ExecutionFailed,
}

/// Proposal type determines thresholds and voting periods
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProposalType {
    /// Parameter change (e.g., adjust thresholds)
    ParameterChange,
    /// Policy update (governance rules)
    PolicyUpdate,
    /// Emergency action (fast-track voting)
    Emergency,
    /// Constitutional amendment (high threshold)
    Constitutional,
    /// Spending from treasury
    Spending,
}

impl ProposalType {
    /// Get the required approval threshold (as fraction of total voting power).
    #[must_use]
    pub fn approval_threshold(&self) -> f64 {
        match self {
            ProposalType::ParameterChange => 0.5,
            ProposalType::PolicyUpdate => 0.6,
            ProposalType::Emergency => 0.67,
            ProposalType::Constitutional => 0.75,
            ProposalType::Spending => 0.5,
        }
    }

    /// Get the quorum requirement (minimum participation).
    #[must_use]
    pub fn quorum_threshold(&self) -> f64 {
        match self {
            ProposalType::ParameterChange => 0.1,
            ProposalType::PolicyUpdate => 0.15,
            ProposalType::Emergency => 0.2,
            ProposalType::Constitutional => 0.25,
            ProposalType::Spending => 0.1,
        }
    }

    /// Get the voting period in epochs.
    #[must_use]
    pub fn voting_period(&self) -> u64 {
        match self {
            ProposalType::Emergency => 3, // Fast-track: 3 epochs
            ProposalType::ParameterChange => 7,
            ProposalType::PolicyUpdate => 14,
            ProposalType::Spending => 7,
            ProposalType::Constitutional => 28, // Longest: 28 epochs
        }
    }
}

/// A governance proposal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Proposal {
    /// Unique proposal ID (SHA3 hash of content)
    pub id: [u8; 32],
    /// Proposal type
    pub proposal_type: ProposalType,
    /// Proposer's public key hash
    pub proposer: [u8; 32],
    /// Human-readable title
    pub title: String,
    /// Detailed description (markdown)
    pub description: String,
    /// Hash of the action to execute if passed
    pub action_hash: [u8; 32],
    /// Current status
    pub status: ProposalStatus,
    /// Epoch when proposal was created
    pub created_epoch: u64,
    /// Epoch when voting started (0 if not yet started)
    pub voting_start_epoch: u64,
    /// Number of seconds required (for pending proposals)
    pub seconds_required: u32,
    /// Current seconds received
    pub seconds: Vec<[u8; 32]>,
    /// Votes cast
    pub votes: Vec<Vote>,
    /// Total stake eligible to vote
    pub total_eligible_stake: u64,
}

impl Proposal {
    /// Create a new proposal.
    #[must_use]
    pub fn new(
        proposal_type: ProposalType,
        proposer: [u8; 32],
        title: String,
        description: String,
        action_hash: [u8; 32],
        current_epoch: u64,
        total_eligible_stake: u64,
    ) -> Self {
        // Generate proposal ID
        let mut hasher = Sha3_256::new();
        hasher.update(proposer);
        hasher.update(title.as_bytes());
        hasher.update(current_epoch.to_le_bytes());
        let id: [u8; 32] = hasher.finalize().into();

        let seconds_required = match proposal_type {
            ProposalType::Emergency => 1,
            ProposalType::Constitutional => 5,
            _ => 2,
        };

        Proposal {
            id,
            proposal_type,
            proposer,
            title,
            description,
            action_hash,
            status: ProposalStatus::Pending,
            created_epoch: current_epoch,
            voting_start_epoch: 0,
            seconds_required,
            seconds: Vec::new(),
            votes: Vec::new(),
            total_eligible_stake,
        }
    }

    /// Add a second to the proposal.
    pub fn add_second(&mut self, seconder: [u8; 32]) -> Result<(), &'static str> {
        if self.status != ProposalStatus::Pending {
            return Err("Proposal not in pending status");
        }

        if seconder == self.proposer {
            return Err("Proposer cannot second their own proposal");
        }

        if self.seconds.contains(&seconder) {
            return Err("Already seconded by this account");
        }

        self.seconds.push(seconder);

        // Check if we have enough seconds to start voting
        if self.seconds.len() >= self.seconds_required as usize {
            self.status = ProposalStatus::Voting;
        }

        Ok(())
    }

    /// Start the voting period.
    pub fn start_voting(&mut self, current_epoch: u64) -> Result<(), &'static str> {
        if self.status != ProposalStatus::Pending {
            return Err("Proposal must be in pending status");
        }

        if self.seconds.len() < self.seconds_required as usize {
            return Err("Not enough seconds to start voting");
        }

        self.voting_start_epoch = current_epoch;
        self.status = ProposalStatus::Voting;
        Ok(())
    }

    /// Cast a vote on this proposal.
    pub fn cast_vote(&mut self, vote: Vote, current_epoch: u64) -> Result<(), &'static str> {
        if self.status != ProposalStatus::Voting {
            return Err("Proposal not in voting period");
        }

        let voting_end = self.voting_start_epoch + self.proposal_type.voting_period();
        if current_epoch > voting_end {
            return Err("Voting period has ended");
        }

        // Check for duplicate votes
        if self.votes.iter().any(|v| v.voter_id == vote.voter_id) {
            return Err("Already voted on this proposal");
        }

        self.votes.push(vote);
        Ok(())
    }

    /// Calculate the voting results.
    #[must_use]
    pub fn tally(&self, current_epoch: u64) -> VotingResult {
        let voting_end = self.voting_start_epoch + self.proposal_type.voting_period();

        let mut aye_power = 0.0;
        let mut nay_power = 0.0;
        let mut abstain_power = 0.0;
        let mut total_stake_voted = 0u64;

        for vote in &self.votes {
            let power = vote.voting_power(current_epoch, voting_end);
            total_stake_voted = total_stake_voted.saturating_add(vote.stake);

            match vote.direction {
                VoteDirection::Aye => aye_power += power,
                VoteDirection::Nay => nay_power += power,
                VoteDirection::Abstain => abstain_power += power,
            }
        }

        let total_power = aye_power + nay_power + abstain_power;
        let approval_ratio = if total_power > 0.0 {
            aye_power / (aye_power + nay_power)
        } else {
            0.0
        };

        let turnout = if self.total_eligible_stake > 0 {
            total_stake_voted as f64 / self.total_eligible_stake as f64
        } else {
            0.0
        };

        VotingResult {
            aye_power,
            nay_power,
            abstain_power,
            total_power,
            approval_ratio,
            turnout,
            quorum_met: turnout >= self.proposal_type.quorum_threshold(),
            threshold_met: approval_ratio >= self.proposal_type.approval_threshold(),
        }
    }

    /// Finalize the proposal after voting period ends.
    pub fn finalize(&mut self, current_epoch: u64) -> Result<ProposalStatus, &'static str> {
        if self.status != ProposalStatus::Voting {
            return Err("Proposal not in voting status");
        }

        let voting_end = self.voting_start_epoch + self.proposal_type.voting_period();
        if current_epoch < voting_end {
            return Err("Voting period has not ended");
        }

        let result = self.tally(current_epoch);

        self.status = if result.quorum_met && result.threshold_met {
            ProposalStatus::Passed
        } else {
            ProposalStatus::Rejected
        };

        Ok(self.status)
    }
}

/// Result of tallying votes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VotingResult {
    /// Total voting power for Aye
    pub aye_power: f64,
    /// Total voting power for Nay
    pub nay_power: f64,
    /// Total voting power for Abstain
    pub abstain_power: f64,
    /// Total voting power cast
    pub total_power: f64,
    /// Approval ratio (Aye / (Aye + Nay))
    pub approval_ratio: f64,
    /// Turnout (stake voted / total eligible stake)
    pub turnout: f64,
    /// Whether quorum was met
    pub quorum_met: bool,
    /// Whether approval threshold was met
    pub threshold_met: bool,
}

impl VotingResult {
    /// Check if the proposal passed.
    #[must_use]
    pub fn passed(&self) -> bool {
        self.quorum_met && self.threshold_met
    }
}

/// Delegation record for representative democracy
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Delegation {
    /// Delegator's public key hash
    pub delegator: [u8; 32],
    /// Delegate's public key hash
    pub delegate: [u8; 32],
    /// Stake delegated
    pub stake: u64,
    /// Conviction level for delegated votes
    pub conviction: Conviction,
    /// Epoch when delegation was created
    pub created_epoch: u64,
    /// Optional expiry epoch (0 for no expiry)
    pub expires_epoch: u64,
}

/// Conviction Voting Engine
pub struct ConvictionVotingEngine {
    /// Active proposals by ID
    proposals: HashMap<[u8; 32], Proposal>,
    /// Active delegations by delegator
    delegations: HashMap<[u8; 32], Delegation>,
    /// Locked stakes (voter -> (unlock_epoch, stake))
    locked_stakes: HashMap<[u8; 32], Vec<(u64, u64)>>,
    /// Current epoch
    current_epoch: u64,
    /// Total registered stake in the system
    total_stake: u64,
}

impl Default for ConvictionVotingEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl ConvictionVotingEngine {
    /// Create a new conviction voting engine.
    #[must_use]
    pub fn new() -> Self {
        ConvictionVotingEngine {
            proposals: HashMap::new(),
            delegations: HashMap::new(),
            locked_stakes: HashMap::new(),
            current_epoch: 0,
            total_stake: 0,
        }
    }

    /// Set the total registered stake.
    pub fn set_total_stake(&mut self, stake: u64) {
        self.total_stake = stake;
    }

    /// Advance to the next epoch.
    pub fn advance_epoch(&mut self) {
        self.current_epoch += 1;

        // Clean up expired locks
        for locks in self.locked_stakes.values_mut() {
            locks.retain(|(unlock_epoch, _)| *unlock_epoch > self.current_epoch);
        }

        // Clean up expired delegations
        self.delegations
            .retain(|_, d| d.expires_epoch == 0 || d.expires_epoch > self.current_epoch);
    }

    /// Get the current epoch.
    #[must_use]
    pub fn get_epoch(&self) -> u64 {
        self.current_epoch
    }

    /// Submit a new proposal.
    pub fn submit_proposal(
        &mut self,
        proposal_type: ProposalType,
        proposer: [u8; 32],
        title: String,
        description: String,
        action_hash: [u8; 32],
    ) -> Result<[u8; 32], &'static str> {
        let proposal = Proposal::new(
            proposal_type,
            proposer,
            title,
            description,
            action_hash,
            self.current_epoch,
            self.total_stake,
        );

        let id = proposal.id;
        self.proposals.insert(id, proposal);
        Ok(id)
    }

    /// Get a proposal by ID.
    #[must_use]
    pub fn get_proposal(&self, id: &[u8; 32]) -> Option<&Proposal> {
        self.proposals.get(id)
    }

    /// Get a mutable proposal by ID.
    pub fn get_proposal_mut(&mut self, id: &[u8; 32]) -> Option<&mut Proposal> {
        self.proposals.get_mut(id)
    }

    /// Second a proposal.
    pub fn second_proposal(
        &mut self,
        proposal_id: &[u8; 32],
        seconder: [u8; 32],
    ) -> Result<(), &'static str> {
        let proposal = self
            .proposals
            .get_mut(proposal_id)
            .ok_or("Proposal not found")?;

        proposal.add_second(seconder)?;

        // Auto-start voting if enough seconds
        if proposal.seconds.len() >= proposal.seconds_required as usize
            && proposal.status == ProposalStatus::Voting
            && proposal.voting_start_epoch == 0
        {
            proposal.voting_start_epoch = self.current_epoch;
        }

        Ok(())
    }

    /// Cast a vote on a proposal.
    pub fn vote(
        &mut self,
        proposal_id: &[u8; 32],
        voter_id: [u8; 32],
        direction: VoteDirection,
        stake: u64,
        conviction: Conviction,
    ) -> Result<(), &'static str> {
        // Check available stake
        let locked = self.get_locked_stake(&voter_id);
        if stake > self.total_stake.saturating_sub(locked) {
            return Err("Insufficient unlocked stake");
        }

        let proposal = self
            .proposals
            .get_mut(proposal_id)
            .ok_or("Proposal not found")?;

        let vote = Vote {
            voter_id,
            direction,
            stake,
            conviction,
            cast_epoch: self.current_epoch,
            delegated_from: Vec::new(),
        };

        proposal.cast_vote(vote, self.current_epoch)?;

        // Record the lock
        let voting_end = proposal.voting_start_epoch + proposal.proposal_type.voting_period();
        let unlock_epoch = voting_end + conviction.lock_period();

        self.locked_stakes
            .entry(voter_id)
            .or_default()
            .push((unlock_epoch, stake));

        Ok(())
    }

    /// Create a delegation.
    pub fn delegate(
        &mut self,
        delegator: [u8; 32],
        delegate: [u8; 32],
        stake: u64,
        conviction: Conviction,
        expires_epoch: u64,
    ) -> Result<(), &'static str> {
        if delegator == delegate {
            return Err("Cannot delegate to self");
        }

        // Check for circular delegation
        // would_create_cycle(delegator, delegate): checks if delegate's chain leads back to delegator
        if self.would_create_cycle(delegator, delegate) {
            return Err("Delegation would create cycle");
        }

        let delegation = Delegation {
            delegator,
            delegate,
            stake,
            conviction,
            created_epoch: self.current_epoch,
            expires_epoch,
        };

        self.delegations.insert(delegator, delegation);
        Ok(())
    }

    /// Check if creating a delegation would create a cycle.
    fn would_create_cycle(&self, from: [u8; 32], to: [u8; 32]) -> bool {
        let mut current = to;
        let mut visited = Vec::new();

        while let Some(delegation) = self.delegations.get(&current) {
            if delegation.delegate == from || visited.contains(&delegation.delegate) {
                return true;
            }
            visited.push(current);
            current = delegation.delegate;
        }

        false
    }

    /// Remove a delegation.
    pub fn undelegate(&mut self, delegator: &[u8; 32]) -> Result<(), &'static str> {
        self.delegations
            .remove(delegator)
            .map(|_| ())
            .ok_or("No delegation found")
    }

    /// Get the total locked stake for a voter.
    #[must_use]
    pub fn get_locked_stake(&self, voter_id: &[u8; 32]) -> u64 {
        self.locked_stakes
            .get(voter_id)
            .map(|locks| {
                locks
                    .iter()
                    .filter(|(epoch, _)| *epoch > self.current_epoch)
                    .map(|(_, stake)| *stake)
                    .sum()
            })
            .unwrap_or(0)
    }

    /// Finalize a proposal after voting ends.
    pub fn finalize_proposal(
        &mut self,
        proposal_id: &[u8; 32],
    ) -> Result<ProposalStatus, &'static str> {
        let proposal = self
            .proposals
            .get_mut(proposal_id)
            .ok_or("Proposal not found")?;

        proposal.finalize(self.current_epoch)
    }

    /// Get all active proposals.
    #[must_use]
    pub fn get_active_proposals(&self) -> Vec<&Proposal> {
        self.proposals
            .values()
            .filter(|p| matches!(p.status, ProposalStatus::Pending | ProposalStatus::Voting))
            .collect()
    }

    /// Tally votes for a proposal.
    #[must_use]
    pub fn tally(&self, proposal_id: &[u8; 32]) -> Option<VotingResult> {
        self.proposals
            .get(proposal_id)
            .map(|p| p.tally(self.current_epoch))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_conviction_multipliers() {
        assert!((Conviction::None.multiplier() - 0.1).abs() < 1e-9);
        assert!((Conviction::Locked1x.multiplier() - 1.0).abs() < 1e-9);
        assert!((Conviction::Locked6x.multiplier() - 6.0).abs() < 1e-9);
    }

    #[test]
    fn test_conviction_lock_periods() {
        assert_eq!(Conviction::None.lock_period(), 0);
        assert_eq!(Conviction::Locked1x.lock_period(), 1);
        assert_eq!(Conviction::Locked6x.lock_period(), 32);
    }

    #[test]
    fn test_vote_power_calculation() {
        let vote = Vote {
            voter_id: [1u8; 32],
            direction: VoteDirection::Aye,
            stake: 1000,
            conviction: Conviction::Locked2x,
            cast_epoch: 0,
            delegated_from: Vec::new(),
        };

        // Base power: 1000 * 2.0 = 2000
        // Early voting bonus at start: 1.2x
        let power = vote.voting_power(0, 10);
        assert!((power - 2400.0).abs() < 1e-6);

        // At end: 1.0x bonus
        let power_end = vote.voting_power(10, 10);
        assert!((power_end - 2000.0).abs() < 1e-6);
    }

    #[test]
    fn test_proposal_creation() {
        let proposer = [1u8; 32];
        let proposal = Proposal::new(
            ProposalType::ParameterChange,
            proposer,
            "Test Proposal".to_string(),
            "Description".to_string(),
            [0u8; 32],
            100,
            10000,
        );

        assert_eq!(proposal.status, ProposalStatus::Pending);
        assert_eq!(proposal.seconds_required, 2);
        assert!(proposal.votes.is_empty());
    }

    #[test]
    fn test_proposal_seconding() {
        let mut proposal = Proposal::new(
            ProposalType::ParameterChange,
            [1u8; 32],
            "Test".to_string(),
            "Desc".to_string(),
            [0u8; 32],
            0,
            10000,
        );

        // Can't second your own proposal
        assert!(proposal.add_second([1u8; 32]).is_err());

        // First second
        assert!(proposal.add_second([2u8; 32]).is_ok());
        assert_eq!(proposal.status, ProposalStatus::Pending);

        // Second second triggers voting
        assert!(proposal.add_second([3u8; 32]).is_ok());
        assert_eq!(proposal.status, ProposalStatus::Voting);

        // Can't second twice
        assert!(proposal.add_second([2u8; 32]).is_err());
    }

    #[test]
    fn test_voting_engine_flow() {
        let mut engine = ConvictionVotingEngine::new();
        engine.set_total_stake(10000);

        // Submit proposal
        let proposer = [1u8; 32];
        let proposal_id = engine
            .submit_proposal(
                ProposalType::ParameterChange,
                proposer,
                "Increase threshold".to_string(),
                "Set threshold to 0.9".to_string(),
                [0u8; 32],
            )
            .unwrap();

        // Second the proposal
        engine.second_proposal(&proposal_id, [2u8; 32]).unwrap();
        engine.second_proposal(&proposal_id, [3u8; 32]).unwrap();

        // Cast votes
        engine
            .vote(
                &proposal_id,
                [4u8; 32],
                VoteDirection::Aye,
                5000,
                Conviction::Locked2x,
            )
            .unwrap();
        engine
            .vote(
                &proposal_id,
                [5u8; 32],
                VoteDirection::Nay,
                1000,
                Conviction::Locked1x,
            )
            .unwrap();

        // Check tally
        let result = engine.tally(&proposal_id).unwrap();
        assert!(result.aye_power > result.nay_power);

        // Advance past voting period
        for _ in 0..10 {
            engine.advance_epoch();
        }

        // Finalize
        let status = engine.finalize_proposal(&proposal_id).unwrap();
        assert_eq!(status, ProposalStatus::Passed);
    }

    #[test]
    fn test_delegation() {
        let mut engine = ConvictionVotingEngine::new();

        let delegator = [1u8; 32];
        let delegate = [2u8; 32];

        // Create delegation
        engine
            .delegate(delegator, delegate, 1000, Conviction::Locked1x, 0)
            .unwrap();

        // Can't delegate to self
        assert!(engine
            .delegate([3u8; 32], [3u8; 32], 100, Conviction::None, 0)
            .is_err());

        // Can't create circular delegation
        assert!(engine
            .delegate(delegate, delegator, 100, Conviction::None, 0)
            .is_err());

        // Can remove delegation
        engine.undelegate(&delegator).unwrap();
    }

    #[test]
    fn test_stake_locking() {
        let mut engine = ConvictionVotingEngine::new();
        engine.set_total_stake(10000);

        let voter = [1u8; 32];
        let proposal_id = engine
            .submit_proposal(
                ProposalType::Emergency, // Short voting period
                [2u8; 32],
                "Emergency".to_string(),
                "Urgent fix".to_string(),
                [0u8; 32],
            )
            .unwrap();

        // Second (emergency only needs 1)
        engine.second_proposal(&proposal_id, [3u8; 32]).unwrap();

        // Vote with conviction
        engine
            .vote(
                &proposal_id,
                voter,
                VoteDirection::Aye,
                5000,
                Conviction::Locked4x,
            )
            .unwrap();

        // Stake should be locked
        let locked = engine.get_locked_stake(&voter);
        assert_eq!(locked, 5000);

        // Advance past lock period (3 voting + 8 lock = 11 epochs)
        for _ in 0..15 {
            engine.advance_epoch();
        }

        // Stake should be unlocked
        let locked_after = engine.get_locked_stake(&voter);
        assert_eq!(locked_after, 0);
    }

    #[test]
    fn test_proposal_types_thresholds() {
        assert!((ProposalType::ParameterChange.approval_threshold() - 0.5).abs() < 1e-9);
        assert!((ProposalType::Constitutional.approval_threshold() - 0.75).abs() < 1e-9);

        assert_eq!(ProposalType::Emergency.voting_period(), 3);
        assert_eq!(ProposalType::Constitutional.voting_period(), 28);
    }

    #[test]
    fn test_quorum_not_met() {
        let mut engine = ConvictionVotingEngine::new();
        engine.set_total_stake(100000); // Large total stake

        let proposal_id = engine
            .submit_proposal(
                ProposalType::PolicyUpdate, // 15% quorum required
                [1u8; 32],
                "Test".to_string(),
                "Desc".to_string(),
                [0u8; 32],
            )
            .unwrap();

        // Second
        engine.second_proposal(&proposal_id, [2u8; 32]).unwrap();
        engine.second_proposal(&proposal_id, [3u8; 32]).unwrap();

        // Vote with very small stake (below quorum)
        engine
            .vote(
                &proposal_id,
                [4u8; 32],
                VoteDirection::Aye,
                1000,
                Conviction::Locked1x,
            )
            .unwrap();

        // Advance past voting period
        for _ in 0..20 {
            engine.advance_epoch();
        }

        // Should fail due to quorum
        let status = engine.finalize_proposal(&proposal_id).unwrap();
        assert_eq!(status, ProposalStatus::Rejected);
    }
}
