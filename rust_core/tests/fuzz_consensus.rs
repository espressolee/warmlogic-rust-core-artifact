//! Fuzz tests for BFT consensus engine
//! Tests that consensus operations don't panic on arbitrary inputs

#![allow(deprecated)] // cast_vote is deprecated but we're testing it

use proptest::prelude::*;
use warm_logic_rs::consensus::bft::{BFTEngine, Vote};

proptest! {
    // Test that casting votes with arbitrary data doesn't panic
    #[test]
    fn test_cast_vote_arbitrary(
        voter_id in "[a-zA-Z0-9]{1,64}",
        block_hash in "[a-f0-9]{1,64}",
        signature in "[a-f0-9]{0,200}",
        quorum_size in 1usize..100
    ) {
        let mut engine = BFTEngine::new(quorum_size);

        let vote = Vote {
            voter_id: voter_id.clone(),
            block_hash: block_hash.clone(),
            round: 0,
            signature,
            decision_hash: None,
        };

        // Should NOT panic
        let _ = engine.cast_vote(vote);
    }

    // Test that multiple rounds don't cause issues
    #[test]
    fn test_multiple_rounds(
        num_rounds in 1usize..50,
        quorum_size in 2usize..10
    ) {
        let mut engine = BFTEngine::new(quorum_size);

        for round in 0..num_rounds {
            engine.start_round(round as u64);

            // Add some votes
            for voter in 0..quorum_size {
                let vote = Vote {
                    voter_id: format!("voter_{}", voter),
                    block_hash: format!("block_{}", round),
                    round: round as u64,
                    signature: format!("sig_{}", voter),
                    decision_hash: None,
                };
                engine.propose(format!("block_{}", round), None);
                let _ = engine.cast_vote(vote);
            }

            // Check quorum status
            let _ = engine.has_quorum();
        }
    }

    // Test that duplicate votes are handled correctly
    #[test]
    fn test_duplicate_votes(
        num_duplicates in 1usize..100,
        quorum_size in 2usize..10
    ) {
        let mut engine = BFTEngine::new(quorum_size);
        engine.propose("test_block".to_string(), None);

        // Same voter votes multiple times
        for _ in 0..num_duplicates {
            let vote = Vote {
                voter_id: "same_voter".to_string(),
                block_hash: "test_block".to_string(),
                round: 0,
                signature: "sig".to_string(),
                decision_hash: None,
            };
            let _ = engine.cast_vote(vote);
        }

        // Should only count as 1 vote
        prop_assert_eq!(engine.get_votes().len(), 1);
    }

    // Test reset_round behavior
    #[test]
    fn test_reset_round(
        initial_round in 0u64..1000,
        num_votes in 0usize..20,
        quorum_size in 2usize..10
    ) {
        let mut engine = BFTEngine::new(quorum_size);
        engine.start_round(initial_round);
        engine.propose("block_hash".to_string(), None);

        // Add votes
        for i in 0..num_votes {
            let vote = Vote {
                voter_id: format!("voter_{}", i),
                block_hash: "block_hash".to_string(),
                round: initial_round,
                signature: format!("sig_{}", i),
                decision_hash: None,
            };
            let _ = engine.cast_vote(vote);
        }

        // Reset should clear everything (start_round clears votes and proposal)
        engine.start_round(0);
        prop_assert!(engine.get_votes().is_empty());
        prop_assert!(engine.current_proposal.is_none());
    }

    // Test wrong block votes
    #[test]
    fn test_wrong_block_votes(
        proposed_block in "[a-f0-9]{1,64}",
        voted_block in "[a-f0-9]{1,64}"
    ) {
        let mut engine = BFTEngine::new(2);
        engine.propose(proposed_block.clone(), None);

        let vote = Vote {
            voter_id: "voter".to_string(),
            block_hash: voted_block.clone(),
            round: 0,
            signature: "sig".to_string(),
            decision_hash: None,
        };

        let result = engine.cast_vote(vote);

        // If blocks don't match, vote should be rejected
        if proposed_block != voted_block {
            prop_assert!(!result);
            prop_assert!(engine.get_votes().is_empty());
        }
    }
}
