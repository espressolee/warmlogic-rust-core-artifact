#![allow(dead_code)]
pub mod accelerated;
// pub mod constant_time;

use fips204::ml_dsa_65;
use fips204::traits::{SerDes, Signer, Verifier};

// ML-KEM-768 (FIPS 203) for Post-Quantum Key Encapsulation
use fips203::ml_kem_768;
use fips203::traits::{Decaps, Encaps, KeyGen, SerDes as KemSerDes};

use aes_gcm::aead::generic_array::GenericArray;
use aes_gcm::{
    aead::{Aead, OsRng},
    Aes256Gcm, KeyInit,
};
use serde::{Deserialize, Serialize};
use zeroize::{Zeroize, ZeroizeOnDrop};

#[cfg(not(feature = "std"))]
use alloc::format;
#[cfg(not(feature = "std"))]
use alloc::string::String;
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "std")]
use std::cell::RefCell;

// [Phase 7.1b] Thread-local buffer pools for ML-DSA-65 operations
// Reduces allocation overhead for high-frequency signing/verification
#[cfg(feature = "std")]
thread_local! {
    static SK_BUFFER: RefCell<[u8; 4032]> = RefCell::new([0u8; 4032]);
    static PK_BUFFER: RefCell<[u8; 1952]> = RefCell::new([0u8; 1952]);
    static SIG_BUFFER: RefCell<[u8; 3309]> = RefCell::new([0u8; 3309]);
}

/// Represents a Public/Private key pair.
#[cfg_attr(feature = "python", pyclass)]
#[derive(Serialize, Deserialize, Clone, Zeroize, ZeroizeOnDrop)]
pub struct PQCKeypair {
    pub public_key: String,
    pub private_key: String,
}

impl core::fmt::Debug for PQCKeypair {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("PQCKeypair")
            .field("public_key", &self.public_key)
            .field("private_key", &"REDACTED")
            .finish()
    }
}

impl PQCKeypair {
    /// Generates a hardened PQC keypair (ML-DSA-65 Production).
    /// Uses Hardware-Bound entropy for maximum security.
    #[must_use]
    pub fn generate_raw() -> (String, String) {
        // 1. Get entropy from hardware
        let mut seed = [0u8; 32];
        let _ = crate::hardware::HardwareEntropy::get_bytes(&mut seed);
        Self::generate_from_seed(seed)
    }

    /// Generates a PQC keypair from a specific 32-byte seed.
    /// This is used for deterministic hardware identity (HSM).
    #[must_use]
    pub fn generate_from_seed(seed: [u8; 32]) -> (String, String) {
        use rand::SeedableRng;
        use rand_chacha::ChaCha20Rng;

        // 1. Initialize CSPRNG from the provided seed
        let mut rng = ChaCha20Rng::from_seed(seed);

        // 2. Generate keypair (infallible with valid RNG)
        let (pk, sk) = match ml_dsa_65::try_keygen_with_rng(&mut rng) {
            Ok(keypair) => keypair,
            Err(_) => {
                // SAFETY: ML-DSA keygen with ChaCha20 RNG should never fail.
                #[cfg(feature = "std")]
                {
                    eprintln!("CRITICAL: ML-DSA KeyGen failed with provided seed.");
                    std::process::abort();
                }
                #[cfg(not(feature = "std"))]
                {
                    loop {} // Halt on bare-metal
                }
            }
        };

        let pk_bytes = pk.into_bytes();
        let sk_bytes = sk.into_bytes();
        let pk_hex = hex::encode(pk_bytes);
        let sk_hex = hex::encode(sk_bytes);
        (pk_hex.clone(), format!("{}:{}", pk_hex, sk_hex))
    }

    /// Generates a PQCKeypair struct (for API compatibility with field access).
    /// Use generate_raw() for tuple-based access.
    #[must_use]
    pub fn generate() -> Self {
        let (pk, sk) = Self::generate_raw();
        PQCKeypair {
            public_key: pk,
            private_key: sk,
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl PQCKeypair {
    #[staticmethod]
    #[pyo3(name = "generate")]
    #[must_use]
    pub fn py_generate() -> (String, String) {
        Self::generate_raw()
    }

    #[staticmethod]
    #[pyo3(name = "generate_from_seed")]
    #[must_use]
    pub fn py_generate_from_seed(seed: [u8; 32]) -> (String, String) {
        Self::generate_from_seed(seed)
    }
}

/// Sovereign Implementation of ML-DSA (FIPS 204).
#[cfg_attr(feature = "python", pyclass)]
pub struct MLDSA;

impl MLDSA {
    /// Signs a message using ML-DSA-65 with thread-local buffer pooling.
    ///
    /// [Phase 7.1b] Optimized version using pre-allocated buffers.
    /// All sensitive buffers are zeroized after use.
    #[cfg(feature = "std")]
    pub fn sign_raw_with_buffer(private_key_hex: &str, message: &str) -> Result<String, String> {
        use rand::SeedableRng;
        use rand_chacha::ChaCha20Rng;
        use zeroize::Zeroize;

        // [C4 Security Fix] Reject simulated keys in signing operations.
        if private_key_hex.starts_with("WARM-KEY-SIM-") {
            return Err("Simulated keys cannot be used for signing".to_string());
        }

        let parts: Vec<&str> = private_key_hex.split(':').collect();
        let sk_hex = parts
            .last()
            .ok_or("Invalid Private Key Format: Missing parts")?;

        // Decode and zeroize on all exit paths
        let mut sk_bytes = hex::decode(sk_hex).map_err(|e| format!("Invalid SK hex: {}", e))?;

        let result = SK_BUFFER.with(|buf| {
            let mut buffer = buf.borrow_mut();

            // Copy decoded bytes into thread-local buffer
            if sk_bytes.len() != 4032 {
                return Err(format!(
                    "Invalid SK length: expected 4032, got {}",
                    sk_bytes.len()
                ));
            }
            buffer.copy_from_slice(&sk_bytes);

            let sk = ml_dsa_65::PrivateKey::try_from_bytes(*buffer)
                .map_err(|e| format!("Failed to reconstruct ML-DSA Private Key: {:?}", e))?;

            #[cfg(feature = "std")]
            let start = std::time::Instant::now();

            // Hardware Entropy for Randomized Signing
            // Zeroize seed after RNG initialization
            let mut seed = [0u8; 32];
            let _ = crate::hardware::HardwareEntropy::get_bytes(&mut seed);
            let mut rng = ChaCha20Rng::from_seed(seed);
            seed.zeroize();

            let sig = sk
                .try_sign_with_rng(&mut rng, message.as_bytes(), &[])
                .map_err(|e| format!("ML-DSA Signing Failed: {:?}", e))?;

            // Zeroize buffer before releasing
            buffer.zeroize();

            #[cfg(feature = "std")]
            {
                let duration = start.elapsed();
                if duration.as_micros() > 5000 {
                    eprintln!(
                        "⚠️ [PQC] Slow Signing Detected: {:?} (Optimization Recommended)",
                        duration
                    );
                }
            }

            Ok(hex::encode(sig))
        });

        // Always zeroize sk_bytes before returning
        sk_bytes.zeroize();

        result
    }

    /// Signs a message using real ML-DSA-65 Logic.
    ///
    /// All sensitive buffers are zeroized after use.
    pub fn sign_raw(private_key_hex: &str, message: &str) -> Result<String, String> {
        // [Phase 7.1b] Delegate to optimized buffer version on std
        #[cfg(feature = "std")]
        {
            Self::sign_raw_with_buffer(private_key_hex, message)
        }

        // [Phase 7.1b] Fallback to original implementation on no_std
        #[cfg(not(feature = "std"))]
        {
            use rand::SeedableRng;
            use rand_chacha::ChaCha20Rng;
            use zeroize::Zeroize;

            // [C4 Security Fix] Reject simulated keys in signing operations.
            if private_key_hex.starts_with("WARM-KEY-SIM-") {
                return Err("Simulated keys cannot be used for signing".to_string());
            }

            let parts: Vec<&str> = private_key_hex.split(':').collect();
            let sk_hex = parts
                .last()
                .ok_or("Invalid Private Key Format: Missing parts")?;

            // Decode and zeroize on all exit paths
            let mut sk_bytes = hex::decode(sk_hex).map_err(|e| format!("Invalid SK hex: {}", e))?;

            let result = (|| {
                let mut sk_arr: [u8; 4032] =
                    sk_bytes.clone().try_into().map_err(|e: Vec<u8>| {
                        format!("Invalid SK length: expected 4032, got {}", e.len())
                    })?;

                let sk = ml_dsa_65::PrivateKey::try_from_bytes(sk_arr)
                    .map_err(|e| format!("Failed to reconstruct ML-DSA Private Key: {:?}", e));

                // Zeroize the array copy immediately after use
                sk_arr.zeroize();

                let sk = sk?;

                // Hardware Entropy for Randomized Signing
                // Zeroize seed after RNG initialization
                let mut seed = [0u8; 32];
                let _ = crate::hardware::HardwareEntropy::get_bytes(&mut seed);
                let mut rng = ChaCha20Rng::from_seed(seed);
                seed.zeroize();

                let sig = sk
                    .try_sign_with_rng(&mut rng, message.as_bytes(), &[])
                    .map_err(|e| format!("ML-DSA Signing Failed: {:?}", e))?;

                Ok(hex::encode(sig))
            })();

            // Always zeroize sk_bytes before returning
            sk_bytes.zeroize();

            result
        }
    }

    /// Verifies a signature using ML-DSA-65 with thread-local buffer pooling.
    ///
    /// [Phase 7.1b] Optimized version using pre-allocated buffers.
    #[cfg(feature = "std")]
    #[must_use]
    pub fn verify_raw_with_buffer(public_key: &str, message: &str, signature: &str) -> bool {
        if public_key.starts_with("WARM-KEY-SIM-") {
            return false;
        }

        let pk_bytes = match hex::decode(public_key) {
            Ok(b) => b,
            Err(_) => return false,
        };

        let sig_bytes = match hex::decode(signature) {
            Ok(b) => b,
            Err(_) => return false,
        };

        PK_BUFFER.with(|pk_buf| {
            SIG_BUFFER.with(|sig_buf| {
                let mut pk_buffer = pk_buf.borrow_mut();
                let mut sig_buffer = sig_buf.borrow_mut();

                // Validate and copy public key
                if pk_bytes.len() != 1952 {
                    return false;
                }
                pk_buffer.copy_from_slice(&pk_bytes);

                let pk = match ml_dsa_65::PublicKey::try_from_bytes(*pk_buffer) {
                    Ok(k) => k,
                    Err(_) => return false,
                };

                // Validate and copy signature
                if sig_bytes.len() != 3309 {
                    return false;
                }
                sig_buffer.copy_from_slice(&sig_bytes);

                pk.verify(message.as_bytes(), &*sig_buffer, &[])
            })
        })
    }

    /// Verifies a signature using ML-DSA-65.
    #[must_use]
    pub fn verify_raw(public_key: &str, message: &str, signature: &str) -> bool {
        // [Phase 7.1b] Delegate to optimized buffer version on std
        #[cfg(feature = "std")]
        {
            Self::verify_raw_with_buffer(public_key, message, signature)
        }

        // [Phase 7.1b] Fallback to original implementation on no_std
        #[cfg(not(feature = "std"))]
        {
            if public_key.starts_with("WARM-KEY-SIM-") {
                return false;
            }
            let pk_bytes = match hex::decode(public_key) {
                Ok(b) => b,
                Err(_) => return false,
            };
            let pk_arr: [u8; 1952] = match pk_bytes.try_into() {
                Ok(a) => a,
                Err(_) => return false,
            };
            let pk = match ml_dsa_65::PublicKey::try_from_bytes(pk_arr) {
                Ok(k) => k,
                Err(_) => return false,
            };
            let sig_bytes = match hex::decode(signature) {
                Ok(b) => b,
                Err(_) => return false,
            };
            let sig_arr: [u8; 3309] = match sig_bytes.try_into() {
                Ok(a) => a,
                Err(_) => return false,
            };
            pk.verify(message.as_bytes(), &sig_arr, &[])
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl MLDSA {
    /// Signs a message using ML-DSA-65.
    /// Returns hex-encoded signature or raises exception on failure.
    ///
    /// Validates input sizes to prevent DoS.
    #[staticmethod]
    pub fn sign(private_key_hex: &str, message: &str) -> pyo3::PyResult<String> {
        // FFI Input Validation
        crate::ffi_limits::validate_hex(private_key_hex, "private_key")
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        crate::ffi_limits::validate_string(message, "message")
            .map_err(pyo3::exceptions::PyValueError::new_err)?;

        Self::sign_raw(private_key_hex, message).map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Verifies a signature using ML-DSA-65.
    ///
    /// Validates input sizes to prevent DoS.
    #[staticmethod]
    #[must_use]
    pub fn verify(public_key: &str, message: &str, signature: &str) -> bool {
        // FFI Input Validation - fail closed on invalid input
        if crate::ffi_limits::validate_hex(public_key, "public_key").is_err() {
            return false;
        }
        if crate::ffi_limits::validate_string(message, "message").is_err() {
            return false;
        }
        if crate::ffi_limits::validate_hex(signature, "signature").is_err() {
            return false;
        }

        Self::verify_raw(public_key, message, signature)
    }
}

// ============================================================================
// ML-KEM-768 (FIPS 203) - Post-Quantum Key Encapsulation Mechanism
// ============================================================================

/// ML-KEM-768 Key Encapsulation Result
#[cfg_attr(feature = "python", pyclass)]
#[derive(Debug, Clone)]
pub struct KEMEncapsResult {
    /// The shared secret key (32 bytes, hex-encoded)
    pub shared_secret: String,
    /// The ciphertext to send to the decapsulating party (1088 bytes, hex-encoded)
    pub ciphertext: String,
}

#[cfg(feature = "python")]
#[pymethods]
impl KEMEncapsResult {
    #[getter]
    fn get_shared_secret(&self) -> String {
        self.shared_secret.clone()
    }

    #[getter]
    fn get_ciphertext(&self) -> String {
        self.ciphertext.clone()
    }
}

/// Sovereign Implementation of ML-KEM-768 (FIPS 203).
/// Post-Quantum Key Encapsulation Mechanism for secure key exchange.
#[cfg_attr(feature = "python", pyclass)]
pub struct MLKEM;

impl MLKEM {
    /// Generates an ML-KEM-768 keypair.
    /// Returns (encapsulation_key, decapsulation_key) as hex-encoded strings.
    ///
    /// - Encapsulation key (public): 1184 bytes
    /// - Decapsulation key (private): 2400 bytes
    #[cfg(feature = "std")]
    pub fn keygen_raw() -> Result<(String, String), String> {
        use rand_core::OsRng;

        let (ek, dk) = ml_kem_768::KG::try_keygen_with_rng(&mut OsRng)
            .map_err(|e| format!("ML-KEM KeyGen Failed: {}", e))?;

        let ek_bytes = ek.into_bytes();
        let dk_bytes = dk.into_bytes();

        Ok((hex::encode(ek_bytes), hex::encode(dk_bytes)))
    }

    /// Generates an ML-KEM-768 keypair - no_std version.
    #[cfg(not(feature = "std"))]
    pub fn keygen_raw() -> Result<(String, String), String> {
        use rand::SeedableRng;
        use rand_chacha::ChaCha20Rng;

        let mut seed = [0u8; 32];
        getrandom::getrandom(&mut seed).map_err(|e| format!("Failed to get entropy: {:?}", e))?;
        let mut rng = ChaCha20Rng::from_seed(seed);

        let (ek, dk) = ml_kem_768::KG::try_keygen_with_rng(&mut rng)
            .map_err(|e| format!("ML-KEM KeyGen Failed: {}", e))?;

        let ek_bytes = ek.into_bytes();
        let dk_bytes = dk.into_bytes();

        Ok((hex::encode(ek_bytes), hex::encode(dk_bytes)))
    }

    /// Encapsulates a shared secret using the recipient's encapsulation key.
    /// Returns (shared_secret, ciphertext) as hex-encoded strings.
    ///
    /// - Shared secret: 32 bytes
    /// - Ciphertext: 1088 bytes
    #[cfg(feature = "std")]
    pub fn encapsulate_raw(encaps_key_hex: &str) -> Result<KEMEncapsResult, String> {
        use rand_core::OsRng;

        let ek_bytes = hex::decode(encaps_key_hex)
            .map_err(|e| format!("Invalid encapsulation key hex: {}", e))?;

        let ek_arr: [u8; ml_kem_768::EK_LEN] = ek_bytes.try_into().map_err(|e: Vec<u8>| {
            format!(
                "Invalid encapsulation key length: expected {}, got {}",
                ml_kem_768::EK_LEN,
                e.len()
            )
        })?;

        let ek = ml_kem_768::EncapsKey::try_from_bytes(ek_arr)
            .map_err(|e| format!("Invalid encapsulation key: {}", e))?;

        let (ssk, ct) = ek
            .try_encaps_with_rng(&mut OsRng)
            .map_err(|e| format!("ML-KEM Encapsulation Failed: {}", e))?;

        Ok(KEMEncapsResult {
            shared_secret: hex::encode(ssk.into_bytes()),
            ciphertext: hex::encode(ct.into_bytes()),
        })
    }

    /// Encapsulates a shared secret - no_std version.
    #[cfg(not(feature = "std"))]
    pub fn encapsulate_raw(encaps_key_hex: &str) -> Result<KEMEncapsResult, String> {
        use alloc::vec::Vec;
        use rand::SeedableRng;
        use rand_chacha::ChaCha20Rng;

        let ek_bytes = hex::decode(encaps_key_hex)
            .map_err(|e| format!("Invalid encapsulation key hex: {}", e))?;

        let ek_arr: [u8; ml_kem_768::EK_LEN] = ek_bytes.try_into().map_err(|e: Vec<u8>| {
            format!(
                "Invalid encapsulation key length: expected {}, got {}",
                ml_kem_768::EK_LEN,
                e.len()
            )
        })?;

        let ek = ml_kem_768::EncapsKey::try_from_bytes(ek_arr)
            .map_err(|e| format!("Invalid encapsulation key: {}", e))?;

        let mut seed = [0u8; 32];
        getrandom::getrandom(&mut seed).map_err(|e| format!("Failed to get entropy: {:?}", e))?;
        let mut rng = ChaCha20Rng::from_seed(seed);

        let (ssk, ct) = ek
            .try_encaps_with_rng(&mut rng)
            .map_err(|e| format!("ML-KEM Encapsulation Failed: {}", e))?;

        Ok(KEMEncapsResult {
            shared_secret: hex::encode(ssk.into_bytes()),
            ciphertext: hex::encode(ct.into_bytes()),
        })
    }

    /// Decapsulates the ciphertext using the decapsulation key to recover the shared secret.
    /// Returns the shared secret as a hex-encoded string (32 bytes).
    ///
    /// All sensitive buffers are zeroized after use.
    pub fn decapsulate_raw(decaps_key_hex: &str, ciphertext_hex: &str) -> Result<String, String> {
        use zeroize::Zeroize;

        // Decode and zeroize on all exit paths
        let mut dk_bytes = hex::decode(decaps_key_hex)
            .map_err(|e| format!("Invalid decapsulation key hex: {}", e))?;

        let result = (|| {
            let mut dk_arr: [u8; ml_kem_768::DK_LEN] =
                dk_bytes.clone().try_into().map_err(|e: Vec<u8>| {
                    format!(
                        "Invalid decapsulation key length: expected {}, got {}",
                        ml_kem_768::DK_LEN,
                        e.len()
                    )
                })?;

            let dk = ml_kem_768::DecapsKey::try_from_bytes(dk_arr)
                .map_err(|e| format!("Invalid decapsulation key: {}", e));

            // Zeroize the array copy immediately after use
            dk_arr.zeroize();

            let dk = dk?;

            let ct_bytes = hex::decode(ciphertext_hex)
                .map_err(|e| format!("Invalid ciphertext hex: {}", e))?;

            let ct_arr: [u8; ml_kem_768::CT_LEN] = ct_bytes.try_into().map_err(|e: Vec<u8>| {
                format!(
                    "Invalid ciphertext length: expected {}, got {}",
                    ml_kem_768::CT_LEN,
                    e.len()
                )
            })?;

            let ct = ml_kem_768::CipherText::try_from_bytes(ct_arr)
                .map_err(|e| format!("Invalid ciphertext: {}", e))?;

            let ssk = dk
                .try_decaps(&ct)
                .map_err(|e| format!("ML-KEM Decapsulation Failed: {}", e))?;

            Ok(hex::encode(ssk.into_bytes()))
        })();

        // Always zeroize dk_bytes before returning
        dk_bytes.zeroize();

        result
    }
}

/// Hybrid PQC Encryption Result (ML-KEM + AES-256-GCM)
#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HybridEncryptResult {
    pub kem_ciphertext: String,
    pub aes_ciphertext: String,
    pub nonce: String,
    pub tag: String,
}

#[cfg(feature = "python")]
#[pymethods]
impl HybridEncryptResult {
    fn __getitem__(&self, key: String) -> pyo3::PyResult<String> {
        match key.as_str() {
            "kem_ciphertext" => Ok(self.kem_ciphertext.clone()),
            "aes_ciphertext" => Ok(self.aes_ciphertext.clone()),
            "nonce" => Ok(self.nonce.clone()),
            "tag" => Ok(self.tag.clone()),
            _ => Err(pyo3::exceptions::PyKeyError::new_err(key)),
        }
    }
}

/// Strategic Implementation of Hybrid Encryption.
#[cfg_attr(feature = "python", pyclass)]
pub struct HybridEncryption;

impl HybridEncryption {
    #[cfg(feature = "std")]
    pub fn encrypt_raw(
        public_key_hex: &str,
        plaintext: &[u8],
    ) -> Result<HybridEncryptResult, String> {
        use aes_gcm::aead::AeadCore;

        // 1. ML-KEM Encapsulation
        let kem_result = MLKEM::encapsulate_raw(public_key_hex)?;
        let shared_secret = hex::decode(&kem_result.shared_secret)
            .map_err(|e| format!("Invalid shared secret hex: {}", e))?;

        // 2. AES-GCM Encryption
        let key = GenericArray::from_slice(&shared_secret);
        let cipher = Aes256Gcm::new(key);

        let nonce = Aes256Gcm::generate_nonce(&mut OsRng);

        let ciphertext = cipher
            .encrypt(&nonce, plaintext)
            .map_err(|e| format!("AES-GCM Encryption Failed: {}", e))?;

        // Split ciphertext and tag (Aes256Gcm::encrypt appends tag)
        let tag_len = 16;
        if ciphertext.len() < tag_len {
            return Err("Encryption produced invalid ciphertext".to_string());
        }
        let (ct, tag) = ciphertext.split_at(ciphertext.len() - tag_len);

        Ok(HybridEncryptResult {
            kem_ciphertext: kem_result.ciphertext,
            aes_ciphertext: hex::encode(ct),
            nonce: hex::encode(nonce),
            tag: hex::encode(tag),
        })
    }

    #[cfg(feature = "std")]
    pub fn decrypt_raw(
        private_key_hex: &str,
        kem_ciphertext_hex: &str,
        aes_ciphertext_hex: &str,
        nonce_hex: &str,
        tag_hex: &str,
    ) -> Result<Vec<u8>, String> {
        // 1. ML-KEM Decapsulation
        let shared_secret_hex = MLKEM::decapsulate_raw(private_key_hex, kem_ciphertext_hex)?;
        let shared_secret = hex::decode(&shared_secret_hex)
            .map_err(|e| format!("Invalid shared secret hex: {}", e))?;

        // 2. AES-GCM Decryption
        let key = GenericArray::from_slice(&shared_secret);
        let cipher = Aes256Gcm::new(key);

        let nonce_bytes =
            hex::decode(nonce_hex).map_err(|e| format!("Invalid nonce hex: {}", e))?;
        let nonce = GenericArray::from_slice(&nonce_bytes);

        let mut full_ciphertext = hex::decode(aes_ciphertext_hex)
            .map_err(|e| format!("Invalid ciphertext hex: {}", e))?;
        let tag_bytes = hex::decode(tag_hex).map_err(|e| format!("Invalid tag hex: {}", e))?;
        full_ciphertext.extend_from_slice(&tag_bytes);

        let plaintext = cipher
            .decrypt(nonce, full_ciphertext.as_slice())
            .map_err(|e| format!("AES-GCM Decryption Failed: {}", e))?;

        Ok(plaintext)
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl HybridEncryption {
    #[staticmethod]
    pub fn encrypt(public_key_hex: &str, plaintext: &[u8]) -> pyo3::PyResult<HybridEncryptResult> {
        Self::encrypt_raw(public_key_hex, plaintext)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    #[staticmethod]
    pub fn decrypt(
        private_key_hex: &str,
        kem_ciphertext: &str,
        aes_ciphertext: &str,
        nonce: &str,
        tag: &str,
    ) -> pyo3::PyResult<Vec<u8>> {
        Self::decrypt_raw(private_key_hex, kem_ciphertext, aes_ciphertext, nonce, tag)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl MLKEM {
    /// Generate ML-KEM-768 keypair.
    /// Returns (encapsulation_key, decapsulation_key) tuple.
    /// Raises PyValueError on failure.
    #[staticmethod]
    pub fn keygen() -> pyo3::PyResult<(String, String)> {
        Self::keygen_raw().map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Encapsulate using recipient's public key.
    /// Returns KEMEncapsResult with shared_secret and ciphertext.
    /// Raises PyValueError on invalid key.
    #[staticmethod]
    pub fn encapsulate(encaps_key_hex: &str) -> pyo3::PyResult<KEMEncapsResult> {
        Self::encapsulate_raw(encaps_key_hex).map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Decapsulate ciphertext to recover shared secret.
    /// Returns shared secret as hex string.
    /// Raises PyValueError on invalid key or ciphertext.
    #[staticmethod]
    pub fn decapsulate(decaps_key_hex: &str, ciphertext_hex: &str) -> pyo3::PyResult<String> {
        Self::decapsulate_raw(decaps_key_hex, ciphertext_hex)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mldsa_roundtrip() {
        let (pk, sk) = PQCKeypair::generate_raw();
        let message = "Kinetic Reality Check";
        let signature = MLDSA::sign_raw(&sk, message).unwrap();
        assert!(MLDSA::verify_raw(&pk, message, &signature));
    }

    #[test]
    #[cfg(feature = "std")]
    fn test_mldsa_buffered_roundtrip() {
        let (pk, sk) = PQCKeypair::generate_raw();
        let message = "Kinetic Reality Check with Buffer";
        let signature = MLDSA::sign_raw_with_buffer(&sk, message).unwrap();
        assert!(MLDSA::verify_raw_with_buffer(&pk, message, &signature));
    }

    #[test]
    #[cfg(feature = "std")]
    fn test_buffered_vs_standard_consistency() {
        let (pk, sk) = PQCKeypair::generate_raw();
        let message = "Cross-implementation test";

        // Sign with buffer, verify with standard
        let sig1 = MLDSA::sign_raw_with_buffer(&sk, message).unwrap();
        assert!(MLDSA::verify_raw(&pk, message, &sig1));

        // Sign with standard, verify with buffer
        let sig2 = MLDSA::sign_raw(&sk, message).unwrap();
        assert!(MLDSA::verify_raw_with_buffer(&pk, message, &sig2));
    }

    #[test]
    #[cfg(feature = "std")]
    fn test_buffer_reuse() {
        // Test that thread-local buffers work correctly across multiple operations
        let (pk, sk) = PQCKeypair::generate_raw();

        for i in 0..10 {
            let message = format!("Message {}", i);
            let signature = MLDSA::sign_raw_with_buffer(&sk, &message).unwrap();
            assert!(MLDSA::verify_raw_with_buffer(&pk, &message, &signature));
        }
    }

    #[test]
    fn test_mlkem_roundtrip() {
        // Generate keypair
        let (ek, dk) = MLKEM::keygen_raw().unwrap();

        // Encapsulate - sender creates shared secret and ciphertext
        let result = MLKEM::encapsulate_raw(&ek).unwrap();
        let sender_secret = result.shared_secret;
        let ciphertext = result.ciphertext;

        // Decapsulate - recipient recovers the same shared secret
        let recipient_secret = MLKEM::decapsulate_raw(&dk, &ciphertext).unwrap();

        // Both parties should have the same shared secret
        assert_eq!(sender_secret, recipient_secret);

        // Verify key lengths
        assert_eq!(hex::decode(&ek).unwrap().len(), ml_kem_768::EK_LEN);
        assert_eq!(hex::decode(&dk).unwrap().len(), ml_kem_768::DK_LEN);
        assert_eq!(hex::decode(&ciphertext).unwrap().len(), ml_kem_768::CT_LEN);
        assert_eq!(hex::decode(&sender_secret).unwrap().len(), 32); // SSK_LEN
    }

    #[test]
    fn test_mlkem_wrong_decapsulation_key() {
        // Generate two keypairs
        let (ek1, _dk1) = MLKEM::keygen_raw().unwrap();
        let (_ek2, dk2) = MLKEM::keygen_raw().unwrap();

        // Encapsulate with first key
        let result = MLKEM::encapsulate_raw(&ek1).unwrap();

        // Try to decapsulate with wrong key - should produce different shared secret
        // (ML-KEM uses implicit rejection, so decapsulation "succeeds" but produces wrong secret)
        let wrong_secret = MLKEM::decapsulate_raw(&dk2, &result.ciphertext).unwrap();

        // Secrets should NOT match
        assert_ne!(result.shared_secret, wrong_secret);
    }

    #[test]
    fn test_mlkem_invalid_key_length() {
        let result = MLKEM::encapsulate_raw("deadbeef");
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .contains("Invalid encapsulation key length"));
    }
}
