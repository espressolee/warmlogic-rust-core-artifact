//! Python bindings for Groth16 ZK-SNARK system.
//!
//! Exposes governance proof generation and verification to Python.

#[cfg(feature = "python")]
use crate::pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use crate::pyo3::prelude::*;
#[cfg(feature = "python")]
use crate::pyo3::types::PyDict;
#[cfg(feature = "python")]
use crate::pyo3::Bound;

use super::prover::{Prover, TrustedSetup};
use super::transition::{KernelStateTransitionCircuit, TransitionPublicInputs};
use super::types::{
    DecisionType, GovernancePublicInputs, ProvingKey, SerializedProof, VerifyingKey,
};
use super::verifier::Verifier;
use super::GovernanceCircuit;

/// Python-accessible ZK Governance Prover
#[pyclass(name = "ZKGovernanceProver")]
pub struct PyZKGovernanceProver {
    proving_key: Option<ProvingKey>,
    verifying_key: Option<VerifyingKey>,
    circuit_id: String,
}

#[pymethods]
impl PyZKGovernanceProver {
    /// Create a new ZK prover with trusted setup
    #[new]
    #[must_use]
    pub fn new() -> Self {
        Self {
            proving_key: None,
            verifying_key: None,
            circuit_id: String::new(),
        }
    }

    /// Generate proving and verifying keys (trusted setup)
    /// Call this once before generating proofs
    pub fn setup(&mut self) -> PyResult<()> {
        // Create a template circuit for setup
        let template_inputs = GovernancePublicInputs {
            model_hash: [0u8; 32],
            decision_hash: [0u8; 32],
            policy_hash: [0u8; 32],
            decision_type: DecisionType::PolicyCompliance,
            epoch: 0,
            node_id: [0u8; 32],
        };

        let template_circuit = GovernanceCircuit::new(
            template_inputs,
            10,    // authority_level
            1,     // threshold
            1,     // approval_count
            false, // no veto
        );

        let (pk, vk) = TrustedSetup::generate_keys_dev(template_circuit)
            .map_err(|e| PyValueError::new_err(format!("Setup failed: {}", e)))?;

        self.proving_key = Some(pk);
        self.verifying_key = Some(vk);
        self.circuit_id = "wl_governance_v1".to_string();

        Ok(())
    }

    /// Generate a governance proof
    ///
    /// Args:
    ///     decision_hash: 32-byte hash of the decision
    ///     policy_hash: 32-byte hash of the policy
    ///     decision_type: One of "policy", "veto", "quorum", "compliance", "identity"
    ///     epoch: Timestamp/epoch of the decision
    ///     node_id: 32-byte node identifier
    ///     authority_level: Authority level (private witness)
    ///     threshold: Required approval threshold (private witness)
    ///     approval_count: Actual approvals received (private witness)
    ///     is_veto: Whether this is a veto action (private witness)
    ///
    /// Returns:
    ///     dict with proof_hex, public_inputs, circuit_id, timestamp
    #[pyo3(signature = (decision_hash, policy_hash, decision_type, epoch, node_id, authority_level, threshold, approval_count, is_veto=false))]
    #[allow(clippy::too_many_arguments)]
    pub fn prove<'py>(
        &self,
        py: Python<'py>,
        decision_hash: Vec<u8>,
        policy_hash: Vec<u8>,
        decision_type: &str,
        epoch: u64,
        node_id: Vec<u8>,
        authority_level: u8,
        threshold: u8,
        approval_count: u8,
        is_veto: bool,
    ) -> PyResult<Bound<'py, PyDict>> {
        let pk = self
            .proving_key
            .as_ref()
            .ok_or_else(|| PyValueError::new_err("Prover not initialized. Call setup() first."))?;

        // Convert inputs
        let decision_hash: [u8; 32] = decision_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("decision_hash must be 32 bytes"))?;
        let policy_hash: [u8; 32] = policy_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("policy_hash must be 32 bytes"))?;
        let node_id: [u8; 32] = node_id
            .try_into()
            .map_err(|_| PyValueError::new_err("node_id must be 32 bytes"))?;

        let dt = match decision_type {
            "policy" => DecisionType::PolicyCompliance,
            "veto" => DecisionType::VetoAuthority,
            "quorum" => DecisionType::QuorumReached,
            "compliance" => DecisionType::RegulatoryCompliance,
            "identity" => DecisionType::IdentityAttestation,
            _ => return Err(PyValueError::new_err("Invalid decision_type")),
        };

        let public_inputs = GovernancePublicInputs {
            model_hash: [0u8; 32],
            decision_hash,
            policy_hash,
            decision_type: dt,
            epoch,
            node_id,
        };

        let circuit = GovernanceCircuit::new(
            public_inputs.clone(),
            authority_level,
            threshold,
            approval_count,
            is_veto,
        );

        let (proof, inputs) = Prover::prove_governance(&circuit, pk)
            .map_err(|e| PyValueError::new_err(format!("Proof generation failed: {}", e)))?;

        let serialized = SerializedProof::from_proof(&proof, &inputs, &self.circuit_id)
            .map_err(|e| PyValueError::new_err(format!("Serialization failed: {}", e)))?;

        // Build result dict
        let result = PyDict::new_bound(py);
        result.set_item("proof_hex", serialized.proof_hex())?;
        result.set_item("proof_size", serialized.size())?;
        result.set_item("circuit_id", &serialized.circuit_id)?;
        result.set_item("timestamp", serialized.timestamp)?;
        result.set_item("decision_hash", hex::encode(decision_hash))?;
        result.set_item("policy_hash", hex::encode(policy_hash))?;

        Ok(result)
    }

    /// Verify a governance proof
    ///
    /// Args:
    ///     proof_hex: Hex-encoded proof bytes
    ///     decision_hash: 32-byte hash of the decision
    ///     policy_hash: 32-byte hash of the policy
    ///     decision_type: Decision type string
    ///     epoch: Timestamp/epoch
    ///     node_id: 32-byte node identifier
    ///
    /// Returns:
    ///     bool: True if proof is valid
    pub fn verify(
        &self,
        proof_hex: &str,
        decision_hash: Vec<u8>,
        policy_hash: Vec<u8>,
        decision_type: &str,
        epoch: u64,
        node_id: Vec<u8>,
    ) -> PyResult<bool> {
        let vk = self.verifying_key.as_ref().ok_or_else(|| {
            PyValueError::new_err("Verifier not initialized. Call setup() first.")
        })?;

        // Convert inputs
        let decision_hash: [u8; 32] = decision_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("decision_hash must be 32 bytes"))?;
        let policy_hash: [u8; 32] = policy_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("policy_hash must be 32 bytes"))?;
        let node_id: [u8; 32] = node_id
            .try_into()
            .map_err(|_| PyValueError::new_err("node_id must be 32 bytes"))?;

        let dt = match decision_type {
            "policy" => DecisionType::PolicyCompliance,
            "veto" => DecisionType::VetoAuthority,
            "quorum" => DecisionType::QuorumReached,
            "compliance" => DecisionType::RegulatoryCompliance,
            "identity" => DecisionType::IdentityAttestation,
            _ => return Err(PyValueError::new_err("Invalid decision_type")),
        };

        let public_inputs = GovernancePublicInputs {
            model_hash: [0u8; 32],
            decision_hash,
            policy_hash,
            decision_type: dt,
            epoch,
            node_id,
        };

        // Decode proof
        let proof_bytes = hex::decode(proof_hex)
            .map_err(|e| PyValueError::new_err(format!("Invalid proof hex: {}", e)))?;

        let serialized = SerializedProof {
            proof_bytes,
            public_inputs: vec![], // Will be reconstructed
            circuit_id: self.circuit_id.clone(),
            timestamp: 0,
        };

        let proof = serialized
            .to_proof()
            .map_err(|e| PyValueError::new_err(format!("Invalid proof: {}", e)))?;

        let inputs = public_inputs.to_field_elements();

        let valid = Verifier::verify(&proof, &inputs, vk)
            .map_err(|e| PyValueError::new_err(format!("Verification failed: {}", e)))?;

        Ok(valid)
    }

    /// Check if the prover is initialized
    #[must_use]
    pub fn is_ready(&self) -> bool {
        self.proving_key.is_some() && self.verifying_key.is_some()
    }

    /// Get the circuit ID
    #[must_use]
    pub fn get_circuit_id(&self) -> String {
        self.circuit_id.clone()
    }
}

impl Default for PyZKGovernanceProver {
    fn default() -> Self {
        Self::new()
    }
}

/// Python-accessible ZK Transition Prover
#[pyclass(name = "ZKTransitionProver")]
pub struct PyZKTransitionProver {
    proving_key: Option<ProvingKey>,
    verifying_key: Option<VerifyingKey>,
    circuit_id: String,
}

#[pymethods]
impl PyZKTransitionProver {
    /// Create a new ZK transition prover
    #[new]
    #[must_use]
    pub fn new() -> Self {
        Self {
            proving_key: None,
            verifying_key: None,
            circuit_id: String::new(),
        }
    }

    /// Generate proving and verifying keys for transitions
    pub fn setup(&mut self) -> PyResult<()> {
        let template_inputs = TransitionPublicInputs {
            pre_state_hash: [0u8; 32],
            post_state_hash: [0u8; 32],
            action_hash: [0u8; 32],
            epoch: 0,
            node_id: [0u8; 32],
            invariant_flags: 0b1111,
        };

        let circuit = KernelStateTransitionCircuit::new(template_inputs, 0, 0, 0, 0, true);

        let (pk, vk) = TrustedSetup::generate_keys_dev(circuit)
            .map_err(|e| PyValueError::new_err(format!("Setup failed: {}", e)))?;

        self.proving_key = Some(pk);
        self.verifying_key = Some(vk);
        self.circuit_id = KernelStateTransitionCircuit::CIRCUIT_ID.to_string();

        Ok(())
    }

    /// Generate a state transition proof
    #[pyo3(signature = (pre_state_hash, post_state_hash, action_hash, epoch, node_id, entropy_before, entropy_after, weight_delta, confidence_score, was_constitutional))]
    #[allow(clippy::too_many_arguments)]
    pub fn prove<'py>(
        &self,
        py: Python<'py>,
        pre_state_hash: Vec<u8>,
        post_state_hash: Vec<u8>,
        action_hash: Vec<u8>,
        epoch: u64,
        node_id: Vec<u8>,
        entropy_before: u64,
        entropy_after: u64,
        weight_delta: u64,
        confidence_score: u64,
        was_constitutional: bool,
    ) -> PyResult<Bound<'py, PyDict>> {
        let pk = self
            .proving_key
            .as_ref()
            .ok_or_else(|| PyValueError::new_err("Prover not initialized. Call setup() first."))?;

        let pre_state_hash: [u8; 32] = pre_state_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("pre_state_hash must be 32 bytes"))?;
        let post_state_hash: [u8; 32] = post_state_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("post_state_hash must be 32 bytes"))?;
        let action_hash: [u8; 32] = action_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("action_hash must be 32 bytes"))?;
        let node_id: [u8; 32] = node_id
            .try_into()
            .map_err(|_| PyValueError::new_err("node_id must be 32 bytes"))?;

        let public_inputs = TransitionPublicInputs {
            pre_state_hash,
            post_state_hash,
            action_hash,
            epoch,
            node_id,
            invariant_flags: 0b1111,
        };

        let circuit = KernelStateTransitionCircuit::new(
            public_inputs.clone(),
            entropy_before,
            entropy_after,
            weight_delta,
            confidence_score,
            was_constitutional,
        );

        let (proof, inputs) = Prover::prove(circuit, pk, public_inputs.to_field_elements())
            .map_err(|e| PyValueError::new_err(format!("Proof generation failed: {}", e)))?;

        let serialized = SerializedProof::from_proof(&proof, &inputs, &self.circuit_id)
            .map_err(|e| PyValueError::new_err(format!("Serialization failed: {}", e)))?;

        let result = PyDict::new_bound(py);
        result.set_item("proof_hex", serialized.proof_hex())?;
        result.set_item("circuit_id", &serialized.circuit_id)?;
        result.set_item("timestamp", serialized.timestamp)?;

        Ok(result)
    }

    /// Verify a state transition proof
    pub fn verify(
        &self,
        proof_hex: &str,
        pre_state_hash: Vec<u8>,
        post_state_hash: Vec<u8>,
        action_hash: Vec<u8>,
        epoch: u64,
        node_id: Vec<u8>,
    ) -> PyResult<bool> {
        let vk = self.verifying_key.as_ref().ok_or_else(|| {
            PyValueError::new_err("Verifier not initialized. Call setup() first.")
        })?;

        let pre_state_hash: [u8; 32] = pre_state_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("pre_state_hash must be 32 bytes"))?;
        let post_state_hash: [u8; 32] = post_state_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("post_state_hash must be 32 bytes"))?;
        let action_hash: [u8; 32] = action_hash
            .try_into()
            .map_err(|_| PyValueError::new_err("action_hash must be 32 bytes"))?;
        let node_id: [u8; 32] = node_id
            .try_into()
            .map_err(|_| PyValueError::new_err("node_id must be 32 bytes"))?;

        let public_inputs = TransitionPublicInputs {
            pre_state_hash,
            post_state_hash,
            action_hash,
            epoch,
            node_id,
            invariant_flags: 0b1111,
        };

        let proof_bytes = hex::decode(proof_hex)
            .map_err(|e| PyValueError::new_err(format!("Invalid proof hex: {}", e)))?;

        let serialized = SerializedProof {
            proof_bytes,
            public_inputs: vec![],
            circuit_id: self.circuit_id.clone(),
            timestamp: 0,
        };

        let proof = serialized
            .to_proof()
            .map_err(|e| PyValueError::new_err(format!("Invalid proof: {}", e)))?;

        let inputs = public_inputs.to_field_elements();

        let valid = Verifier::verify(&proof, &inputs, vk)
            .map_err(|e| PyValueError::new_err(format!("Verification failed: {}", e)))?;

        Ok(valid)
    }

    /// Check if the prover is ready
    #[must_use]
    pub fn is_ready(&self) -> bool {
        self.proving_key.is_some() && self.verifying_key.is_some()
    }

    /// Save keys to directory
    pub fn save_keys(&self, dir: &str) -> PyResult<()> {
        let pk = self
            .proving_key
            .as_ref()
            .ok_or_else(|| PyValueError::new_err("Proving key not found. Call setup() first."))?;
        let vk = self
            .verifying_key
            .as_ref()
            .ok_or_else(|| PyValueError::new_err("Verifying key not found. Call setup() first."))?;

        let path = std::path::Path::new(dir);
        if !path.exists() {
            std::fs::create_dir_all(path)
                .map_err(|e| PyValueError::new_err(format!("Failed to create directory: {}", e)))?;
        }

        super::prover::keys::save_proving_key(pk, &path.join("transition.pk"))
            .map_err(|e| PyValueError::new_err(format!("Failed to save PK: {}", e)))?;
        super::prover::keys::save_verifying_key(vk, &path.join("transition.vk"))
            .map_err(|e| PyValueError::new_err(format!("Failed to save VK: {}", e)))?;

        Ok(())
    }

    /// Load keys from directory
    pub fn load_keys(&mut self, dir: &str) -> PyResult<()> {
        let path = std::path::Path::new(dir);
        let pk = super::prover::keys::load_proving_key(&path.join("transition.pk"))
            .map_err(|e| PyValueError::new_err(format!("Failed to load PK: {}", e)))?;
        let vk = super::prover::keys::load_verifying_key(&path.join("transition.vk"))
            .map_err(|e| PyValueError::new_err(format!("Failed to load VK: {}", e)))?;

        self.proving_key = Some(pk);
        self.verifying_key = Some(vk);
        self.circuit_id = KernelStateTransitionCircuit::CIRCUIT_ID.to_string();

        Ok(())
    }

    /// Get the circuit ID
    #[must_use]
    pub fn get_circuit_id(&self) -> String {
        self.circuit_id.clone()
    }
}

#[pyclass(name = "ZKRecoveryProver")]
pub struct PyRecoveryProver {
    circuit_id: String,
}

#[pymethods]
impl PyRecoveryProver {
    #[new]
    #[must_use]
    pub fn new() -> Self {
        Self {
            circuit_id: super::recovery_circuit::StateSnapshotCircuit::CIRCUIT_ID.to_string(),
        }
    }

    /// Validates system state alignment via ZK witness check.
    /// Proves Version + HW Fingerprint + State Root consistency.
    pub fn verify_alignment(
        &self,
        epoch: u64,
        state_root: Vec<u8>,
        hardware_fingerprint: Vec<u8>,
        hsm_secret: Vec<u8>,
    ) -> PyResult<bool> {
        let state_root: [u8; 32] = state_root
            .try_into()
            .map_err(|_| PyValueError::new_err("state_root must be 32 bytes"))?;
        let hardware_fingerprint: [u8; 32] = hardware_fingerprint
            .try_into()
            .map_err(|_| PyValueError::new_err("hardware_fingerprint must be 32 bytes"))?;
        let hsm_secret: [u8; 32] = hsm_secret
            .try_into()
            .map_err(|_| PyValueError::new_err("hsm_secret must be 32 bytes"))?;

        let circuit = super::recovery_circuit::StateSnapshotCircuit::new(
            epoch,
            state_root,
            hardware_fingerprint,
            hsm_secret,
        );

        match circuit.validate_satisfiability() {
            Ok(_) => Ok(true),
            Err(e) => {
                println!("[ZK-RECOVERY] Alignment failed: {}", e);
                Ok(false)
            }
        }
    }

    #[must_use]
    pub fn get_circuit_id(&self) -> String {
        self.circuit_id.clone()
    }
}

impl Default for PyRecoveryProver {
    fn default() -> Self {
        Self::new()
    }
}

/// Check if ZK module is loaded (for debugging)
#[pyfunction]
#[must_use]
pub fn zk_module_loaded() -> bool {
    true
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_zk_governance_prover_initial_state() {
        let prover = PyZKGovernanceProver::new();
        assert!(!prover.is_ready());
        assert_eq!(prover.get_circuit_id(), "");
    }

    #[test]
    fn test_zk_transition_prover_initial_state() {
        let prover = PyZKTransitionProver::new();
        assert!(!prover.is_ready());
        assert_eq!(prover.get_circuit_id(), "");
    }

    #[cfg(feature = "zk")]
    #[test]
    fn test_zk_transition_prover_setup() {
        let mut prover = PyZKTransitionProver::new();
        // setup generates keys, which involves many ZK operations
        let _ = prover.setup();
        assert!(prover.is_ready());
        assert!(!prover.get_circuit_id().is_empty());
    }
}
