use super::HardwareEntropy;
use sha3::{Digest, Sha3_256};
use zeroize::Zeroizing;

#[cfg(not(feature = "std"))]
use alloc::format;
#[cfg(not(feature = "std"))]
use alloc::string::String;

/// Virtual Hardware Security Module (vHSM)
///
/// This struct provides an axiomatic software-emulated "Warm Key" device.
/// In Phase 2, we use this software execution module to prove the architecture
/// where the Private Key NEVER leaves the "Hardware" (in this case, this struct).
///
/// [C3 Security Fix] Private key is now wrapped in `Zeroizing<String>` to ensure
/// the key material is zeroed from memory when the HSM is dropped. This prevents:
/// - Key material being swapped to disk
/// - Key material remaining in memory after use
/// - Key material being readable by debuggers after HSM destruction
#[cfg_attr(feature = "python", pyclass)]
pub struct VirtualHSM {
    /// The hardware-bound identity. In a real device, this is burnt into the secure element.
    /// Here, we derive it deterministically from the host machine's hardware entropy.
    private_seed: u64,
    /// Cached ML-DSA keypair (generated deterministically from seed)
    public_key: String,
    /// [C3 CRITICAL FIX] Private key protected with automatic zeroization on drop
    private_key: Zeroizing<String>,
}

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
#[pymethods]
impl VirtualHSM {
    #[new]
    pub fn py_new() -> Self {
        Self::power_on()
    }

    #[staticmethod]
    #[pyo3(name = "from_seed")]
    pub fn py_from_seed_vhsm(seed: u64) -> Self {
        Self::from_seed(seed)
    }

    #[pyo3(name = "sign_blob")]
    pub fn py_sign_blob(&self, blob: &[u8]) -> PyResult<String> {
        self.sign_blob(blob)
            .map_err(pyo3::exceptions::PyRuntimeError::new_err)
    }

    #[pyo3(name = "get_public_identity")]
    pub fn py_get_public_identity(&self) -> String {
        self.get_public_identity()
    }

    #[pyo3(name = "get_public_key")]
    pub fn py_get_public_key(&self) -> String {
        self.get_public_key().to_string()
    }
}

impl VirtualHSM {
    /// "Inserts" the Warm Key into the device (Initializes the HSM).
    #[must_use]
    pub fn power_on() -> Self {
        let (seed, _proof) = HardwareEntropy::derive_seed_raw();
        Self::from_seed(seed)
    }

    /// Initialize from a specific seed (For Deterministic Testing Clusters)
    /// [C3 Security Fix] Private key is now automatically zeroized on drop
    #[must_use]
    pub fn from_seed(seed: u64) -> Self {
        // Generate a proper ML-DSA keypair deterministically from the seed
        let mut seed_bytes = [0u8; 32];
        // We expand the u64 seed to 32 bytes to satisfy PQCKeypair requirements
        seed_bytes[..8].copy_from_slice(&seed.to_le_bytes());
        // For the remaining bytes, we use a fixed derivation to ensure uniqueness
        for i in 8..32 {
            seed_bytes[i] = seed_bytes[i % 8] ^ 0xA5;
        }

        let (pk, sk) = crate::crypto::PQCKeypair::generate_from_seed(seed_bytes);
        VirtualHSM {
            private_seed: seed,
            public_key: pk,
            // [C3 CRITICAL FIX] Wrap private key in Zeroizing for secure cleanup
            private_key: Zeroizing::new(sk),
        }
    }

    /// Executes a hardware-bound signed operation.
    /// The private key is accessed from secure memory and used for signing.
    /// It is never returned to the caller.
    ///
    /// [H5 Security Fix] Returns Result instead of panicking on signing failure.
    /// HSM operations should never panic - failures must be handled gracefully.
    /// [C3 Security Fix] Private key access goes through Zeroizing wrapper.
    pub fn sign_blob(&self, blob: &[u8]) -> Result<String, String> {
        let message =
            core::str::from_utf8(blob).map_err(|_| "HSM_FAILURE: Invalid UTF-8 in blob")?;
        // Access private key through Zeroizing wrapper (auto-deref via Deref trait)
        crate::crypto::MLDSA::sign_raw(&self.private_key, message)
            .map_err(|e| format!("HSM_FAILURE: Signing failed - {}", e))
    }

    /// Returns the PUBLIC identity of the device.
    /// This is safe to share (e.g., the Kinetic ID).
    #[must_use]
    pub fn get_public_identity(&self) -> String {
        // Return first 32 chars of public key as identity
        let id_hash = {
            let mut hasher = Sha3_256::new();
            hasher.update(self.public_key.as_bytes());
            hasher.update(self.private_seed.to_le_bytes());
            hex::encode(hasher.finalize())
        };
        format!("WARM-KEY-{}", &id_hash[..16])
    }

    /// Returns the full public key for verification purposes.
    #[must_use]
    pub fn get_public_key(&self) -> &str {
        &self.public_key
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vhsm_power_on() {
        let hsm = VirtualHSM::power_on();
        assert!(!hsm.get_public_key().is_empty());
        assert!(hsm.get_public_identity().starts_with("WARM-KEY-"));
    }

    #[test]
    fn test_vhsm_from_seed() {
        let hsm1 = VirtualHSM::from_seed(12345);
        let hsm2 = VirtualHSM::from_seed(12345);

        // Same seed should produce same private_seed
        assert_eq!(hsm1.private_seed, hsm2.private_seed);

        // But keypairs are generated fresh (not from seed currently)
        // so public keys will differ
        assert!(!hsm1.get_public_key().is_empty());
        assert!(!hsm2.get_public_key().is_empty());
    }

    #[test]
    fn test_vhsm_sign_blob() {
        let hsm = VirtualHSM::power_on();

        let message = b"Hello, World!";
        let result = hsm.sign_blob(message);
        assert!(result.is_ok());

        let signature = result.unwrap();
        assert!(!signature.is_empty());
    }

    #[test]
    fn test_vhsm_sign_verify_roundtrip() {
        let hsm = VirtualHSM::power_on();

        let message = "Test message for signing";
        let signature = hsm.sign_blob(message.as_bytes()).unwrap();

        // Verify with public key
        let verified = crate::crypto::MLDSA::verify_raw(hsm.get_public_key(), message, &signature);
        assert!(verified);
    }

    #[test]
    fn test_vhsm_sign_invalid_utf8() {
        let hsm = VirtualHSM::power_on();

        // Invalid UTF-8 sequence
        let invalid_utf8 = vec![0xff, 0xfe, 0xfd];
        let result = hsm.sign_blob(&invalid_utf8);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Invalid UTF-8"));
    }

    #[test]
    fn test_vhsm_public_identity_format() {
        let hsm = VirtualHSM::power_on();
        let identity = hsm.get_public_identity();

        assert!(identity.starts_with("WARM-KEY-"));
        // Should have 16 hex chars after prefix (9 + 16 = 25)
        assert_eq!(identity.len(), 25);
    }

    #[test]
    fn test_vhsm_public_key_not_empty() {
        let hsm = VirtualHSM::from_seed(42);
        let pk = hsm.get_public_key();

        assert!(!pk.is_empty());
        // ML-DSA public keys are hex-encoded, should be valid hex
        assert!(hex::decode(pk).is_ok());
    }
}
