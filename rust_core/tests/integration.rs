//! Integration tests for WarmLogic Rust Core.
//!
//! These tests verify the end-to-end flow of the system,
//! testing interactions between multiple modules.

use warm_logic_rs::consensus::bft::{BFTEngine, Vote};
use warm_logic_rs::crypto::{PQCKeypair, MLDSA};
use warm_logic_rs::hardware::v_hsm::VirtualHSM;
use warm_logic_rs::slashing::SlashingEngine;

/// Test the full signing and verification flow using HSM
#[test]
fn test_hsm_sign_verify_integration() {
    let hsm = VirtualHSM::power_on();

    let message = "Transaction: Alice sends 100 to Bob";
    let signature = hsm.sign_blob(message.as_bytes()).unwrap();

    // Verify using the public key from HSM
    let verified = MLDSA::verify_raw(hsm.get_public_key(), message, &signature);
    assert!(verified);

    // Tampered message should fail
    let tampered = "Transaction: Alice sends 1000 to Bob";
    let verified_tampered = MLDSA::verify_raw(hsm.get_public_key(), tampered, &signature);
    assert!(!verified_tampered);
}

/// Test BFT consensus with cryptographically signed votes
#[test]
fn test_bft_with_crypto_signatures() {
    let (pk, sk) = PQCKeypair::generate_raw();

    let mut engine = BFTEngine::new(1); // Quorum of 1 for testing
    engine.start_round(0);
    engine.propose("block_hash_123".to_string(), None);

    // Create a properly signed vote
    let message = format!("{}:{}", "block_hash_123", 0);
    let signature = MLDSA::sign_raw(&sk, &message).unwrap();

    let vote = Vote {
        voter_id: "validator_1".to_string(),
        block_hash: "block_hash_123".to_string(),
        round: 0,
        signature,
        decision_hash: None,
    };

    // Cast vote with verification
    let result = engine.cast_vote_verified(vote, &pk);
    assert!(result.is_ok());
    assert!(result.unwrap()); // Quorum reached with 1 vote
}

/// Test that invalid signatures are rejected by BFT
#[test]
fn test_bft_rejects_invalid_signature() {
    let (pk, _sk) = PQCKeypair::generate_raw();

    let mut engine = BFTEngine::new(1);
    engine.start_round(0);
    engine.propose("block_hash_456".to_string(), None);

    // Create a vote with invalid signature
    let vote = Vote {
        voter_id: "validator_1".to_string(),
        block_hash: "block_hash_456".to_string(),
        round: 0,
        signature: "invalid_signature".to_string(),
        decision_hash: None,
    };

    // Should be rejected
    let result = engine.cast_vote_verified(vote, &pk);
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("Invalid vote signature"));
}

/// Test slashing engine with governance module
#[test]
fn test_slashing_integration() {
    let engine = SlashingEngine::new();

    // Low severity - no slashing
    let verdict_low = engine.evaluate_violation_raw("actor_1", 0.5);
    assert!(verdict_low.is_none());

    // High severity - economic burn
    let verdict_high = engine.evaluate_violation_raw("actor_2", 0.9);
    assert!(verdict_high.is_some());

    // Critical severity - state lock
    let verdict_critical = engine.evaluate_violation_raw("actor_3", 0.99);
    assert!(verdict_critical.is_some());
}

/// Test multiple validators reaching consensus
#[test]
fn test_multi_validator_consensus() {
    // Generate keypairs for 3 validators
    let validators: Vec<_> = (0..3).map(|_| PQCKeypair::generate_raw()).collect();

    let mut engine = BFTEngine::new(2); // Quorum of 2
    engine.start_round(1);
    engine.propose("genesis_block".to_string(), None);

    // First validator votes - no quorum
    let msg = format!("{}:{}", "genesis_block", 1);
    let sig1 = MLDSA::sign_raw(&validators[0].1, &msg).unwrap();
    let vote1 = Vote {
        voter_id: "v1".to_string(),
        block_hash: "genesis_block".to_string(),
        round: 1,
        signature: sig1,
        decision_hash: None,
    };
    let result1 = engine.cast_vote_verified(vote1, &validators[0].0);
    assert!(result1.is_ok());
    assert!(!result1.unwrap()); // No quorum yet

    // Second validator votes - quorum reached
    let sig2 = MLDSA::sign_raw(&validators[1].1, &msg).unwrap();
    let vote2 = Vote {
        voter_id: "v2".to_string(),
        block_hash: "genesis_block".to_string(),
        round: 1,
        signature: sig2,
        decision_hash: None,
    };
    let result2 = engine.cast_vote_verified(vote2, &validators[1].0);
    assert!(result2.is_ok());
    assert!(result2.unwrap()); // Quorum reached!

    assert!(engine.has_quorum());
    assert_eq!(engine.get_votes().len(), 2);
}

/// Test HSM identity consistency
#[test]
fn test_hsm_identity_consistency() {
    let hsm = VirtualHSM::power_on();

    let identity1 = hsm.get_public_identity();
    let identity2 = hsm.get_public_identity();

    // Identity should be consistent
    assert_eq!(identity1, identity2);
    assert!(identity1.starts_with("WARM-KEY-"));
}

/// Test that different seeds produce different keypairs
#[test]
fn test_hsm_seed_isolation() {
    let hsm1 = VirtualHSM::from_seed(1);
    let hsm2 = VirtualHSM::from_seed(2);

    // Different seeds should produce different identities
    assert_ne!(hsm1.get_public_identity(), hsm2.get_public_identity());
    assert_ne!(hsm1.get_public_key(), hsm2.get_public_key());
}

/// Test round progression in BFT
#[test]
fn test_bft_round_progression() {
    let (pk, sk) = PQCKeypair::generate_raw();

    let mut engine = BFTEngine::new(1);

    // Round 0
    engine.start_round(0);
    engine.propose("block_0".to_string(), None);

    let msg0 = format!("{}:{}", "block_0", 0);
    let sig0 = MLDSA::sign_raw(&sk, &msg0).unwrap();
    let vote0 = Vote {
        voter_id: "v1".to_string(),
        block_hash: "block_0".to_string(),
        round: 0,
        signature: sig0,
        decision_hash: None,
    };
    let _ = engine.cast_vote_verified(vote0, &pk);
    assert!(engine.has_quorum());

    // Start Round 1 - votes should reset
    engine.start_round(1);
    engine.propose("block_1".to_string(), None);

    assert!(!engine.has_quorum());
    assert!(engine.get_votes().is_empty());

    // Vote from old round should be rejected
    let old_msg = format!("{}:{}", "block_1", 0);
    let old_sig = MLDSA::sign_raw(&sk, &old_msg).unwrap();
    let old_vote = Vote {
        voter_id: "v1".to_string(),
        block_hash: "block_1".to_string(),
        round: 0, // Old round
        signature: old_sig,
        decision_hash: None,
    };
    let result = engine.cast_vote_verified(old_vote, &pk);
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("round mismatch"));
}
