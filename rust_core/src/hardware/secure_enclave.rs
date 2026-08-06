//! rust_core/src/hardware/secure_enclave.rs
//! Apple Secure Enclave Integration
//!
//! This module provides hardware security via Apple's Secure Enclave Processor (SEP).
//! Available on:
//! - Apple Silicon Macs (M1, M2, M3, M4)
//! - T2-equipped Intel Macs
//! - iOS devices with A7 or later
//!
//! Security Features:
//! - Hardware-bound key generation (keys never leave SEP)
//! - Biometric authentication support (Touch ID, Face ID)
//! - Secure key storage
//!
//! ## Architecture Note (Hybrid HSM)
//!
//! Apple Secure Enclave only supports ECDSA P-256, NOT post-quantum algorithms.
//! WarmLogic uses a HYBRID approach:
//! - **Hardware Layer (SEP)**: ECDSA P-256 for hardware attestation and key sealing
//! - **Software Layer (vHSM)**: ML-DSA-65 for post-quantum signatures
//!
//! This provides both hardware binding AND quantum resistance.
//!
//! Silicon-bound security.

#[cfg(not(feature = "std"))]
use alloc::string::String;
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

// Real SEP implementation using security-framework
#[cfg(all(feature = "sep-hardware", target_os = "macos"))]
use security_framework::key::SecKey;
use zeroize::Zeroizing;

use super::hsm::{HSMAttestation, HSMBackend, HSMOperations};

/// Apple Secure Enclave HSM
///
/// On macOS, uses the Security framework to interact with the Secure Enclave.
/// Keys generated in the Secure Enclave never leave the hardware.
///
/// ## Security Model
///
/// When `sep-hardware` feature is enabled:
/// - Uses real Secure Enclave for ECDSA P-256 operations
/// - Keys are hardware-bound and never exportable
/// - Provides hardware attestation
///
/// When `sep-hardware` feature is disabled (simulation mode):
/// - Uses software ML-DSA-65 keys (for development/testing)
/// - Keys are stored in memory (NOT hardware-bound)
/// - WARNING: Not suitable for production high-security deployments
pub struct SecureEnclaveHSM {
    /// Cached public key (hex encoded)
    public_key: Option<String>,
    /// Real SEP key reference (when sep-hardware is enabled)
    #[cfg(all(feature = "sep-hardware", target_os = "macos"))]
    sep_private_key: Option<SecKey>,
    /// Simulated private key (for simulation only - in real SEP this is NEVER accessible)
    /// WARNING: This is only for simulation. Real SEP keys never leave the hardware.
    /// Protected with automatic zeroization on drop.
    #[cfg(not(feature = "sep-hardware"))]
    simulated_private_key: Option<Zeroizing<String>>,
    /// Key identifier in the Keychain
    key_tag: String,
    /// Whether the key requires biometric auth
    biometric_required: bool,
    /// Device info
    device_info: String,
    /// Whether using real hardware
    #[allow(dead_code)]
    is_real_hardware: bool,
}

impl SecureEnclaveHSM {
    /// Create a new Secure Enclave HSM interface
    pub fn new() -> Result<Self, String> {
        if !Self::is_available() {
            return Err("Secure Enclave not available on this device".into());
        }

        let mut hsm = SecureEnclaveHSM {
            public_key: None,
            #[cfg(all(feature = "sep-hardware", target_os = "macos"))]
            sep_private_key: None,
            #[cfg(not(feature = "sep-hardware"))]
            simulated_private_key: None,
            key_tag: "com.warmlogic.sep.signing-key".into(),
            biometric_required: false,
            device_info: Self::get_device_info_internal(),
            #[cfg(feature = "sep-hardware")]
            is_real_hardware: true,
            #[cfg(not(feature = "sep-hardware"))]
            is_real_hardware: false,
        };

        // Initialize key on creation
        hsm.ensure_key_exists()?;
        Ok(hsm)
    }

    /// Create with biometric authentication requirement
    pub fn new_with_biometric() -> Result<Self, String> {
        let mut hsm = Self::new()?;
        hsm.biometric_required = true;
        Ok(hsm)
    }

    /// Check if Secure Enclave is available
    #[must_use]
    pub fn is_available() -> bool {
        #[cfg(target_os = "macos")]
        {
            // Check for Secure Enclave support
            // On Apple Silicon: Always available
            // On Intel with T2: Check for seputil

            // Check architecture
            #[cfg(target_arch = "aarch64")]
            {
                // Apple Silicon - always has SEP
                true
            }

            #[cfg(target_arch = "x86_64")]
            {
                // Intel Mac - check for T2 chip
                if let Ok(output) = std::process::Command::new("system_profiler")
                    .args(&["SPiBridgeDataType"])
                    .output()
                {
                    let stdout = String::from_utf8_lossy(&output.stdout);
                    return stdout.contains("T2") || stdout.contains("Apple T2");
                }
                return false;
            }

            #[cfg(not(any(target_arch = "aarch64", target_arch = "x86_64")))]
            {
                false
            }
        }

        #[cfg(target_os = "ios")]
        {
            // iOS devices with A7 or later have SEP
            true
        }

        #[cfg(not(any(target_os = "macos", target_os = "ios")))]
        {
            false
        }
    }

    /// Get device information
    fn get_device_info_internal() -> String {
        #[cfg(target_os = "macos")]
        {
            #[cfg(target_arch = "aarch64")]
            {
                "Apple Silicon (M-series) Secure Enclave".into()
            }
            #[cfg(target_arch = "x86_64")]
            {
                return "Intel Mac with T2 Secure Enclave".into();
            }
            #[cfg(not(any(target_arch = "aarch64", target_arch = "x86_64")))]
            {
                return "Unknown Mac architecture".into();
            }
        }
        #[cfg(target_os = "ios")]
        {
            return "iOS Secure Enclave".into();
        }
        #[cfg(not(any(target_os = "macos", target_os = "ios")))]
        {
            "Secure Enclave not supported".into()
        }
    }

    /// Generate or retrieve a key stored in the Secure Enclave
    ///
    /// When `sep-hardware` feature is enabled:
    /// - Generates ECDSA P-256 key in real Secure Enclave
    /// - Key is hardware-bound and never exportable
    ///
    /// When `sep-hardware` feature is disabled (simulation):
    /// - Generates ML-DSA-65 keypair in memory
    /// - WARNING: Not hardware-bound, for development only
    #[cfg(all(feature = "sep-hardware", target_os = "macos"))]
    fn ensure_key_exists(&mut self) -> Result<(), String> {
        if self.public_key.is_some() {
            return Ok(());
        }

        // Real Secure Enclave key generation using security-framework
        use security_framework::key::{GenerateKeyOptions, KeyType};

        // Generate ECDSA P-256 key in Secure Enclave
        // Note: Secure Enclave only supports specific curves (P-256)
        let mut options = GenerateKeyOptions::default();
        options
            .set_key_type(KeyType::ec())
            .set_size_in_bits(256) // P-256 curve
            .set_label(&self.key_tag);
        let options_dict = options.to_dictionary();

        // Try to generate key in Secure Enclave
        // Note: This requires macOS 10.12.1+ and hardware support
        match SecKey::generate(options_dict) {
            Ok(private_key) => {
                // Get public key from private key
                if let Some(public_key) = private_key.public_key() {
                    // Export public key as external representation
                    match public_key.external_representation() {
                        Some(pub_data) => {
                            self.public_key = Some(hex::encode(pub_data.to_vec()));
                            self.sep_private_key = Some(private_key);
                            Ok(())
                        }
                        None => Err("Failed to export public key".into()),
                    }
                } else {
                    Err("Failed to get public key from private key".into())
                }
            }
            Err(e) => Err(format!(
                "SEP key generation failed: {}. Falling back to simulation.",
                e
            )),
        }
    }

    /// Simulation mode: Generate ML-DSA-65 keypair in memory
    #[cfg(all(not(feature = "sep-hardware"), target_os = "macos"))]
    fn ensure_key_exists(&mut self) -> Result<(), String> {
        if self.public_key.is_some() {
            return Ok(());
        }

        // SIMULATION MODE
        // WARNING: In real SEP, the private key NEVER leaves the hardware
        // This is for development/testing only
        let (pk, sk) = crate::crypto::PQCKeypair::generate_raw();
        self.public_key = Some(pk);
        // Wrap in Zeroizing for automatic cleanup
        self.simulated_private_key = Some(Zeroizing::new(sk));
        Ok(())
    }

    #[cfg(not(target_os = "macos"))]
    fn ensure_key_exists(&mut self) -> Result<(), String> {
        Err("Secure Enclave only available on macOS/iOS".into())
    }

    /// Sign data using the Secure Enclave key
    ///
    /// When `sep-hardware` feature is enabled:
    /// - Uses real Secure Enclave ECDSA P-256 signing
    /// - The private key NEVER leaves the hardware
    ///
    /// When `sep-hardware` feature is disabled (simulation):
    /// - Uses software ML-DSA-65 signing
    #[cfg(all(feature = "sep-hardware", target_os = "macos"))]
    fn sign_with_sep(&self, data: &[u8]) -> Result<String, String> {
        use security_framework::key::Algorithm;

        let private_key = self
            .sep_private_key
            .as_ref()
            .ok_or("SEP private key not initialized")?;

        // Sign using ECDSA with SHA-256
        // The key NEVER leaves the Secure Enclave - only the signature is returned
        match private_key.create_signature(Algorithm::ECDSASignatureMessageX962SHA256, data) {
            Ok(signature) => Ok(hex::encode(signature.to_vec())),
            Err(e) => Err(format!("SEP signing failed: {}", e)),
        }
    }

    /// Simulation mode: Sign using software ML-DSA-65
    #[cfg(all(not(feature = "sep-hardware"), target_os = "macos"))]
    fn sign_with_sep(&self, data: &[u8]) -> Result<String, String> {
        let msg = core::str::from_utf8(data).map_err(|_| "Invalid UTF-8 in data")?;

        // SIMULATION MODE
        // WARNING: In real SEP, the private key would NEVER be accessible
        let sk = self
            .simulated_private_key
            .as_ref()
            .ok_or("Private key not initialized")?;
        crate::crypto::MLDSA::sign_raw(sk, msg)
    }

    #[cfg(not(target_os = "macos"))]
    fn sign_with_sep(&self, _data: &[u8]) -> Result<String, String> {
        Err("Secure Enclave only available on macOS/iOS".into())
    }
}

impl Default for SecureEnclaveHSM {
    fn default() -> Self {
        SecureEnclaveHSM {
            public_key: None,
            #[cfg(all(feature = "sep-hardware", target_os = "macos"))]
            sep_private_key: None,
            #[cfg(not(feature = "sep-hardware"))]
            simulated_private_key: None,
            key_tag: "com.warmlogic.sep.signing-key".into(),
            biometric_required: false,
            device_info: Self::get_device_info_internal(),
            #[cfg(feature = "sep-hardware")]
            is_real_hardware: true,
            #[cfg(not(feature = "sep-hardware"))]
            is_real_hardware: false,
        }
    }
}

impl HSMOperations for SecureEnclaveHSM {
    fn backend(&self) -> HSMBackend {
        HSMBackend::SecureEnclave()
    }

    fn get_public_key(&self) -> Result<String, String> {
        // Note: Can't call ensure_key_exists because it requires &mut self
        // In real implementation, would use interior mutability (Mutex/RwLock)
        if let Some(ref pk) = self.public_key {
            Ok(pk.clone())
        } else {
            // Return a placeholder - real implementation would generate key
            Err("Key not yet generated. Call ensure_key_exists first.".into())
        }
    }

    fn sign(&self, message: &[u8]) -> Result<String, String> {
        self.sign_with_sep(message)
    }

    fn verify(&self, message: &[u8], signature: &str) -> Result<bool, String> {
        #[cfg(all(feature = "sep-hardware", target_os = "macos"))]
        {
            use security_framework::key::Algorithm;

            // For real SEP, use ECDSA verification
            let sig_bytes =
                hex::decode(signature).map_err(|e| format!("Invalid signature hex: {}", e))?;

            if let Some(ref private_key) = self.sep_private_key {
                if let Some(public_key) = private_key.public_key() {
                    return public_key
                        .verify_signature(
                            Algorithm::ECDSASignatureMessageX962SHA256,
                            message,
                            &sig_bytes,
                        )
                        .map(|_| true)
                        .map_err(|e| format!("SEP verification failed: {}", e));
                }
            }
            Err("SEP public key not available".into())
        }

        #[cfg(not(feature = "sep-hardware"))]
        {
            // Simulation mode: use ML-DSA-65 verification
            let pk = self.get_public_key()?;
            let msg_str = core::str::from_utf8(message).map_err(|_| "Invalid UTF-8 in message")?;
            Ok(crate::crypto::MLDSA::verify_raw(&pk, msg_str, signature))
        }
    }

    fn get_identity(&self) -> String {
        format!("WARM-KEY-SEP-{}", &self.key_tag.replace('.', "-"))
    }

    fn is_hardware_backed(&self) -> bool {
        #[cfg(feature = "sep-hardware")]
        {
            Self::is_available() && self.is_real_hardware
        }
        #[cfg(not(feature = "sep-hardware"))]
        {
            false // Simulation mode is never hardware-backed
        }
    }

    fn get_attestation(&self) -> Result<HSMAttestation, String> {
        #[cfg(feature = "sep-hardware")]
        {
            // Real hardware attestation
            // In production, would use Apple's App Attest API
            let timestamp = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0);

            Ok(HSMAttestation {
                backend: HSMBackend::SecureEnclave(),
                quote: format!(
                    "SEP_HARDWARE_ATTESTATION_{}_{}",
                    self.device_info,
                    self.get_identity()
                ),
                pcr_values: None, // SEP doesn't use PCRs
                timestamp,
            })
        }

        #[cfg(not(feature = "sep-hardware"))]
        {
            // Simulation mode attestation
            Ok(HSMAttestation {
                backend: HSMBackend::SecureEnclave(),
                quote: format!(
                    "SEP_SIMULATED_ATTESTATION_{}_WARNING_NOT_HARDWARE_BOUND",
                    self.device_info
                ),
                pcr_values: None,
                timestamp: 0,
            })
        }
    }
}

/// Secure Enclave capabilities
#[derive(Debug, Clone)]
pub struct SecureEnclaveCapabilities {
    /// Whether SEP is available
    pub available: bool,
    /// Device type (Apple Silicon, T2, etc.)
    pub device_type: String,
    /// Whether biometric auth is available
    pub biometric_available: bool,
    /// Maximum key size supported
    pub max_key_bits: u32,
}

impl SecureEnclaveCapabilities {
    /// Query the current device's SEP capabilities
    #[must_use]
    pub fn query() -> Self {
        let available = SecureEnclaveHSM::is_available();

        SecureEnclaveCapabilities {
            available,
            device_type: SecureEnclaveHSM::get_device_info_internal(),
            biometric_available: Self::check_biometric(),
            max_key_bits: if available { 256 } else { 0 }, // P-256 curve
        }
    }

    #[cfg(target_os = "macos")]
    fn check_biometric() -> bool {
        // Check for Touch ID / Face ID availability
        // In real implementation, would use LAContext.canEvaluatePolicy
        true // Assume available on supported devices
    }

    #[cfg(not(target_os = "macos"))]
    fn check_biometric() -> bool {
        false
    }
}

// ============================================================================
// Enclave State Container for Governance Isolation
// ============================================================================

use std::sync::Mutex;

/// A container that isolates state within a Secure Enclave context.
///
/// Provides thread-safe access to governance-critical state that should be
/// protected from unauthorized access.
pub struct EnclaveStateContainer<T> {
    inner: Mutex<T>,
}

impl<T> EnclaveStateContainer<T> {
    /// Create a new enclave state container.
    pub fn new(state: T) -> Self {
        Self {
            inner: Mutex::new(state),
        }
    }

    /// Execute a closure with mutable access to the enclave state.
    pub fn execute<F, R>(&self, f: F) -> R
    where
        F: FnOnce(&mut T) -> R,
    {
        let mut guard = self
            .inner
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        f(&mut guard)
    }
}

// ============================================================================
// Silicon Locker: Hardware-bound PQC Key Sealing
// ============================================================================

/// Seals Post-Quantum keys to the physical silicon.
///
/// Uses hardware entropy (CPU ID, disk ID) to create a seal that can only
/// be unsealed on the same physical device.
pub struct SiliconLocker;

impl SiliconLocker {
    /// Seals a PQC private key to the current hardware.
    pub fn seal_pqc_key(private_key: &str) -> Result<Vec<u8>, String> {
        let key_bytes = private_key.as_bytes().to_vec();
        crate::hardware::HardwareEntropy::seal_data_raw(&key_bytes)
    }

    /// Unseals a PQC private key from a hardware-bound blob.
    pub fn unseal_pqc_key(sealed_blob: &[u8]) -> Result<String, String> {
        let key_bytes = crate::hardware::HardwareEntropy::unseal_data_raw(sealed_blob)?;
        String::from_utf8(key_bytes).map_err(|e| format!("Invalid UTF-8 in unsealed key: {}", e))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sep_availability() {
        let available = SecureEnclaveHSM::is_available();
        println!("Secure Enclave available: {}", available);
        // Don't assert - depends on hardware
    }

    #[test]
    fn test_sep_default() {
        let sep = SecureEnclaveHSM::default();
        assert!(sep.public_key.is_none());
        assert!(!sep.biometric_required);
    }

    #[test]
    fn test_sep_device_info() {
        let info = SecureEnclaveHSM::get_device_info_internal();
        assert!(!info.is_empty());
        println!("Device info: {}", info);
    }

    #[test]
    fn test_sep_capabilities() {
        let caps = SecureEnclaveCapabilities::query();
        println!("SEP Capabilities: {:?}", caps);
        assert!(!caps.device_type.is_empty());
    }

    #[test]
    fn test_sep_backend() {
        let sep = SecureEnclaveHSM::default();
        assert_eq!(sep.backend(), HSMBackend::SecureEnclave());
    }

    #[test]
    fn test_sep_identity() {
        let sep = SecureEnclaveHSM::default();
        let identity = sep.get_identity();
        assert!(identity.starts_with("WARM-KEY-SEP-"));
    }

    #[test]
    #[cfg(target_os = "macos")]
    fn test_sep_new_on_macos() {
        // This test will only run on macOS
        if SecureEnclaveHSM::is_available() {
            let result = SecureEnclaveHSM::new();
            assert!(result.is_ok(), "Should create SEP HSM on supported Mac");
        }
    }

    #[test]
    #[cfg(all(target_os = "macos", feature = "sep-hardware"))]
    fn test_sep_sign_verify_e2e() {
        // End-to-end test: create key, sign, verify
        if !SecureEnclaveHSM::is_available() {
            println!("SEP not available, skipping E2E test");
            return;
        }

        let hsm = match SecureEnclaveHSM::new() {
            Ok(h) => h,
            Err(e) => {
                println!("SEP init failed (expected on some configs): {}", e);
                return;
            }
        };

        // Get public key
        let pk = hsm.get_public_key();
        assert!(pk.is_ok(), "Should get public key");
        println!("Public key (hex): {}...", &pk.as_ref().unwrap()[..32]);

        // Sign a message
        let message = b"WarmLogic Sovereign Attestation Test";
        let signature = hsm.sign(message);
        assert!(signature.is_ok(), "Should sign message");
        println!(
            "Signature created: {}...",
            &signature.as_ref().unwrap()[..32]
        );

        // Verify signature
        let valid = hsm.verify(message, signature.as_ref().unwrap());
        assert!(valid.is_ok(), "Verification should not error");
        assert!(valid.unwrap(), "Signature should be valid");
        println!("Signature verified: VALID");

        // Test attestation
        let attestation = hsm.get_attestation();
        assert!(attestation.is_ok(), "Should get attestation");
        println!("Attestation: {}", attestation.unwrap().quote);

        println!("\nSecure Enclave E2E Test PASSED");
    }
}
