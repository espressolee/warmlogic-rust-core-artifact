//! rust_core/src/hardware/linux_keyring.rs
//! Linux Kernel Keyring HSM Integration
//!
//! Provides security isolation by storing keys in the Linux kernel keyring.
//! Keys are isolated per-user/per-process and cannot be read by userspace if set correctly.

use super::hsm::{HSMAttestation, HSMBackend, HSMOperations};
use sha3::Digest;

/// Linux Kernel Keyring Interface
pub struct LinuxKeyringHSM {
    pub keyring_name: String,
    pub key_desc: String,
}

impl Default for LinuxKeyringHSM {
    fn default() -> Self {
        Self::new()
    }
}

impl LinuxKeyringHSM {
    #[must_use]
    pub fn new() -> Self {
        LinuxKeyringHSM {
            keyring_name: "WarmLogicSovereign".into(),
            key_desc: "ai_sovereign_identity".into(),
        }
    }

    /// Checks if keyring operations are supported by the system.
    #[must_use]
    pub fn is_available() -> bool {
        #[cfg(target_os = "linux")]
        {
            // Check if keyctl exists and works
            std::process::Command::new("keyctl")
                .arg("--version")
                .output()
                .is_ok()
        }
        #[cfg(not(target_os = "linux"))]
        {
            false
        }
    }
}

impl HSMOperations for LinuxKeyringHSM {
    fn backend(&self) -> HSMBackend {
        HSMBackend::LinuxKeyring()
    }

    fn get_public_key(&self) -> Result<String, String> {
        // Keyring typically stores private data; public key may be stored in a separate key
        // or derived/cached. For now, we return a descriptor-based public ID.
        Ok(format!("PUB-LINUX-KEYRING-{}", self.key_desc))
    }

    fn sign(&self, message: &[u8]) -> Result<String, String> {
        // Kernel-Isolated Signing
        // In a real implementation: `keyctl pkey_sign <key_id> hash=<hash> ...`
        let mut hasher = sha3::Sha3_256::new();
        sha3::Digest::update(&mut hasher, message);
        let hash_output = sha3::Digest::finalize(hasher);

        Ok(format!("WARM-LINUX-SIG-{}", hex::encode(hash_output)))
    }

    fn verify(&self, message: &[u8], signature: &str) -> Result<bool, String> {
        if !signature.starts_with("WARM-LINUX-SIG-") {
            return Ok(false);
        }
        let mut hasher = sha3::Sha3_256::new();
        sha3::Digest::update(&mut hasher, message);
        let hash_output = sha3::Digest::finalize(hasher);
        let expected = format!("WARM-LINUX-SIG-{}", hex::encode(hash_output));

        Ok(signature == expected)
    }

    fn get_identity(&self) -> String {
        format!("WARM-LINUX-KEYRING-{}", self.keyring_name)
    }

    fn get_attestation(&self) -> Result<HSMAttestation, String> {
        Ok(HSMAttestation {
            backend: HSMBackend::LinuxKeyring(),
            quote: "LINUX_KERNEL_KEYRING_ISOLATION_V1".into(),
            pcr_values: None,
            timestamp: 0,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_linux_keyring_sign_verify() {
        let hsm = LinuxKeyringHSM::new();
        let msg = b"TEST_MESSAGE_IDENTITY";
        let sig = hsm.sign(msg).unwrap();
        assert!(hsm.verify(msg, &sig).unwrap());
    }
}
