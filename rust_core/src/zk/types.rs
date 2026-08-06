//! ZK Type definitions for WarmLogic Groth16 system.
//!
//! Uses BLS12-381 curve (same as Ethereum 2.0, Zcash Sapling).

#[cfg(feature = "python")]
use crate::pyo3::prelude::*;
use ark_bls12_381::{Bls12_381, Fr as BlsFr, G1Projective, G2Projective};
use ark_groth16::{
    Groth16, PreparedVerifyingKey, Proof as Groth16Proof, ProvingKey as Groth16ProvingKey,
    VerifyingKey as Groth16VerifyingKey,
};
use ark_serialize::{CanonicalDeserialize, CanonicalSerialize};
use ark_std::vec::Vec;
use serde::{Deserialize, Serialize};
use zeroize::Zeroize;

/// Field element type (BLS12-381 scalar field)
pub type Fr = BlsFr;

/// G1 group element
pub type G1 = G1Projective;

/// G2 group element
pub type G2 = G2Projective;

/// Groth16 proof type
pub type Proof = Groth16Proof<Bls12_381>;

/// Proving key for Groth16
pub type ProvingKey = Groth16ProvingKey<Bls12_381>;

/// Verifying key for Groth16
pub type VerifyingKey = Groth16VerifyingKey<Bls12_381>;

/// Prepared verifying key (optimized for batch verification)
pub type PreparedVK = PreparedVerifyingKey<Bls12_381>;

/// SNARK system type
pub type SNARKSystem = Groth16<Bls12_381>;

/// Represents a Sigma-protocol or recursive-aggregation proof (Legacy/Simulation).
#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct ZKProof {
    pub challenge: [u8; 32],
    pub z1: [u8; 32],
    pub z2: [u8; 32],
    pub commitment: [u8; 32],
}

/// [Phase 20] Universal PLONK Proof Type
#[cfg(feature = "zk")]
pub type UniversalProof = dusk_plonk::prelude::Proof;

/// [Phase 20] Universal Public Parameters (SRS)
#[cfg(feature = "zk")]
pub type UniversalParams = dusk_plonk::prelude::PublicParameters;

/// Serialized proof for storage/transmission
#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerializedProof {
    /// Proof bytes (compressed)
    pub proof_bytes: Vec<u8>,
    /// Public inputs
    pub public_inputs: Vec<[u8; 32]>,
    /// Circuit identifier
    pub circuit_id: String,
    /// Timestamp
    pub timestamp: u64,
}

impl SerializedProof {
    /// Create from Groth16 proof and public inputs
    pub fn from_proof(
        proof: &Proof,
        public_inputs: &[Fr],
        circuit_id: &str,
    ) -> Result<Self, ark_serialize::SerializationError> {
        let mut proof_bytes = Vec::new();
        proof.serialize_compressed(&mut proof_bytes)?;

        let public_inputs_bytes: Vec<[u8; 32]> = public_inputs
            .iter()
            .map(|fr| {
                let mut bytes = [0u8; 32];
                let mut buf = Vec::new();
                fr.serialize_compressed(&mut buf).ok();
                if buf.len() >= 32 {
                    bytes.copy_from_slice(&buf[..32]);
                } else {
                    bytes[..buf.len()].copy_from_slice(&buf);
                }
                bytes
            })
            .collect();

        Ok(Self {
            proof_bytes,
            public_inputs: public_inputs_bytes,
            circuit_id: circuit_id.to_string(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        })
    }

    /// Deserialize back to Groth16 proof
    pub fn to_proof(&self) -> Result<Proof, ark_serialize::SerializationError> {
        // arkworks uses its own io traits from ark_std
        Proof::deserialize_compressed(&self.proof_bytes[..])
    }

    /// Get proof size in bytes
    #[must_use]
    pub fn size(&self) -> usize {
        self.proof_bytes.len()
    }

    /// Get hex representation of proof
    #[must_use]
    pub fn proof_hex(&self) -> String {
        hex::encode(&self.proof_bytes)
    }
}

/// Governance decision types that can be proven
/// Zeroize support for containing structs
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Zeroize)]
#[non_exhaustive]
#[repr(u8)]
pub enum DecisionType {
    /// Policy compliance check
    PolicyCompliance = 0,
    /// Veto authority exercise
    VetoAuthority = 1,
    /// Quorum threshold
    QuorumReached = 2,
    /// Regulatory compliance
    RegulatoryCompliance = 3,
    /// Identity attestation
    IdentityAttestation = 4,
}

impl DecisionType {
    /// Get circuit identifier for this decision type
    #[must_use]
    pub fn circuit_id(&self) -> &'static str {
        match self {
            Self::PolicyCompliance => "wl_policy_v1",
            Self::VetoAuthority => "wl_veto_v1",
            Self::QuorumReached => "wl_quorum_v1",
            Self::RegulatoryCompliance => "wl_compliance_v1",
            Self::IdentityAttestation => "wl_identity_v1",
        }
    }
}

/// Public inputs for governance proof
/// Zeroize support for GovernanceCircuit
#[derive(Debug, Clone, Serialize, Deserialize, Zeroize)]
pub struct GovernancePublicInputs {
    /// Hash of the decision being proven
    pub decision_hash: [u8; 32],
    /// Hash of the policy applied
    pub policy_hash: [u8; 32],
    /// Decision type
    pub decision_type: DecisionType,
    /// Epoch/timestamp of decision
    pub epoch: u64,
    /// Node ID that created the proof
    pub node_id: [u8; 32],
    /// Hash of the AI model weights (ZK-ML Attestation)
    pub model_hash: [u8; 32],
}

impl GovernancePublicInputs {
    /// Convert to field elements for circuit
    #[must_use]
    pub fn to_field_elements(&self) -> Vec<Fr> {
        #[allow(unused_imports)]
        use ark_ff::PrimeField;

        let mut elements = Vec::with_capacity(10);

        // Decision hash (split into two field elements for 256 bits)
        let (low, high) = split_hash_to_field_elements(&self.decision_hash);
        elements.push(low);
        elements.push(high);

        // Policy hash
        let (low, high) = split_hash_to_field_elements(&self.policy_hash);
        elements.push(low);
        elements.push(high);

        // Decision type
        elements.push(Fr::from(self.decision_type as u64));

        // Epoch
        elements.push(Fr::from(self.epoch));

        // Node ID (full 256 bits split into two field elements)
        let (node_id_low, node_id_high) = split_hash_to_field_elements(&self.node_id);
        elements.push(node_id_low);
        elements.push(node_id_high);

        // Model Hash
        let (m_low, m_high) = split_hash_to_field_elements(&self.model_hash);
        elements.push(m_low);
        elements.push(m_high);

        elements
    }
}

/// Split a 32-byte hash into two field elements
fn split_hash_to_field_elements(hash: &[u8; 32]) -> (Fr, Fr) {
    use ark_ff::PrimeField;

    // BLS12-381 scalar field is ~254 bits, so we split 256-bit hash
    let mut low_bytes = [0u8; 32];
    let mut high_bytes = [0u8; 32];

    low_bytes[..16].copy_from_slice(&hash[..16]);
    high_bytes[..16].copy_from_slice(&hash[16..]);

    let low = Fr::from_le_bytes_mod_order(&low_bytes);
    let high = Fr::from_le_bytes_mod_order(&high_bytes);

    (low, high)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ark_ff::UniformRand;
    use ark_std::test_rng;

    #[test]
    fn test_serialized_proof_roundtrip() {
        // This test requires a valid proof, which needs circuit setup
        // For now, just test the type definitions compile
        let _rng = test_rng();
        let _fr = Fr::rand(&mut test_rng());
    }

    #[test]
    fn test_decision_type_circuit_id() {
        assert_eq!(DecisionType::PolicyCompliance.circuit_id(), "wl_policy_v1");
        assert_eq!(DecisionType::VetoAuthority.circuit_id(), "wl_veto_v1");
    }

    #[test]
    fn test_public_inputs_to_field_elements() {
        let inputs = GovernancePublicInputs {
            decision_hash: [1u8; 32],
            policy_hash: [2u8; 32],
            decision_type: DecisionType::PolicyCompliance,
            epoch: 1000,
            node_id: [3u8; 32],
            model_hash: [1u8; 32],
        };

        let elements = inputs.to_field_elements();
        assert_eq!(elements.len(), 10); // 2 (decision) + 2 (policy) + 1 (type) + 1 (epoch) + 2 (node_id) + 2 (model) = 10
    }
}
