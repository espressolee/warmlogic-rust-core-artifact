//! Byzantine Behavior Detection and Slashing Integration.
//!
//! Collective Decision Protocol
//!
//! This module bridges the BFT consensus engine with the slashing system,
//! detecting Byzantine violations and generating slashing verdicts.

#[cfg(not(feature = "std"))]
use alloc::string::{String, ToString};
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

use crate::consensus::bft::{AnonymousVote, ViewChangeMessage, Vote};
use crate::slashing::{SlashingEngine, SlashingVerdict, ViolationType};
use serde::{Deserialize, Serialize};

#[cfg(not(feature = "std"))]
use hashbrown::{HashMap, HashSet};
#[cfg(feature = "std")]
use std::collections::{HashMap, HashSet};

/// Byzantine violation detected during consensus.
#[derive(Debug, Clone, Serialize, Deserialize, borsh::BorshSerialize, borsh::BorshDeserialize)]
pub enum ByzantineViolation {
    /// Voter submitted votes for different blocks in the same round.
    EquivocationDetected {
        voter_id: String,
        round: u64,
        block_hash_1: String,
        block_hash_2: String,
    },
    /// Anonymous vote with duplicate nullifier (double membership proof).
    DoubleAnonymousVote { nullifier: [u8; 32], round: u64 },
    /// View change message conflicts with existing message from same sender.
    ConflictingViewChange {
        sender_id: String,
        view_1: u64,
        view_2: u64,
    },
    /// Invalid signature detected on vote.
    InvalidSignature { voter_id: String, vote_hash: String },
    /// Invalid ZK proof detected.
    InvalidZKProof { proof_hash: String },
}

/// Byzantine detector that integrates with slashing.
///
/// Tracks votes and view change messages to detect equivocation
/// and other Byzantine behaviors.
#[derive(Debug)]
pub struct ByzantineDetector {
    /// Vote history: (voter_id, round) -> (block_hash, vote_signature)
    vote_history: HashMap<(String, u64), (String, String)>,
    /// View change history: sender_id -> (view, signature)
    view_change_history: HashMap<String, (u64, String)>,
    /// Detected violations (not yet processed)
    pending_violations: Vec<ByzantineViolation>,
    /// Slashing engine for generating verdicts
    slashing_engine: SlashingEngine,
}

impl Default for ByzantineDetector {
    fn default() -> Self {
        Self::new()
    }
}

impl ByzantineDetector {
    /// Create a new Byzantine detector.
    #[must_use]
    pub fn new() -> Self {
        Self {
            vote_history: HashMap::new(),
            view_change_history: HashMap::new(),
            pending_violations: Vec::new(),
            slashing_engine: SlashingEngine::new(),
        }
    }

    /// Check a vote for equivocation before acceptance.
    ///
    /// Returns Some(violation) if the voter previously voted for a different block
    /// in the same round (equivocation detected).
    pub fn check_vote(&mut self, vote: &Vote) -> Option<ByzantineViolation> {
        let key = (vote.voter_id.clone(), vote.round);

        if let Some((prev_block, prev_sig)) = self.vote_history.get(&key) {
            // Check if this is a conflicting vote (different block hash)
            if *prev_block != vote.block_hash {
                let violation = ByzantineViolation::EquivocationDetected {
                    voter_id: vote.voter_id.clone(),
                    round: vote.round,
                    block_hash_1: prev_block.clone(),
                    block_hash_2: vote.block_hash.clone(),
                };
                self.pending_violations.push(violation.clone());
                return Some(violation);
            }
            // Same block but different signature is suspicious but not equivocation
            if *prev_sig != vote.signature {
                // This could be a replay with modified signature, but same block
                // is not equivocation. Log for analysis but don't slash.
            }
        }

        // Record this vote for future equivocation detection
        self.vote_history
            .insert(key, (vote.block_hash.clone(), vote.signature.clone()));

        None
    }

    /// Check anonymous vote for double membership proof.
    ///
    /// Returns Some(violation) if nullifier was seen before.
    pub fn check_anonymous_vote(
        &mut self,
        vote: &AnonymousVote,
        existing_nullifiers: &HashSet<[u8; 32]>,
    ) -> Option<ByzantineViolation> {
        if existing_nullifiers.contains(&vote.nullifier) {
            let violation = ByzantineViolation::DoubleAnonymousVote {
                nullifier: vote.nullifier,
                round: vote.round,
            };
            self.pending_violations.push(violation.clone());
            return Some(violation);
        }
        None
    }

    /// Check view change message for conflicts.
    ///
    /// Returns Some(violation) if sender already sent a conflicting view change.
    pub fn check_view_change(&mut self, msg: &ViewChangeMessage) -> Option<ByzantineViolation> {
        if let Some((prev_view, _prev_sig)) = self.view_change_history.get(&msg.sender_id) {
            // Different view with same sender in same view change round
            if *prev_view != msg.new_view {
                let violation = ByzantineViolation::ConflictingViewChange {
                    sender_id: msg.sender_id.clone(),
                    view_1: *prev_view,
                    view_2: msg.new_view,
                };
                self.pending_violations.push(violation.clone());
                return Some(violation);
            }
        }

        // Record for future conflict detection
        self.view_change_history
            .insert(msg.sender_id.clone(), (msg.new_view, msg.signature.clone()));

        None
    }

    /// Record an invalid signature violation.
    pub fn record_invalid_signature(&mut self, voter_id: &str, vote_hash: &str) {
        self.pending_violations
            .push(ByzantineViolation::InvalidSignature {
                voter_id: voter_id.to_string(),
                vote_hash: vote_hash.to_string(),
            });
    }

    /// Record an invalid ZK proof violation.
    pub fn record_invalid_zk_proof(&mut self, proof_hash: &str) {
        self.pending_violations
            .push(ByzantineViolation::InvalidZKProof {
                proof_hash: proof_hash.to_string(),
            });
    }

    /// Process pending violations and generate slashing verdicts.
    ///
    /// Returns verdicts for all pending violations and clears the queue.
    pub fn process_violations(&mut self) -> Vec<SlashingVerdict> {
        let violations = std::mem::take(&mut self.pending_violations);
        let mut verdicts = Vec::new();

        for violation in violations {
            let verdict = match violation {
                ByzantineViolation::EquivocationDetected {
                    voter_id,
                    block_hash_1,
                    block_hash_2,
                    ..
                } => {
                    let v = self.slashing_engine.evaluate_double_vote(
                        &voter_id,
                        &block_hash_1,
                        &block_hash_2,
                    );
                    // Record to prevent double-slashing
                    if self.slashing_engine.record_slash(&v) {
                        Some(v)
                    } else {
                        None
                    }
                }
                ByzantineViolation::DoubleAnonymousVote { nullifier, .. } => {
                    // For anonymous votes, we can't identify the voter,
                    // but we record the nullifier as evidence
                    let nullifier_hex = hex::encode(nullifier);
                    // Use "anonymous" as actor since identity is hidden
                    let v = self.slashing_engine.evaluate_double_vote(
                        "anonymous",
                        &nullifier_hex,
                        &nullifier_hex,
                    );
                    Some(v)
                }
                ByzantineViolation::ConflictingViewChange {
                    sender_id,
                    view_1,
                    view_2,
                } => {
                    let v = self
                        .slashing_engine
                        .evaluate_conflicting_view_change(&sender_id, view_1, view_2);
                    if self.slashing_engine.record_slash(&v) {
                        Some(v)
                    } else {
                        None
                    }
                }
                ByzantineViolation::InvalidSignature {
                    voter_id,
                    vote_hash,
                } => {
                    // Invalid signature could be attack or network corruption
                    // Use lighter penalty than double voting
                    Some(SlashingVerdict {
                        reason: format!(
                            "Invalid signature on vote {}",
                            &vote_hash[..8.min(vote_hash.len())]
                        ),
                        penalty: crate::slashing::Penalty::EconomicBurn(200),
                        actor: voter_id,
                        violation_type: Some(ViolationType::InvalidSignature),
                        evidence_hash: Some(vote_hash),
                        witness: None,
                        timestamp: std::time::SystemTime::now()
                            .duration_since(std::time::UNIX_EPOCH)
                            .map(|d| d.as_secs())
                            .unwrap_or(0),
                    })
                }
                ByzantineViolation::InvalidZKProof { proof_hash } => {
                    let v = self
                        .slashing_engine
                        .evaluate_invalid_zk_proof("anonymous_prover", &proof_hash);
                    Some(v)
                }
            };

            if let Some(v) = verdict {
                verdicts.push(v);
            }
        }

        verdicts
    }

    /// Get count of pending violations.
    #[must_use]
    pub fn pending_violation_count(&self) -> usize {
        self.pending_violations.len()
    }

    /// Clear vote history for a new round.
    ///
    /// Should be called at the start of each round to reset equivocation tracking.
    pub fn clear_round_history(&mut self) {
        self.vote_history.clear();
    }

    /// Clear view change history after successful view change.
    pub fn clear_view_change_history(&mut self) {
        self.view_change_history.clear();
    }

    /// Get slashing statistics.
    #[must_use]
    pub fn slashed_count(&self) -> usize {
        self.slashing_engine.slashed_count()
    }

    /// Check if an actor was already slashed for a violation type.
    #[must_use]
    pub fn was_slashed(&self, actor: &str, violation_type: &ViolationType) -> bool {
        self.slashing_engine.was_slashed(actor, violation_type)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_vote(voter: &str, block: &str, round: u64) -> Vote {
        Vote {
            voter_id: voter.to_string(),
            block_hash: block.to_string(),
            round,
            signature: format!("sig_{}_{}_{}", voter, block, round),
            decision_hash: None,
        }
    }

    #[test]
    fn test_equivocation_detection() {
        let mut detector = ByzantineDetector::new();

        // First vote - should pass
        let vote1 = create_vote("validator_1", "block_aaa", 5);
        assert!(detector.check_vote(&vote1).is_none());

        // Same voter, same round, different block - EQUIVOCATION!
        let vote2 = create_vote("validator_1", "block_bbb", 5);
        let violation = detector.check_vote(&vote2);
        assert!(violation.is_some());

        match violation.unwrap() {
            ByzantineViolation::EquivocationDetected {
                voter_id,
                block_hash_1,
                block_hash_2,
                ..
            } => {
                assert_eq!(voter_id, "validator_1");
                assert_eq!(block_hash_1, "block_aaa");
                assert_eq!(block_hash_2, "block_bbb");
            }
            _ => panic!("Expected EquivocationDetected"),
        }
    }

    #[test]
    fn test_same_vote_no_violation() {
        let mut detector = ByzantineDetector::new();

        let vote1 = create_vote("validator_1", "block_aaa", 5);
        assert!(detector.check_vote(&vote1).is_none());

        // Same vote again - no violation (just update)
        let vote2 = create_vote("validator_1", "block_aaa", 5);
        assert!(detector.check_vote(&vote2).is_none());
    }

    #[test]
    fn test_different_round_no_conflict() {
        let mut detector = ByzantineDetector::new();

        // Vote in round 5
        let vote1 = create_vote("validator_1", "block_aaa", 5);
        assert!(detector.check_vote(&vote1).is_none());

        // Different vote in round 6 - OK, different rounds
        let vote2 = create_vote("validator_1", "block_bbb", 6);
        assert!(detector.check_vote(&vote2).is_none());
    }

    #[test]
    fn test_conflicting_view_change() {
        let mut detector = ByzantineDetector::new();

        let msg1 = ViewChangeMessage {
            new_view: 10,
            sender_id: "node_1".to_string(),
            last_prepared_round: None,
            last_prepared_block: None,
            signature: "sig_1".to_string(),
            timestamp_ms: 1000,
        };
        assert!(detector.check_view_change(&msg1).is_none());

        // Same sender, different view - CONFLICT!
        let msg2 = ViewChangeMessage {
            new_view: 11,
            sender_id: "node_1".to_string(),
            last_prepared_round: None,
            last_prepared_block: None,
            signature: "sig_2".to_string(),
            timestamp_ms: 1001,
        };
        let violation = detector.check_view_change(&msg2);
        assert!(violation.is_some());

        match violation.unwrap() {
            ByzantineViolation::ConflictingViewChange {
                sender_id,
                view_1,
                view_2,
            } => {
                assert_eq!(sender_id, "node_1");
                assert_eq!(view_1, 10);
                assert_eq!(view_2, 11);
            }
            _ => panic!("Expected ConflictingViewChange"),
        }
    }

    #[test]
    fn test_process_violations_generates_verdicts() {
        let mut detector = ByzantineDetector::new();

        // Create equivocation
        let vote1 = create_vote("bad_actor", "block_x", 1);
        detector.check_vote(&vote1);
        let vote2 = create_vote("bad_actor", "block_y", 1);
        detector.check_vote(&vote2);

        assert_eq!(detector.pending_violation_count(), 1);

        let verdicts = detector.process_violations();
        assert_eq!(verdicts.len(), 1);
        assert_eq!(verdicts[0].actor, "bad_actor");
        assert_eq!(
            verdicts[0].violation_type,
            Some(ViolationType::DoubleVoting)
        );

        // Pending should be cleared
        assert_eq!(detector.pending_violation_count(), 0);
    }

    #[test]
    fn test_double_slash_prevention() {
        let mut detector = ByzantineDetector::new();

        // First equivocation
        let vote1 = create_vote("repeat_offender", "block_a", 1);
        detector.check_vote(&vote1);
        let vote2 = create_vote("repeat_offender", "block_b", 1);
        detector.check_vote(&vote2);

        let verdicts1 = detector.process_violations();
        assert_eq!(verdicts1.len(), 1);

        // Second equivocation from same actor
        detector.clear_round_history(); // New round
        let vote3 = create_vote("repeat_offender", "block_c", 2);
        detector.check_vote(&vote3);
        let vote4 = create_vote("repeat_offender", "block_d", 2);
        detector.check_vote(&vote4);

        let verdicts2 = detector.process_violations();
        // Should be empty - already slashed for DoubleVoting
        assert_eq!(verdicts2.len(), 0);

        assert!(detector.was_slashed("repeat_offender", &ViolationType::DoubleVoting));
    }

    #[test]
    fn test_anonymous_vote_double_spend() {
        let mut detector = ByzantineDetector::new();
        let mut nullifiers = std::collections::HashSet::new();

        let nullifier = [42u8; 32];
        nullifiers.insert(nullifier);

        let vote = AnonymousVote {
            block_hash: "block_z".to_string(),
            round: 1,
            zk_proof: vec![1, 2, 3],
            nullifier,
        };

        let violation = detector.check_anonymous_vote(&vote, &nullifiers);
        assert!(violation.is_some());

        match violation.unwrap() {
            ByzantineViolation::DoubleAnonymousVote { round, .. } => {
                assert_eq!(round, 1);
            }
            _ => panic!("Expected DoubleAnonymousVote"),
        }
    }
}
