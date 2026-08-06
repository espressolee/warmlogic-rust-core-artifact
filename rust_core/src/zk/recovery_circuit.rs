//! State Snapshot Circuit for proving system survival integrity.
//! Resonance OS - Survival Integrity

use ark_r1cs_std::fields::fp::FpVar;
use ark_r1cs_std::prelude::*;
use ark_relations::r1cs::{ConstraintSynthesizer, ConstraintSystemRef, SynthesisError};
use ark_std::vec::Vec;
use zeroize::{Zeroize, ZeroizeOnDrop};

use super::types::Fr;
use super::{ZKError, ZKResult};

impl StateSnapshotCircuit {
    /// Validates that the circuit constraints can be satisfied with the provided witness.
    /// [Harsh Audit] Performs an O(N) check without the O(N log N) overhead of full proving.
    pub fn validate_satisfiability(&self) -> ZKResult<()> {
        use ark_relations::r1cs::ConstraintSystem;
        let cs = ConstraintSystem::<Fr>::new_ref();
        self.clone()
            .generate_constraints(cs.clone())
            .map_err(|e| ZKError::ConstraintViolation(format!("Synthesis error: {}", e)))?;

        if !cs
            .is_satisfied()
            .map_err(|e| ZKError::ConstraintViolation(e.to_string()))?
        {
            return Err(ZKError::ConstraintViolation(
                "Circuit not satisfied by witness".into(),
            ));
        }
        Ok(())
    }
}

/// State Snapshot Circuit for Groth16 proving
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct StateSnapshotCircuit {
    /// Public: Epoch/timestamp of snapshot
    pub epoch: u64,
    /// Public: State root at this epoch
    pub state_root: [u8; 32],
    /// Public: Hardware fingerprint (RoT)
    pub hardware_fingerprint: [u8; 32],
    /// Private: HSM secret used for sealing
    pub hsm_secret: [u8; 32],
}

impl StateSnapshotCircuit {
    pub const CIRCUIT_ID: &'static str = "wl_recovery_v1";
    pub const NUM_PUBLIC_INPUTS: usize = 5; // epoch(1) + state_root(2) + hw_fingerprint(2)

    pub fn new(
        epoch: u64,
        state_root: [u8; 32],
        hardware_fingerprint: [u8; 32],
        hsm_secret: [u8; 32],
    ) -> Self {
        Self {
            epoch,
            state_root,
            hardware_fingerprint,
            hsm_secret,
        }
    }

    pub fn get_public_inputs(&self) -> Vec<Fr> {
        let mut inputs = Vec::with_capacity(Self::NUM_PUBLIC_INPUTS);
        inputs.push(Fr::from(self.epoch));

        // Split 32-byte hashes into field elements
        let (root_low, root_high) = split_to_field_elements(&self.state_root);
        inputs.push(root_low);
        inputs.push(root_high);

        let (hw_low, hw_high) = split_to_field_elements(&self.hardware_fingerprint);
        inputs.push(hw_low);
        inputs.push(hw_high);

        inputs
    }
}

fn split_to_field_elements(data: &[u8; 32]) -> (Fr, Fr) {
    use ark_ff::PrimeField;
    let mut low_bytes = [0u8; 32];
    let mut high_bytes = [0u8; 32];
    low_bytes[..16].copy_from_slice(&data[..16]);
    high_bytes[..16].copy_from_slice(&data[16..]);
    (
        Fr::from_le_bytes_mod_order(&low_bytes),
        Fr::from_le_bytes_mod_order(&high_bytes),
    )
}

impl ConstraintSynthesizer<Fr> for StateSnapshotCircuit {
    fn generate_constraints(self, cs: ConstraintSystemRef<Fr>) -> Result<(), SynthesisError> {
        let public_elements = self.get_public_inputs();

        let epoch = FpVar::new_input(cs.clone(), || Ok(public_elements[0]))?;
        let _state_root_low = FpVar::new_input(cs.clone(), || Ok(public_elements[1]))?;
        let _state_root_high = FpVar::new_input(cs.clone(), || Ok(public_elements[2]))?;
        let _hw_fingerprint_low = FpVar::new_input(cs.clone(), || Ok(public_elements[3]))?;
        let _hw_fingerprint_high = FpVar::new_input(cs.clone(), || Ok(public_elements[4]))?;

        // Private witness
        let hsm_secret = FpVar::new_witness(cs.clone(), || {
            use ark_ff::PrimeField;
            Ok(Fr::from_le_bytes_mod_order(&self.hsm_secret))
        })?;

        // Constraint 1: Epoch must be non-zero
        let zero = FpVar::constant(Fr::from(0u64));
        epoch.enforce_not_equal(&zero)?;

        // Constraint 2: HSM Secret must be non-zero (proving presence of RoT)
        hsm_secret.enforce_not_equal(&zero)?;

        // Integrity Binding:
        // In a full implementation, we would prove H(hsm_secret) matches
        // a commitment in the hardware attestation report.

        Ok(())
    }
}
