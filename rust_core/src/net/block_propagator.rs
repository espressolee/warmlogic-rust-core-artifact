//! rust_core/src/net/block_propagator.rs
//! P2P Block Propagation Engine.
//!
//! Implements the block propagation layer for distributed consensus:
//! - Block proposal broadcasting from leader
//! - Vote collection and aggregation
//! - Commit announcement with quorum proof
//! - View change coordination

use crate::net::gossip::{
    BlockCommit, BlockProposal, BlockVote, GossipMessage, P2PNewView, P2PViewChange,
};
use crate::net::kademlia::NodeId;
use std::collections::{HashMap, HashSet};

#[cfg(feature = "python")]
use pyo3::prelude::*;

// ============================================================================
// CONSTANTS
// ============================================================================

/// Minimum votes required for quorum (2f+1 where f = (n-1)/3)
#[must_use]
pub fn quorum_threshold(total_validators: usize) -> usize {
    let f = (total_validators.saturating_sub(1)) / 3;
    2 * f + 1
}

/// Maximum block size in bytes (4 MB)
pub const MAX_BLOCK_SIZE: usize = 4_194_304;

/// Maximum votes to collect per round
pub const MAX_VOTES_PER_ROUND: usize = 1000;

/// View change timeout multiplier (exponential backoff)
pub const VIEW_CHANGE_TIMEOUT_MULTIPLIER: u64 = 2;

// ============================================================================
// BLOCK PROPAGATION STATE
// ============================================================================

/// State of a block in the propagation pipeline
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BlockState {
    /// Block proposed, waiting for votes
    Proposed,
    /// Enough votes collected (quorum reached)
    Prepared,
    /// Block committed to ledger
    Committed,
    /// Block rejected (conflicting block committed)
    Rejected,
}

/// Pending block waiting for votes
#[derive(Debug, Clone)]
pub struct PendingBlock {
    pub proposal: BlockProposal,
    pub votes: Vec<BlockVote>,
    pub state: BlockState,
    pub received_at_ms: u64,
}

impl PendingBlock {
    #[must_use]
    pub fn new(proposal: BlockProposal, received_at_ms: u64) -> Self {
        Self {
            proposal,
            votes: Vec::new(),
            state: BlockState::Proposed,
            received_at_ms,
        }
    }

    /// Add a vote and check if quorum is reached
    pub fn add_vote(&mut self, vote: BlockVote, quorum: usize) -> bool {
        // Verify vote matches this block
        if vote.view != self.proposal.view
            || vote.round != self.proposal.round
            || vote.block_hash != self.proposal.block_hash
        {
            return false;
        }

        // Check for duplicate voter
        if self.votes.iter().any(|v| v.voter_id == vote.voter_id) {
            return false;
        }

        self.votes.push(vote);

        // Check quorum
        if self.votes.len() >= quorum && self.state == BlockState::Proposed {
            self.state = BlockState::Prepared;
            return true;
        }

        false
    }
}

// ============================================================================
// VIEW CHANGE STATE
// ============================================================================

/// State of view change process
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ViewChangeState {
    /// Normal operation
    Normal,
    /// Waiting for view change messages
    Collecting,
    /// View change completed, waiting for new leader
    WaitingNewView,
}

/// View change tracker
#[derive(Debug, Clone)]
pub struct ViewChangeTracker {
    pub target_view: u64,
    pub messages: Vec<P2PViewChange>,
    pub state: ViewChangeState,
    pub started_at_ms: u64,
}

impl ViewChangeTracker {
    #[must_use]
    pub fn new(target_view: u64, started_at_ms: u64) -> Self {
        Self {
            target_view,
            messages: Vec::new(),
            state: ViewChangeState::Collecting,
            started_at_ms,
        }
    }

    /// Add a view change message and check if quorum is reached
    pub fn add_message(&mut self, msg: P2PViewChange, quorum: usize) -> bool {
        if msg.new_view != self.target_view {
            return false;
        }

        // Check for duplicate sender
        if self.messages.iter().any(|m| m.sender_id == msg.sender_id) {
            return false;
        }

        self.messages.push(msg);

        if self.messages.len() >= quorum && self.state == ViewChangeState::Collecting {
            self.state = ViewChangeState::WaitingNewView;
            return true;
        }

        false
    }
}

// ============================================================================
// BLOCK PROPAGATOR
// ============================================================================

/// P2P Block Propagation Engine
#[cfg_attr(feature = "python", pyclass)]
#[derive(Debug)]
pub struct BlockPropagator {
    /// Our node ID
    pub node_id: NodeId,
    /// Current view number
    pub view: u64,
    /// Current round number
    pub round: u64,
    /// List of validator node IDs
    pub validators: Vec<NodeId>,
    /// Pending blocks by (view, round)
    pub pending_blocks: HashMap<(u64, u64), PendingBlock>,
    /// Committed block hashes by (view, round)
    pub committed_blocks: HashMap<(u64, u64), [u8; 32]>,
    /// View change tracker (if active)
    pub view_change: Option<ViewChangeTracker>,
    /// Last committed state root
    pub state_root: [u8; 32],
    /// Messages to broadcast
    pub outbound_messages: Vec<GossipMessage>,
    /// Voters we've seen in this round
    voters_seen: HashSet<NodeId>,
}

impl BlockPropagator {
    /// Create a new block propagator
    #[must_use]
    pub fn new(node_id: NodeId, validators: Vec<NodeId>) -> Self {
        Self {
            node_id,
            view: 0,
            round: 0,
            validators,
            pending_blocks: HashMap::new(),
            committed_blocks: HashMap::new(),
            view_change: None,
            state_root: [0u8; 32],
            outbound_messages: Vec::new(),
            voters_seen: HashSet::new(),
        }
    }

    /// Get the leader for a given view
    #[must_use]
    pub fn get_leader(&self, view: u64) -> Option<&NodeId> {
        if self.validators.is_empty() {
            return None;
        }
        let index = (view as usize) % self.validators.len();
        self.validators.get(index)
    }

    /// Check if we are the leader for the current view
    #[must_use]
    pub fn is_leader(&self) -> bool {
        self.get_leader(self.view)
            .map(|leader| leader == &self.node_id)
            .unwrap_or(false)
    }

    /// Get quorum threshold
    #[must_use]
    pub fn quorum(&self) -> usize {
        quorum_threshold(self.validators.len())
    }

    // ========================================================================
    // BLOCK PROPOSAL (Leader)
    // ========================================================================

    /// Propose a new block (leader only)
    pub fn propose_block(
        &mut self,
        block_data: Vec<u8>,
        prev_hash: [u8; 32],
        timestamp_ms: u64,
        sign_fn: impl FnOnce(&[u8]) -> Vec<u8>,
    ) -> Result<BlockProposal, String> {
        if !self.is_leader() {
            return Err("Not the leader for current view".to_string());
        }

        if block_data.len() > MAX_BLOCK_SIZE {
            return Err(format!(
                "Block size {} exceeds maximum {}",
                block_data.len(),
                MAX_BLOCK_SIZE
            ));
        }

        // Compute block hash (SHA3-256 of header fields)
        let mut hasher_input = Vec::new();
        hasher_input.extend_from_slice(&self.view.to_le_bytes());
        hasher_input.extend_from_slice(&self.round.to_le_bytes());
        hasher_input.extend_from_slice(&prev_hash);
        hasher_input.extend_from_slice(&block_data);
        hasher_input.extend_from_slice(&timestamp_ms.to_le_bytes());

        let block_hash = sha3_256(&hasher_input);

        // Create proposal
        let mut proposal = BlockProposal {
            view: self.view,
            round: self.round,
            leader_id: self.node_id,
            block_hash,
            block_data,
            prev_hash,
            timestamp_ms,
            signature: Vec::new(),
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };

        // Sign the proposal
        let sign_data = proposal_sign_data(&proposal);
        proposal.signature = sign_fn(&sign_data);

        // Track as pending
        let pending = PendingBlock::new(proposal.clone(), timestamp_ms);
        self.pending_blocks.insert((self.view, self.round), pending);

        // Queue for broadcast
        self.outbound_messages
            .push(GossipMessage::BlockProposal(proposal.clone()));

        Ok(proposal)
    }

    // ========================================================================
    // BLOCK VOTE (Validators)
    // ========================================================================

    /// Process a received block proposal and vote on it
    pub fn process_proposal(
        &mut self,
        proposal: BlockProposal,
        timestamp_ms: u64,
        verify_fn: impl FnOnce(&[u8], &[u8], &NodeId) -> bool,
        sign_fn: impl FnOnce(&[u8]) -> Vec<u8>,
    ) -> Result<Option<BlockVote>, String> {
        // Verify proposal is from expected leader
        let expected_leader = self.get_leader(proposal.view).ok_or("No leader for view")?;

        if &proposal.leader_id != expected_leader {
            return Err("Proposal not from expected leader".to_string());
        }

        // Verify proposal view/round
        if proposal.view < self.view {
            return Err("Proposal from old view".to_string());
        }

        if proposal.view == self.view && proposal.round < self.round {
            return Err("Proposal from old round".to_string());
        }

        // Verify block hash
        let computed_hash = compute_block_hash(&proposal);
        if computed_hash != proposal.block_hash {
            return Err("Block hash mismatch".to_string());
        }

        // Verify signature
        let sign_data = proposal_sign_data(&proposal);
        if !verify_fn(&sign_data, &proposal.signature, &proposal.leader_id) {
            return Err("Invalid proposal signature".to_string());
        }

        // Verify block size
        if proposal.block_data.len() > MAX_BLOCK_SIZE {
            return Err("Block exceeds maximum size".to_string());
        }

        // Update our view/round if proposal is ahead
        if proposal.view > self.view || (proposal.view == self.view && proposal.round > self.round)
        {
            self.view = proposal.view;
            self.round = proposal.round;
            self.voters_seen.clear();
        }

        // Track the pending block
        let pending = PendingBlock::new(proposal.clone(), timestamp_ms);
        self.pending_blocks
            .insert((proposal.view, proposal.round), pending);

        // Check if we're a validator
        if !self.validators.contains(&self.node_id) {
            return Ok(None); // Not a validator, don't vote
        }

        // Create vote
        let mut vote = BlockVote {
            view: proposal.view,
            round: proposal.round,
            voter_id: self.node_id,
            block_hash: proposal.block_hash,
            signature: Vec::new(),
        };

        // Sign the vote
        let vote_data = vote_sign_data(&vote);
        vote.signature = sign_fn(&vote_data);

        // Queue for broadcast
        self.outbound_messages
            .push(GossipMessage::BlockVote(vote.clone()));

        Ok(Some(vote))
    }

    /// Process a received vote
    pub fn process_vote(
        &mut self,
        vote: BlockVote,
        verify_fn: impl FnOnce(&[u8], &[u8], &NodeId) -> bool,
    ) -> Result<bool, String> {
        // Verify voter is a validator
        if !self.validators.contains(&vote.voter_id) {
            return Err("Vote from non-validator".to_string());
        }

        // Check for duplicate
        if self.voters_seen.contains(&vote.voter_id) {
            return Err("Duplicate vote from validator".to_string());
        }

        // Verify signature
        let vote_data = vote_sign_data(&vote);
        if !verify_fn(&vote_data, &vote.signature, &vote.voter_id) {
            return Err("Invalid vote signature".to_string());
        }

        // Compute quorum before mutable borrow
        let quorum = self.quorum();

        // Get pending block
        let key = (vote.view, vote.round);
        let pending = self
            .pending_blocks
            .get_mut(&key)
            .ok_or("No pending block for vote")?;

        // Verify vote matches block
        if vote.block_hash != pending.proposal.block_hash {
            return Err("Vote for different block hash".to_string());
        }

        // Add vote
        self.voters_seen.insert(vote.voter_id);
        let quorum_reached = pending.add_vote(vote, quorum);

        if quorum_reached {
            // Commit the block
            self.commit_block(key)?;
        }

        Ok(quorum_reached)
    }

    // ========================================================================
    // BLOCK COMMIT
    // ========================================================================

    /// Commit a block that has reached quorum
    fn commit_block(&mut self, key: (u64, u64)) -> Result<BlockCommit, String> {
        let pending = self
            .pending_blocks
            .get_mut(&key)
            .ok_or("No pending block")?;

        if pending.state != BlockState::Prepared {
            return Err("Block not prepared".to_string());
        }

        // Mark as committed
        pending.state = BlockState::Committed;

        // Update state root via formal block application to the shard's state.
        let new_state_root = compute_state_root(&pending.proposal, &self.state_root);
        self.state_root = new_state_root;

        // Store committed block
        self.committed_blocks
            .insert(key, pending.proposal.block_hash);

        // Create commit message
        let commit = BlockCommit {
            view: pending.proposal.view,
            round: pending.proposal.round,
            block_hash: pending.proposal.block_hash,
            vote_signatures: pending.votes.clone(),
            state_root: new_state_root,
        };

        // Queue for broadcast
        self.outbound_messages
            .push(GossipMessage::BlockCommit(commit.clone()));

        // Advance round
        self.round += 1;
        self.voters_seen.clear();

        Ok(commit)
    }

    /// Process a received commit message
    pub fn process_commit(
        &mut self,
        commit: BlockCommit,
        verify_fn: impl Fn(&[u8], &[u8], &NodeId) -> bool,
    ) -> Result<(), String> {
        // Verify quorum of votes
        if commit.vote_signatures.len() < self.quorum() {
            return Err("Insufficient votes in commit".to_string());
        }

        // Verify each vote signature
        for vote in &commit.vote_signatures {
            if vote.block_hash != commit.block_hash {
                return Err("Vote hash mismatch in commit".to_string());
            }

            let vote_data = vote_sign_data(vote);
            if !verify_fn(&vote_data, &vote.signature, &vote.voter_id) {
                return Err("Invalid vote signature in commit".to_string());
            }
        }

        // Apply commit
        self.committed_blocks
            .insert((commit.view, commit.round), commit.block_hash);
        self.state_root = commit.state_root;

        // Update view/round if behind
        if commit.view > self.view || (commit.view == self.view && commit.round >= self.round) {
            self.view = commit.view;
            self.round = commit.round + 1;
            self.voters_seen.clear();
        }

        // Clean up pending block
        self.pending_blocks.remove(&(commit.view, commit.round));

        Ok(())
    }

    // ========================================================================
    // VIEW CHANGE
    // ========================================================================

    /// Initiate a view change
    pub fn initiate_view_change(
        &mut self,
        timestamp_ms: u64,
        sign_fn: impl FnOnce(&[u8]) -> Vec<u8>,
    ) -> P2PViewChange {
        let new_view = self.view + 1;

        // Find last prepared block
        let (last_prepared_round, last_prepared_block) = self
            .pending_blocks
            .values()
            .filter(|p| p.proposal.view == self.view && p.state == BlockState::Prepared)
            .max_by_key(|p| p.proposal.round)
            .map(|p| (Some(p.proposal.round), Some(p.proposal.block_hash)))
            .unwrap_or((None, None));

        let mut msg = P2PViewChange {
            new_view,
            sender_id: self.node_id.clone(),
            last_prepared_round,
            last_prepared_block,
            timestamp_ms,
            signature: Vec::new(),
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };

        // Sign the message
        let sign_data = view_change_sign_data(&msg);
        msg.signature = sign_fn(&sign_data);

        // Track view change and add our own message
        let mut tracker = ViewChangeTracker::new(new_view, timestamp_ms);
        tracker.messages.push(msg.clone()); // Count our own message
        self.view_change = Some(tracker);

        // Queue for broadcast
        self.outbound_messages
            .push(GossipMessage::ViewChange(msg.clone()));

        msg
    }

    /// Process a received view change message
    pub fn process_view_change(
        &mut self,
        msg: P2PViewChange,
        verify_fn: impl FnOnce(&[u8], &[u8], &NodeId) -> bool,
    ) -> Result<bool, String> {
        // Verify sender is a validator
        if !self.validators.contains(&msg.sender_id) {
            return Err("View change from non-validator".to_string());
        }

        // Verify signature
        let sign_data = view_change_sign_data(&msg);
        if !verify_fn(&sign_data, &msg.signature, &msg.sender_id) {
            return Err("Invalid view change signature".to_string());
        }

        // Compute quorum before mutable borrow
        let quorum = self.quorum();

        // Get or create tracker
        let tracker = self
            .view_change
            .get_or_insert_with(|| ViewChangeTracker::new(msg.new_view, msg.timestamp_ms));

        // Add message
        let quorum_reached = tracker.add_message(msg, quorum);

        Ok(quorum_reached)
    }

    /// Complete view change as new leader
    pub fn complete_view_change(
        &mut self,
        _timestamp_ms: u64,
        sign_fn: impl FnOnce(&[u8]) -> Vec<u8>,
    ) -> Result<P2PNewView, String> {
        let tracker = self.view_change.as_ref().ok_or("No active view change")?;

        if tracker.state != ViewChangeState::WaitingNewView {
            return Err("View change not ready to complete".to_string());
        }

        let new_view = tracker.target_view;

        // Verify we are the new leader
        let new_leader = self.get_leader(new_view).ok_or("No leader for new view")?;

        if new_leader != &self.node_id {
            return Err("We are not the new leader".to_string());
        }

        // Find highest prepared block from view change messages
        let (starting_round, prepared_block) = tracker
            .messages
            .iter()
            .filter_map(|m| m.last_prepared_round.map(|r| (r, m.last_prepared_block)))
            .max_by_key(|(r, _)| *r)
            .map(|(r, b)| (r + 1, b))
            .unwrap_or((0, None));

        let mut msg = P2PNewView {
            view: new_view,
            leader_id: self.node_id.clone(),
            view_change_proofs: tracker.messages.clone(),
            starting_round,
            prepared_block,
            signature: Vec::new(),
        };

        // Sign the message
        let sign_data = new_view_sign_data(&msg);
        msg.signature = sign_fn(&sign_data);

        // Apply view change
        self.view = new_view;
        self.round = starting_round;
        self.view_change = None;
        self.voters_seen.clear();

        // Queue for broadcast
        self.outbound_messages
            .push(GossipMessage::NewView(msg.clone()));

        Ok(msg)
    }

    /// Process a received new view message
    pub fn process_new_view(
        &mut self,
        msg: P2PNewView,
        verify_fn: impl Fn(&[u8], &[u8], &NodeId) -> bool,
    ) -> Result<(), String> {
        // Verify new leader
        let expected_leader = self.get_leader(msg.view).ok_or("No leader for new view")?;

        if &msg.leader_id != expected_leader {
            return Err("New view not from expected leader".to_string());
        }

        // Verify signature
        let sign_data = new_view_sign_data(&msg);
        if !verify_fn(&sign_data, &msg.signature, &msg.leader_id) {
            return Err("Invalid new view signature".to_string());
        }

        // Verify quorum of view change proofs
        if msg.view_change_proofs.len() < self.quorum() {
            return Err("Insufficient view change proofs".to_string());
        }

        // Verify each view change signature
        for vc in &msg.view_change_proofs {
            let vc_data = view_change_sign_data(vc);
            if !verify_fn(&vc_data, &vc.signature, &vc.sender_id) {
                return Err("Invalid view change proof signature".to_string());
            }
        }

        // Apply new view
        self.view = msg.view;
        self.round = msg.starting_round;
        self.view_change = None;
        self.voters_seen.clear();

        Ok(())
    }

    // ========================================================================
    // MESSAGE ROUTING
    // ========================================================================

    /// Process an incoming gossip message
    pub fn process_message(
        &mut self,
        msg: GossipMessage,
        timestamp_ms: u64,
        verify_fn: impl Fn(&[u8], &[u8], &NodeId) -> bool + Copy,
        sign_fn: impl FnOnce(&[u8]) -> Vec<u8>,
    ) -> Result<(), String> {
        match msg {
            GossipMessage::BlockProposal(proposal) => {
                self.process_proposal(proposal, timestamp_ms, verify_fn, sign_fn)?;
            }
            GossipMessage::BlockVote(vote) => {
                self.process_vote(vote, verify_fn)?;
            }
            GossipMessage::BlockCommit(commit) => {
                self.process_commit(commit, verify_fn)?;
            }
            GossipMessage::ViewChange(vc) => {
                self.process_view_change(vc, verify_fn)?;
            }
            GossipMessage::NewView(nv) => {
                self.process_new_view(nv, verify_fn)?;
            }
            _ => {
                // Other message types handled elsewhere
            }
        }
        Ok(())
    }

    /// Drain outbound messages for broadcasting
    pub fn drain_outbound(&mut self) -> Vec<GossipMessage> {
        std::mem::take(&mut self.outbound_messages)
    }
}

// ============================================================================
// PYTHON BINDINGS
// ============================================================================

#[cfg(feature = "python")]
#[pymethods]
impl BlockPropagator {
    /// Create a new block propagator for Python
    #[new]
    pub fn py_new(node_id: Vec<u8>, validator_ids: Vec<Vec<u8>>) -> PyResult<Self> {
        // Convert node_id to NodeId
        if node_id.len() != 32 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "node_id must be 32 bytes",
            ));
        }
        let mut node_id_arr = [0u8; 32];
        node_id_arr.copy_from_slice(&node_id);

        // Convert validator_ids to Vec<NodeId>
        let mut validators = Vec::new();
        for vid in validator_ids {
            if vid.len() != 32 {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Each validator_id must be 32 bytes",
                ));
            }
            let mut vid_arr = [0u8; 32];
            vid_arr.copy_from_slice(&vid);
            validators.push(vid_arr);
        }

        Ok(Self::new(node_id_arr, validators))
    }

    /// Get the current view number
    #[getter]
    pub fn get_view(&self) -> u64 {
        self.view
    }

    /// Get the current round number
    #[getter]
    pub fn get_round(&self) -> u64 {
        self.round
    }

    /// Get our node ID as bytes
    #[getter]
    pub fn get_node_id(&self) -> Vec<u8> {
        self.node_id.to_vec()
    }

    /// Get the current state root
    #[getter]
    pub fn get_state_root(&self) -> Vec<u8> {
        self.state_root.to_vec()
    }

    /// Check if we are the current leader
    pub fn py_is_leader(&self) -> bool {
        self.is_leader()
    }

    /// Get the quorum threshold
    pub fn py_quorum(&self) -> usize {
        self.quorum()
    }

    /// Get the leader node ID for the current view
    pub fn py_get_current_leader(&self) -> Option<Vec<u8>> {
        self.get_leader(self.view).map(|id| id.to_vec())
    }

    /// Broadcast a block proposal (simplified Python wrapper)
    /// Returns the proposal as a dict-like object
    pub fn py_broadcast_block(
        &mut self,
        block_data: Vec<u8>,
        prev_hash: Vec<u8>,
        timestamp_ms: u64,
    ) -> PyResult<Vec<u8>> {
        // Validate inputs
        if prev_hash.len() != 32 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "prev_hash must be 32 bytes",
            ));
        }

        let mut prev_hash_arr = [0u8; 32];
        prev_hash_arr.copy_from_slice(&prev_hash);

        // Simple test signature function (in production, would use real crypto)
        let sign_fn = |data: &[u8]| -> Vec<u8> {
            use sha3::{Digest, Sha3_256};
            let mut hasher = Sha3_256::new();
            hasher.update(data);
            hasher.finalize().to_vec()
        };

        // Propose the block
        let proposal = self
            .propose_block(block_data, prev_hash_arr, timestamp_ms, sign_fn)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;

        // Return block hash
        Ok(proposal.block_hash.to_vec())
    }

    /// Get the number of pending blocks
    pub fn py_pending_count(&self) -> usize {
        self.pending_blocks.len()
    }

    /// Get the number of committed blocks
    pub fn py_committed_count(&self) -> usize {
        self.committed_blocks.len()
    }

    /// Check if we have an active view change
    pub fn py_has_view_change(&self) -> bool {
        self.view_change.is_some()
    }

    /// Drain outbound messages and return count
    pub fn py_drain_outbound_count(&mut self) -> usize {
        let messages = self.drain_outbound();
        messages.len()
    }
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/// Compute SHA3-256 hash
fn sha3_256(data: &[u8]) -> [u8; 32] {
    use sha3::{Digest, Sha3_256};
    let mut hasher = Sha3_256::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut hash = [0u8; 32];
    hash.copy_from_slice(&result);
    hash
}

/// Compute block hash from proposal
fn compute_block_hash(proposal: &BlockProposal) -> [u8; 32] {
    let mut hasher_input = Vec::new();
    hasher_input.extend_from_slice(&proposal.view.to_le_bytes());
    hasher_input.extend_from_slice(&proposal.round.to_le_bytes());
    hasher_input.extend_from_slice(&proposal.prev_hash);
    hasher_input.extend_from_slice(&proposal.block_data);
    hasher_input.extend_from_slice(&proposal.timestamp_ms.to_le_bytes());
    sha3_256(&hasher_input)
}

/// Compute state root after applying block
fn compute_state_root(proposal: &BlockProposal, prev_state_root: &[u8; 32]) -> [u8; 32] {
    let mut input = Vec::new();
    input.extend_from_slice(prev_state_root);
    input.extend_from_slice(&proposal.block_hash);
    input.extend_from_slice(&proposal.block_data);
    sha3_256(&input)
}

/// Generate signing data for proposal
fn proposal_sign_data(proposal: &BlockProposal) -> Vec<u8> {
    let mut data = Vec::new();
    data.extend_from_slice(b"PROPOSAL:");
    data.extend_from_slice(&proposal.view.to_le_bytes());
    data.extend_from_slice(&proposal.round.to_le_bytes());
    data.extend_from_slice(&proposal.block_hash);
    data.extend_from_slice(&proposal.prev_hash);
    data.extend_from_slice(&proposal.timestamp_ms.to_le_bytes());
    data
}

/// Generate signing data for vote
fn vote_sign_data(vote: &BlockVote) -> Vec<u8> {
    let mut data = Vec::new();
    data.extend_from_slice(b"VOTE:");
    data.extend_from_slice(&vote.view.to_le_bytes());
    data.extend_from_slice(&vote.round.to_le_bytes());
    data.extend_from_slice(&vote.block_hash);
    data
}

/// Generate signing data for view change
fn view_change_sign_data(msg: &P2PViewChange) -> Vec<u8> {
    let mut data = Vec::new();
    data.extend_from_slice(b"VIEWCHANGE:");
    data.extend_from_slice(&msg.new_view.to_le_bytes());
    if let Some(round) = msg.last_prepared_round {
        data.extend_from_slice(&round.to_le_bytes());
    }
    if let Some(ref hash) = msg.last_prepared_block {
        data.extend_from_slice(hash);
    }
    data.extend_from_slice(&msg.timestamp_ms.to_le_bytes());
    data
}

/// Generate signing data for new view
fn new_view_sign_data(msg: &P2PNewView) -> Vec<u8> {
    let mut data = Vec::new();
    data.extend_from_slice(b"NEWVIEW:");
    data.extend_from_slice(&msg.view.to_le_bytes());
    data.extend_from_slice(&msg.starting_round.to_le_bytes());
    if let Some(ref hash) = msg.prepared_block {
        data.extend_from_slice(hash);
    }
    // Include count of proofs for integrity
    data.extend_from_slice(&(msg.view_change_proofs.len() as u32).to_le_bytes());
    data
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    fn make_node_id(n: u8) -> NodeId {
        let mut id = [0u8; 32];
        id[0] = n;
        id
    }

    fn test_logic_sign(data: &[u8]) -> Vec<u8> {
        // Simple test signature: SHA3-256 of data
        sha3_256(data).to_vec()
    }

    fn test_logic_verify(_data: &[u8], sig: &[u8], _node: &NodeId) -> bool {
        // Accept any 32-byte signature for tests
        sig.len() == 32
    }

    #[test]
    fn test_quorum_threshold() {
        assert_eq!(quorum_threshold(1), 1);
        assert_eq!(quorum_threshold(3), 1);
        assert_eq!(quorum_threshold(4), 3);
        assert_eq!(quorum_threshold(5), 3);
        assert_eq!(quorum_threshold(7), 5);
        assert_eq!(quorum_threshold(10), 7);
    }

    #[test]
    fn test_block_propagator_new() {
        let node_id = make_node_id(1);
        let validators = vec![make_node_id(1), make_node_id(2), make_node_id(3)];
        let propagator = BlockPropagator::new(node_id, validators.clone());

        assert_eq!(propagator.view, 0);
        assert_eq!(propagator.round, 0);
        assert_eq!(propagator.validators.len(), 3);
        assert_eq!(propagator.quorum(), 1); // (3-1)/3 = 0, 2*0+1 = 1
    }

    #[test]
    fn test_get_leader_rotation() {
        let node_id = make_node_id(1);
        let validators = vec![make_node_id(1), make_node_id(2), make_node_id(3)];
        let propagator = BlockPropagator::new(node_id, validators);

        assert_eq!(propagator.get_leader(0), Some(&make_node_id(1)));
        assert_eq!(propagator.get_leader(1), Some(&make_node_id(2)));
        assert_eq!(propagator.get_leader(2), Some(&make_node_id(3)));
        assert_eq!(propagator.get_leader(3), Some(&make_node_id(1)));
    }

    #[test]
    fn test_propose_block_leader_only() {
        let node_id = make_node_id(2); // Not view 0 leader
        let validators = vec![make_node_id(1), make_node_id(2), make_node_id(3)];
        let mut propagator = BlockPropagator::new(node_id, validators);

        let result = propagator.propose_block(vec![1, 2, 3], [0u8; 32], 1000, test_logic_sign);

        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Not the leader"));
    }

    #[test]
    fn test_propose_block_success() {
        let node_id = make_node_id(1); // View 0 leader
        let validators = vec![make_node_id(1), make_node_id(2), make_node_id(3)];
        let mut propagator = BlockPropagator::new(node_id, validators);

        let result = propagator.propose_block(vec![1, 2, 3], [0u8; 32], 1000, test_logic_sign);

        assert!(result.is_ok());
        let proposal = result.unwrap();
        assert_eq!(proposal.view, 0);
        assert_eq!(proposal.round, 0);
        assert_eq!(proposal.block_data, vec![1, 2, 3]);
        assert!(!proposal.signature.is_empty());

        // Should have queued broadcast
        assert_eq!(propagator.outbound_messages.len(), 1);
    }

    #[test]
    fn test_process_proposal_and_vote() {
        // Leader creates proposal
        let leader_id = make_node_id(1);
        let validators = vec![make_node_id(1), make_node_id(2), make_node_id(3)];
        let mut leader = BlockPropagator::new(leader_id, validators.clone());

        let proposal = leader
            .propose_block(vec![1, 2, 3], [0u8; 32], 1000, test_logic_sign)
            .unwrap();

        // Validator processes proposal
        let validator_id = make_node_id(2);
        let mut validator = BlockPropagator::new(validator_id, validators);

        let vote_result =
            validator.process_proposal(proposal, 1001, test_logic_verify, test_logic_sign);

        assert!(vote_result.is_ok());
        let vote = vote_result.unwrap();
        assert!(vote.is_some());

        let vote = vote.unwrap();
        assert_eq!(vote.view, 0);
        assert_eq!(vote.round, 0);
        assert_eq!(vote.voter_id, make_node_id(2));
    }

    #[test]
    fn test_view_change_initiation() {
        let node_id = make_node_id(1);
        let validators = vec![make_node_id(1), make_node_id(2), make_node_id(3)];
        let mut propagator = BlockPropagator::new(node_id, validators);

        let vc = propagator.initiate_view_change(1000, test_logic_sign);

        assert_eq!(vc.new_view, 1);
        assert_eq!(vc.sender_id, make_node_id(1));
        assert!(!vc.signature.is_empty());
        assert!(propagator.view_change.is_some());
    }

    #[test]
    fn test_view_change_quorum() {
        let node_id = make_node_id(1);
        let validators = vec![
            make_node_id(1),
            make_node_id(2),
            make_node_id(3),
            make_node_id(4),
        ];
        let mut propagator = BlockPropagator::new(node_id, validators);
        // quorum = 2*1+1 = 3 for 4 validators

        // Initiate view change
        propagator.initiate_view_change(1000, test_logic_sign);

        // Process view change from node 2
        let vc2 = P2PViewChange {
            new_view: 1,
            sender_id: make_node_id(2),
            last_prepared_round: None,
            last_prepared_block: None,
            timestamp_ms: 1001,
            signature: test_logic_sign(b"vc2"),
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };
        let result = propagator.process_view_change(vc2, test_logic_verify);
        assert!(result.is_ok());
        assert!(!result.unwrap()); // Not yet quorum

        // Process view change from node 3
        let vc3 = P2PViewChange {
            new_view: 1,
            sender_id: make_node_id(3),
            last_prepared_round: None,
            last_prepared_block: None,
            timestamp_ms: 1002,
            signature: test_logic_sign(b"vc3"),
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };
        let result = propagator.process_view_change(vc3, test_logic_verify);
        assert!(result.is_ok());
        assert!(result.unwrap()); // Quorum reached (3 messages including ours)
    }

    #[test]
    fn test_pending_block_add_vote() {
        let proposal = BlockProposal {
            view: 0,
            round: 0,
            leader_id: make_node_id(1),
            block_hash: [1u8; 32],
            block_data: vec![1, 2, 3],
            prev_hash: [0u8; 32],
            timestamp_ms: 1000,
            signature: vec![1, 2, 3],
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };

        let mut pending = PendingBlock::new(proposal, 1000);

        // Add first vote
        let vote1 = BlockVote {
            view: 0,
            round: 0,
            voter_id: make_node_id(2),
            block_hash: [1u8; 32],
            signature: vec![1],
        };
        assert!(!pending.add_vote(vote1, 2)); // Quorum = 2, not reached

        // Add second vote (quorum reached)
        let vote2 = BlockVote {
            view: 0,
            round: 0,
            voter_id: make_node_id(3),
            block_hash: [1u8; 32],
            signature: vec![2],
        };
        assert!(pending.add_vote(vote2, 2));
        assert_eq!(pending.state, BlockState::Prepared);
    }

    #[test]
    fn test_duplicate_vote_rejected() {
        let proposal = BlockProposal {
            view: 0,
            round: 0,
            leader_id: make_node_id(1),
            block_hash: [1u8; 32],
            block_data: vec![],
            prev_hash: [0u8; 32],
            timestamp_ms: 1000,
            signature: vec![],
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };

        let mut pending = PendingBlock::new(proposal, 1000);

        let vote = BlockVote {
            view: 0,
            round: 0,
            voter_id: make_node_id(2),
            block_hash: [1u8; 32],
            signature: vec![1],
        };

        pending.add_vote(vote.clone(), 3);
        assert!(!pending.add_vote(vote, 3)); // Duplicate rejected
        assert_eq!(pending.votes.len(), 1);
    }

    #[test]
    fn test_full_consensus_round() {
        // Setup: 4 validators, quorum = 3
        let validators = vec![
            make_node_id(1), // Leader for view 0
            make_node_id(2),
            make_node_id(3),
            make_node_id(4),
        ];

        // Leader creates propagator and proposes block
        let mut leader = BlockPropagator::new(make_node_id(1), validators.clone());
        let proposal = leader
            .propose_block(
                vec![0xDE, 0xAD, 0xBE, 0xEF],
                [0u8; 32],
                1000,
                test_logic_sign,
            )
            .unwrap();

        // Validators receive proposal and vote
        let mut v2 = BlockPropagator::new(make_node_id(2), validators.clone());
        let vote2 = v2
            .process_proposal(proposal.clone(), 1001, test_logic_verify, test_logic_sign)
            .unwrap()
            .unwrap();

        let mut v3 = BlockPropagator::new(make_node_id(3), validators.clone());
        let vote3 = v3
            .process_proposal(proposal.clone(), 1002, test_logic_verify, test_logic_sign)
            .unwrap()
            .unwrap();

        let mut v4 = BlockPropagator::new(make_node_id(4), validators.clone());
        let vote4 = v4
            .process_proposal(proposal.clone(), 1003, test_logic_verify, test_logic_sign)
            .unwrap()
            .unwrap();

        // Leader collects votes
        let result1 = leader.process_vote(vote2.clone(), test_logic_verify);
        assert!(result1.is_ok());
        assert!(!result1.unwrap()); // Not yet quorum (1 vote)

        let result2 = leader.process_vote(vote3.clone(), test_logic_verify);
        assert!(result2.is_ok());
        assert!(!result2.unwrap()); // Not yet quorum (2 votes)

        let result3 = leader.process_vote(vote4.clone(), test_logic_verify);
        assert!(result3.is_ok());
        assert!(result3.unwrap()); // Quorum reached! (3 votes)

        // Verify block was committed
        let committed = leader.committed_blocks.get(&(0, 0));
        assert!(committed.is_some());
        assert_eq!(committed.unwrap(), &proposal.block_hash);

        // Verify round advanced
        assert_eq!(leader.round, 1);
    }

    #[test]
    fn test_process_commit_message() {
        let validators = vec![make_node_id(1), make_node_id(2), make_node_id(3)];

        let mut propagator = BlockPropagator::new(make_node_id(4), validators);
        // quorum = 1 for 3 validators

        let block_hash = [0xABu8; 32];
        let commit = BlockCommit {
            view: 0,
            round: 0,
            block_hash,
            vote_signatures: vec![BlockVote {
                view: 0,
                round: 0,
                voter_id: make_node_id(1),
                block_hash,
                signature: test_logic_sign(b"vote1"),
            }],
            state_root: [0xCDu8; 32],
        };

        let result = propagator.process_commit(commit.clone(), test_logic_verify);
        assert!(result.is_ok());

        // Verify state updated
        assert_eq!(propagator.state_root, [0xCDu8; 32]);
        assert!(propagator.committed_blocks.contains_key(&(0, 0)));
        assert_eq!(propagator.round, 1);
    }

    #[test]
    fn test_reject_invalid_leader_proposal() {
        let validators = vec![
            make_node_id(1), // Leader for view 0
            make_node_id(2),
            make_node_id(3),
        ];

        let mut propagator = BlockPropagator::new(make_node_id(2), validators);

        // Create proposal from wrong leader (node 3 instead of node 1)
        let fake_proposal = BlockProposal {
            view: 0,
            round: 0,
            leader_id: make_node_id(3), // Wrong leader!
            block_hash: [0u8; 32],
            block_data: vec![1, 2, 3],
            prev_hash: [0u8; 32],
            timestamp_ms: 1000,
            signature: test_logic_sign(b"fake"),
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };

        let result =
            propagator.process_proposal(fake_proposal, 1001, test_logic_verify, test_logic_sign);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not from expected leader"));
    }

    #[test]
    fn test_new_view_completion() {
        let validators = vec![
            make_node_id(1), // View 0 leader
            make_node_id(2), // View 1 leader
            make_node_id(3),
            make_node_id(4),
        ];

        // Node 2 initiates view change to view 1 (where it will be leader)
        let mut node2 = BlockPropagator::new(make_node_id(2), validators.clone());
        node2.initiate_view_change(1000, test_logic_sign);

        // Receive view changes from others
        let vc1 = P2PViewChange {
            new_view: 1,
            sender_id: make_node_id(1),
            last_prepared_round: None,
            last_prepared_block: None,
            timestamp_ms: 1001,
            signature: test_logic_sign(b"vc1"),
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };
        node2.process_view_change(vc1, test_logic_verify).unwrap();

        let vc3 = P2PViewChange {
            new_view: 1,
            sender_id: make_node_id(3),
            last_prepared_round: None,
            last_prepared_block: None,
            timestamp_ms: 1002,
            signature: test_logic_sign(b"vc3"),
            temporal_proof: None, // [Phase 2.2] Explicit: no temporal proof yet
        };
        let quorum_reached = node2.process_view_change(vc3, test_logic_verify).unwrap();
        assert!(quorum_reached);

        // Complete view change as new leader
        let new_view_msg = node2.complete_view_change(1003, test_logic_sign);
        assert!(new_view_msg.is_ok());

        let nv = new_view_msg.unwrap();
        assert_eq!(nv.view, 1);
        assert_eq!(nv.leader_id, make_node_id(2));
        assert_eq!(node2.view, 1);
        assert!(node2.view_change.is_none());
    }
}
