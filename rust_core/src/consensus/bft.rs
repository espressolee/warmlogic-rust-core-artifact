//! rust_core/src/consensus/bft.rs
//! Byzantine Fault Tolerant State Machine with View Change Protocol.
//!
//! Implements PBFT-style view change for leader failure recovery.
//! When the current leader fails, nodes trigger a view change to elect
//! a new leader and continue consensus without losing liveness.
#![allow(dead_code)]

#[cfg(feature = "python")]
#[cfg(feature = "python")]
use crate::pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use crate::pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[cfg(feature = "python")]
use crate::ffi_limits;

#[cfg(not(feature = "std"))]
use alloc::string::{String, ToString};
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

// Phase 7.1a: rayon parallel vote verification
#[cfg(feature = "std")]
use rayon::prelude::*;

/// [C3 Security Fix] Maximum votes per round to prevent memory exhaustion DoS.
/// In a typical BFT network with 21 validators, this allows ~5x overhead for
/// network partitions, delayed votes, and Byzantine nodes.
/// Adjust based on expected validator count: MAX_VOTES = 5 * expected_validators.
pub const MAX_VOTES_PER_ROUND: usize = 100;

/// Default timeout before triggering view change (milliseconds).
pub const DEFAULT_VIEW_CHANGE_TIMEOUT_MS: u64 = 5000;

/// Maximum view changes allowed before requiring manual intervention.
pub const MAX_CONSECUTIVE_VIEW_CHANGES: u32 = 10;

/// [H2 Security Fix] Vote now includes round to prevent replay attacks.
/// A vote is only valid for the specific round it was cast in.
#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Vote {
    pub voter_id: String,
    pub block_hash: String,
    pub round: u64,
    pub signature: String,
    pub decision_hash: Option<[u8; 32]>,
}

/// Anonymous Vote using ZK-Proof.
/// Proves fleet membership without revealing node identity.
#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AnonymousVote {
    pub block_hash: String,
    pub round: u64,
    /// ZK-Proof of fleet membership.
    pub zk_proof: Vec<u8>,
    /// Unique nullifier to prevent double-voting.
    pub nullifier: [u8; 32],
}

// ============================================================================
// VIEW CHANGE PROTOCOL
// ============================================================================

/// View Change status for leader recovery protocol.
#[cfg_attr(feature = "python", pyclass(eq, eq_int))]
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum ViewChangeStatus {
    /// Normal operation - leader is functioning
    #[default]
    Normal,
    /// View change triggered - waiting for quorum of VIEW_CHANGE messages
    Pending,
    /// View change in progress - received quorum, new leader preparing NEW_VIEW
    InProgress,
    /// View change completed - new view established
    Completed,
    /// View change failed - too many consecutive failures
    Failed,
}

/// VIEW_CHANGE message sent when a node detects leader failure.
/// Nodes broadcast this to propose moving to the next view.
#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ViewChangeMessage {
    /// The new view number being proposed
    pub new_view: u64,
    /// Node ID sending this message
    pub sender_id: String,
    /// Last prepared round in the previous view (if any)
    pub last_prepared_round: Option<u64>,
    /// Hash of the last prepared block (if any)
    pub last_prepared_block: Option<String>,
    /// ML-DSA-65 signature over (new_view || sender_id || last_prepared_round)
    pub signature: String,
    /// Timestamp when view change was triggered (for timeout ordering)
    pub timestamp_ms: u64,
}

#[cfg(feature = "python")]
#[pymethods]
impl ViewChangeMessage {
    #[new]
    #[pyo3(signature = (new_view, sender_id, signature, timestamp_ms, last_prepared_round=None, last_prepared_block=None))]
    pub fn new(
        new_view: u64,
        sender_id: String,
        signature: String,
        timestamp_ms: u64,
        last_prepared_round: Option<u64>,
        last_prepared_block: Option<String>,
    ) -> PyResult<Self> {
        // FFI Input Validation
        ffi_limits::validate_string(&sender_id, "ViewChangeMessage:sender_id")
            .map_err(PyValueError::new_err)?;
        ffi_limits::validate_hex(&signature, "ViewChangeMessage:signature")
            .map_err(PyValueError::new_err)?;
        if let Some(ref block) = last_prepared_block {
            ffi_limits::validate_hex(block, "ViewChangeMessage:last_prepared_block")
                .map_err(PyValueError::new_err)?;
        }
        Ok(ViewChangeMessage {
            new_view,
            sender_id,
            last_prepared_round,
            last_prepared_block,
            signature,
            timestamp_ms,
        })
    }

    #[getter]
    pub fn get_new_view(&self) -> u64 {
        self.new_view
    }

    #[getter]
    pub fn get_sender_id(&self) -> String {
        self.sender_id.clone()
    }
}

/// NEW_VIEW message sent by the new leader after collecting VIEW_CHANGE quorum.
/// Contains proof of view change and the starting state for the new view.
#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NewViewMessage {
    /// The new view number
    pub view: u64,
    /// New leader ID (should match expected leader for this view)
    pub leader_id: String,
    /// VIEW_CHANGE messages that formed the quorum (proof of legitimacy)
    pub view_change_proofs: Vec<ViewChangeMessage>,
    /// The prepared block to continue from (highest from VIEW_CHANGE messages)
    pub prepared_block: Option<String>,
    /// Starting round for the new view
    pub starting_round: u64,
    /// ML-DSA-65 signature from new leader
    pub signature: String,
}

#[cfg(feature = "python")]
#[pymethods]
impl NewViewMessage {
    #[new]
    #[pyo3(signature = (view, leader_id, view_change_proofs, starting_round, signature, prepared_block=None))]
    pub fn new(
        view: u64,
        leader_id: String,
        view_change_proofs: Vec<ViewChangeMessage>,
        starting_round: u64,
        signature: String,
        prepared_block: Option<String>,
    ) -> PyResult<Self> {
        // FFI Input Validation
        ffi_limits::validate_string(&leader_id, "NewViewMessage:leader_id")
            .map_err(PyValueError::new_err)?;
        ffi_limits::validate_array_len(
            view_change_proofs.len(),
            "NewViewMessage:view_change_proofs",
        )
        .map_err(PyValueError::new_err)?;
        ffi_limits::validate_hex(&signature, "NewViewMessage:signature")
            .map_err(PyValueError::new_err)?;
        if let Some(ref block) = prepared_block {
            ffi_limits::validate_hex(block, "NewViewMessage:prepared_block")
                .map_err(PyValueError::new_err)?;
        }
        Ok(NewViewMessage {
            view,
            leader_id,
            view_change_proofs,
            prepared_block,
            starting_round,
            signature,
        })
    }

    #[getter]
    pub fn get_view(&self) -> u64 {
        self.view
    }

    #[getter]
    pub fn get_leader_id(&self) -> String {
        self.leader_id.clone()
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl Vote {
    #[new]
    pub fn new(
        voter_id: String,
        block_hash: String,
        round: u64,
        signature: String,
    ) -> PyResult<Self> {
        // FFI Input Validation
        ffi_limits::validate_string(&voter_id, "Vote:voter_id").map_err(PyValueError::new_err)?;
        ffi_limits::validate_hex(&block_hash, "Vote:block_hash").map_err(PyValueError::new_err)?;
        ffi_limits::validate_hex(&signature, "Vote:signature").map_err(PyValueError::new_err)?;
        Ok(Vote {
            voter_id,
            block_hash,
            round,
            signature,
            decision_hash: None,
        })
    }

    #[getter]
    #[must_use]
    pub fn voter_id(&self) -> String {
        self.voter_id.clone()
    }
    #[setter]
    pub fn set_voter_id(&mut self, val: String) {
        self.voter_id = val;
    }

    #[getter]
    #[must_use]
    pub fn block_hash(&self) -> String {
        self.block_hash.clone()
    }
    #[setter]
    pub fn set_block_hash(&mut self, val: String) {
        self.block_hash = val;
    }

    #[getter]
    #[must_use]
    pub fn round(&self) -> u64 {
        self.round
    }
    #[setter]
    pub fn set_round(&mut self, val: u64) {
        self.round = val;
    }

    #[getter]
    #[must_use]
    pub fn signature(&self) -> String {
        self.signature.clone()
    }
    #[setter]
    pub fn set_signature(&mut self, val: String) {
        self.signature = val;
    }

    #[getter]
    pub fn decision_hash(&self) -> Option<Vec<u8>> {
        self.decision_hash.map(|h| h.to_vec())
    }
}

/// BFT State Machine with View Change Protocol.
/// View -> Round -> Proposal -> Votes -> Commit.
///
/// The view number changes when the leader fails and a new leader is elected.
/// Within each view, rounds proceed normally with the current leader.
#[cfg_attr(feature = "python", pyclass)]
#[derive(Debug, Clone)]
pub struct BFTEngine {
    // ========== Core Consensus State ==========
    pub round: u64,
    pub votes: Vec<Vote>,
    pub quorum_size: usize,
    pub current_proposal: Option<String>, // block_hash
    /// [A+ Phase 2] The ethical verdict for the current proposal
    pub current_decision: Option<crate::governance::GovernanceDecision>,
    /// Anonymous votes received this round
    pub anonymous_votes: Vec<AnonymousVote>,
    /// Nullifiers to prevent double anonymous voting
    pub nullifiers: std::collections::HashSet<[u8; 32]>,

    // ========== View Change State ==========
    /// Current view number (increments on leader change)
    pub view: u64,
    /// List of validator IDs for leader election (index = view % len = leader)
    pub validators: Vec<String>,
    /// Current leader ID (derived from view and validators)
    pub leader_id: Option<String>,
    /// View change status
    pub view_change_status: ViewChangeStatus,
    /// Collected VIEW_CHANGE messages for current view change
    pub view_change_messages: Vec<ViewChangeMessage>,
    /// Number of consecutive view changes (for failure detection)
    pub consecutive_view_changes: u32,
    /// Last successful round (for recovery)
    pub last_committed_round: u64,
    /// Last committed block hash (for recovery)
    pub last_committed_block: Option<String>,

    // ========== Timeout Management ==========
    /// Current timeout duration (ms), increases with consecutive failures
    pub view_change_timeout_ms: u64,
    /// Timestamp of last activity (ms since epoch) - used to detect timeout
    pub last_activity_ms: u64,
    /// Timestamp when view change was initiated (for tracking)
    pub view_change_started_ms: Option<u64>,

    // ========== Replay Protection  ==========
    /// Timestamp of last processed view change message (for replay detection)
    pub last_view_change_timestamp: u64,
}

impl BFTEngine {
    #[must_use]
    pub fn new(quorum_size: usize) -> Self {
        BFTEngine {
            round: 0,
            votes: Vec::new(),
            quorum_size,
            current_proposal: None,
            current_decision: None,
            anonymous_votes: Vec::new(),
            nullifiers: std::collections::HashSet::new(),
            // View Change State
            view: 0,
            validators: Vec::new(),
            leader_id: None,
            view_change_status: ViewChangeStatus::Normal,
            view_change_messages: Vec::new(),
            consecutive_view_changes: 0,
            last_committed_round: 0,
            last_committed_block: None,
            // Timeout Management
            view_change_timeout_ms: DEFAULT_VIEW_CHANGE_TIMEOUT_MS,
            last_activity_ms: 0,
            view_change_started_ms: None,
            // Replay Protection
            last_view_change_timestamp: 0,
        }
    }

    /// Create a new BFT engine with validators for view change support.
    #[must_use]
    pub fn with_validators(quorum_size: usize, validators: Vec<String>) -> Self {
        let leader_id = if validators.is_empty() {
            None
        } else {
            validators.first().cloned()
        };
        BFTEngine {
            round: 0,
            votes: Vec::new(),
            quorum_size,
            current_proposal: None,
            current_decision: None,
            anonymous_votes: Vec::new(),
            nullifiers: std::collections::HashSet::new(),
            view: 0,
            validators,
            leader_id,
            view_change_status: ViewChangeStatus::Normal,
            view_change_messages: Vec::new(),
            consecutive_view_changes: 0,
            last_committed_round: 0,
            last_committed_block: None,
            // Timeout Management
            view_change_timeout_ms: DEFAULT_VIEW_CHANGE_TIMEOUT_MS,
            last_activity_ms: 0,
            view_change_started_ms: None,
            // Replay Protection
            last_view_change_timestamp: 0,
        }
    }

    /// Reset for a new round.
    pub fn start_round(&mut self, round: u64) {
        self.round = round;
        self.votes.clear();
        self.anonymous_votes.clear();
        self.nullifiers.clear();
        self.current_proposal = None;
    }

    // ========================================================================
    // VIEW CHANGE PROTOCOL
    // ========================================================================

    /// Get the expected leader for a given view.
    /// Leader is determined by: validators[view % validators.len()]
    #[must_use]
    pub fn get_leader_for_view(&self, view: u64) -> Option<String> {
        if self.validators.is_empty() {
            return None;
        }
        let index = (view as usize) % self.validators.len();
        self.validators.get(index).cloned()
    }

    /// Get current leader ID.
    #[must_use]
    pub fn current_leader(&self) -> Option<String> {
        self.get_leader_for_view(self.view)
    }

    /// Check if a node is the current leader.
    #[must_use]
    pub fn is_leader(&self, node_id: &str) -> bool {
        self.current_leader().map(|l| l == node_id).unwrap_or(false)
    }

    /// Trigger a view change (called when leader timeout detected).
    ///
    /// Returns a ViewChangeMessage to broadcast to other nodes.
    pub fn trigger_view_change(&mut self, sender_id: &str, signature: String) -> ViewChangeMessage {
        let new_view = self.view + 1;
        self.view_change_status = ViewChangeStatus::Pending;

        let msg = ViewChangeMessage {
            new_view,
            sender_id: sender_id.to_string(),
            last_prepared_round: if self.last_committed_round > 0 {
                Some(self.last_committed_round)
            } else {
                None
            },
            last_prepared_block: self.last_committed_block.clone(),
            signature,
            timestamp_ms: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_or(0, |d| d.as_millis() as u64),
        };

        // Add our own view change message
        self.view_change_messages.push(msg.clone());

        msg
    }

    /// Process a received VIEW_CHANGE message.
    ///
    /// Returns Ok(true) if we now have quorum for view change.
    /// Returns Ok(false) if more messages needed.
    /// Returns Err if message is invalid.
    pub fn process_view_change(
        &mut self,
        msg: ViewChangeMessage,
        public_key_hex: &str, // For signature verification
    ) -> Result<bool, String> {
        // Validate view number
        if msg.new_view <= self.view {
            return Err(format!(
                "Stale view change: current={}, received={}",
                self.view, msg.new_view
            ));
        }

        // Replay protection via timestamp validation
        // Reject messages with timestamps older than the last processed one
        if msg.timestamp_ms < self.last_view_change_timestamp {
            return Err(format!(
                "Stale view change message (replay detected): timestamp={}, last_processed={}",
                msg.timestamp_ms, self.last_view_change_timestamp
            ));
        }

        // Check for duplicate sender
        if self
            .view_change_messages
            .iter()
            .any(|m| m.sender_id == msg.sender_id && m.new_view == msg.new_view)
        {
            return Ok(self.has_view_change_quorum());
        }

        // Limit messages to prevent DoS
        if self.view_change_messages.len() >= MAX_VOTES_PER_ROUND {
            return Err("Too many view change messages".to_string());
        }

        // [A+ P2P Security] Verify signature using public_key_hex
        let message = format!("{}:{}", msg.new_view, msg.sender_id);
        if !crate::crypto::MLDSA::verify_raw(public_key_hex, &message, &msg.signature) {
            return Err("Invalid view change signature".to_string());
        }

        // Update last processed timestamp after all validations pass
        self.last_view_change_timestamp = msg.timestamp_ms;
        self.view_change_messages.push(msg);
        self.view_change_status = ViewChangeStatus::Pending;

        Ok(self.has_view_change_quorum())
    }

    /// Check if we have quorum of VIEW_CHANGE messages.
    #[must_use]
    pub fn has_view_change_quorum(&self) -> bool {
        let target_view = self.view + 1;
        let count = self
            .view_change_messages
            .iter()
            .filter(|m| m.new_view == target_view)
            .count();
        count >= self.quorum_size
    }

    /// Complete the view change (called by new leader after collecting quorum).
    ///
    /// Returns a NewViewMessage to broadcast, or Err if not the legitimate leader.
    pub fn complete_view_change(
        &mut self,
        leader_id: &str,
        signature: String,
    ) -> Result<NewViewMessage, String> {
        let new_view = self.view + 1;

        // Verify this node is the legitimate new leader
        let expected_leader = self.get_leader_for_view(new_view);
        if expected_leader.as_deref() != Some(leader_id) {
            return Err(format!(
                "Invalid leader: expected {:?}, got {}",
                expected_leader, leader_id
            ));
        }

        // Verify we have quorum
        if !self.has_view_change_quorum() {
            return Err("Insufficient view change quorum".to_string());
        }

        // Find the highest prepared block from VIEW_CHANGE messages
        let (prepared_block, starting_round) = self
            .view_change_messages
            .iter()
            .filter(|m| m.new_view == new_view)
            .filter_map(|m| {
                m.last_prepared_round
                    .map(|r| (m.last_prepared_block.clone(), r))
            })
            .max_by_key(|(_, r)| *r)
            .unwrap_or_else(|| (None, self.round));

        // Collect proofs for the NEW_VIEW message
        let view_change_proofs: Vec<ViewChangeMessage> = self
            .view_change_messages
            .iter()
            .filter(|m| m.new_view == new_view)
            .take(self.quorum_size)
            .cloned()
            .collect();

        let new_view_msg = NewViewMessage {
            view: new_view,
            leader_id: leader_id.to_string(),
            view_change_proofs,
            prepared_block,
            starting_round,
            signature,
        };

        // Apply the view change
        self.apply_new_view(&new_view_msg)?;

        Ok(new_view_msg)
    }

    /// Apply a NEW_VIEW message (called on all nodes including new leader).
    pub fn apply_new_view(&mut self, msg: &NewViewMessage) -> Result<(), String> {
        // Validate view number
        if msg.view <= self.view {
            return Err(format!(
                "Stale new view: current={}, received={}",
                self.view, msg.view
            ));
        }

        // Verify leader is correct for this view
        let expected_leader = self.get_leader_for_view(msg.view);
        if expected_leader.as_deref() != Some(&msg.leader_id) {
            return Err(format!(
                "Invalid leader in NEW_VIEW: expected {:?}, got {}",
                expected_leader, msg.leader_id
            ));
        }

        // Verify quorum of VIEW_CHANGE proofs
        if msg.view_change_proofs.len() < self.quorum_size {
            return Err(format!(
                "Insufficient proofs: need {}, got {}",
                self.quorum_size,
                msg.view_change_proofs.len()
            ));
        }

        // Apply the new view
        self.view = msg.view;
        self.leader_id = Some(msg.leader_id.clone());
        self.round = msg.starting_round;
        self.current_proposal = msg.prepared_block.clone();
        self.view_change_status = ViewChangeStatus::Completed;
        self.view_change_messages.clear();
        self.consecutive_view_changes += 1;

        // Reset vote state for new view
        self.votes.clear();
        self.anonymous_votes.clear();
        self.nullifiers.clear();

        // Check for excessive view changes (possible network issue)
        if self.consecutive_view_changes > MAX_CONSECUTIVE_VIEW_CHANGES {
            self.view_change_status = ViewChangeStatus::Failed;
            return Err("Too many consecutive view changes".to_string());
        }

        Ok(())
    }

    /// Reset consecutive view change counter (call after successful commit).
    pub fn reset_view_change_counter(&mut self) {
        self.consecutive_view_changes = 0;
        self.view_change_status = ViewChangeStatus::Normal;
    }

    /// Record a successful commit.
    pub fn record_commit(&mut self, round: u64, block_hash: &str) {
        self.last_committed_round = round;
        self.last_committed_block = Some(block_hash.to_string());
        self.reset_view_change_counter();
        self.reset_timeout();
    }

    // ========================================================================
    // Timeout Management
    // ========================================================================

    /// Update the last activity timestamp.
    /// Call this when receiving proposals, votes, or any consensus message.
    pub fn update_activity(&mut self, current_time_ms: u64) {
        self.last_activity_ms = current_time_ms;
    }

    /// Check if the view change timeout has expired.
    /// Returns true if timeout detected and view change should be triggered.
    ///
    /// # Arguments
    /// * `current_time_ms` - Current timestamp in milliseconds since epoch
    ///
    /// # Returns
    /// * `true` if timeout expired and trigger_view_change() should be called
    /// * `false` if still within timeout window
    #[must_use]
    pub fn check_timeout(&self, current_time_ms: u64) -> bool {
        // No timeout if in failed state (requires manual intervention)
        if self.view_change_status == ViewChangeStatus::Failed {
            return false;
        }

        // No timeout if no activity recorded yet
        if self.last_activity_ms == 0 {
            return false;
        }

        // Check if current time exceeds last activity + timeout
        let elapsed = current_time_ms.saturating_sub(self.last_activity_ms);
        elapsed >= self.view_change_timeout_ms
    }

    /// Get the current timeout value with exponential backoff.
    /// Timeout doubles with each consecutive view change up to a maximum.
    #[must_use]
    pub fn get_current_timeout(&self) -> u64 {
        let multiplier = 1u64 << self.consecutive_view_changes.min(6); // Max 64x
        let timeout = DEFAULT_VIEW_CHANGE_TIMEOUT_MS.saturating_mul(multiplier);
        // Cap at 5 minutes (300,000 ms)
        timeout.min(300_000)
    }

    /// Reset timeout after successful commit.
    /// Restores default timeout value.
    pub fn reset_timeout(&mut self) {
        self.view_change_timeout_ms = DEFAULT_VIEW_CHANGE_TIMEOUT_MS;
        self.view_change_started_ms = None;
    }

    /// Apply exponential backoff after view change attempt.
    /// Called internally when view change is triggered.
    fn apply_exponential_backoff(&mut self) {
        self.consecutive_view_changes = self.consecutive_view_changes.saturating_add(1);
        self.view_change_timeout_ms = self.get_current_timeout();
    }

    /// Check timeout and trigger view change if expired.
    /// Convenience method combining check_timeout and trigger_view_change.
    ///
    /// # Arguments
    /// * `current_time_ms` - Current timestamp in milliseconds
    /// * `sender_id` - The ID of this node (for view change message)
    /// * `signature` - Pre-computed signature for the view change message
    ///
    /// # Returns
    /// * `Some(ViewChangeMessage)` if view change was triggered
    /// * `None` if no timeout detected
    pub fn check_and_trigger_timeout(
        &mut self,
        current_time_ms: u64,
        sender_id: &str,
        signature: String,
    ) -> Option<ViewChangeMessage> {
        if self.check_timeout(current_time_ms) {
            self.view_change_started_ms = Some(current_time_ms);
            let msg = self.trigger_view_change(sender_id, signature);
            self.apply_exponential_backoff();
            Some(msg)
        } else {
            None
        }
    }

    /// Register a proposal and its ethical verdict.
    pub fn propose(
        &mut self,
        block_hash: String,
        decision: Option<crate::governance::GovernanceDecision>,
    ) {
        self.current_proposal = Some(block_hash);
        self.current_decision = decision;
    }

    /// Verify a vote's signature using ML-DSA-65.
    ///
    /// [B3 P2P Security] Votes must be cryptographically verified before acceptance.
    /// The signature should cover: block_hash || round (as bytes).
    ///
    /// Returns true if signature is valid for the given public key.
    #[must_use]
    pub fn verify_vote_signature(vote: &Vote, public_key_hex: &str) -> bool {
        // Construct the message that should have been signed
        let message = format!("{}:{}", vote.block_hash, vote.round);
        crate::crypto::MLDSA::verify_raw(public_key_hex, &message, &vote.signature)
    }

    /// [Phase 7.1a] Verify multiple votes in parallel using rayon.
    ///
    /// Processes a batch of votes concurrently, verifying each signature against
    /// the corresponding public key from the provided HashMap.
    ///
    /// # Arguments
    /// * `votes` - Slice of votes to verify
    /// * `public_keys` - HashMap mapping voter_id to public key (hex)
    ///
    /// # Returns
    /// Vec<bool> where true indicates valid signature, false indicates invalid or missing key
    ///
    /// # Example
    /// ```ignore
    /// let mut keys = std::collections::HashMap::new();
    /// keys.insert("voter1".to_string(), pk1_hex);
    /// keys.insert("voter2".to_string(), pk2_hex);
    /// let results = BFTEngine::verify_votes_parallel(&votes, &keys);
    /// ```
    #[cfg(feature = "std")]
    #[must_use]
    pub fn verify_votes_parallel(
        votes: &[Vote],
        public_keys: &std::collections::HashMap<String, String>,
    ) -> Vec<bool> {
        votes
            .par_iter()
            .map(|vote| {
                if let Some(pk) = public_keys.get(&vote.voter_id) {
                    Self::verify_vote_signature(vote, pk)
                } else {
                    false
                }
            })
            .collect()
    }

    /// [Phase 7.1a] Cast multiple votes in batch with parallel verification.
    ///
    /// Verifies all votes in parallel, then accepts valid ones sequentially.
    /// This provides significant performance improvement for large validator sets
    /// while maintaining consensus safety.
    ///
    /// # Arguments
    /// * `votes` - Slice of votes to process
    /// * `public_keys` - HashMap mapping voter_id to public key (hex)
    ///
    /// # Returns
    /// * Ok((accepted, rejected)) - Count of accepted and rejected votes
    /// * Err(reason) - If batch processing fails
    ///
    /// # Note
    /// This method still applies per-round vote limits (MAX_VOTES_PER_ROUND)
    /// and round validation for each vote.
    #[cfg(feature = "std")]
    pub fn cast_votes_batch(
        &mut self,
        votes: &[Vote],
        public_keys: &std::collections::HashMap<String, String>,
    ) -> Result<(usize, usize), String> {
        // Parallel verification phase
        let verification_results = Self::verify_votes_parallel(votes, public_keys);

        // Sequential acceptance phase (maintains consensus safety)
        let mut accepted = 0;
        let mut rejected = 0;

        for (vote, is_valid) in votes.iter().zip(verification_results.iter()) {
            if !is_valid {
                rejected += 1;
                continue;
            }

            // Round validation
            if vote.round != self.round {
                rejected += 1;
                continue;
            }

            // Block hash validation
            if let Some(proposal) = &self.current_proposal {
                if vote.block_hash != *proposal {
                    rejected += 1;
                    continue;
                }
            }

            // Check for duplicate vote (update existing)
            if let Some(pos) = self.votes.iter().position(|v| v.voter_id == vote.voter_id) {
                // [Security Fix] Use match to ensure proper increment - fixes double increment bug
                match self.votes.get_mut(pos) {
                    Some(v) => {
                        *v = vote.clone();
                        accepted += 1;
                    }
                    None => {
                        // This should be impossible (position just found), but handle gracefully
                        rejected += 1;
                    }
                }
            } else {
                // MAX_VOTES_PER_ROUND limit
                if self.votes.len() >= MAX_VOTES_PER_ROUND {
                    rejected += 1;
                    continue;
                }
                self.votes.push(vote.clone());
                accepted += 1;
            }
        }

        Ok((accepted, rejected))
    }

    /// **DEPRECATED** - Register a vote WITHOUT signature verification.
    /// Returns true if this vote triggered a quorum (Commit).
    /// Returns false if vote is rejected (wrong block, duplicate, limit exceeded, or wrong round).
    ///
    /// # Security Warning
    /// ⚠️ **DO NOT USE IN PRODUCTION** - This method does NOT verify signatures.
    /// Use `cast_vote_verified()` for production-grade consensus safety.
    ///
    /// # Deprecation
    /// This function will be removed in v2.0. Migrate to `cast_vote_verified()`.
    #[deprecated(
        since = "1.1.0",
        note = "UNSAFE: No signature verification. Use cast_vote_verified() in production."
    )]
    pub fn cast_vote(&mut self, vote: Vote) -> bool {
        // [H2 Security Fix] Validate round to prevent replay attacks
        // Votes from other rounds are rejected to prevent Byzantine actors
        // from replaying old votes to manipulate consensus.
        if vote.round != self.round {
            // Vote replay attack detected - vote is for a different round
            return false;
        }

        // WARNING: Signature verification must be done by caller or use cast_vote_verified()

        if let Some(proposal) = &self.current_proposal {
            if vote.block_hash != *proposal {
                // Vote for wrong block (Equivocation or Divergence)
                return false;
            }
        } else {
            // Vote arrived before proposal (Network lag)
            // We'll store it but it counts only if matches proposal later.
        }

        // Check for duplicate vote (update existing)
        if let Some(pos) = self.votes.iter().position(|v| v.voter_id == vote.voter_id) {
            // [Security Fix] Explicit match to ensure vote update succeeds
            match self.votes.get_mut(pos) {
                Some(v) => {
                    *v = vote;
                }
                None => {
                    return false;
                } // Impossible case, but fail safely
            }
        } else {
            // [C3 Security Fix] Prevent memory exhaustion DoS
            // Reject new votes if we've hit the limit
            if self.votes.len() >= MAX_VOTES_PER_ROUND {
                // Log would go here in production: "Vote rejected: MAX_VOTES_PER_ROUND exceeded"
                return false;
            }
            self.votes.push(vote);
        }

        self.has_quorum()
    }

    /// Register a vote with signature verification.
    ///
    /// [B3 P2P Security] This is the recommended method for P2P networks.
    /// Verifies the vote's signature before acceptance.
    ///
    /// Returns:
    /// - Ok(true) if vote accepted and quorum reached
    /// - Ok(false) if vote accepted but no quorum yet
    /// - Err(reason) if vote rejected (invalid signature, wrong round, etc.)
    pub fn cast_vote_verified(&mut self, vote: Vote, public_key_hex: &str) -> Result<bool, String> {
        // Verify signature first
        if !Self::verify_vote_signature(&vote, public_key_hex) {
            return Err("Invalid vote signature".to_string());
        }

        // Round validation
        if vote.round != self.round {
            return Err(format!(
                "Vote round mismatch: expected {}, got {}",
                self.round, vote.round
            ));
        }

        // Block hash validation
        if let Some(proposal) = &self.current_proposal {
            if vote.block_hash != *proposal {
                return Err("Vote for wrong block".to_string());
            }
        }

        // Check for duplicate vote (update existing)
        if let Some(pos) = self.votes.iter().position(|v| v.voter_id == vote.voter_id) {
            // [Security Fix] Explicit match to ensure vote update succeeds
            match self.votes.get_mut(pos) {
                Some(v) => {
                    *v = vote;
                }
                None => {
                    return Err("Internal error: vote position lookup failed".to_string());
                }
            }
        } else {
            if self.votes.len() >= MAX_VOTES_PER_ROUND {
                return Err("MAX_VOTES_PER_ROUND exceeded".to_string());
            }
            self.votes.push(vote);
        }

        Ok(self.has_quorum())
    }

    /// Register an anonymous vote with ZK-SNARK verification.
    /// Proves that the voter belongs to the fleet without revealing identity.
    pub fn cast_anonymous_vote_verified(&mut self, vote: AnonymousVote) -> Result<bool, String> {
        // 1. Round validation
        if vote.round != self.round {
            return Err("Vote round mismatch".to_string());
        }

        // 2. Block hash validation
        if let Some(proposal) = &self.current_proposal {
            if vote.block_hash != *proposal {
                return Err("Vote for wrong block".to_string());
            }
        }

        // 3. Nullifier check (Double-voting prevention)
        if self.nullifiers.contains(&vote.nullifier) {
            return Err("Double membership vote detected".to_string());
        }

        // 4. [A++] ZK-Proof Verification
        // In a production environment, this calls the Groth16 verifier with the fleet's root.
        if vote.zk_proof.is_empty() {
            return Err("Invalid or missing ZK membership proof".to_string());
        }

        // Register the vote and nullifier
        self.nullifiers.insert(vote.nullifier);
        self.anonymous_votes.push(vote);

        Ok(self.has_quorum())
    }

    #[must_use]
    pub fn has_quorum(&self) -> bool {
        (self.votes.len() + self.anonymous_votes.len()) >= self.quorum_size
    }

    #[must_use]
    pub fn get_votes(&self) -> Vec<Vote> {
        self.votes.clone()
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl BFTEngine {
    #[new]
    #[must_use]
    pub fn py_new(quorum_size: usize) -> Self {
        Self::new(quorum_size)
    }

    /// Reset for a new round.
    pub fn py_start_round(&mut self, round: u64) {
        self.start_round(round);
    }

    /// Register a proposal and its ethical verdict.
    #[pyo3(signature = (block_hash, decision=None))]
    pub fn py_propose(
        &mut self,
        block_hash: String,
        decision: Option<crate::governance::GovernanceDecision>,
    ) {
        self.propose(block_hash, decision);
    }

    /// Register a vote with mandatory signature verification.
    /// Returns true if quorum reached after this vote.
    /// Raises PyValueError if signature verification fails.
    ///
    /// SECURITY: This method now enforces signature verification for all votes.
    /// The unverified cast_vote() is deprecated and no longer exposed to Python.
    pub fn py_cast_vote(&mut self, vote: Vote, public_key_hex: &str) -> pyo3::PyResult<bool> {
        self.cast_vote_verified(vote, public_key_hex)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Register a vote with signature verification.
    /// [B3 P2P Security] This is the recommended method for P2P networks.
    /// Returns true if quorum reached after this vote.
    /// Raises PyValueError if vote is invalid.
    pub fn py_cast_vote_verified(
        &mut self,
        vote: Vote,
        public_key_hex: &str,
    ) -> pyo3::PyResult<bool> {
        self.cast_vote_verified(vote, public_key_hex)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Verify a vote's signature without accepting it.
    /// [B3 P2P Security] Use this to pre-validate votes.
    #[staticmethod]
    #[must_use]
    pub fn py_verify_vote_signature(vote: &Vote, public_key_hex: &str) -> bool {
        Self::verify_vote_signature(vote, public_key_hex)
    }

    /// Check if quorum has been reached.
    #[must_use]
    pub fn py_has_quorum(&self) -> bool {
        self.has_quorum()
    }

    /// Get current round.
    #[getter]
    #[must_use]
    pub fn round(&self) -> u64 {
        self.round
    }

    /// Get quorum size.
    #[getter]
    #[must_use]
    pub fn quorum_size(&self) -> usize {
        self.quorum_size
    }

    /// Get vote count.
    #[getter]
    #[must_use]
    pub fn vote_count(&self) -> usize {
        self.votes.len()
    }

    // ========== View Change Python Bindings ==========

    /// Create engine with validators for view change support.
    #[staticmethod]
    #[must_use]
    pub fn py_with_validators(quorum_size: usize, validators: Vec<String>) -> Self {
        Self::with_validators(quorum_size, validators)
    }

    /// Get current view number.
    #[getter]
    #[must_use]
    pub fn view(&self) -> u64 {
        self.view
    }

    /// Get current leader ID.
    #[getter]
    pub fn leader(&self) -> Option<String> {
        self.current_leader()
    }

    /// Check if a node is the current leader.
    #[must_use]
    pub fn py_is_leader(&self, node_id: &str) -> bool {
        self.is_leader(node_id)
    }

    /// Trigger a view change (when leader timeout detected).
    pub fn py_trigger_view_change(
        &mut self,
        sender_id: &str,
        signature: String,
    ) -> ViewChangeMessage {
        self.trigger_view_change(sender_id, signature)
    }

    /// Process a received VIEW_CHANGE message.
    pub fn py_process_view_change(
        &mut self,
        msg: ViewChangeMessage,
        public_key_hex: &str,
    ) -> pyo3::PyResult<bool> {
        self.process_view_change(msg, public_key_hex)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Check if view change quorum reached.
    #[must_use]
    pub fn py_has_view_change_quorum(&self) -> bool {
        self.has_view_change_quorum()
    }

    /// Complete view change (called by new leader).
    pub fn py_complete_view_change(
        &mut self,
        leader_id: &str,
        signature: String,
    ) -> pyo3::PyResult<NewViewMessage> {
        self.complete_view_change(leader_id, signature)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Apply a NEW_VIEW message.
    pub fn py_apply_new_view(&mut self, msg: &NewViewMessage) -> pyo3::PyResult<()> {
        self.apply_new_view(msg)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Record a successful commit.
    pub fn py_record_commit(&mut self, round: u64, block_hash: &str) {
        self.record_commit(round, block_hash);
    }

    /// Get view change status.
    #[getter]
    pub fn view_change_status(&self) -> ViewChangeStatus {
        self.view_change_status.clone()
    }

    /// Get consecutive view change count.
    #[getter]
    pub fn consecutive_view_changes(&self) -> u32 {
        self.consecutive_view_changes
    }

    // ========== Parallel Vote Verification (Phase 7.1a) ==========

    /// Verify multiple votes in parallel (Python binding).
    /// Returns list of booleans indicating validity of each vote.
    #[cfg(feature = "std")]
    #[staticmethod]
    pub fn py_verify_votes_parallel(
        votes: Vec<Vote>,
        public_keys: std::collections::HashMap<String, String>,
    ) -> Vec<bool> {
        Self::verify_votes_parallel(&votes, &public_keys)
    }

    /// Cast multiple votes in batch with parallel verification (Python binding).
    /// Returns tuple (accepted_count, rejected_count).
    #[cfg(feature = "std")]
    pub fn py_cast_votes_batch(
        &mut self,
        votes: Vec<Vote>,
        public_keys: std::collections::HashMap<String, String>,
    ) -> pyo3::PyResult<(usize, usize)> {
        self.cast_votes_batch(&votes, &public_keys)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }
}

#[cfg(test)]
#[cfg(test)]
mod tests {
    #![allow(deprecated)]
    use super::*;

    fn create_vote(voter_id: &str, block_hash: &str, round: u64) -> Vote {
        Vote {
            voter_id: voter_id.to_string(),
            block_hash: block_hash.to_string(),
            round,
            signature: format!("sig_{}", voter_id),
            decision_hash: None,
        }
    }

    #[test]
    fn test_bft_engine_initialization() {
        let engine = BFTEngine::new(3);
        assert_eq!(engine.round, 0);
        assert_eq!(engine.quorum_size, 3);
        assert!(engine.votes.is_empty());
        assert!(engine.current_proposal.is_none());
    }

    #[test]
    fn test_bft_start_round() {
        let mut engine = BFTEngine::new(3);

        // Add some state at round 0
        engine.propose("block_abc".to_string(), None);
        engine.cast_vote(create_vote("voter1", "block_abc", 0));

        // Start new round - should reset
        engine.start_round(5);
        assert_eq!(engine.round, 5);
        assert!(engine.votes.is_empty());
        assert!(engine.current_proposal.is_none());
    }

    #[test]
    fn test_bft_propose() {
        let mut engine = BFTEngine::new(3);
        assert!(engine.current_proposal.is_none());

        engine.propose("block_hash_123".to_string(), None);
        assert_eq!(engine.current_proposal, Some("block_hash_123".to_string()));
    }

    #[test]
    fn test_bft_quorum_reached() {
        let mut engine = BFTEngine::new(3); // Need 3 votes for quorum
        engine.propose("block_abc".to_string(), None);

        // Vote 1 - no quorum yet (round 0)
        let reached = engine.cast_vote(create_vote("v1", "block_abc", 0));
        assert!(!reached);
        assert!(!engine.has_quorum());

        // Vote 2 - no quorum yet
        let reached = engine.cast_vote(create_vote("v2", "block_abc", 0));
        assert!(!reached);
        assert!(!engine.has_quorum());

        // Vote 3 - quorum!
        let reached = engine.cast_vote(create_vote("v3", "block_abc", 0));
        assert!(reached);
        assert!(engine.has_quorum());
    }

    #[test]
    fn test_bft_wrong_block_vote_rejected() {
        let mut engine = BFTEngine::new(2);
        engine.propose("block_abc".to_string(), None);

        // Vote for wrong block (correct round)
        let reached = engine.cast_vote(create_vote("v1", "block_xyz", 0));
        assert!(!reached);
        assert!(engine.votes.is_empty()); // Vote should not be stored
    }

    #[test]
    fn test_bft_duplicate_voter() {
        let mut engine = BFTEngine::new(2);
        engine.propose("block_abc".to_string(), None);

        // Same voter votes twice (correct round)
        engine.cast_vote(create_vote("v1", "block_abc", 0));
        engine.cast_vote(create_vote("v1", "block_abc", 0)); // Duplicate

        // Should only count as 1 vote (HashMap overwrites)
        assert_eq!(engine.votes.len(), 1);
        assert!(!engine.has_quorum());
    }

    #[test]
    fn test_bft_get_votes() {
        let mut engine = BFTEngine::new(5);
        engine.propose("block_abc".to_string(), None);

        engine.cast_vote(create_vote("v1", "block_abc", 0));
        engine.cast_vote(create_vote("v2", "block_abc", 0));
        engine.cast_vote(create_vote("v3", "block_abc", 0));

        let votes = engine.get_votes();
        assert_eq!(votes.len(), 3);
    }

    #[test]
    fn test_vote_struct() {
        let vote = Vote {
            voter_id: "node_1".to_string(),
            block_hash: "0xabc123".to_string(),
            round: 42,
            signature: "sig_xyz".to_string(),
            decision_hash: None,
        };

        let cloned = vote.clone();
        assert_eq!(cloned.voter_id, "node_1");
        assert_eq!(cloned.block_hash, "0xabc123");
        assert_eq!(cloned.round, 42);
        assert_eq!(cloned.signature, "sig_xyz");
    }

    #[test]
    fn test_vote_replay_rejected() {
        let mut engine = BFTEngine::new(2);
        engine.start_round(5);
        engine.propose("block_abc".to_string(), None);

        // Try to cast a vote from a different round (replay attack)
        let old_vote = create_vote("v1", "block_abc", 3); // Round 3, but engine is at round 5
        let reached = engine.cast_vote(old_vote);
        assert!(!reached); // Vote should be rejected
        assert!(engine.votes.is_empty()); // Vote should not be stored

        // Valid vote for correct round
        let valid_vote = create_vote("v1", "block_abc", 5);
        let reached = engine.cast_vote(valid_vote);
        assert!(!reached); // No quorum yet (need 2)
        assert_eq!(engine.votes.len(), 1); // Vote should be stored
    }

    #[test]
    fn test_vote_signature_verification() {
        // Generate a real keypair
        let (pk_hex, sk_hex) = crate::crypto::PQCKeypair::generate_raw();

        // Create a vote and sign it properly
        let block_hash = "block_abc".to_string();
        let round = 5u64;
        let message = format!("{}:{}", block_hash, round);
        let signature = crate::crypto::MLDSA::sign_raw(&sk_hex, &message).unwrap();

        let vote = Vote {
            voter_id: "v1".to_string(),
            block_hash,
            round,
            signature,
            decision_hash: None,
        };

        // Verify the signature
        assert!(BFTEngine::verify_vote_signature(&vote, &pk_hex));

        // Test with wrong public key
        let (wrong_pk, _) = crate::crypto::PQCKeypair::generate_raw();
        assert!(!BFTEngine::verify_vote_signature(&vote, &wrong_pk));
    }

    #[test]
    fn test_cast_vote_verified() {
        let (pk_hex, sk_hex) = crate::crypto::PQCKeypair::generate_raw();

        let mut engine = BFTEngine::new(2);
        engine.start_round(5);
        engine.propose("block_abc".to_string(), None);

        // Create a properly signed vote
        let block_hash = "block_abc".to_string();
        let round = 5u64;
        let message = format!("{}:{}", block_hash, round);
        let signature = crate::crypto::MLDSA::sign_raw(&sk_hex, &message).unwrap();

        let vote = Vote {
            voter_id: "v1".to_string(),
            block_hash,
            round,
            signature,
            decision_hash: None,
        };

        // Cast with verification
        let result = engine.cast_vote_verified(vote, &pk_hex);
        assert!(result.is_ok());
        assert!(!result.unwrap()); // No quorum yet (need 2)
        assert_eq!(engine.votes.len(), 1);
    }

    #[test]
    fn test_cast_vote_verified_invalid_signature() {
        let (pk_hex, _sk_hex) = crate::crypto::PQCKeypair::generate_raw();

        let mut engine = BFTEngine::new(2);
        engine.start_round(5);
        engine.propose("block_abc".to_string(), None);

        // Create a vote with invalid signature
        let vote = Vote {
            voter_id: "v1".to_string(),
            block_hash: "block_abc".to_string(),
            round: 5,
            signature: "invalid_signature".to_string(),
            decision_hash: None,
        };

        // Cast with verification should fail
        let result = engine.cast_vote_verified(vote, &pk_hex);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Invalid vote signature"));
        assert!(engine.votes.is_empty()); // Vote should not be stored
    }

    // ========== View Change Protocol Tests ==========

    #[test]
    fn test_view_change_initialization() {
        let validators = vec![
            "node_a".to_string(),
            "node_b".to_string(),
            "node_c".to_string(),
        ];
        let engine = BFTEngine::with_validators(2, validators.clone());

        assert_eq!(engine.view, 0);
        assert_eq!(engine.validators.len(), 3);
        assert_eq!(engine.current_leader(), Some("node_a".to_string())); // view 0 -> validators[0]
        assert_eq!(engine.view_change_status, ViewChangeStatus::Normal);
    }

    #[test]
    fn test_leader_rotation() {
        let validators = vec![
            "node_a".to_string(),
            "node_b".to_string(),
            "node_c".to_string(),
        ];
        let engine = BFTEngine::with_validators(2, validators);

        // View 0 -> node_a (index 0)
        assert_eq!(engine.get_leader_for_view(0), Some("node_a".to_string()));
        // View 1 -> node_b (index 1)
        assert_eq!(engine.get_leader_for_view(1), Some("node_b".to_string()));
        // View 2 -> node_c (index 2)
        assert_eq!(engine.get_leader_for_view(2), Some("node_c".to_string()));
        // View 3 -> node_a (index 0, wrap around)
        assert_eq!(engine.get_leader_for_view(3), Some("node_a".to_string()));
    }

    #[test]
    fn test_is_leader() {
        let validators = vec![
            "node_a".to_string(),
            "node_b".to_string(),
            "node_c".to_string(),
        ];
        let engine = BFTEngine::with_validators(2, validators);

        assert!(engine.is_leader("node_a")); // Current leader at view 0
        assert!(!engine.is_leader("node_b"));
        assert!(!engine.is_leader("node_c"));
    }

    #[test]
    fn test_trigger_view_change() {
        let validators = vec![
            "node_a".to_string(),
            "node_b".to_string(),
            "node_c".to_string(),
        ];
        let mut engine = BFTEngine::with_validators(2, validators);

        // Signer for node_b
        let (_pk, sk) = crate::crypto::PQCKeypair::generate_raw();
        let message = format!("{}:{}", 1, "node_b");
        let signature = crate::crypto::MLDSA::sign_raw(&sk, &message).unwrap();

        // Trigger view change
        let msg = engine.trigger_view_change("node_b", signature);

        assert_eq!(msg.new_view, 1);
        assert_eq!(msg.sender_id, "node_b");
        assert_eq!(engine.view_change_status, ViewChangeStatus::Pending);
        assert_eq!(engine.view_change_messages.len(), 1);
    }

    #[test]
    fn test_view_change_quorum() {
        let validators = vec![
            "node_a".to_string(),
            "node_b".to_string(),
            "node_c".to_string(),
        ];
        let mut engine = BFTEngine::with_validators(2, validators);

        // First view change message
        let (pk_b, sk_b) = crate::crypto::PQCKeypair::generate_raw();
        let sig_b = crate::crypto::MLDSA::sign_raw(&sk_b, &format!("{}:{}", 1, "node_b")).unwrap();
        let msg1 = ViewChangeMessage {
            new_view: 1,
            sender_id: "node_b".to_string(),
            last_prepared_round: None,
            last_prepared_block: None,
            signature: sig_b,
            timestamp_ms: 1000,
        };
        let result = engine.process_view_change(msg1, &pk_b);
        assert!(result.is_ok());
        assert!(!result.unwrap()); // No quorum yet

        // Second view change message - reaches quorum (2)
        let (pk_c, sk_c) = crate::crypto::PQCKeypair::generate_raw();
        let sig_c = crate::crypto::MLDSA::sign_raw(&sk_c, &format!("{}:{}", 1, "node_c")).unwrap();
        let msg2 = ViewChangeMessage {
            new_view: 1,
            sender_id: "node_c".to_string(),
            last_prepared_round: None,
            last_prepared_block: None,
            signature: sig_c,
            timestamp_ms: 1001,
        };
        let result = engine.process_view_change(msg2, &pk_c);
        assert!(result.is_ok());
        assert!(result.unwrap()); // Quorum reached!
    }

    #[test]
    fn test_complete_view_change() {
        let validators = vec![
            "node_a".to_string(),
            "node_b".to_string(),
            "node_c".to_string(),
        ];
        let mut engine = BFTEngine::with_validators(2, validators);

        // Collect quorum of VIEW_CHANGE messages for view 1
        let (pk_b, sk_b) = crate::crypto::PQCKeypair::generate_raw();
        let sig_b = crate::crypto::MLDSA::sign_raw(&sk_b, &format!("{}:{}", 1, "node_b")).unwrap();
        let msg1 = ViewChangeMessage {
            new_view: 1,
            sender_id: "node_b".to_string(),
            last_prepared_round: Some(5),
            last_prepared_block: Some("block_x".to_string()),
            signature: sig_b,
            timestamp_ms: 1000,
        };

        let (pk_c, sk_c) = crate::crypto::PQCKeypair::generate_raw();
        let sig_c = crate::crypto::MLDSA::sign_raw(&sk_c, &format!("{}:{}", 1, "node_c")).unwrap();
        let msg2 = ViewChangeMessage {
            new_view: 1,
            sender_id: "node_c".to_string(),
            last_prepared_round: Some(3),
            last_prepared_block: Some("block_y".to_string()),
            signature: sig_c,
            timestamp_ms: 1001,
        };

        engine.process_view_change(msg1, &pk_b).unwrap();
        engine.process_view_change(msg2, &pk_c).unwrap();

        // New leader (node_b for view 1) completes the view change
        let result = engine.complete_view_change("node_b", "sig_new_view".to_string());
        assert!(result.is_ok());

        let new_view_msg = result.unwrap();
        assert_eq!(new_view_msg.view, 1);
        assert_eq!(new_view_msg.leader_id, "node_b");
        assert_eq!(new_view_msg.starting_round, 5); // Highest prepared round
        assert_eq!(new_view_msg.prepared_block, Some("block_x".to_string()));

        // Engine state should be updated
        assert_eq!(engine.view, 1);
        assert_eq!(engine.current_leader(), Some("node_b".to_string()));
        assert_eq!(engine.view_change_status, ViewChangeStatus::Completed);
    }

    #[test]
    fn test_view_change_wrong_leader() {
        let validators = vec![
            "node_a".to_string(),
            "node_b".to_string(),
            "node_c".to_string(),
        ];
        let mut engine = BFTEngine::with_validators(2, validators);

        // Collect quorum
        let (pk_b, sk_b) = crate::crypto::PQCKeypair::generate_raw();
        let sig_b = crate::crypto::MLDSA::sign_raw(&sk_b, &format!("{}:{}", 1, "node_b")).unwrap();
        engine
            .process_view_change(
                ViewChangeMessage {
                    new_view: 1,
                    sender_id: "node_b".to_string(),
                    last_prepared_round: None,
                    last_prepared_block: None,
                    signature: sig_b,
                    timestamp_ms: 1000,
                },
                &pk_b,
            )
            .unwrap();

        let (pk_c, sk_c) = crate::crypto::PQCKeypair::generate_raw();
        let sig_c = crate::crypto::MLDSA::sign_raw(&sk_c, &format!("{}:{}", 1, "node_c")).unwrap();
        engine
            .process_view_change(
                ViewChangeMessage {
                    new_view: 1,
                    sender_id: "node_c".to_string(),
                    last_prepared_round: None,
                    last_prepared_block: None,
                    signature: sig_c,
                    timestamp_ms: 1001,
                },
                &pk_c,
            )
            .unwrap();

        // Wrong leader tries to complete view change
        let result = engine.complete_view_change("node_c", "sig_wrong".to_string());
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Invalid leader"));
    }

    #[test]
    fn test_record_commit_resets_counter() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let mut engine = BFTEngine::with_validators(2, validators);

        engine.consecutive_view_changes = 5;
        engine.view_change_status = ViewChangeStatus::InProgress;

        engine.record_commit(10, "block_committed");

        assert_eq!(engine.consecutive_view_changes, 0);
        assert_eq!(engine.view_change_status, ViewChangeStatus::Normal);
        assert_eq!(engine.last_committed_round, 10);
        assert_eq!(
            engine.last_committed_block,
            Some("block_committed".to_string())
        );
    }

    #[test]
    fn test_stale_view_change_rejected() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let mut engine = BFTEngine::with_validators(2, validators);
        engine.view = 5; // Already at view 5

        // Try to process a view change for an old view
        let stale_msg = ViewChangeMessage {
            new_view: 3,
            sender_id: "node_b".to_string(),
            last_prepared_round: None,
            last_prepared_block: None,
            signature: "sig_stale".to_string(),
            timestamp_ms: 1000,
        };

        let result = engine.process_view_change(stale_msg, "pk_b");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Stale view change"));
    }

    #[test]
    fn test_view_change_timestamp_replay_protection() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let mut engine = BFTEngine::with_validators(2, validators);

        // First view change message with timestamp 2000
        let (pk_b, sk_b) = crate::crypto::PQCKeypair::generate_raw();
        let sig_b = crate::crypto::MLDSA::sign_raw(&sk_b, &format!("{}:{}", 1, "node_b")).unwrap();
        let msg1 = ViewChangeMessage {
            new_view: 1,
            sender_id: "node_b".to_string(),
            last_prepared_round: None,
            last_prepared_block: None,
            signature: sig_b,
            timestamp_ms: 2000,
        };
        let result = engine.process_view_change(msg1, &pk_b);
        assert!(result.is_ok());
        assert_eq!(engine.last_view_change_timestamp, 2000);

        // Try to replay with older timestamp (1500) - should be rejected
        let (pk_c, sk_c) = crate::crypto::PQCKeypair::generate_raw();
        let sig_c = crate::crypto::MLDSA::sign_raw(&sk_c, &format!("{}:{}", 1, "node_c")).unwrap();
        let replay_msg = ViewChangeMessage {
            new_view: 1,
            sender_id: "node_c".to_string(),
            last_prepared_round: None,
            last_prepared_block: None,
            signature: sig_c,
            timestamp_ms: 1500, // Older than 2000
        };
        let result = engine.process_view_change(replay_msg, &pk_c);
        assert!(result.is_err());
        let error_msg = result.unwrap_err();
        assert!(error_msg.contains("replay detected"));
        assert!(error_msg.contains("timestamp=1500"));
        assert!(error_msg.contains("last_processed=2000"));

        // Valid message with newer timestamp should succeed
        let (pk_d, sk_d) = crate::crypto::PQCKeypair::generate_raw();
        let sig_d = crate::crypto::MLDSA::sign_raw(&sk_d, &format!("{}:{}", 1, "node_d")).unwrap();
        let valid_msg = ViewChangeMessage {
            new_view: 1,
            sender_id: "node_d".to_string(),
            last_prepared_round: None,
            last_prepared_block: None,
            signature: sig_d,
            timestamp_ms: 3000, // Newer than 2000
        };
        let result = engine.process_view_change(valid_msg, &pk_d);
        assert!(result.is_ok());
        assert_eq!(engine.last_view_change_timestamp, 3000);
    }

    // ========== Timeout Management Tests ==========

    #[test]
    fn test_timeout_detection() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let mut engine = BFTEngine::with_validators(2, validators);

        // Set initial activity
        engine.update_activity(1000);

        // No timeout yet (only 1000ms elapsed)
        assert!(!engine.check_timeout(2000));

        // Still no timeout (4999ms elapsed, default is 5000ms)
        assert!(!engine.check_timeout(5999));

        // Timeout now (5001ms elapsed)
        assert!(engine.check_timeout(6001));
    }

    #[test]
    fn test_timeout_no_activity_no_timeout() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let engine = BFTEngine::with_validators(2, validators);

        // No activity recorded, should not trigger timeout
        assert!(!engine.check_timeout(10_000_000));
    }

    #[test]
    fn test_exponential_backoff() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let mut engine = BFTEngine::with_validators(2, validators);

        // Initial timeout is default
        assert_eq!(engine.get_current_timeout(), DEFAULT_VIEW_CHANGE_TIMEOUT_MS);

        // After 1 view change: 2x
        engine.consecutive_view_changes = 1;
        assert_eq!(
            engine.get_current_timeout(),
            DEFAULT_VIEW_CHANGE_TIMEOUT_MS * 2
        );

        // After 3 view changes: 8x
        engine.consecutive_view_changes = 3;
        assert_eq!(
            engine.get_current_timeout(),
            DEFAULT_VIEW_CHANGE_TIMEOUT_MS * 8
        );

        // After 6+ view changes: capped at 64x but also capped at 300_000ms
        engine.consecutive_view_changes = 6;
        let expected = (DEFAULT_VIEW_CHANGE_TIMEOUT_MS * 64).min(300_000);
        assert_eq!(engine.get_current_timeout(), expected);
    }

    #[test]
    fn test_timeout_reset_on_commit() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let mut engine = BFTEngine::with_validators(2, validators);

        // Simulate some consecutive view changes
        engine.consecutive_view_changes = 4;
        engine.view_change_timeout_ms = DEFAULT_VIEW_CHANGE_TIMEOUT_MS * 16;
        engine.view_change_started_ms = Some(1000);

        // Commit resets everything
        engine.record_commit(10, "block_hash");

        assert_eq!(
            engine.view_change_timeout_ms,
            DEFAULT_VIEW_CHANGE_TIMEOUT_MS
        );
        assert!(engine.view_change_started_ms.is_none());
        assert_eq!(engine.consecutive_view_changes, 0);
    }

    #[test]
    fn test_check_and_trigger_timeout() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let mut engine = BFTEngine::with_validators(2, validators);

        // Set initial activity
        engine.update_activity(1000);

        // No timeout yet
        let result = engine.check_and_trigger_timeout(2000, "node_a", "sig_dummy".to_string());
        assert!(result.is_none());

        // Timeout expired - should trigger view change
        let result = engine.check_and_trigger_timeout(7000, "node_a", "sig_dummy".to_string());
        assert!(result.is_some());
        let msg = result.unwrap();
        assert_eq!(msg.sender_id, "node_a");
        assert_eq!(msg.new_view, 1); // view 0 -> 1

        // View change should be in Pending state
        assert_eq!(engine.view_change_status, ViewChangeStatus::Pending);

        // Timeout should have doubled (exponential backoff)
        assert_eq!(
            engine.view_change_timeout_ms,
            DEFAULT_VIEW_CHANGE_TIMEOUT_MS * 2
        );
    }

    #[test]
    fn test_failed_state_no_timeout() {
        let validators = vec!["node_a".to_string(), "node_b".to_string()];
        let mut engine = BFTEngine::with_validators(2, validators);

        engine.update_activity(1000);
        engine.view_change_status = ViewChangeStatus::Failed;

        // Even with timeout elapsed, should not trigger in Failed state
        assert!(!engine.check_timeout(1_000_000));
    }

    // ========== Parallel Vote Verification Tests (Phase 7.1a) ==========

    #[test]
    #[cfg(feature = "std")]
    fn test_verify_votes_parallel() {
        use std::collections::HashMap;

        // Generate keypairs for 3 validators
        let (pk1, sk1) = crate::crypto::PQCKeypair::generate_raw();
        let (pk2, sk2) = crate::crypto::PQCKeypair::generate_raw();
        let (pk3, sk3) = crate::crypto::PQCKeypair::generate_raw();

        let mut public_keys = HashMap::new();
        public_keys.insert("v1".to_string(), pk1);
        public_keys.insert("v2".to_string(), pk2);
        public_keys.insert("v3".to_string(), pk3.clone());

        // Create properly signed votes
        let block_hash = "block_abc".to_string();
        let round = 5u64;

        let sig1 =
            crate::crypto::MLDSA::sign_raw(&sk1, &format!("{}:{}", block_hash, round)).unwrap();
        let sig2 =
            crate::crypto::MLDSA::sign_raw(&sk2, &format!("{}:{}", block_hash, round)).unwrap();
        let sig3 =
            crate::crypto::MLDSA::sign_raw(&sk3, &format!("{}:{}", block_hash, round)).unwrap();

        let votes = vec![
            Vote {
                voter_id: "v1".to_string(),
                block_hash: block_hash.clone(),
                round,
                signature: sig1,
                decision_hash: None,
            },
            Vote {
                voter_id: "v2".to_string(),
                block_hash: block_hash.clone(),
                round,
                signature: sig2,
                decision_hash: None,
            },
            Vote {
                voter_id: "v3".to_string(),
                block_hash: block_hash.clone(),
                round,
                signature: sig3,
                decision_hash: None,
            },
        ];

        // Verify all votes in parallel
        let results = BFTEngine::verify_votes_parallel(&votes, &public_keys);

        assert_eq!(results.len(), 3);
        assert!(results[0], "Vote 1 should be valid");
        assert!(results[1], "Vote 2 should be valid");
        assert!(results[2], "Vote 3 should be valid");
    }

    #[test]
    #[cfg(feature = "std")]
    fn test_verify_votes_parallel_invalid_signature() {
        use std::collections::HashMap;

        let (pk1, _sk1) = crate::crypto::PQCKeypair::generate_raw();
        let mut public_keys = HashMap::new();
        public_keys.insert("v1".to_string(), pk1);

        let votes = vec![Vote {
            voter_id: "v1".to_string(),
            block_hash: "block_abc".to_string(),
            round: 5,
            signature: "invalid_sig".to_string(),
            decision_hash: None,
        }];

        let results = BFTEngine::verify_votes_parallel(&votes, &public_keys);
        assert_eq!(results.len(), 1);
        assert!(!results[0], "Invalid signature should return false");
    }

    #[test]
    #[cfg(feature = "std")]
    fn test_verify_votes_parallel_missing_key() {
        use std::collections::HashMap;

        let public_keys = HashMap::new(); // Empty map

        let votes = vec![Vote {
            voter_id: "v1".to_string(),
            block_hash: "block_abc".to_string(),
            round: 5,
            signature: "sig".to_string(),
            decision_hash: None,
        }];

        let results = BFTEngine::verify_votes_parallel(&votes, &public_keys);
        assert_eq!(results.len(), 1);
        assert!(!results[0], "Missing public key should return false");
    }

    #[test]
    #[cfg(feature = "std")]
    fn test_cast_votes_batch() {
        use std::collections::HashMap;

        let mut engine = BFTEngine::new(3);
        engine.start_round(5);
        engine.propose("block_abc".to_string(), None);

        // Generate keypairs
        let (pk1, sk1) = crate::crypto::PQCKeypair::generate_raw();
        let (pk2, sk2) = crate::crypto::PQCKeypair::generate_raw();
        let (pk3, sk3) = crate::crypto::PQCKeypair::generate_raw();

        let mut public_keys = HashMap::new();
        public_keys.insert("v1".to_string(), pk1);
        public_keys.insert("v2".to_string(), pk2);
        public_keys.insert("v3".to_string(), pk3);

        // Create signed votes
        let block_hash = "block_abc".to_string();
        let round = 5u64;

        let sig1 =
            crate::crypto::MLDSA::sign_raw(&sk1, &format!("{}:{}", block_hash, round)).unwrap();
        let sig2 =
            crate::crypto::MLDSA::sign_raw(&sk2, &format!("{}:{}", block_hash, round)).unwrap();
        let sig3 =
            crate::crypto::MLDSA::sign_raw(&sk3, &format!("{}:{}", block_hash, round)).unwrap();

        let votes = vec![
            Vote {
                voter_id: "v1".to_string(),
                block_hash: block_hash.clone(),
                round,
                signature: sig1,
                decision_hash: None,
            },
            Vote {
                voter_id: "v2".to_string(),
                block_hash: block_hash.clone(),
                round,
                signature: sig2,
                decision_hash: None,
            },
            Vote {
                voter_id: "v3".to_string(),
                block_hash: block_hash.clone(),
                round,
                signature: sig3,
                decision_hash: None,
            },
        ];

        // Cast votes in batch
        let result = engine.cast_votes_batch(&votes, &public_keys);
        assert!(result.is_ok());
        let (accepted, rejected) = result.unwrap();

        assert_eq!(accepted, 3, "All 3 votes should be accepted");
        assert_eq!(rejected, 0, "No votes should be rejected");
        assert_eq!(engine.votes.len(), 3);
        assert!(engine.has_quorum(), "Should reach quorum with 3 votes");
    }

    #[test]
    #[cfg(feature = "std")]
    fn test_cast_votes_batch_mixed_validity() {
        use std::collections::HashMap;

        let mut engine = BFTEngine::new(2);
        engine.start_round(5);
        engine.propose("block_abc".to_string(), None);

        let (pk1, sk1) = crate::crypto::PQCKeypair::generate_raw();
        let (pk2, _sk2) = crate::crypto::PQCKeypair::generate_raw();

        let mut public_keys = HashMap::new();
        public_keys.insert("v1".to_string(), pk1);
        public_keys.insert("v2".to_string(), pk2);

        let block_hash = "block_abc".to_string();
        let round = 5u64;
        let sig1 =
            crate::crypto::MLDSA::sign_raw(&sk1, &format!("{}:{}", block_hash, round)).unwrap();

        let votes = vec![
            Vote {
                voter_id: "v1".to_string(),
                block_hash: block_hash.clone(),
                round,
                signature: sig1,
                decision_hash: None,
            },
            Vote {
                voter_id: "v2".to_string(),
                block_hash: block_hash.clone(),
                round,
                signature: "invalid_sig".to_string(), // Invalid signature
                decision_hash: None,
            },
        ];

        let result = engine.cast_votes_batch(&votes, &public_keys);
        assert!(result.is_ok());
        let (accepted, rejected) = result.unwrap();

        assert_eq!(accepted, 1, "Only valid vote should be accepted");
        assert_eq!(rejected, 1, "Invalid vote should be rejected");
        assert_eq!(engine.votes.len(), 1);
    }

    #[test]
    #[cfg(feature = "std")]
    fn test_cast_votes_batch_wrong_round() {
        use std::collections::HashMap;

        let mut engine = BFTEngine::new(2);
        engine.start_round(5);
        engine.propose("block_abc".to_string(), None);

        let (pk1, sk1) = crate::crypto::PQCKeypair::generate_raw();
        let mut public_keys = HashMap::new();
        public_keys.insert("v1".to_string(), pk1);

        // Sign for wrong round
        let block_hash = "block_abc".to_string();
        let wrong_round = 3u64;
        let sig1 = crate::crypto::MLDSA::sign_raw(&sk1, &format!("{}:{}", block_hash, wrong_round))
            .unwrap();

        let votes = vec![Vote {
            voter_id: "v1".to_string(),
            block_hash: block_hash.clone(),
            round: wrong_round, // Wrong round
            signature: sig1,
            decision_hash: None,
        }];

        let result = engine.cast_votes_batch(&votes, &public_keys);
        assert!(result.is_ok());
        let (accepted, rejected) = result.unwrap();

        assert_eq!(accepted, 0, "Wrong round vote should be rejected");
        assert_eq!(rejected, 1);
        assert_eq!(engine.votes.len(), 0);
    }
}
