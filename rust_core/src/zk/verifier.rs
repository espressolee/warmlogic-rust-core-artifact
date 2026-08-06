//! Groth16 Verifier for WarmLogic ZK proofs.
//!
//! This module handles proof verification using the arkworks Groth16 implementation.

use ark_groth16::{Groth16, PreparedVerifyingKey};
use ark_snark::SNARK;

use super::error::{ZKError, ZKResult};
use super::types::{Fr, PreparedVK, Proof, SerializedProof, VerifyingKey};

/// Verifier for checking Groth16 proofs
pub struct Verifier;

impl Verifier {
    /// Verify a proof against public inputs and verifying key
    pub fn verify(
        proof: &Proof,
        public_inputs: &[Fr],
        verifying_key: &VerifyingKey,
    ) -> ZKResult<bool> {
        let result =
            Groth16::<ark_bls12_381::Bls12_381>::verify(verifying_key, public_inputs, proof)
                .map_err(|_e| ZKError::VerificationFailed)?;

        Ok(result)
    }

    /// Verify a proof with prepared verifying key (faster for repeated verification)
    pub fn verify_prepared(
        proof: &Proof,
        public_inputs: &[Fr],
        prepared_vk: &PreparedVK,
    ) -> ZKResult<bool> {
        let result = Groth16::<ark_bls12_381::Bls12_381>::verify_with_processed_vk(
            prepared_vk,
            public_inputs,
            proof,
        )
        .map_err(|_e| ZKError::VerificationFailed)?;

        Ok(result)
    }

    /// Verify a serialized proof
    pub fn verify_serialized(
        serialized: &SerializedProof,
        verifying_key: &VerifyingKey,
    ) -> ZKResult<bool> {
        #[allow(unused_imports)]
        use ark_ff::PrimeField;
        #[allow(unused_imports)]
        use ark_serialize::CanonicalDeserialize;

        // Deserialize proof
        let proof = serialized.to_proof()?;

        // Deserialize public inputs
        let public_inputs: Vec<Fr> = serialized
            .public_inputs
            .iter()
            .map(|bytes| Fr::from_le_bytes_mod_order(bytes))
            .collect();

        Self::verify(&proof, &public_inputs, verifying_key)
    }

    /// Prepare a verifying key for faster repeated verification
    #[must_use]
    pub fn prepare_verifying_key(vk: &VerifyingKey) -> PreparedVK {
        PreparedVerifyingKey::from(vk.clone())
    }

    /// Batch verify multiple proofs (more efficient than individual verification)
    pub fn batch_verify(
        proofs: &[(Proof, Vec<Fr>)],
        verifying_key: &VerifyingKey,
    ) -> ZKResult<Vec<bool>> {
        let prepared_vk = Self::prepare_verifying_key(verifying_key);

        proofs
            .iter()
            .map(|(proof, inputs)| Self::verify_prepared(proof, inputs, &prepared_vk))
            .collect()
    }
}

/// Verification result with additional metadata
#[derive(Debug, Clone)]
pub struct VerificationResult {
    /// Whether the proof is valid
    pub valid: bool,
    /// Circuit identifier
    pub circuit_id: String,
    /// Verification timestamp
    pub timestamp: u64,
    /// Number of public inputs verified
    pub num_public_inputs: usize,
}

impl VerificationResult {
    /// Create a new verification result
    #[must_use]
    pub fn new(valid: bool, circuit_id: &str, num_public_inputs: usize) -> Self {
        Self {
            valid,
            circuit_id: circuit_id.to_string(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
            num_public_inputs,
        }
    }

    /// Create from verification attempt
    #[must_use]
    pub fn from_verification(
        proof: &Proof,
        public_inputs: &[Fr],
        verifying_key: &VerifyingKey,
        circuit_id: &str,
    ) -> Self {
        let valid = Verifier::verify(proof, public_inputs, verifying_key).unwrap_or(false);
        Self::new(valid, circuit_id, public_inputs.len())
    }
}

/// On-chain verifier interface (for smart contract integration)
pub mod onchain {
    use super::*;
    #[allow(unused_imports)]
    use ark_ff::{BigInteger, PrimeField};
    use ark_serialize::CanonicalSerialize;

    /// Solidity-compatible proof representation
    #[derive(Debug, Clone)]
    pub struct SolidityProof {
        pub a: [u8; 64],  // G1 point (compressed: 48 bytes, but padded for solidity)
        pub b: [u8; 128], // G2 point (compressed: 96 bytes, but padded for solidity)
        pub c: [u8; 64],  // G1 point
    }

    impl SolidityProof {
        /// Convert from arkworks proof
        pub fn from_proof(proof: &Proof) -> ZKResult<Self> {
            let mut a_bytes = Vec::new();
            let mut b_bytes = Vec::new();
            let mut c_bytes = Vec::new();

            proof
                .a
                .serialize_compressed(&mut a_bytes)
                .map_err(|e| ZKError::SerializationError(format!("{:?}", e)))?;
            proof
                .b
                .serialize_compressed(&mut b_bytes)
                .map_err(|e| ZKError::SerializationError(format!("{:?}", e)))?;
            proof
                .c
                .serialize_compressed(&mut c_bytes)
                .map_err(|e| ZKError::SerializationError(format!("{:?}", e)))?;

            let mut a = [0u8; 64];
            let mut b = [0u8; 128];
            let mut c = [0u8; 64];

            a[..a_bytes.len()].copy_from_slice(&a_bytes);
            b[..b_bytes.len()].copy_from_slice(&b_bytes);
            c[..c_bytes.len()].copy_from_slice(&c_bytes);

            Ok(Self { a, b, c })
        }

        /// Convert public inputs to Solidity uint256 array format
        #[must_use]
        pub fn inputs_to_solidity(inputs: &[Fr]) -> Vec<[u8; 32]> {
            inputs
                .iter()
                .map(|fr| {
                    let mut bytes = [0u8; 32];
                    let bigint = fr.into_bigint();
                    let limbs: &[u64] = bigint.as_ref();

                    // Convert limbs to bytes (little-endian)
                    for (i, limb) in limbs.iter().enumerate() {
                        let start = i * 8;
                        if start + 8 <= 32 {
                            let limb_bytes: [u8; 8] = limb.to_le_bytes();
                            bytes[start..start + 8].copy_from_slice(&limb_bytes);
                        }
                    }

                    bytes
                })
                .collect()
        }

        /// Generate a Solidity verifier contract skeleton.
        ///
        /// WARNING: this emits a SKELETON, not a working verifier. The pairing
        /// check is not implemented, so the generated `verify` reverts. Do not
        /// deploy it expecting proof verification; implement the pairing check
        /// first. It must never be changed to return a value without one --
        /// an always-accepting verifier is worse than none.
        #[must_use]
        pub fn generate_verifier_contract(vk: &VerifyingKey) -> String {
            use sha3::{Digest, Sha3_256};
            let mut hasher = Sha3_256::new();
            let mut vk_bytes = Vec::new();
            // Grounding: Serialize VK to generate a unique root
            vk.serialize_compressed(&mut vk_bytes).unwrap_or_default();
            hasher.update(&vk_bytes);
            let vk_root = hex::encode(hasher.finalize());

            // Phase 12.10: full state wipe - Grounded Contract Generation
            format!(
                r#"
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// WarmLogic Groth16 Verifier
// VK_ROOT: {}
contract WarmLogicVerifier {{
    function verify(
        uint256[2] memory a,
        uint256[2][2] memory b,
        uint256[2] memory c,
        uint256[] memory publicInputs
    ) public pure returns (bool) {{
        // NOT IMPLEMENTED: the Groth16 pairing check is missing.
        // Fail closed rather than accept every proof.
        revert("WarmLogicVerifier: pairing check not implemented");
    }}
}}
"#,
                vk_root
            )
        }
    }
}

#[cfg(test)]
mod tests {
    use super::super::prover::{Prover, TrustedSetup};
    use super::super::types::{DecisionType, GovernancePublicInputs};
    use super::super::GovernanceCircuit;
    use super::*;

    #[test]
    fn test_verify_valid_proof() {
        let public_inputs = GovernancePublicInputs {
            model_hash: [1u8; 32],
            decision_hash: [1u8; 32],
            policy_hash: [2u8; 32],
            decision_type: DecisionType::PolicyCompliance,
            epoch: 1000,
            node_id: [3u8; 32],
        };

        let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
        let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
        let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

        let valid = Verifier::verify(&proof, &inputs, &vk).unwrap();
        assert!(valid, "Valid proof should verify");
    }

    #[test]
    fn test_verify_invalid_inputs() {
        let public_inputs = GovernancePublicInputs {
            model_hash: [1u8; 32],
            decision_hash: [1u8; 32],
            policy_hash: [2u8; 32],
            decision_type: DecisionType::PolicyCompliance,
            epoch: 1000,
            node_id: [3u8; 32],
        };

        let circuit = GovernanceCircuit::new(public_inputs.clone(), 5, 3, 5, false);
        let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
        let (proof, _inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

        // Use different inputs
        let wrong_inputs = GovernancePublicInputs {
            decision_hash: [9u8; 32], // Different!
            policy_hash: [2u8; 32],
            decision_type: DecisionType::PolicyCompliance,
            epoch: 1000,
            node_id: [3u8; 32],
            model_hash: [1u8; 32],
        };
        let wrong_inputs_vec = wrong_inputs.to_field_elements();

        let valid = Verifier::verify(&proof, &wrong_inputs_vec, &vk).unwrap();
        assert!(!valid, "Proof with wrong inputs should not verify");
    }

    #[test]
    fn test_verification_result() {
        let public_inputs = GovernancePublicInputs {
            model_hash: [1u8; 32],
            decision_hash: [1u8; 32],
            policy_hash: [2u8; 32],
            decision_type: DecisionType::PolicyCompliance,
            epoch: 1000,
            node_id: [3u8; 32],
        };

        let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
        let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
        let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

        let result = VerificationResult::from_verification(
            &proof,
            &inputs,
            &vk,
            GovernanceCircuit::CIRCUIT_ID,
        );

        assert!(result.valid);
        assert_eq!(result.circuit_id, "wl_governance_v1");
        assert_eq!(result.num_public_inputs, 9);
    }
}
