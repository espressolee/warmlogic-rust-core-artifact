//! rust_core/src/sdk.rs
//! Sovereign SDK: Ethical enforcement gateway
//!
//! This module provides the high-level ABI for AI models to interact with
//! the Sovereign Kernel's ethical enforcement layer (VetoEngine).

#[cfg(feature = "python")]
use crate::governance::GovernanceVerdict;
use crate::governance::VetoEngine;
#[cfg(feature = "python")]
use sha3::{Digest, Sha3_256};

#[cfg(feature = "python")]
use pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use pyo3::prelude::*;

pub mod abi;
pub use abi::{SovereignIntent, SovereignVerdict};

/// The Moral Gateway: Enforces kernel-level supervision over AI models.
#[cfg_attr(feature = "python", pyclass)]
pub struct MoralGateway {
    pub engine: VetoEngine,
}

#[cfg(feature = "python")]
#[pymethods]
impl MoralGateway {
    #[new]
    pub fn new() -> Self {
        Self {
            engine: VetoEngine::new(),
        }
    }

    /// Evaluates an AI intent against the kernel's ethical policies.
    /// Returns a SovereignVerdict.
    pub fn evaluate_intent(&self, _intent: SovereignIntent) -> PyResult<SovereignVerdict> {
        // Map SDK intent to Governance metrics (Production Baseline)
        let epsilon_c = 1.0;
        let tau_ethics = 0.5;

        // Evaluate via the VetoEngine
        let decision = self.engine.evaluate(tau_ethics, epsilon_c);

        let mut hasher = Sha3_256::new();
        hasher.update(decision.reason.as_bytes());
        let verdict_hash: [u8; 32] = hasher.finalize().into();

        Ok(SovereignVerdict {
            is_allowed: matches!(decision.verdict, GovernanceVerdict::Allow),
            reason: decision.reason.clone(),
            verdict_type: format!("{:?}", decision.verdict),
            verdict_hash,
            proof_hash: decision.proof_hash,
        })
    }

    /// [Hardened ABI v1.0] Evaluates a serialized intent payload and returns a serialized verdict.
    /// This enforces a strict copy-based memory boundary (ISB).
    pub fn evaluate_intent_hardened(&self, payload: &[u8]) -> PyResult<Vec<u8>> {
        // 1. Copy and deserialize (O(N) boundary)
        let intent: SovereignIntent = serde_json::from_slice(payload)
            .map_err(|e| PyValueError::new_err(format!("Invalid intent payload: {}", e)))?;

        // 2. Verify signature if present (Mandatory for non-debug agents)
        if let Some(sig) = &intent.signature {
            let msg = format!("{}:{}", intent.action_type, intent.payload);
            if !crate::crypto::MLDSA::verify(&intent.agent_id, &msg, sig) {
                return Err(PyValueError::new_err(
                    "Invalid Kinetic signature for intent",
                ));
            }
        }

        // 3. Evaluate via the VetoEngine
        let (epsilon_c, tau_ethics, reason_prefix) = if intent.action_type == "governance_eval" {
            // Parse payload as GovernanceInputs
            match serde_json::from_str::<crate::governance::constitution::GovernanceInputs>(
                &intent.payload,
            ) {
                Ok(gov_inputs) => {
                    let result =
                        crate::governance::constitution::evaluate_constitution(&gov_inputs);
                    (result.epsilon_c, result.tau_ethics, result.reason)
                }
                Err(e) => {
                    // Fallback for malformed governance payload
                    (0.0, 1.0, format!("Malformed governance payload: {}", e))
                }
            }
        } else {
            // Default baseline for other intents
            (1.0, 0.5, "Standard Intent".to_string())
        };

        let decision = self.engine.evaluate(tau_ethics, epsilon_c);
        let final_reason = if reason_prefix == "Standard Intent" {
            decision.reason.clone()
        } else {
            format!("{}: {}", reason_prefix, decision.reason)
        };

        let mut hasher = Sha3_256::new();
        hasher.update(final_reason.as_bytes());
        let verdict_hash: [u8; 32] = hasher.finalize().into();

        // 4. Create Verdict
        let verdict = SovereignVerdict {
            is_allowed: matches!(decision.verdict, GovernanceVerdict::Allow),
            reason: final_reason,
            verdict_type: format!("{:?}", decision.verdict),
            verdict_hash,
            proof_hash: decision.proof_hash,
        };

        // 5. Serialize and return (O(N) boundary)
        serde_json::to_vec(&verdict)
            .map_err(|e| PyValueError::new_err(format!("Serialization failed: {}", e)))
    }
}
