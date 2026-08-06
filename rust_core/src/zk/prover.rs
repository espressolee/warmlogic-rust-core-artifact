//! Groth16 Prover for WarmLogic ZK proofs.
//!
//! This module handles proof generation using the arkworks Groth16 implementation.

use ark_groth16::Groth16;
use ark_relations::r1cs::ConstraintSynthesizer;
use ark_snark::SNARK;
use ark_std::rand::rngs::StdRng;
use ark_std::rand::SeedableRng;

use super::error::{ZKError, ZKResult};
use super::types::{Fr, Proof, ProvingKey, SerializedProof, VerifyingKey};
use super::GovernanceCircuit;

/// Prover for generating Groth16 proofs
pub struct Prover;

impl Prover {
    /// Generate a proof for a governance circuit
    pub fn prove_governance(
        circuit: &GovernanceCircuit,
        proving_key: &ProvingKey,
    ) -> ZKResult<(Proof, Vec<Fr>)> {
        // Validate circuit first
        circuit.validate()?;

        // Get public inputs
        let public_inputs = circuit.get_public_inputs();

        // Generate proof
        let mut rng = StdRng::from_entropy();
        let proof =
            Groth16::<ark_bls12_381::Bls12_381>::prove(proving_key, circuit.clone(), &mut rng)
                .map_err(|e| ZKError::ProvingError(format!("{:?}", e)))?;

        Ok((proof, public_inputs))
    }

    /// Generate a proof for any circuit implementing ConstraintSynthesizer
    pub fn prove<C: ConstraintSynthesizer<Fr> + Clone>(
        circuit: C,
        proving_key: &ProvingKey,
        public_inputs: Vec<Fr>,
    ) -> ZKResult<(Proof, Vec<Fr>)> {
        let mut rng = StdRng::from_entropy();
        let proof = Groth16::<ark_bls12_381::Bls12_381>::prove(proving_key, circuit, &mut rng)
            .map_err(|e| ZKError::ProvingError(format!("{:?}", e)))?;

        Ok((proof, public_inputs))
    }

    /// Generate a serialized proof for storage/transmission
    pub fn prove_serialized<C: ConstraintSynthesizer<Fr> + Clone>(
        circuit: C,
        proving_key: &ProvingKey,
        public_inputs: Vec<Fr>,
        circuit_id: &str,
    ) -> ZKResult<SerializedProof> {
        let (proof, inputs) = Self::prove(circuit, proving_key, public_inputs)?;
        SerializedProof::from_proof(&proof, &inputs, circuit_id)
            .map_err(|e| ZKError::SerializationError(format!("{:?}", e)))
    }
}

/// Trusted setup for generating proving/verifying keys
pub struct TrustedSetup;

impl TrustedSetup {
    /// Load keys from pre-computed CRS file (PRODUCTION-SAFE)
    ///
    /// This loads proving and verifying keys from a trusted setup ceremony output.
    /// Use this in production to avoid single-party toxic waste.
    ///
    /// # Security
    /// - Keys must be generated via multi-party computation (MPC) ceremony
    /// - CRS file should be signed and integrity-checked
    /// - Never accept runtime-generated keys in production
    pub fn load_keys_from_crs(
        pk_path: &std::path::Path,
        vk_path: &std::path::Path,
    ) -> ZKResult<(ProvingKey, VerifyingKey)> {
        let pk = keys::load_proving_key(pk_path)?;
        let vk = keys::load_verifying_key(vk_path)?;

        #[cfg(feature = "std")]
        eprintln!("[ZK] Loaded keys from MPC ceremony CRS files");

        Ok((pk, vk))
    }

    /// Runtime key generation (DEVELOPMENT ONLY - logs warning)
    ///
    /// WARNING: This uses a random seed from a single party. In production,
    /// this allows toxic waste (tau) to be known, enabling forged proofs.
    ///
    /// # Security Risk
    /// - Single-party setup = known toxic waste
    /// - Known toxic waste = ability to forge proofs
    /// - Forged proofs = broken soundness
    ///
    /// # Production Requirements
    /// Use `load_keys_from_crs()` with keys from MPC ceremony instead.
    #[cfg(not(feature = "production"))]
    pub fn generate_keys_dev<C: ConstraintSynthesizer<Fr>>(
        circuit: C,
    ) -> ZKResult<(ProvingKey, VerifyingKey)> {
        #[cfg(feature = "std")]
        eprintln!(" WARNING: Using runtime CRS generation. NOT FOR PRODUCTION.");
        #[cfg(feature = "std")]
        eprintln!(" Single-party setup allows toxic waste extraction.");
        #[cfg(feature = "std")]
        eprintln!(" Use MPC ceremony + load_keys_from_crs() in production.");

        let mut rng = StdRng::from_entropy();
        let (pk, vk) =
            Groth16::<ark_bls12_381::Bls12_381>::circuit_specific_setup(circuit, &mut rng)
                .map_err(|e| ZKError::SetupError(format!("{:?}", e)))?;

        Ok((pk, vk))
    }

    /// Compatibility alias for legacy code (DEPRECATED)
    ///
    /// # Deprecation Notice
    /// This function is deprecated and will be removed in a future release.
    /// Use `generate_keys_dev()` in development or `load_keys_from_crs()` in production.
    #[deprecated(
        since = "1.1.0",
        note = "Use generate_keys_dev() (dev only) or load_keys_from_crs() (production)"
    )]
    #[cfg(not(feature = "production"))]
    pub fn generate_keys<C: ConstraintSynthesizer<Fr>>(
        circuit: C,
    ) -> ZKResult<(ProvingKey, VerifyingKey)> {
        Self::generate_keys_dev(circuit)
    }

    /// Production-safe key generation enforcer
    ///
    /// This function is available when the `production` feature is enabled.
    /// It ONLY allows loading keys from CRS files, blocking runtime generation.
    #[cfg(feature = "production")]
    pub fn generate_keys<C: ConstraintSynthesizer<Fr>>(
        _circuit: C,
    ) -> ZKResult<(ProvingKey, VerifyingKey)> {
        Err(ZKError::SetupError(
            "Runtime key generation is disabled in production. \
             Use load_keys_from_crs() with MPC ceremony output."
                .to_string(),
        ))
    }

    /// Generate keys with a deterministic seed (for testing only!)
    ///
    /// WARNING: NEVER use this in production. The seed makes the
    /// proving key predictable, which breaks soundness.
    #[cfg(test)]
    pub fn generate_keys_deterministic<C: ConstraintSynthesizer<Fr>>(
        circuit: C,
        seed: u64,
    ) -> ZKResult<(ProvingKey, VerifyingKey)> {
        let mut rng = StdRng::seed_from_u64(seed);

        let (pk, vk) =
            Groth16::<ark_bls12_381::Bls12_381>::circuit_specific_setup(circuit, &mut rng)
                .map_err(|e| ZKError::SetupError(format!("{:?}", e)))?;

        Ok((pk, vk))
    }
}

/// Key management for proving/verifying keys
pub mod keys {
    use super::*;
    use ark_serialize::{CanonicalDeserialize, CanonicalSerialize};
    use std::fs;
    use std::path::Path;

    /// Save proving key to file
    pub fn save_proving_key(pk: &ProvingKey, path: &Path) -> ZKResult<()> {
        let mut bytes = Vec::new();
        pk.serialize_compressed(&mut bytes)
            .map_err(|e| ZKError::SerializationError(format!("{:?}", e)))?;

        fs::write(path, &bytes)
            .map_err(|e| ZKError::SerializationError(format!("Failed to write file: {}", e)))
    }

    /// Load proving key from file
    pub fn load_proving_key(path: &Path) -> ZKResult<ProvingKey> {
        let bytes = fs::read(path)
            .map_err(|e| ZKError::SerializationError(format!("Failed to read file: {}", e)))?;

        ProvingKey::deserialize_compressed(&bytes[..])
            .map_err(|e| ZKError::SerializationError(format!("{:?}", e)))
    }

    /// Save verifying key to file
    pub fn save_verifying_key(vk: &VerifyingKey, path: &Path) -> ZKResult<()> {
        let mut bytes = Vec::new();
        vk.serialize_compressed(&mut bytes)
            .map_err(|e| ZKError::SerializationError(format!("{:?}", e)))?;

        fs::write(path, &bytes)
            .map_err(|e| ZKError::SerializationError(format!("Failed to write file: {}", e)))
    }

    /// Load verifying key from file
    pub fn load_verifying_key(path: &Path) -> ZKResult<VerifyingKey> {
        let bytes = fs::read(path)
            .map_err(|e| ZKError::SerializationError(format!("Failed to read file: {}", e)))?;

        VerifyingKey::deserialize_compressed(&bytes[..])
            .map_err(|e| ZKError::SerializationError(format!("{:?}", e)))
    }

    /// Get the size of a proving key in bytes
    #[must_use]
    pub fn proving_key_size(pk: &ProvingKey) -> usize {
        pk.serialized_size(ark_serialize::Compress::Yes)
    }

    /// Get the size of a verifying key in bytes
    #[must_use]
    pub fn verifying_key_size(vk: &VerifyingKey) -> usize {
        vk.serialized_size(ark_serialize::Compress::Yes)
    }
}

#[cfg(test)]
mod tests {
    use super::super::types::{DecisionType, GovernancePublicInputs};
    use super::super::GovernanceCircuit;
    use super::*;

    #[test]
    fn test_trusted_setup_and_prove() {
        // Create a simple circuit for setup
        let public_inputs = GovernancePublicInputs {
            model_hash: [1u8; 32],
            decision_hash: [1u8; 32],
            policy_hash: [2u8; 32],
            decision_type: DecisionType::PolicyCompliance,
            epoch: 1000,
            node_id: [3u8; 32],
        };

        let circuit = GovernanceCircuit::new(
            public_inputs.clone(),
            5, // authority_level
            3, // threshold
            5, // approval_count
            false,
        );

        // Generate keys (deterministic for test reproducibility)
        let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();

        // Prove
        let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

        // Verify (using verifier module)
        use super::super::verifier::Verifier;
        assert!(Verifier::verify(&proof, &inputs, &vk).unwrap());
    }

    #[test]
    fn test_key_sizes() {
        let public_inputs = GovernancePublicInputs {
            model_hash: [1u8; 32],
            decision_hash: [1u8; 32],
            policy_hash: [2u8; 32],
            decision_type: DecisionType::PolicyCompliance,
            epoch: 1000,
            node_id: [3u8; 32],
        };

        let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
        let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit, 42).unwrap();

        let pk_size = keys::proving_key_size(&pk);
        let vk_size = keys::verifying_key_size(&vk);

        println!("Proving key size: {} bytes", pk_size);
        println!("Verifying key size: {} bytes", vk_size);

        // Verifying key should be small (< 1KB for simple circuits)
        assert!(vk_size < 2048, "VK too large: {} bytes", vk_size);
    }
}
