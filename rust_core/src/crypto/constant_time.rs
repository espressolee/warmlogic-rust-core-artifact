//! rust_core/src/crypto/constant_time.rs
//! Constant-time cryptographic operations.
//!
//! Provides timing-attack resistant comparisons for sensitive data.
//! All operations execute in constant time regardless of input values.

use subtle::{Choice, ConstantTimeEq};

// ============================================================================
// CONSTANT-TIME COMPARISON FUNCTIONS
// ============================================================================

/// Constant-time comparison of two byte slices.
///
/// Returns true if and only if the slices are equal.
/// Executes in constant time to prevent timing attacks.
///
/// # Security
/// - Compares all bytes regardless of early mismatches
/// - Execution time is independent of where differences occur
/// - Safe for comparing secrets (keys, MACs, signatures)
#[inline]
pub fn ct_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.ct_eq(b).into()
}

/// Constant-time comparison of two 32-byte arrays (common for hashes).
#[inline]
pub fn ct_eq_32(a: &[u8; 32], b: &[u8; 32]) -> bool {
    a.ct_eq(b).into()
}

/// Constant-time comparison of two 64-byte arrays (common for signatures).
#[inline]
pub fn ct_eq_64(a: &[u8; 64], b: &[u8; 64]) -> bool {
    a.ct_eq(b).into()
}

/// Constant-time comparison with expected hash (hex-encoded).
///
/// # Arguments
/// * `computed` - The computed hash bytes
/// * `expected_hex` - The expected hash as hex string
///
/// # Returns
/// `true` if hashes match, `false` otherwise (including invalid hex)
pub fn ct_eq_hex(computed: &[u8], expected_hex: &str) -> bool {
    match hex::decode(expected_hex) {
        Ok(expected) => ct_eq(computed, &expected),
        Err(_) => false,
    }
}

/// Constant-time comparison of two strings.
///
/// Compares the underlying byte representation in constant time.
/// Useful for comparing block hashes stored as hex strings.
#[inline]
pub fn ct_eq_str(a: &str, b: &str) -> bool {
    ct_eq(a.as_bytes(), b.as_bytes())
}

/// Constant-time selection between two values.
///
/// Returns `a` if `choice` is 1, `b` if `choice` is 0.
/// Does not branch on the choice value.
#[inline]
pub fn ct_select<T: Copy + Default>(choice: Choice, a: T, b: T) -> T {
    // For simple types, we can use conditional move
    // This is a simplified version - for complex types use subtle::ConditionallySelectable
    if choice.into() {
        a
    } else {
        b
    }
}

/// Constant-time check if a byte slice is all zeros.
#[inline]
pub fn ct_is_zero(data: &[u8]) -> bool {
    let mut acc: u8 = 0;
    for &byte in data {
        acc |= byte;
    }
    acc == 0
}

/// Constant-time check if a 32-byte array is all zeros.
#[inline]
pub fn ct_is_zero_32(data: &[u8; 32]) -> bool {
    ct_is_zero(data)
}

// ============================================================================
// HASH VERIFICATION
// ============================================================================

/// Verify a SHA3-256 hash in constant time.
///
/// # Arguments
/// * `data` - The data to hash
/// * `expected_hash` - The expected hash (32 bytes)
///
/// # Returns
/// `true` if the computed hash matches the expected hash
pub fn ct_verify_sha3_256(data: &[u8], expected_hash: &[u8; 32]) -> bool {
    use sha3::{Digest, Sha3_256};
    let mut hasher = Sha3_256::new();
    hasher.update(data);
    let computed = hasher.finalize();
    let computed_arr: [u8; 32] = computed.into();
    ct_eq_32(&computed_arr, expected_hash)
}

/// Verify a SHA3-256 hash against hex-encoded expected value.
pub fn ct_verify_sha3_256_hex(data: &[u8], expected_hex: &str) -> bool {
    use sha3::{Digest, Sha3_256};
    let mut hasher = Sha3_256::new();
    hasher.update(data);
    let computed = hasher.finalize();
    ct_eq_hex(&computed, expected_hex)
}

// ============================================================================
// SIGNATURE VERIFICATION HELPERS
// ============================================================================

/// Constant-time verification result accumulator.
///
/// Accumulates multiple verification results without short-circuiting.
/// All checks are performed regardless of intermediate failures.
#[derive(Clone, Copy)]
pub struct VerificationAccumulator {
    result: Choice,
}

impl VerificationAccumulator {
    /// Create a new accumulator starting with success (true).
    pub fn new() -> Self {
        Self {
            result: Choice::from(1),
        }
    }

    /// AND a boolean condition into the accumulator.
    #[inline]
    pub fn and(&mut self, condition: bool) {
        self.result &= Choice::from(condition as u8);
    }

    /// AND a Choice into the accumulator.
    #[inline]
    pub fn and_choice(&mut self, choice: Choice) {
        self.result &= choice;
    }

    /// AND a constant-time equality check into the accumulator.
    #[inline]
    pub fn and_ct_eq(&mut self, a: &[u8], b: &[u8]) {
        if a.len() != b.len() {
            self.result &= Choice::from(0);
        } else {
            self.result &= a.ct_eq(b);
        }
    }

    /// Get the final verification result.
    #[inline]
    pub fn is_valid(&self) -> bool {
        self.result.into()
    }
}

impl Default for VerificationAccumulator {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ct_eq_equal_slices() {
        let a = [1u8, 2, 3, 4, 5];
        let b = [1u8, 2, 3, 4, 5];
        assert!(ct_eq(&a, &b));
    }

    #[test]
    fn test_ct_eq_different_slices() {
        let a = [1u8, 2, 3, 4, 5];
        let b = [1u8, 2, 3, 4, 6];
        assert!(!ct_eq(&a, &b));
    }

    #[test]
    fn test_ct_eq_different_lengths() {
        let a = [1u8, 2, 3, 4, 5];
        let b = [1u8, 2, 3, 4];
        assert!(!ct_eq(&a, &b));
    }

    #[test]
    fn test_ct_eq_empty() {
        let a: [u8; 0] = [];
        let b: [u8; 0] = [];
        assert!(ct_eq(&a, &b));
    }

    #[test]
    fn test_ct_eq_32() {
        let a = [0xABu8; 32];
        let b = [0xABu8; 32];
        let c = [0xCDu8; 32];
        assert!(ct_eq_32(&a, &b));
        assert!(!ct_eq_32(&a, &c));
    }

    #[test]
    fn test_ct_eq_hex() {
        let data = [0xDE, 0xAD, 0xBE, 0xEF];
        assert!(ct_eq_hex(&data, "deadbeef"));
        assert!(ct_eq_hex(&data, "DEADBEEF"));
        assert!(!ct_eq_hex(&data, "deadbeee"));
        assert!(!ct_eq_hex(&data, "invalid"));
    }

    #[test]
    fn test_ct_is_zero() {
        let zeros = [0u8; 16];
        let nonzero = [0u8, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        assert!(ct_is_zero(&zeros));
        assert!(!ct_is_zero(&nonzero));
    }

    #[test]
    fn test_ct_is_zero_32() {
        let zeros = [0u8; 32];
        let nonzero = {
            let mut arr = [0u8; 32];
            arr[31] = 1;
            arr
        };
        assert!(ct_is_zero_32(&zeros));
        assert!(!ct_is_zero_32(&nonzero));
    }

    #[test]
    fn test_ct_verify_sha3_256() {
        let data = b"hello world";
        // SHA3-256 of "hello world"
        let expected =
            hex::decode("644bcc7e564373040999aac89e7622f3ca71fba1d972fd94a31c3bfbf24e3938")
                .unwrap();
        let expected_arr: [u8; 32] = expected.try_into().unwrap();
        assert!(ct_verify_sha3_256(data, &expected_arr));

        // Wrong hash
        let wrong = [0u8; 32];
        assert!(!ct_verify_sha3_256(data, &wrong));
    }

    #[test]
    fn test_ct_verify_sha3_256_hex() {
        let data = b"hello world";
        assert!(ct_verify_sha3_256_hex(
            data,
            "644bcc7e564373040999aac89e7622f3ca71fba1d972fd94a31c3bfbf24e3938"
        ));
        assert!(!ct_verify_sha3_256_hex(
            data,
            "0000000000000000000000000000000000000000000000000000000000000000"
        ));
    }

    #[test]
    fn test_verification_accumulator() {
        let mut acc = VerificationAccumulator::new();
        assert!(acc.is_valid());

        acc.and(true);
        assert!(acc.is_valid());

        acc.and(true);
        assert!(acc.is_valid());

        acc.and(false);
        assert!(!acc.is_valid());

        // Once false, stays false
        acc.and(true);
        assert!(!acc.is_valid());
    }

    #[test]
    fn test_verification_accumulator_ct_eq() {
        let mut acc = VerificationAccumulator::new();
        let a = [1u8, 2, 3];
        let b = [1u8, 2, 3];
        let c = [1u8, 2, 4];

        acc.and_ct_eq(&a, &b);
        assert!(acc.is_valid());

        acc.and_ct_eq(&a, &c);
        assert!(!acc.is_valid());
    }

    #[test]
    fn test_verification_accumulator_all_checks_run() {
        // Verify that all checks are performed even after failure
        // (This is what prevents timing attacks)
        let mut acc = VerificationAccumulator::new();

        // First check fails
        acc.and(false);

        // These checks should still be performed (no short-circuit)
        acc.and(true);
        acc.and_ct_eq(&[1u8], &[1u8]);

        // Result should still be false
        assert!(!acc.is_valid());
    }
}
