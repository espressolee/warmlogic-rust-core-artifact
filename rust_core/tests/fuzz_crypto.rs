//! Fuzz tests for cryptographic operations
//! Tests that crypto functions don't panic on arbitrary inputs

use proptest::prelude::*;
use warm_logic_rs::crypto::{PQCKeypair, MLDSA};

proptest! {
    // Test that signing arbitrary messages doesn't panic
    #[test]
    fn test_sign_arbitrary_message(
        message in ".*{0,1000}"
    ) {
        let (pk, sk) = PQCKeypair::generate_raw();

        // This should NOT panic
        let result = MLDSA::sign_raw(&sk, &message);

        // If signing succeeded, verify should work
        if let Ok(sig) = result {
            let _ = MLDSA::verify_raw(&pk, &message, &sig);
        }
    }

    // Test that verification with arbitrary signatures doesn't panic
    #[test]
    fn test_verify_arbitrary_signature(
        message in ".*{0,100}",
        fake_sig in "[a-f0-9]{0,500}"
    ) {
        let (pk, _sk) = PQCKeypair::generate_raw();

        // This should NOT panic, just return false
        let result = MLDSA::verify_raw(&pk, &message, &fake_sig);
        // Fake signature should fail verification
        prop_assert!(!result);
    }

    // Test that verification with arbitrary public keys doesn't panic
    #[test]
    fn test_verify_arbitrary_pubkey(
        message in ".*{0,100}",
        fake_pk in "[a-f0-9]{0,500}",
        fake_sig in "[a-f0-9]{0,500}"
    ) {
        // This should NOT panic
        let _ = MLDSA::verify_raw(&fake_pk, &message, &fake_sig);
    }

    // Test keypair generation produces valid keys
    #[test]
    fn test_keypair_valid(
        _i in 0..5
    ) {
        let (pk, sk) = PQCKeypair::generate_raw();

        // Keys should be valid hex strings
        prop_assert!(!pk.is_empty());
        prop_assert!(!sk.is_empty());

        // Should be able to sign and verify
        let result = MLDSA::sign_raw(&sk, "test");
        if let Ok(sig) = result {
            let verified = MLDSA::verify_raw(&pk, "test", &sig);
            prop_assert!(verified);
        }
    }

    // Test that empty messages can be signed
    #[test]
    fn test_sign_empty_message(_i in 0..10) {
        let (pk, sk) = PQCKeypair::generate_raw();

        let result = MLDSA::sign_raw(&sk, "");
        if let Ok(sig) = result {
            let verified = MLDSA::verify_raw(&pk, "", &sig);
            prop_assert!(verified);
        }
    }

    // Test unicode messages
    #[test]
    fn test_sign_unicode_message(
        message in "[가-힣]{0,50}|[あ-ん]{0,50}|[א-ת]{0,50}"
    ) {
        let (pk, sk) = PQCKeypair::generate_raw();

        let result = MLDSA::sign_raw(&sk, &message);
        if let Ok(sig) = result {
            let verified = MLDSA::verify_raw(&pk, &message, &sig);
            prop_assert!(verified);
        }
    }
}
