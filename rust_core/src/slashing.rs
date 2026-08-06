//! Slashing Engine for Byzantine Fault Detection and Penalization.
//!
//! Collective Decision Protocol
//!
//! This module implements slashing for:
//! - Policy violations
//! - Byzantine voting behavior
//! - Invalid ZK proofs
//! - Double signing
//! - View change manipulation

#[cfg(not(feature = "std"))]
use alloc::collections::BTreeSet;
#[cfg(not(feature = "std"))]
use alloc::format; // For format! macro
#[cfg(not(feature = "std"))]
use alloc::string::{String, ToString}; // For String and ToString trait
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;
#[cfg(feature = "python")]
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

/// Violation types that trigger slashing
#[cfg_attr(feature = "python", pyclass(eq))]
#[derive(
    Debug,
    Serialize,
    Deserialize,
    Clone,
    PartialEq,
    Eq,
    borsh::BorshSerialize,
    borsh::BorshDeserialize,
)]
#[non_exhaustive]
pub enum ViolationType {
    /// General policy violation
    PolicyViolation,
    /// Double voting in same round
    DoubleVoting,
    /// Invalid signature on vote/proposal
    InvalidSignature,
    /// Invalid ZK proof
    InvalidZKProof,
    /// Conflicting view change messages
    ConflictingViewChange,
    /// Task completion fraud (Multi-Agent)
    TaskCompletionFraud,
    /// Attestation forgery
    AttestationForgery,
    /// Timeout or liveness failure
    LivenessFailure,
}

#[cfg_attr(feature = "python", pyclass(eq))]
#[derive(
    Debug, Serialize, Deserialize, Clone, PartialEq, borsh::BorshSerialize, borsh::BorshDeserialize,
)]
#[non_exhaustive]
pub enum Penalty {
    /// State lock (freeze all operations)
    StateLock(),
    /// Burn staked tokens
    EconomicBurn(u64),
    /// Remove from validator set
    IdentityIsolation(),
    /// Reputation reduction
    ReputationSlash(u32),
    /// Temporary suspension (epochs)
    TemporarySuspension(u32),
    /// Economic Burn AND State Lock (Total Isolation)
    TotalIsolation(u64),
}

/// Evidence witness for a slashing event.
/// Contains the cryptographic proofs of a Byzantine violation.
#[derive(Debug, Serialize, Deserialize, Clone, borsh::BorshSerialize, borsh::BorshDeserialize)]
pub struct SlashingWitness {
    pub violation: crate::consensus::byzantine::ByzantineViolation,
    /// ZK-Proof (Groth16/PLONK) of the violation.
    /// Proves that the actor signed two different values for the same slot.
    pub zk_proof: Vec<u8>,
}

/// Cryptographic proof of a violation
/// Contains evidence that can be verified before slashing
#[derive(Debug, Serialize, Deserialize, Clone, borsh::BorshSerialize, borsh::BorshDeserialize)]
pub struct ViolationProof {
    /// Type of violation
    pub violation_type: ViolationType,
    /// SHA3-256 hash of the evidence (conflicting votes, invalid proof, etc.)
    pub evidence_hash: [u8; 32],
    /// ML-DSA-65 signature from the reporter
    pub reporter_signature: Vec<u8>,
    /// Timestamp of the violation (seconds since UNIX epoch)
    pub timestamp: u64,
    /// Public key of the reporter (hex-encoded ML-DSA-65)
    pub reporter_pubkey: String,
    /// Raw evidence data (e.g., conflicting vote hashes, ZK proof bytes)
    pub raw_evidence: Vec<u8>,
}

/// Error types for proof verification
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SlashingError {
    /// Evidence hash mismatch
    InvalidEvidenceHash,
    /// Reporter signature verification failed
    InvalidReporterSignature,
    /// Timestamp is too old or in the future
    InvalidTimestamp,
    /// Evidence data is malformed
    MalformedEvidence,
    /// Proof verification failed
    ProofVerificationFailed(String),
}

#[cfg_attr(feature = "python", pyclass)]
#[derive(Debug, Serialize, Deserialize, Clone, borsh::BorshSerialize, borsh::BorshDeserialize)]
pub struct SlashingVerdict {
    pub reason: String,
    pub penalty: Penalty,
    pub actor: String,
    /// Violation type for categorization
    pub violation_type: Option<ViolationType>,
    /// Evidence hash (e.g., conflicting vote hashes)
    pub evidence_hash: Option<String>,
    /// Verifiable proof of the verdict
    pub witness: Option<SlashingWitness>,
    /// Timestamp of violation
    pub timestamp: u64,
}

#[cfg(feature = "python")]
#[pymethods]
impl SlashingVerdict {
    #[getter]
    fn reason(&self) -> String {
        self.reason.clone()
    }

    #[getter]
    fn penalty(&self) -> Penalty {
        self.penalty.clone()
    }

    #[getter]
    fn actor(&self) -> String {
        self.actor.clone()
    }

    #[getter]
    fn timestamp(&self) -> u64 {
        self.timestamp
    }

    /// Get evidence hash
    #[getter]
    fn evidence_hash(&self) -> Option<String> {
        self.evidence_hash.clone()
    }

    /// Get violation type as string
    #[getter]
    fn violation_type_str(&self) -> Option<String> {
        self.violation_type.as_ref().map(|v| format!("{:?}", v))
    }
}

/// Slashing configuration
#[derive(Debug, Clone)]
pub struct SlashingConfig {
    /// Burn amount for double voting
    pub double_vote_burn: u64,
    /// Burn amount for invalid ZK proof
    pub invalid_zk_burn: u64,
    /// Reputation slash for task fraud
    pub task_fraud_reputation_slash: u32,
    /// Suspension epochs for liveness failure
    pub liveness_suspension_epochs: u32,
    /// Burn amount for invalid signature
    pub invalid_signature_burn: u64,
}

impl Default for SlashingConfig {
    fn default() -> Self {
        Self {
            double_vote_burn: 1000,
            invalid_zk_burn: 500,
            task_fraud_reputation_slash: 50,
            liveness_suspension_epochs: 10,
            invalid_signature_burn: 5000, // Harsh penalty for forgery
        }
    }
}

#[cfg_attr(feature = "python", pyclass)]
#[derive(Debug, Clone)]
pub struct SlashingEngine {
    /// Slashing configuration
    config: SlashingConfig,
    /// Slashed actors (to prevent double-slashing)
    #[cfg(feature = "std")]
    slashed_actors: std::collections::HashSet<String>,
    #[cfg(not(feature = "std"))]
    #[cfg(not(feature = "std"))]
    slashed_actors: BTreeSet<String>,
}

impl Default for SlashingEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl SlashingEngine {
    #[must_use]
    pub fn new() -> Self {
        Self {
            config: SlashingConfig::default(),
            #[cfg(feature = "std")]
            slashed_actors: std::collections::HashSet::new(),
            #[cfg(not(feature = "std"))]
            slashed_actors: BTreeSet::new(),
        }
    }

    /// Create with custom configuration
    #[must_use]
    pub fn with_config(config: SlashingConfig) -> Self {
        Self {
            config,
            #[cfg(feature = "std")]
            slashed_actors: std::collections::HashSet::new(),
            #[cfg(not(feature = "std"))]
            slashed_actors: BTreeSet::new(),
        }
    }

    /// Get current timestamp (seconds since epoch)
    fn current_timestamp() -> u64 {
        #[cfg(feature = "std")]
        {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0)
        }
        #[cfg(not(feature = "std"))]
        {
            0 // Mocked for bare-metal
        }
    }

    /// [DEPRECATED - ] Use evaluate_violation_with_proof instead.
    /// This function lacks cryptographic evidence verification and should not be used
    /// for production slashing decisions.
    #[deprecated(
        since = "0.9.0",
        note = "Use evaluate_violation_with_proof for cryptographic evidence verification"
    )]
    #[must_use]
    pub fn evaluate_violation_raw(&self, actor: &str, severity: f64) -> Option<SlashingVerdict> {
        if severity > 0.95 {
            Some(SlashingVerdict {
                reason: "Critical Policy Violation detected in ACT Engine".to_string(),
                penalty: Penalty::StateLock(),
                actor: actor.to_string(),
                violation_type: Some(ViolationType::PolicyViolation),
                evidence_hash: None,
                witness: None,
                timestamp: Self::current_timestamp(),
            })
        } else if severity > 0.80 {
            Some(SlashingVerdict {
                reason: "Suspicious Economic Pattern".to_string(),
                penalty: Penalty::EconomicBurn(100),
                actor: actor.to_string(),
                violation_type: Some(ViolationType::PolicyViolation),
                evidence_hash: None,
                witness: None,
                timestamp: Self::current_timestamp(),
            })
        } else {
            None
        }
    }

    /// Verify cryptographic proof of a violation
    fn verify_proof(&self, proof: &ViolationProof) -> Result<(), SlashingError> {
        use sha3::{Digest, Sha3_256};

        // 1. Verify evidence hash matches raw evidence
        let mut hasher = Sha3_256::new();
        hasher.update(&proof.raw_evidence);
        let computed_hash: [u8; 32] = hasher.finalize().into();

        if computed_hash != proof.evidence_hash {
            return Err(SlashingError::InvalidEvidenceHash);
        }

        // 2. Verify timestamp (must be within 1 hour of current time)
        let current_time = Self::current_timestamp();
        let time_diff = if proof.timestamp > current_time {
            proof.timestamp - current_time
        } else {
            current_time - proof.timestamp
        };

        if time_diff > 3600 {
            // 1 hour window
            return Err(SlashingError::InvalidTimestamp);
        }

        // 3. Verify reporter signature using ML-DSA-65
        // Construct the signed message: violation_type || evidence_hash || timestamp
        let message = format!(
            "{:?}||{}||{}",
            proof.violation_type,
            hex::encode(proof.evidence_hash),
            proof.timestamp
        );

        let signature_hex = hex::encode(&proof.reporter_signature);
        let is_valid =
            crate::crypto::MLDSA::verify_raw(&proof.reporter_pubkey, &message, &signature_hex);

        if !is_valid {
            return Err(SlashingError::InvalidReporterSignature);
        }

        Ok(())
    }

    /// Evaluate violation with cryptographic proof verification
    ///
    /// This is the secure version that requires:
    /// - Cryptographic evidence (hashed and signed)
    /// - Reporter signature verification (ML-DSA-65)
    /// - Timestamp validation
    ///
    /// Returns Ok(Some(verdict)) if violation is proven and should be slashed
    /// Returns Ok(None) if violation is not severe enough
    /// Returns Err if proof verification fails
    pub fn evaluate_violation_with_proof(
        &self,
        actor: &str,
        proof: &ViolationProof,
    ) -> Result<Option<SlashingVerdict>, SlashingError> {
        // 1. Verify the cryptographic proof
        self.verify_proof(proof)?;

        // 2. Calculate severity based on violation type and evidence
        let severity = match proof.violation_type {
            ViolationType::PolicyViolation => {
                // Extract severity from raw evidence (first 8 bytes as f64)
                if proof.raw_evidence.len() < 8 {
                    return Err(SlashingError::MalformedEvidence);
                }
                let severity_bytes: [u8; 8] = proof.raw_evidence[..8]
                    .try_into()
                    .map_err(|_| SlashingError::MalformedEvidence)?;
                f64::from_le_bytes(severity_bytes)
            }
            ViolationType::DoubleVoting => 1.0, // Always critical
            ViolationType::InvalidSignature => 1.0, // Always critical
            ViolationType::InvalidZKProof => 0.9, // High severity
            ViolationType::AttestationForgery => 1.0, // Always critical
            ViolationType::ConflictingViewChange => 0.95, // Critical
            ViolationType::TaskCompletionFraud => 0.85, // High but not critical
            ViolationType::LivenessFailure => 0.70, // Medium severity
        };

        // 3. Determine penalty based on verified severity
        let verdict = if severity > 0.95 {
            Some(SlashingVerdict {
                reason: format!(
                    "Critical {} violation with cryptographic proof",
                    match proof.violation_type {
                        ViolationType::PolicyViolation => "policy",
                        ViolationType::DoubleVoting => "double voting",
                        ViolationType::InvalidSignature => "signature",
                        ViolationType::InvalidZKProof => "ZK proof",
                        ViolationType::AttestationForgery => "attestation",
                        ViolationType::ConflictingViewChange => "view change",
                        ViolationType::TaskCompletionFraud => "task fraud",
                        ViolationType::LivenessFailure => "liveness",
                    }
                ),
                penalty: match proof.violation_type {
                    ViolationType::InvalidSignature | ViolationType::AttestationForgery => {
                        Penalty::TotalIsolation(self.config.invalid_signature_burn)
                    }
                    _ => Penalty::StateLock(),
                },
                actor: actor.to_string(),
                violation_type: Some(proof.violation_type.clone()),
                evidence_hash: Some(hex::encode(proof.evidence_hash)),
                witness: None,
                timestamp: proof.timestamp,
            })
        } else if severity > 0.80 {
            Some(SlashingVerdict {
                reason: format!(
                    "Suspicious {} pattern with cryptographic proof",
                    match proof.violation_type {
                        ViolationType::PolicyViolation => "policy",
                        ViolationType::DoubleVoting => "voting",
                        ViolationType::InvalidSignature => "signature",
                        ViolationType::InvalidZKProof => "ZK proof",
                        ViolationType::AttestationForgery => "attestation",
                        ViolationType::ConflictingViewChange => "view change",
                        ViolationType::TaskCompletionFraud => "task fraud",
                        ViolationType::LivenessFailure => "liveness",
                    }
                ),
                penalty: match proof.violation_type {
                    ViolationType::DoubleVoting => {
                        Penalty::EconomicBurn(self.config.double_vote_burn)
                    }
                    ViolationType::InvalidZKProof => {
                        Penalty::EconomicBurn(self.config.invalid_zk_burn)
                    }
                    ViolationType::TaskCompletionFraud => {
                        Penalty::ReputationSlash(self.config.task_fraud_reputation_slash)
                    }
                    _ => Penalty::EconomicBurn(100),
                },
                actor: actor.to_string(),
                violation_type: Some(proof.violation_type.clone()),
                evidence_hash: Some(hex::encode(proof.evidence_hash)),
                witness: None,
                timestamp: proof.timestamp,
            })
        } else {
            None
        };

        Ok(verdict)
    }

    /// Evaluate Byzantine voting violation
    #[must_use]
    pub fn evaluate_double_vote(
        &self,
        actor: &str,
        vote_hash_1: &str,
        vote_hash_2: &str,
    ) -> SlashingVerdict {
        use sha3::{Digest, Sha3_256};

        // Compute evidence hash
        let mut hasher = Sha3_256::new();
        hasher.update(vote_hash_1.as_bytes());
        hasher.update(vote_hash_2.as_bytes());
        let evidence = hex::encode(hasher.finalize());

        SlashingVerdict {
            reason: format!(
                "Double voting detected: conflicting votes {} and {}",
                &vote_hash_1[..8.min(vote_hash_1.len())],
                &vote_hash_2[..8.min(vote_hash_2.len())]
            ),
            penalty: Penalty::EconomicBurn(self.config.double_vote_burn),
            actor: actor.to_string(),
            violation_type: Some(ViolationType::DoubleVoting),
            evidence_hash: Some(evidence),
            witness: None,
            timestamp: Self::current_timestamp(),
        }
    }

    /// Evaluate invalid ZK proof
    #[must_use]
    pub fn evaluate_invalid_zk_proof(&self, actor: &str, proof_hash: &str) -> SlashingVerdict {
        SlashingVerdict {
            reason: "Invalid ZK proof submitted".to_string(),
            penalty: Penalty::EconomicBurn(self.config.invalid_zk_burn),
            actor: actor.to_string(),
            violation_type: Some(ViolationType::InvalidZKProof),
            evidence_hash: Some(proof_hash.to_string()),
            witness: None,
            timestamp: Self::current_timestamp(),
        }
    }

    /// Evaluate invalid signature (PQC)
    #[must_use]
    pub fn evaluate_invalid_signature(&self, actor: &str, tx_id: &str) -> SlashingVerdict {
        SlashingVerdict {
            reason: "Invalid ML-DSA-65 signature on transaction: Cryptographic Identity Mismatch"
                .to_string(),
            // Total Isolation (Burn + Lock)
            penalty: Penalty::TotalIsolation(self.config.invalid_signature_burn),
            actor: actor.to_string(),
            violation_type: Some(ViolationType::InvalidSignature),
            evidence_hash: Some(tx_id.to_string()),
            witness: None,
            timestamp: Self::current_timestamp(),
        }
    }

    /// Evaluate task completion fraud
    #[must_use]
    pub fn evaluate_task_fraud(&self, actor: &str, task_id: &str) -> SlashingVerdict {
        SlashingVerdict {
            reason: format!("Task completion fraud for task {}", task_id),
            penalty: Penalty::ReputationSlash(self.config.task_fraud_reputation_slash),
            actor: actor.to_string(),
            violation_type: Some(ViolationType::TaskCompletionFraud),
            evidence_hash: Some(task_id.to_string()),
            witness: None,
            timestamp: Self::current_timestamp(),
        }
    }

    /// Evaluate liveness failure (timeout)
    #[must_use]
    pub fn evaluate_liveness_failure(&self, actor: &str, context: &str) -> SlashingVerdict {
        SlashingVerdict {
            reason: format!("Liveness failure: {}", context),
            penalty: Penalty::TemporarySuspension(self.config.liveness_suspension_epochs),
            actor: actor.to_string(),
            violation_type: Some(ViolationType::LivenessFailure),
            evidence_hash: None,
            witness: None,
            timestamp: Self::current_timestamp(),
        }
    }

    /// Evaluate conflicting view change
    #[must_use]
    pub fn evaluate_conflicting_view_change(
        &self,
        actor: &str,
        view_1: u64,
        view_2: u64,
    ) -> SlashingVerdict {
        SlashingVerdict {
            reason: format!("Conflicting view change: views {} and {}", view_1, view_2),
            penalty: Penalty::StateLock(),
            actor: actor.to_string(),
            violation_type: Some(ViolationType::ConflictingViewChange),
            evidence_hash: Some(format!("{}:{}", view_1, view_2)),
            witness: None,
            timestamp: Self::current_timestamp(),
        }
    }

    /// Record a slashing (to prevent double-slashing)
    pub fn record_slash(&mut self, verdict: &SlashingVerdict) -> bool {
        let key = format!(
            "{}:{}",
            verdict.actor,
            verdict
                .violation_type
                .as_ref()
                .map(|v| format!("{:?}", v))
                .unwrap_or_default()
        );

        if self.slashed_actors.contains(&key) {
            return false; // Already slashed for this violation type
        }

        self.slashed_actors.insert(key);
        true
    }

    /// Check if actor was already slashed
    #[must_use]
    pub fn was_slashed(&self, actor: &str, violation_type: &ViolationType) -> bool {
        let key = format!("{}:{:?}", actor, violation_type);
        self.slashed_actors.contains(&key)
    }

    /// Get number of slashed actors
    #[must_use]
    pub fn slashed_count(&self) -> usize {
        self.slashed_actors.len()
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl SlashingEngine {
    #[new]
    fn py_new() -> Self {
        Self::new()
    }

    #[pyo3(name = "evaluate_violation")]
    fn evaluate_violation_py(&self, actor: &str, severity: f64) -> Option<SlashingVerdict> {
        self.evaluate_violation_raw(actor, severity)
    }

    /// Evaluate double voting violation
    #[pyo3(name = "evaluate_double_vote")]
    fn evaluate_double_vote_py(
        &self,
        actor: &str,
        vote_hash_1: &str,
        vote_hash_2: &str,
    ) -> SlashingVerdict {
        self.evaluate_double_vote(actor, vote_hash_1, vote_hash_2)
    }

    /// Evaluate invalid ZK proof
    #[pyo3(name = "evaluate_invalid_zk_proof")]
    fn evaluate_invalid_zk_proof_py(&self, actor: &str, proof_hash: &str) -> SlashingVerdict {
        self.evaluate_invalid_zk_proof(actor, proof_hash)
    }

    /// Evaluate task completion fraud
    #[pyo3(name = "evaluate_task_fraud")]
    fn evaluate_task_fraud_py(&self, actor: &str, task_id: &str) -> SlashingVerdict {
        self.evaluate_task_fraud(actor, task_id)
    }

    /// Evaluate liveness failure
    #[pyo3(name = "evaluate_liveness_failure")]
    fn evaluate_liveness_failure_py(&self, actor: &str, context: &str) -> SlashingVerdict {
        self.evaluate_liveness_failure(actor, context)
    }

    /// Evaluate conflicting view change
    #[pyo3(name = "evaluate_conflicting_view_change")]
    fn evaluate_conflicting_view_change_py(
        &self,
        actor: &str,
        view_1: u64,
        view_2: u64,
    ) -> SlashingVerdict {
        self.evaluate_conflicting_view_change(actor, view_1, view_2)
    }

    /// Get number of slashed actors
    #[pyo3(name = "slashed_count")]
    fn slashed_count_py(&self) -> usize {
        self.slashed_count()
    }

    /// Record a slash (prevents double-slashing)
    #[pyo3(name = "record_slash")]
    fn record_slash_py(&mut self, verdict: &SlashingVerdict) -> bool {
        self.record_slash(verdict)
    }

    /// Check if an actor was already slashed for a violation type
    #[pyo3(name = "was_slashed")]
    fn was_slashed_py(&self, actor: &str, violation_type: &str) -> bool {
        let key = format!("{}:{}", actor, violation_type);
        self.slashed_actors.contains(&key)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_penalty_equality() {
        assert_eq!(Penalty::StateLock(), Penalty::StateLock());
        assert_eq!(Penalty::EconomicBurn(100), Penalty::EconomicBurn(100));
        assert_eq!(Penalty::TotalIsolation(1000), Penalty::TotalIsolation(1000));
        assert_ne!(Penalty::EconomicBurn(100), Penalty::EconomicBurn(200));
        assert_ne!(Penalty::StateLock(), Penalty::EconomicBurn(100));
        assert_ne!(Penalty::TotalIsolation(1000), Penalty::EconomicBurn(1000));
    }

    #[test]
    fn test_slashing_engine_critical_violation() {
        let engine = SlashingEngine::new();

        // Severity > 0.95 = StateLock
        #[allow(deprecated)]
        let verdict = engine.evaluate_violation_raw("malicious_actor", 0.99);
        assert!(verdict.is_some());
        let v = verdict.unwrap();
        assert_eq!(v.penalty, Penalty::StateLock());
        assert_eq!(v.actor, "malicious_actor");
        assert!(v.reason.contains("Critical"));
    }

    #[test]
    fn test_slashing_engine_economic_burn() {
        let engine = SlashingEngine::new();

        // 0.80 < severity <= 0.95 = EconomicBurn
        #[allow(deprecated)]
        let verdict = engine.evaluate_violation_raw("suspicious_actor", 0.85);
        assert!(verdict.is_some());
        let v = verdict.unwrap();
        assert_eq!(v.penalty, Penalty::EconomicBurn(100));
        assert_eq!(v.actor, "suspicious_actor");
    }

    #[test]
    fn test_slashing_engine_no_penalty() {
        let engine = SlashingEngine::new();

        // severity <= 0.80 = No penalty
        #[allow(deprecated)]
        let verdict = engine.evaluate_violation_raw("normal_actor", 0.50);
        assert!(verdict.is_none());

        #[allow(deprecated)]
        let verdict = engine.evaluate_violation_raw("normal_actor", 0.80);
        assert!(verdict.is_none());
    }

    #[test]
    fn test_slashing_engine_invariants_full_range() {
        let engine = SlashingEngine::new();

        // Invariant 1: Severity <= 0.80 -> None
        for i in 0..=800 {
            let severity = i as f64 / 1000.0;
            assert!(
                {
                    #[allow(deprecated)]
                    engine.evaluate_violation_raw("actor", severity).is_none()
                },
                "Failed at severity {}",
                severity
            );
        }

        // Invariant 2: 0.80 < Severity <= 0.95 -> EconomicBurn(100)
        for i in 801..=950 {
            let severity = i as f64 / 1000.0;
            #[allow(deprecated)]
            let verdict = engine.evaluate_violation_raw("actor", severity);
            assert!(verdict.is_some(), "Failed at severity {}", severity);
            assert_eq!(
                verdict.unwrap().penalty,
                Penalty::EconomicBurn(100),
                "Failed at severity {}",
                severity
            );
        }

        // Invariant 3: Severity > 0.95 -> StateLock
        for i in 951..=1000 {
            let severity = i as f64 / 1000.0;
            #[allow(deprecated)]
            let verdict = engine.evaluate_violation_raw("actor", severity);
            assert!(verdict.is_some(), "Failed at severity {}", severity);
            assert_eq!(
                verdict.unwrap().penalty,
                Penalty::StateLock(),
                "Failed at severity {}",
                severity
            );
        }
    }

    #[test]
    fn test_slashing_verdict_clone() {
        let verdict = SlashingVerdict {
            reason: "Test reason".to_string(),
            penalty: Penalty::EconomicBurn(50),
            actor: "test_actor".to_string(),
            violation_type: Some(ViolationType::PolicyViolation),
            evidence_hash: Some("abc123".to_string()),
            witness: None,
            timestamp: 1234567890,
        };

        let cloned = verdict.clone();
        assert_eq!(cloned.reason, verdict.reason);
        assert_eq!(cloned.penalty, verdict.penalty);
        assert_eq!(cloned.actor, verdict.actor);
        assert_eq!(cloned.violation_type, verdict.violation_type);
        assert_eq!(cloned.evidence_hash, verdict.evidence_hash);
        assert_eq!(cloned.timestamp, verdict.timestamp);
    }

    #[test]
    fn test_double_vote_detection() {
        let engine = SlashingEngine::new();
        let verdict = engine.evaluate_double_vote(
            "byzantine_validator",
            "vote_hash_abc123",
            "vote_hash_def456",
        );

        assert_eq!(verdict.actor, "byzantine_validator");
        assert_eq!(verdict.penalty, Penalty::EconomicBurn(1000));
        assert_eq!(verdict.violation_type, Some(ViolationType::DoubleVoting));
        assert!(verdict.evidence_hash.is_some());
        assert!(verdict.reason.contains("Double voting"));
    }

    #[test]
    fn test_invalid_zk_proof_slashing() {
        let engine = SlashingEngine::new();
        let verdict = engine.evaluate_invalid_zk_proof("malicious_prover", "bad_proof_hash");

        assert_eq!(verdict.actor, "malicious_prover");
        assert_eq!(verdict.penalty, Penalty::EconomicBurn(500));
        assert_eq!(verdict.violation_type, Some(ViolationType::InvalidZKProof));
        assert_eq!(verdict.evidence_hash, Some("bad_proof_hash".to_string()));
    }

    #[test]
    fn test_task_fraud_reputation_slash() {
        let engine = SlashingEngine::new();
        let verdict = engine.evaluate_task_fraud("lazy_agent", "task_42");

        assert_eq!(verdict.actor, "lazy_agent");
        assert_eq!(verdict.penalty, Penalty::ReputationSlash(50));
        assert_eq!(
            verdict.violation_type,
            Some(ViolationType::TaskCompletionFraud)
        );
    }

    #[test]
    fn test_liveness_failure_suspension() {
        let engine = SlashingEngine::new();
        let verdict = engine.evaluate_liveness_failure("slow_validator", "missed 10 rounds");

        assert_eq!(verdict.actor, "slow_validator");
        assert_eq!(verdict.penalty, Penalty::TemporarySuspension(10));
        assert_eq!(verdict.violation_type, Some(ViolationType::LivenessFailure));
    }

    #[test]
    fn test_conflicting_view_change() {
        let engine = SlashingEngine::new();
        let verdict = engine.evaluate_conflicting_view_change("equivocator", 100, 101);

        assert_eq!(verdict.actor, "equivocator");
        assert_eq!(verdict.penalty, Penalty::StateLock());
        assert_eq!(
            verdict.violation_type,
            Some(ViolationType::ConflictingViewChange)
        );
        assert_eq!(verdict.evidence_hash, Some("100:101".to_string()));
    }

    #[test]
    fn test_double_slash_prevention() {
        let mut engine = SlashingEngine::new();

        let verdict1 = engine.evaluate_double_vote("bad_actor", "hash1", "hash2");
        assert!(engine.record_slash(&verdict1)); // First slash succeeds

        let verdict2 = engine.evaluate_double_vote("bad_actor", "hash3", "hash4");
        assert!(!engine.record_slash(&verdict2)); // Second slash for same type fails

        assert!(engine.was_slashed("bad_actor", &ViolationType::DoubleVoting));
        assert!(!engine.was_slashed("bad_actor", &ViolationType::InvalidZKProof));
    }

    #[test]
    fn test_slashed_count() {
        let mut engine = SlashingEngine::new();

        let v1 = engine.evaluate_double_vote("actor1", "h1", "h2");
        let v2 = engine.evaluate_invalid_zk_proof("actor2", "proof");
        let v3 = engine.evaluate_task_fraud("actor1", "task1");

        engine.record_slash(&v1);
        engine.record_slash(&v2);
        engine.record_slash(&v3);

        assert_eq!(engine.slashed_count(), 3);
    }

    #[test]
    fn test_custom_slashing_config() {
        let config = SlashingConfig {
            double_vote_burn: 5000,
            invalid_zk_burn: 2500,
            task_fraud_reputation_slash: 100,
            liveness_suspension_epochs: 20,
            invalid_signature_burn: 5000,
        };
        let engine = SlashingEngine::with_config(config);

        let verdict = engine.evaluate_double_vote("actor", "h1", "h2");
        assert_eq!(verdict.penalty, Penalty::EconomicBurn(5000));

        let verdict = engine.evaluate_liveness_failure("actor", "timeout");
        assert_eq!(verdict.penalty, Penalty::TemporarySuspension(20));
    }

    #[test]
    fn test_violation_type_equality() {
        assert_eq!(ViolationType::DoubleVoting, ViolationType::DoubleVoting);
        assert_ne!(ViolationType::DoubleVoting, ViolationType::InvalidZKProof);
    }

    #[test]
    fn test_proof_verification_success() {
        use sha3::{Digest, Sha3_256};

        let engine = SlashingEngine::new();

        // Generate reporter keypair
        let (reporter_pubkey, reporter_privkey) = crate::crypto::PQCKeypair::generate_raw();

        // Create evidence data (severity as f64 bytes)
        let severity = 0.99_f64;
        let raw_evidence = severity.to_le_bytes().to_vec();

        // Hash the evidence
        let mut hasher = Sha3_256::new();
        hasher.update(&raw_evidence);
        let evidence_hash: [u8; 32] = hasher.finalize().into();

        let timestamp = SlashingEngine::current_timestamp();

        // Sign the proof
        let message = format!(
            "{:?}||{}||{}",
            ViolationType::PolicyViolation,
            hex::encode(evidence_hash),
            timestamp
        );

        let signature_hex =
            crate::crypto::MLDSA::sign_raw(&reporter_privkey, &message).expect("Failed to sign");
        let reporter_signature = hex::decode(signature_hex).expect("Failed to decode signature");

        let proof = ViolationProof {
            violation_type: ViolationType::PolicyViolation,
            evidence_hash,
            reporter_signature,
            timestamp,
            reporter_pubkey,
            raw_evidence,
        };

        // Test verification
        let result = engine.evaluate_violation_with_proof("malicious_actor", &proof);
        assert!(result.is_ok());
        let verdict = result.unwrap();
        assert!(verdict.is_some());
        let v = verdict.unwrap();
        assert_eq!(v.actor, "malicious_actor");
        assert_eq!(v.penalty, Penalty::StateLock());
        assert!(v.reason.contains("Critical"));
        assert!(v.reason.contains("cryptographic proof"));
    }

    #[test]
    fn test_proof_verification_invalid_hash() {
        use sha3::{Digest, Sha3_256};

        let engine = SlashingEngine::new();

        let (reporter_pubkey, reporter_privkey) = crate::crypto::PQCKeypair::generate_raw();

        let severity = 0.99_f64;
        let raw_evidence = severity.to_le_bytes().to_vec();

        // Create WRONG hash (not matching raw_evidence)
        let mut hasher = Sha3_256::new();
        hasher.update(b"wrong_evidence");
        let evidence_hash: [u8; 32] = hasher.finalize().into();

        let timestamp = SlashingEngine::current_timestamp();

        let message = format!(
            "{:?}||{}||{}",
            ViolationType::PolicyViolation,
            hex::encode(evidence_hash),
            timestamp
        );

        let signature_hex =
            crate::crypto::MLDSA::sign_raw(&reporter_privkey, &message).expect("Failed to sign");
        let reporter_signature = hex::decode(signature_hex).expect("Failed to decode signature");

        let proof = ViolationProof {
            violation_type: ViolationType::PolicyViolation,
            evidence_hash,
            reporter_signature,
            timestamp,
            reporter_pubkey,
            raw_evidence, // This doesn't match the hash!
        };

        let result = engine.evaluate_violation_with_proof("actor", &proof);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), SlashingError::InvalidEvidenceHash);
    }

    #[test]
    fn test_proof_verification_invalid_signature() {
        use sha3::{Digest, Sha3_256};

        let engine = SlashingEngine::new();

        let (reporter_pubkey, _) = crate::crypto::PQCKeypair::generate_raw();
        let (_, wrong_privkey) = crate::crypto::PQCKeypair::generate_raw(); // Different keypair!

        let severity = 0.99_f64;
        let raw_evidence = severity.to_le_bytes().to_vec();

        let mut hasher = Sha3_256::new();
        hasher.update(&raw_evidence);
        let evidence_hash: [u8; 32] = hasher.finalize().into();

        let timestamp = SlashingEngine::current_timestamp();

        let message = format!(
            "{:?}||{}||{}",
            ViolationType::PolicyViolation,
            hex::encode(evidence_hash),
            timestamp
        );

        // Sign with WRONG key
        let signature_hex =
            crate::crypto::MLDSA::sign_raw(&wrong_privkey, &message).expect("Failed to sign");
        let reporter_signature = hex::decode(signature_hex).expect("Failed to decode signature");

        let proof = ViolationProof {
            violation_type: ViolationType::PolicyViolation,
            evidence_hash,
            reporter_signature,
            timestamp,
            reporter_pubkey, // Public key doesn't match the signing key!
            raw_evidence,
        };

        let result = engine.evaluate_violation_with_proof("actor", &proof);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), SlashingError::InvalidReporterSignature);
    }

    #[test]
    fn test_proof_verification_old_timestamp() {
        use sha3::{Digest, Sha3_256};

        let engine = SlashingEngine::new();

        let (reporter_pubkey, reporter_privkey) = crate::crypto::PQCKeypair::generate_raw();

        let severity = 0.99_f64;
        let raw_evidence = severity.to_le_bytes().to_vec();

        let mut hasher = Sha3_256::new();
        hasher.update(&raw_evidence);
        let evidence_hash: [u8; 32] = hasher.finalize().into();

        // Old timestamp (2 hours ago)
        let timestamp = SlashingEngine::current_timestamp() - 7200;

        let message = format!(
            "{:?}||{}||{}",
            ViolationType::PolicyViolation,
            hex::encode(evidence_hash),
            timestamp
        );

        let signature_hex =
            crate::crypto::MLDSA::sign_raw(&reporter_privkey, &message).expect("Failed to sign");
        let reporter_signature = hex::decode(signature_hex).expect("Failed to decode signature");

        let proof = ViolationProof {
            violation_type: ViolationType::PolicyViolation,
            evidence_hash,
            reporter_signature,
            timestamp,
            reporter_pubkey,
            raw_evidence,
        };

        let result = engine.evaluate_violation_with_proof("actor", &proof);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), SlashingError::InvalidTimestamp);
    }

    #[test]
    fn test_proof_verification_double_voting() {
        use sha3::{Digest, Sha3_256};

        let engine = SlashingEngine::new();

        let (reporter_pubkey, reporter_privkey) = crate::crypto::PQCKeypair::generate_raw();

        // Evidence: conflicting vote hashes
        let raw_evidence = b"vote_hash_abc123||vote_hash_def456".to_vec();

        let mut hasher = Sha3_256::new();
        hasher.update(&raw_evidence);
        let evidence_hash: [u8; 32] = hasher.finalize().into();

        let timestamp = SlashingEngine::current_timestamp();

        let message = format!(
            "{:?}||{}||{}",
            ViolationType::DoubleVoting,
            hex::encode(evidence_hash),
            timestamp
        );

        let signature_hex =
            crate::crypto::MLDSA::sign_raw(&reporter_privkey, &message).expect("Failed to sign");
        let reporter_signature = hex::decode(signature_hex).expect("Failed to decode signature");

        let proof = ViolationProof {
            violation_type: ViolationType::DoubleVoting,
            evidence_hash,
            reporter_signature,
            timestamp,
            reporter_pubkey,
            raw_evidence,
        };

        let result = engine.evaluate_violation_with_proof("byzantine_voter", &proof);
        assert!(result.is_ok());
        let verdict = result.unwrap();
        assert!(verdict.is_some());
        let v = verdict.unwrap();
        assert_eq!(v.actor, "byzantine_voter");
        assert_eq!(v.penalty, Penalty::StateLock()); // Double voting is critical (severity 1.0)
        assert!(v.reason.contains("double voting"));
    }

    #[test]
    fn test_proof_verification_malformed_evidence() {
        use sha3::{Digest, Sha3_256};

        let engine = SlashingEngine::new();

        let (reporter_pubkey, reporter_privkey) = crate::crypto::PQCKeypair::generate_raw();

        // Malformed evidence (PolicyViolation needs 8 bytes for f64 severity)
        let raw_evidence = vec![0x01, 0x02]; // Only 2 bytes!

        let mut hasher = Sha3_256::new();
        hasher.update(&raw_evidence);
        let evidence_hash: [u8; 32] = hasher.finalize().into();

        let timestamp = SlashingEngine::current_timestamp();

        let message = format!(
            "{:?}||{}||{}",
            ViolationType::PolicyViolation,
            hex::encode(evidence_hash),
            timestamp
        );

        let signature_hex =
            crate::crypto::MLDSA::sign_raw(&reporter_privkey, &message).expect("Failed to sign");
        let reporter_signature = hex::decode(signature_hex).expect("Failed to decode signature");

        let proof = ViolationProof {
            violation_type: ViolationType::PolicyViolation,
            evidence_hash,
            reporter_signature,
            timestamp,
            reporter_pubkey,
            raw_evidence,
        };

        let result = engine.evaluate_violation_with_proof("actor", &proof);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), SlashingError::MalformedEvidence);
    }
}
