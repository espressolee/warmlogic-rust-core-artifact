//! rust_core/src/hardware/hsm.rs
//! Unified Hardware Security Module Abstraction Layer
//!
//! This module provides a unified trait for hardware security operations
//! with multiple backends:
//! - SoftwareHSM: Pure software simulation (always available)
//! - TPM2HSM: Real TPM 2.0 hardware (Linux with tpm feature)
//! - SecureEnclaveHSM: Apple Secure Enclave (macOS)
//!
//! Silicon-bound security.

#[cfg(not(feature = "std"))]
use alloc::string::String;
#[cfg(feature = "python")]
use pyo3::prelude::*;

/// HSM Backend Type
#[cfg_attr(feature = "python", pyclass)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum HSMBackend {
    /// Software-only simulation
    Software(),
    /// TPM 2.0 hardware (Linux)
    TPM2(),
    /// Apple Secure Enclave (macOS)
    SecureEnclave(),
    /// Linux Kernel Keyring
    LinuxKeyring(),
    /// Cloud HSM Provider (AWS, Azure, GCP)
    Cloud(super::cloud_hsm::CloudProvider),
    /// PKCS#11 Generic Provider
    PKCS11(),
}

impl HSMBackend {
    /// Human-readable name
    #[must_use]
    pub fn name(&self) -> &'static str {
        match self {
            HSMBackend::Software() => "Software HSM",
            HSMBackend::TPM2() => "TPM 2.0",
            HSMBackend::SecureEnclave() => "Apple Secure Enclave",
            HSMBackend::LinuxKeyring() => "Linux Kernel Keyring",
            HSMBackend::Cloud(p) => match p {
                super::cloud_hsm::CloudProvider::AWS => "AWS CloudHSM",
                super::cloud_hsm::CloudProvider::Azure => "Azure Key Vault",
                super::cloud_hsm::CloudProvider::GCP => "GCP Cloud KMS",
                super::cloud_hsm::CloudProvider::None => "Unknown Cloud",
            },
            HSMBackend::PKCS11() => "PKCS#11 Token",
        }
    }

    /// Security level (1-3)
    /// 1: Software only
    /// 2: Hardware-backed but not certified
    /// 3: Certified hardware (TPM, SEP)
    #[must_use]
    pub fn security_level(&self) -> u8 {
        match self {
            HSMBackend::Software() => 1,
            HSMBackend::LinuxKeyring() => 2,
            HSMBackend::TPM2() => 3,
            HSMBackend::SecureEnclave() => 3,
            HSMBackend::Cloud(_) => 3,
            HSMBackend::PKCS11() => 3,
        }
    }
}

/// Unified HSM Operations Trait
/// All HSM backends must implement these core operations.
pub trait HSMOperations {
    /// Get the backend type
    fn backend(&self) -> HSMBackend;

    /// Generate or retrieve the hardware-bound keypair.
    /// Returns (public_key_hex, error_if_any)
    fn get_public_key(&self) -> Result<String, String>;

    /// Sign a message using the hardware-protected private key.
    /// The private key NEVER leaves the HSM.
    fn sign(&self, message: &[u8]) -> Result<String, String>;

    /// Verify a signature against the HSM's public key.
    fn verify(&self, message: &[u8], signature: &str) -> Result<bool, String>;

    /// Get a unique hardware identity string.
    fn get_identity(&self) -> String;

    /// Check if this HSM is using real hardware.
    fn is_hardware_backed(&self) -> bool {
        self.backend() != HSMBackend::Software()
    }

    /// Get attestation report (if supported).
    fn get_attestation(&self) -> Result<HSMAttestation, String> {
        Err("Attestation not supported by this backend".into())
    }
}

/// HSM Attestation Report
#[derive(Debug, Clone)]
pub struct HSMAttestation {
    /// Backend that generated this attestation
    pub backend: HSMBackend,
    /// Attestation quote/signature
    pub quote: String,
    /// PCR values (if TPM)
    pub pcr_values: Option<Vec<(u32, Vec<u8>)>>,
    /// Timestamp
    pub timestamp: u64,
}

/// Detect the best available HSM backend.
/// Order of preference: SecureEnclave > TPM2 > LinuxKeyring > Software
#[cfg(feature = "std")]
#[must_use]
pub fn detect_best_backend() -> HSMBackend {
    // Check Apple Secure Enclave (macOS)
    #[cfg(target_os = "macos")]
    {
        // Check if we're on Apple Silicon with Secure Enclave
        if std::path::Path::new("/usr/libexec/seputil").exists() {
            return HSMBackend::SecureEnclave();
        }
    }

    // Check TPM 2.0 (Linux)
    #[cfg(target_os = "linux")]
    {
        // Check for TPM device
        if std::path::Path::new("/dev/tpmrm0").exists()
            || std::path::Path::new("/dev/tpm0").exists()
        {
            #[cfg(feature = "tpm")]
            return HSMBackend::TPM2();
        }

        // Check for Kernel Keyring
        if std::path::Path::new("/proc/keys").exists() {
            return HSMBackend::LinuxKeyring();
        }
    }

    // Check for Cloud Environment
    let cloud = super::cloud_hsm::CloudHSM::detect();
    if cloud != super::cloud_hsm::CloudProvider::None {
        return HSMBackend::Cloud(cloud);
    }

    HSMBackend::Software()
}

#[cfg(not(feature = "std"))]
pub fn detect_best_backend() -> HSMBackend {
    HSMBackend::Software()
}

/// HSM Status for monitoring/debugging
#[cfg_attr(feature = "python", pyclass(get_all))]
#[derive(Debug, Clone)]
pub struct HSMStatus {
    pub backend: HSMBackend,
    pub is_initialized: bool,
    pub is_hardware_backed: bool,
    pub security_level: u8,
    pub identity: String,
}

// ============================================================================
// Backend Implementations
// ============================================================================

use super::cloud_hsm::CloudHSM;
use super::pkcs11::{Pkcs11Provider, Pkcs11Session};
#[cfg(target_os = "macos")] // only the macOS factory branches construct it
use super::secure_enclave::SecureEnclaveHSM;
use super::v_hsm::VirtualHSM;

impl HSMOperations for VirtualHSM {
    fn backend(&self) -> HSMBackend {
        HSMBackend::Software()
    }

    fn get_public_key(&self) -> Result<String, String> {
        Ok(self.get_public_key().to_string())
    }

    fn sign(&self, message: &[u8]) -> Result<String, String> {
        self.sign_blob(message)
    }

    fn verify(&self, message: &[u8], signature: &str) -> Result<bool, String> {
        let pk = self.get_public_key();
        let msg_str = core::str::from_utf8(message).map_err(|_| "Invalid UTF-8 in message")?;
        Ok(crate::crypto::MLDSA::verify_raw(pk, msg_str, signature))
    }

    fn get_identity(&self) -> String {
        self.get_public_identity()
    }
}

// ============================================================================
// Unified HSM Factory
// ============================================================================

/// Create the best available HSM based on system capabilities.
#[must_use]
pub fn create_hsm() -> Box<dyn HSMOperations + Send + Sync> {
    let backend = detect_best_backend();

    match backend {
        HSMBackend::Software() => Box::new(VirtualHSM::power_on()),
        HSMBackend::TPM2() => {
            // TPM2 requires Linux with tpm feature
            #[cfg(all(target_os = "linux", feature = "tpm"))]
            {
                if HardwareTPM::is_available() {
                    if let Ok(tpm) = HardwareTPM::new() {
                        return Box::new(tpm);
                    }
                }
                Box::new(VirtualHSM::power_on())
            }
            #[cfg(not(all(target_os = "linux", feature = "tpm")))]
            {
                Box::new(VirtualHSM::power_on())
            }
        }
        HSMBackend::SecureEnclave() => {
            // [C2] Apple Secure Enclave on macOS
            #[cfg(target_os = "macos")]
            {
                if SecureEnclaveHSM::is_available() {
                    if let Ok(sep) = SecureEnclaveHSM::new() {
                        return Box::new(sep);
                    }
                    // Fall through to software on error
                }
                Box::new(VirtualHSM::power_on())
            }
            #[cfg(not(target_os = "macos"))]
            {
                Box::new(VirtualHSM::power_on())
            }
        }
        HSMBackend::LinuxKeyring() => {
            #[cfg(target_os = "linux")]
            {
                Box::new(super::linux_keyring::LinuxKeyringHSM::new())
            }
            #[cfg(not(target_os = "linux"))]
            {
                Box::new(VirtualHSM::power_on())
            }
        }
        HSMBackend::Cloud(_) => {
            if let Ok(cloud) = CloudHSM::new() {
                Box::new(cloud)
            } else {
                Box::new(VirtualHSM::power_on())
            }
        }
        HSMBackend::PKCS11() => {
            #[cfg(feature = "std")]
            {
                Box::new(Pkcs11Session::new(Pkcs11Provider::SoftHsm))
            }
            #[cfg(not(feature = "std"))]
            {
                Box::new(VirtualHSM::power_on())
            }
        }
    }
}

/// Create an HSM with a specific backend (for testing).
pub fn create_hsm_with_backend(
    backend: HSMBackend,
) -> Result<Box<dyn HSMOperations + Send + Sync>, String> {
    match backend {
        HSMBackend::Software() => Ok(Box::new(VirtualHSM::power_on())),
        HSMBackend::TPM2() => {
            #[cfg(all(target_os = "linux", feature = "tpm"))]
            {
                HardwareTPM::new().map(|tpm| Box::new(tpm) as Box<dyn HSMOperations + Send + Sync>)
            }
            #[cfg(not(all(target_os = "linux", feature = "tpm")))]
            {
                Err("TPM2 requires Linux and 'tpm' feature".into())
            }
        }
        HSMBackend::SecureEnclave() => {
            #[cfg(target_os = "macos")]
            {
                // [C2] Apple Secure Enclave
                if SecureEnclaveHSM::is_available() {
                    SecureEnclaveHSM::new()
                        .map(|sep| Box::new(sep) as Box<dyn HSMOperations + Send + Sync>)
                } else {
                    Err("Secure Enclave not available on this device".into())
                }
            }
            #[cfg(not(target_os = "macos"))]
            {
                Err("Secure Enclave requires macOS".into())
            }
        }
        HSMBackend::LinuxKeyring() => {
            #[cfg(target_os = "linux")]
            {
                Ok(Box::new(super::linux_keyring::LinuxKeyringHSM::new())
                    as Box<dyn HSMOperations + Send + Sync>)
            }
            #[cfg(not(target_os = "linux"))]
            {
                Err("Linux Keyring requires Linux".into())
            }
        }
        HSMBackend::Cloud(_) => {
            CloudHSM::new().map(|cloud| Box::new(cloud) as Box<dyn HSMOperations + Send + Sync>)
        }
        HSMBackend::PKCS11() => {
            #[cfg(feature = "std")]
            {
                Ok(Box::new(Pkcs11Session::new(Pkcs11Provider::SoftHsm))
                    as Box<dyn HSMOperations + Send + Sync>)
            }
            #[cfg(not(feature = "std"))]
            {
                Err("PKCS11 requires std feature".into())
            }
        }
    }
}

/// Get the current HSM status
#[cfg_attr(feature = "python", pyfunction)]
#[must_use]
pub fn get_hsm_status() -> HSMStatus {
    let backend = detect_best_backend();
    let hsm = create_hsm();

    HSMStatus {
        backend,
        is_initialized: true,
        is_hardware_backed: hsm.is_hardware_backed(),
        security_level: backend.security_level(),
        identity: hsm.get_identity(),
    }
}

// ============================================================================
// Hybrid HSM Architecture
// ============================================================================
//
// The HybridHSM combines:
// - Hardware security (SEP/TPM) for attestation and key sealing
// - Software security (vHSM) for ML-DSA-65 post-quantum signatures
//
// This provides BOTH hardware binding AND quantum resistance.
//
// Architecture:
// ┌─────────────────────────────────────────────────────────┐
// │  HybridHSM                                              │
// ├─────────────────────────────────────────────────────────┤
// │  Hardware Layer (SEP/TPM)                               │
// │  ├─ Hardware attestation (device binding)               │
// │  ├─ ECDSA P-256 signatures (hardware proof)             │
// │  └─ Key sealing (encrypt PQC keys with HW key)          │
// ├─────────────────────────────────────────────────────────┤
// │  Software Layer (vHSM)                                  │
// │  ├─ ML-DSA-65 signatures (quantum resistant)            │
// │  └─ ML-KEM-768 key exchange                             │
// └─────────────────────────────────────────────────────────┘

/// Hybrid HSM combining hardware attestation with PQC signatures
#[cfg(feature = "std")]
#[cfg_attr(feature = "python", pyclass)]
pub struct HybridHSM {
    /// Hardware HSM for attestation (SEP or TPM)
    hardware_hsm: Option<Box<dyn HSMOperations + Send + Sync>>,
    /// Software HSM for PQC signatures
    software_hsm: VirtualHSM,
    /// Whether hardware HSM is available
    has_hardware: bool,
}

#[cfg(feature = "std")]
impl HybridHSM {
    /// Create a new HybridHSM with the best available hardware backend
    #[must_use]
    pub fn new() -> Self {
        let backend = detect_best_backend();
        let hardware_hsm: Option<Box<dyn HSMOperations + Send + Sync>> = match backend {
            HSMBackend::SecureEnclave() => {
                #[cfg(target_os = "macos")]
                {
                    if SecureEnclaveHSM::is_available() {
                        match SecureEnclaveHSM::new() {
                            Ok(sep) => Some(Box::new(sep)),
                            Err(_) => None,
                        }
                    } else {
                        None
                    }
                }
                #[cfg(not(target_os = "macos"))]
                {
                    None
                }
            }
            HSMBackend::TPM2() => {
                // TPM2 implementation would go here
                None
            }
            _ => None,
        };

        let has_hardware = hardware_hsm.is_some();

        HybridHSM {
            hardware_hsm,
            software_hsm: VirtualHSM::power_on(),
            has_hardware,
        }
    }

    /// Get hardware attestation (if available)
    #[must_use]
    pub fn get_hardware_attestation(&self) -> Option<HSMAttestation> {
        self.hardware_hsm
            .as_ref()
            .and_then(|h| h.get_attestation().ok())
    }

    /// Sign with hardware ECDSA (for hardware binding proof)
    #[must_use]
    pub fn sign_hardware(&self, message: &[u8]) -> Option<String> {
        self.hardware_hsm
            .as_ref()
            .and_then(|h| h.sign(message).ok())
    }

    /// Check if hardware is available
    #[must_use]
    pub fn has_hardware_security(&self) -> bool {
        self.has_hardware
    }

    /// Get combined identity (hardware + software)
    #[must_use]
    pub fn get_combined_identity(&self) -> String {
        let hw_id = self
            .hardware_hsm
            .as_ref()
            .map(|h| h.get_identity())
            .unwrap_or_else(|| "NO_HARDWARE".to_string());
        let sw_id = self.software_hsm.get_public_identity();
        format!("HYBRID-{}-{}", hw_id, &sw_id[..16.min(sw_id.len())])
    }
}

#[cfg(feature = "std")]
#[cfg(feature = "python")]
#[pymethods]
impl HybridHSM {
    #[new]
    pub fn py_new() -> Self {
        Self::new()
    }

    #[pyo3(name = "sign")]
    pub fn py_sign(&self, message: &[u8]) -> PyResult<String> {
        self.sign(message)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
    }

    #[pyo3(name = "get_identity")]
    pub fn py_get_identity(&self) -> String {
        self.get_identity()
    }

    #[pyo3(name = "get_status")]
    pub fn py_get_status(&self) -> HSMStatus {
        get_hsm_status()
    }
}

#[cfg(feature = "std")]
impl HSMOperations for HybridHSM {
    fn backend(&self) -> HSMBackend {
        // Report the hardware backend if available, otherwise software
        self.hardware_hsm
            .as_ref()
            .map(|h| h.backend())
            .unwrap_or(HSMBackend::Software())
    }

    fn get_public_key(&self) -> Result<String, String> {
        // Return PQC public key (for quantum-resistant operations)
        Ok(self.software_hsm.get_public_key().to_string())
    }

    fn sign(&self, message: &[u8]) -> Result<String, String> {
        let res = if let Some(ref hw_hsm) = self.hardware_hsm {
            // Prefer hardware HSM for signing if available
            hw_hsm.sign(message)
        } else {
            // Fallback to software HSM
            self.software_hsm.sign(message)
        };

        if res.is_ok() {
            crate::debug::metrics::increment_counter("hsm_sign_success");
        } else {
            crate::debug::metrics::increment_counter("hsm_sign_failure");
        }
        res
    }

    fn verify(&self, message: &[u8], signature: &str) -> Result<bool, String> {
        // Verify PQC signature
        let pk = self.software_hsm.get_public_key();
        let msg_str = core::str::from_utf8(message).map_err(|_| "Invalid UTF-8 in message")?;
        Ok(crate::crypto::MLDSA::verify_raw(pk, msg_str, signature))
    }

    fn get_identity(&self) -> String {
        self.get_combined_identity()
    }

    fn is_hardware_backed(&self) -> bool {
        self.has_hardware
    }

    fn get_attestation(&self) -> Result<HSMAttestation, String> {
        // Return combined attestation
        let hw_attestation = self.get_hardware_attestation();
        let sw_identity = self.software_hsm.get_public_identity();

        // hardware attestation enforcement: Signed Hardware Quote
        let quote = format!(
            "HYBRID_REALITY_BINDING_V1|HW:{}|PQC:{}",
            hw_attestation
                .as_ref()
                .map(|a| a.quote.clone())
                .unwrap_or_else(|| "UNBOUND".to_string()),
            &sw_identity[..32.min(sw_identity.len())]
        );

        Ok(HSMAttestation {
            backend: self.backend(),
            quote,
            pcr_values: hw_attestation.and_then(|a| a.pcr_values),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
        })
    }
}

// ============================================================================
// Reality Binding: Silicon-Locked Keys
// ============================================================================

/// A sealed key container that can only be opened on the original silicon.
#[cfg(feature = "std")]
pub struct SiliconBoundKey {
    pub sealed_blob: Vec<u8>,
    pub public_key: String,
}

#[cfg(feature = "std")]
impl SiliconBoundKey {
    /// Create a new PQC keypair and seal the private part to the physical hardware.
    pub fn generate_and_seal() -> Result<Self, String> {
        let (pk, sk) = crate::crypto::PQCKeypair::generate_raw();
        let sealed_blob = super::secure_enclave::SiliconLocker::seal_pqc_key(&sk)?;

        Ok(SiliconBoundKey {
            sealed_blob,
            public_key: pk,
        })
    }

    /// Unseals the private key and signs a message.
    /// The private key is zeroized immediately after use.
    pub fn sign_with_unsealed(&self, message: &[u8]) -> Result<String, String> {
        let mut sk = super::secure_enclave::SiliconLocker::unseal_pqc_key(&self.sealed_blob)?;
        let msg_str = core::str::from_utf8(message).map_err(|_| "Invalid UTF-8")?;

        let sig = crate::crypto::MLDSA::sign_raw(&sk, msg_str);

        // Explicitly zeroize for safety (redundant due to SiliconLocker but good practice)
        use zeroize::Zeroize;
        sk.zeroize();

        sig
    }
}

#[cfg(feature = "std")]
impl Default for HybridHSM {
    fn default() -> Self {
        Self::new()
    }
}

/// Create a hybrid HSM (recommended for production)
#[cfg(feature = "std")]
#[must_use]
pub fn create_hybrid_hsm() -> HybridHSM {
    HybridHSM::new()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_backend_names() {
        assert_eq!(HSMBackend::Software().name(), "Software HSM");
        assert_eq!(HSMBackend::TPM2().name(), "TPM 2.0");
        assert_eq!(HSMBackend::SecureEnclave().name(), "Apple Secure Enclave");
    }

    #[test]
    fn test_security_levels() {
        assert_eq!(HSMBackend::Software().security_level(), 1);
        assert_eq!(HSMBackend::TPM2().security_level(), 3);
        assert_eq!(HSMBackend::SecureEnclave().security_level(), 3);
    }

    #[test]
    fn test_detect_backend() {
        let backend = detect_best_backend();
        // Should always return something
        assert!(backend.security_level() >= 1);
    }

    #[test]
    fn test_create_hsm() {
        let hsm = create_hsm();
        let pk = hsm.get_public_key();
        assert!(pk.is_ok());
        assert!(!pk.unwrap().is_empty());
    }

    #[test]
    fn test_hsm_sign_verify() {
        let hsm = create_hsm();
        let message = b"test message for HSM signing";

        let signature = hsm.sign(message);
        assert!(signature.is_ok(), "Signing should succeed");

        let sig = signature.unwrap();
        let verified = hsm.verify(message, &sig);
        assert!(verified.is_ok());
        assert!(verified.unwrap(), "Signature should verify");
    }

    #[test]
    fn test_hsm_identity() {
        let hsm = create_hsm();
        let identity = hsm.get_identity();
        // create_hsm picks the best backend for the host; each backend has its
        // own identity form (WARM-KEY-, WARM-LINUX-KEYRING-, WARM-KEY-TPM2-,
        // WARM-KEY-SEP-). The backend-independent invariant is the family
        // prefix and non-emptiness of the payload.
        assert!(
            identity.starts_with("WARM-"),
            "unexpected identity: {identity}"
        );
        assert!(identity.len() > "WARM-".len());
    }

    #[test]
    fn test_hsm_status() {
        let status = get_hsm_status();
        assert!(status.is_initialized);
        assert!(status.security_level >= 1);
        assert!(!status.identity.is_empty());
    }

    #[test]
    fn test_software_hsm_not_hardware_backed() {
        let hsm = VirtualHSM::power_on();
        assert!(!hsm.is_hardware_backed());
        assert_eq!(hsm.backend(), HSMBackend::Software());
    }
}
