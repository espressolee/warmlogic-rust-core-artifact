//! Crypto stub for no_std environments (WASM, bare-metal).
//!
//! This module provides minimal stubs for crypto operations in environments
//! where full PQC cryptography is not available (e.g., WASM without proper entropy).
//!
//! For production WASM builds, consider:
//! - Using WebCrypto API via wasm-bindgen
//! - Implementing key generation in JavaScript and passing keys to Rust
//! - Using a WASM-compatible crypto library

#![allow(dead_code)]

use alloc::string::String;

/// Stub keypair - PQC crypto not available in no_std
pub struct PQCKeypair {
    pub public_key: String,
    pub private_key: String,
}

impl PQCKeypair {
    pub fn generate_raw() -> (String, String) {
        // In no_std, return placeholder values
        // Real implementation should use platform-specific crypto
        ("STUB_PK_NO_STD".into(), "STUB_SK_NO_STD".into())
    }

    pub fn generate() -> (String, String) {
        Self::generate_raw()
    }
}

/// Stub ML-DSA implementation
pub struct MLDSA;

impl MLDSA {
    pub fn sign_raw(_private_key_hex: &str, _message: &str) -> Result<String, String> {
        // Cannot sign in no_std without proper RNG
        Err("ML-DSA signing not available in no_std mode".into())
    }

    pub fn verify_raw(public_key: &str, _message: &str, _signature: &str) -> bool {
        // Cannot verify with stub keys
        !public_key.starts_with("STUB_")
    }
}

/// Stub KEM result
pub struct KEMEncapsResult {
    pub shared_secret: String,
    pub ciphertext: String,
}

/// Stub ML-KEM implementation
pub struct MLKEM;

impl MLKEM {
    pub fn keygen_raw() -> Result<(String, String), String> {
        Err("ML-KEM keygen not available in no_std mode".into())
    }

    pub fn encapsulate_raw(_encaps_key_hex: &str) -> Result<KEMEncapsResult, String> {
        Err("ML-KEM encapsulation not available in no_std mode".into())
    }

    pub fn decapsulate_raw(_decaps_key_hex: &str, _ciphertext_hex: &str) -> Result<String, String> {
        Err("ML-KEM decapsulation not available in no_std mode".into())
    }
}
