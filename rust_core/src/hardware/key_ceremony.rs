//! Sovereign Key Ceremony
//!
//! This module provides the workflow for initializing a node's hardware root.
//! The Key Ceremony is a one-time event where the node's identities are
//! generated inside an HSM and anchored to the physical silicon.

use super::hsm::HSMOperations;
use super::pkcs11::{Pkcs11KeyType, Pkcs11Provider, Pkcs11Session};
use serde::{Deserialize, Serialize};

#[cfg(feature = "std")]
use std::time::{SystemTime, UNIX_EPOCH};

/// A shard provided by a Guardian during the Key Ceremony.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyCeremonyShard {
    pub guardian_id: String,
    pub shard: crate::security::threshold::SecretShard,
}

/// Workflow for the Sovereign Key Ceremony (Phase 17)
pub struct SovereignKeyCeremony {
    session: Pkcs11Session,
    shards: Vec<KeyCeremonyShard>,
    threshold: u32,
}

impl SovereignKeyCeremony {
    /// Start a new key ceremony with the specified provider and threshold.
    pub fn start(provider: Pkcs11Provider, pin: &str, threshold: u32) -> Result<Self, String> {
        let mut session = Pkcs11Session::new(provider);
        session
            .initialize()
            .map_err(|e| format!("Initialization failed: {}", e))?;
        session
            .login(pin)
            .map_err(|e| format!("Login failed: {}", e))?;

        Ok(SovereignKeyCeremony {
            session,
            shards: Vec::new(),
            threshold,
        })
    }

    /// Register a shard from a trusted Guardian.
    pub fn add_shard(&mut self, shard: KeyCeremonyShard) {
        println!(
            "🔐 [CEREMONY] Registering shard from Guardian: {}",
            shard.guardian_id
        );
        self.shards.push(shard);
    }

    /// Execute the ceremony: Generate the core identity keys once the threshold is met.
    pub fn execute(&mut self) -> Result<KeyCeremonyReport, String> {
        if (self.shards.len() as u32) < self.threshold {
            return Err(format!(
                "Threshold not met: Have {} shards, need {}",
                self.shards.len(),
                self.threshold
            ));
        }

        crate::debug::metrics::increment_counter("key_ceremony_started");

        // 0. Reconstruct the 'deterministic Seed' from Guardian Shards
        use crate::security::threshold::{SecretShard, ThresholdEngine};
        let raw_shards: Vec<SecretShard> = self.shards.iter().map(|s| s.shard.clone()).collect();
        let _divine_seed = ThresholdEngine::reconstruct_divine_seed(&raw_shards);

        println!("[CEREMONY] deterministic Seed Reconstructed. Unlocking Hardware Root...");

        // 1. Generate Governance Identity (ML-DSA-65) - Quantum Resistant Root
        let gov_key = self
            .session
            .generate_keypair("wl_governance_key", Pkcs11KeyType::MlDsa65, false)
            .map_err(|e| format!("Failed to generate governance key: {}", e))?;

        // 2. Generate Attestation Identity (ECDSA P-256) - Hardware Accelerated Proof
        let att_key = self
            .session
            .generate_keypair("wl_attestation_key", Pkcs11KeyType::EcdsaP256, false)
            .map_err(|e| format!("Failed to generate attestation key: {}", e))?;

        let identity = self.session.get_identity();

        #[cfg(feature = "std")]
        crate::debug::metrics::increment_counter("key_ceremony_completed");

        Ok(KeyCeremonyReport {
            identity,
            governance_key_label: gov_key.label,
            attestation_key_label: att_key.label,
            hardware_backed: self.session.is_hardware_backed(),
            guardian_count: self.shards.len() as u32,
            timestamp: {
                #[cfg(feature = "std")]
                {
                    SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_secs()
                }
                #[cfg(not(feature = "std"))]
                0
            },
        })
    }
}

/// Report of a completed key ceremony
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyCeremonyReport {
    pub identity: String,
    pub governance_key_label: String,
    pub attestation_key_label: String,
    pub hardware_backed: bool,
    pub guardian_count: u32,
    pub timestamp: u64,
}
