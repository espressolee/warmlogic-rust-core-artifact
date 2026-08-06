#[cfg(not(feature = "std"))]
use alloc::format;
#[cfg(not(feature = "std"))]
use alloc::string::String;
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

#[cfg(feature = "std")]
use std::string::String;

/// Maximum string length accepted from Python (1 MB).
/// Covers: block hashes, node IDs, signatures, messages.
pub const MAX_STRING_LEN: usize = 1_048_576; // 1 MB

/// Maximum bytes/buffer size from Python (16 MB).
/// Covers: ZK proofs, serialized state, attestation data.
pub const MAX_BYTES_LEN: usize = 16_777_216; // 16 MB

/// Maximum array/vector elements from Python (100,000).
/// Covers: votes, validators, transactions.
pub const MAX_ARRAY_LEN: usize = 100_000;

/// Maximum hex string length (2 MB, since hex is 2x raw bytes).
/// Covers: ML-DSA-65 public keys (~2.5 KB), signatures (~4.6 KB).
pub const MAX_HEX_LEN: usize = 2_097_152; // 2 MB

/// Maximum block/transaction size (4 MB).
pub const MAX_BLOCK_SIZE: usize = 4_194_304; // 4 MB

/// Maximum ZK proof size (1 MB).
/// Groth16 proofs are ~200 bytes, but allow headroom for metadata.
pub const MAX_ZK_PROOF_SIZE: usize = 1_048_576; // 1 MB

/// Validate a string input from FFI.
///
/// Returns Ok(()) if valid, Err with message if too large.
#[inline]
pub fn validate_string(s: &str, context: &str) -> Result<(), String> {
    if s.len() > MAX_STRING_LEN {
        return Err(format!(
            "FFI input too large: {} ({} bytes > {} max)",
            context,
            s.len(),
            MAX_STRING_LEN
        ));
    }
    Ok(())
}

/// Validate a bytes input from FFI.
#[inline]
pub fn validate_bytes(b: &[u8], context: &str) -> Result<(), String> {
    if b.len() > MAX_BYTES_LEN {
        return Err(format!(
            "FFI input too large: {} ({} bytes > {} max)",
            context,
            b.len(),
            MAX_BYTES_LEN
        ));
    }
    Ok(())
}

/// Validate a hex string from FFI.
#[inline]
pub fn validate_hex(s: &str, context: &str) -> Result<(), String> {
    if s.len() > MAX_HEX_LEN {
        return Err(format!(
            "FFI hex input too large: {} ({} bytes > {} max)",
            context,
            s.len(),
            MAX_HEX_LEN
        ));
    }
    Ok(())
}

/// Validate an array/vector length from FFI.
#[inline]
pub fn validate_array_len(len: usize, context: &str) -> Result<(), String> {
    if len > MAX_ARRAY_LEN {
        return Err(format!(
            "FFI array too large: {} ({} elements > {} max)",
            context, len, MAX_ARRAY_LEN
        ));
    }
    Ok(())
}

/// Validate a ZK proof size from FFI.
#[inline]
pub fn validate_zk_proof(b: &[u8], context: &str) -> Result<(), String> {
    if b.len() > MAX_ZK_PROOF_SIZE {
        return Err(format!(
            "FFI ZK proof too large: {} ({} bytes > {} max)",
            context,
            b.len(),
            MAX_ZK_PROOF_SIZE
        ));
    }
    Ok(())
}

/// Validate block/transaction data size from FFI.
#[inline]
pub fn validate_block(b: &[u8], context: &str) -> Result<(), String> {
    if b.len() > MAX_BLOCK_SIZE {
        return Err(format!(
            "FFI block too large: {} ({} bytes > {} max)",
            context,
            b.len(),
            MAX_BLOCK_SIZE
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_string_ok() {
        let s = "a".repeat(1000);
        assert!(validate_string(&s, "test").is_ok());
    }

    #[test]
    fn test_validate_string_too_large() {
        let s = "a".repeat(MAX_STRING_LEN + 1);
        let result = validate_string(&s, "test");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("too large"));
    }

    #[test]
    fn test_validate_bytes_ok() {
        let b = vec![0u8; 1000];
        assert!(validate_bytes(&b, "test").is_ok());
    }

    #[test]
    fn test_validate_bytes_too_large() {
        let b = vec![0u8; MAX_BYTES_LEN + 1];
        let result = validate_bytes(&b, "test");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_array_len_ok() {
        assert!(validate_array_len(1000, "test").is_ok());
    }

    #[test]
    fn test_validate_array_len_too_large() {
        let result = validate_array_len(MAX_ARRAY_LEN + 1, "test");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_hex_ok() {
        // ML-DSA-65 public key is ~2.5 KB hex
        let hex = "ab".repeat(2500);
        assert!(validate_hex(&hex, "test").is_ok());
    }

    #[test]
    fn test_validate_zk_proof_ok() {
        // Groth16 proof is ~200 bytes
        let proof = vec![0u8; 200];
        assert!(validate_zk_proof(&proof, "test").is_ok());
    }
}
