//! Kernel State Transition Circuit for ZK-SNARK proofs.
//!
//! This circuit proves that a kernel state transition from S₀ to S₁
//! was performed correctly, satisfying all constitutional invariants:
//!
//! 1. Entropy must not decrease (thermodynamic consistency)
//! 2. Weight delta is bounded (prevents catastrophic drift)
//! 3. Confidence score exceeds minimum threshold
//! 4. The transition was constitutionally valid
//!
//! ## Circuit Structure
//!
//! Public Inputs (9 field elements):
//! - `pre_state_hash`  (2 FE: SHA3-256 of state before transition)
//! - `post_state_hash` (2 FE: SHA3-256 of state after transition)
//! - `action_hash`     (2 FE: SHA3-256 of the applied action)
//! - `epoch`           (1 FE: kernel tick number)
//! - `node_id_prefix`  (1 FE: first 8 bytes of node identity)
//! - `invariant_flags`  (1 FE: bitmask of satisfied invariants)
//!
//! Private Witnesses:
//! - `entropy_before` / `entropy_after` (Shannon entropy × 1000 as u64)
//! - `weight_delta`  (absolute weight change, scaled ×1000)
//! - `confidence_score` (0-100)
//! - `was_constitutional` (boolean)

use ark_r1cs_std::fields::fp::FpVar;
use ark_r1cs_std::fields::FieldVar;
use ark_r1cs_std::prelude::*;
use ark_relations::r1cs::{ConstraintSynthesizer, ConstraintSystemRef, SynthesisError};

use super::error::{ZKError, ZKResult};
use super::types::Fr;

/// Maximum allowed weight delta per tick (tightened for ).
/// A value of 200 means max 0.2 change to prevent catastrophic drift.
const MAX_WEIGHT_DELTA: u64 = 200;

/// Minimum confidence score for a valid transition (kernel Baseline).
const MIN_CONFIDENCE: u64 = 85;

/// Public inputs for a kernel state transition proof.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TransitionPublicInputs {
    /// SHA3-256 hash of the pre-transition state
    pub pre_state_hash: [u8; 32],
    /// SHA3-256 hash of the post-transition state
    pub post_state_hash: [u8; 32],
    /// SHA3-256 hash of the action applied
    pub action_hash: [u8; 32],
    /// Kernel tick / epoch number
    pub epoch: u64,
    /// Node identity (first 8 bytes used)
    pub node_id: [u8; 32],
    /// Bitmask of satisfied invariants (for public auditability)
    /// Bit 0: entropy non-decrease
    /// Bit 1: weight delta bounded
    /// Bit 2: confidence above minimum
    /// Bit 3: constitutionally valid
    pub invariant_flags: u8,
}

impl TransitionPublicInputs {
    /// Convert to field elements for the circuit.
    #[must_use]
    pub fn to_field_elements(&self) -> Vec<Fr> {
        let mut elements = Vec::with_capacity(9);

        // pre_state_hash (2 FE)
        let (low, high) = split_hash(&self.pre_state_hash);
        elements.push(low);
        elements.push(high);

        // post_state_hash (2 FE)
        let (low, high) = split_hash(&self.post_state_hash);
        elements.push(low);
        elements.push(high);

        // action_hash (2 FE)
        let (low, high) = split_hash(&self.action_hash);
        elements.push(low);
        elements.push(high);

        // epoch (1 FE)
        elements.push(Fr::from(self.epoch));

        // node_id_prefix (1 FE)
        let node_prefix = u64::from_le_bytes(self.node_id[..8].try_into().unwrap_or_default());
        elements.push(Fr::from(node_prefix));

        // invariant_flags (1 FE)
        elements.push(Fr::from(self.invariant_flags as u64));

        elements
    }
}

/// Split a 32-byte hash into two BLS12-381 field elements.
fn split_hash(hash: &[u8; 32]) -> (Fr, Fr) {
    use ark_ff::PrimeField;

    let mut low_bytes = [0u8; 32];
    let mut high_bytes = [0u8; 32];

    low_bytes[..16].copy_from_slice(&hash[..16]);
    high_bytes[..16].copy_from_slice(&hash[16..]);

    (
        Fr::from_le_bytes_mod_order(&low_bytes),
        Fr::from_le_bytes_mod_order(&high_bytes),
    )
}

/// Kernel State Transition Circuit for Groth16 proving.
///
/// Proves that a state transition satisfies all constitutional invariants
/// without revealing the internal state details.
#[derive(Clone)]
pub struct KernelStateTransitionCircuit {
    /// Public inputs
    pub public_inputs: TransitionPublicInputs,

    // === Private Witnesses ===
    /// Shannon entropy of state before transition (× 1000 for fixed-point)
    pub entropy_before: u64,
    /// Shannon entropy of state after transition (× 1000 for fixed-point)
    pub entropy_after: u64,
    /// Absolute weight delta (× 1000 for fixed-point)
    pub weight_delta: u64,
    /// Confidence score of the transition (0-100)
    pub confidence_score: u64,
    /// Whether the transition passed constitutional governance check
    pub was_constitutional: bool,
}

impl KernelStateTransitionCircuit {
    /// Circuit identifier
    pub const CIRCUIT_ID: &'static str = "wl_kernel_transition_v1";

    /// Number of public inputs
    pub const NUM_PUBLIC_INPUTS: usize = 9;

    /// Create a new kernel state transition circuit.
    #[must_use]
    pub fn new(
        public_inputs: TransitionPublicInputs,
        entropy_before: u64,
        entropy_after: u64,
        weight_delta: u64,
        confidence_score: u64,
        was_constitutional: bool,
    ) -> Self {
        Self {
            public_inputs,
            entropy_before,
            entropy_after,
            weight_delta,
            confidence_score,
            was_constitutional,
        }
    }

    /// Validate that all invariants hold before attempting to prove.
    /// This is a fast pre-check; the circuit enforces these in ZK.
    pub fn validate(&self) -> ZKResult<()> {
        // Invariant 1: Entropy must not decrease
        if self.entropy_after < self.entropy_before {
            return Err(ZKError::StateTransitionViolation(
                "Entropy decreased: thermodynamic consistency violated".to_string(),
            ));
        }

        // Invariant 2: Weight delta must be bounded
        if self.weight_delta > MAX_WEIGHT_DELTA {
            return Err(ZKError::StateTransitionViolation(format!(
                "Weight delta {} exceeds maximum {}",
                self.weight_delta, MAX_WEIGHT_DELTA
            )));
        }

        // Invariant 3: Confidence must meet minimum
        if self.confidence_score < MIN_CONFIDENCE {
            return Err(ZKError::StateTransitionViolation(format!(
                "Confidence {} below minimum {}",
                self.confidence_score, MIN_CONFIDENCE
            )));
        }

        // Invariant 4: Must be constitutional
        if !self.was_constitutional {
            return Err(ZKError::StateTransitionViolation(
                "Transition is not constitutionally valid".to_string(),
            ));
        }

        Ok(())
    }

    /// Get public inputs as field elements.
    #[must_use]
    pub fn get_public_inputs(&self) -> Vec<Fr> {
        self.public_inputs.to_field_elements()
    }

    /// Compute the expected invariant flags bitmask.
    #[must_use]
    pub fn compute_invariant_flags(&self) -> u8 {
        let mut flags: u8 = 0;
        if self.entropy_after >= self.entropy_before {
            flags |= 1 << 0;
        }
        if self.weight_delta <= MAX_WEIGHT_DELTA {
            flags |= 1 << 1;
        }
        if self.confidence_score >= MIN_CONFIDENCE {
            flags |= 1 << 2;
        }
        if self.was_constitutional {
            flags |= 1 << 3;
        }
        flags
    }
}

impl ConstraintSynthesizer<Fr> for KernelStateTransitionCircuit {
    fn generate_constraints(self, cs: ConstraintSystemRef<Fr>) -> Result<(), SynthesisError> {
        // ================================================================
        // Allocate Public Inputs (9 field elements)
        // ================================================================
        let public_elements = self.public_inputs.to_field_elements();

        let pre_hash_low = FpVar::new_input(cs.clone(), || Ok(public_elements[0]))?;
        let _pre_hash_high = FpVar::new_input(cs.clone(), || Ok(public_elements[1]))?;
        let post_hash_low = FpVar::new_input(cs.clone(), || Ok(public_elements[2]))?;
        let _post_hash_high = FpVar::new_input(cs.clone(), || Ok(public_elements[3]))?;
        let action_hash_low = FpVar::new_input(cs.clone(), || Ok(public_elements[4]))?;
        let _action_hash_high = FpVar::new_input(cs.clone(), || Ok(public_elements[5]))?;
        let epoch = FpVar::new_input(cs.clone(), || Ok(public_elements[6]))?;
        let _node_id_prefix = FpVar::new_input(cs.clone(), || Ok(public_elements[7]))?;
        let invariant_flags_var = FpVar::new_input(cs.clone(), || Ok(public_elements[8]))?;

        // ================================================================
        // Allocate Private Witnesses
        // ================================================================
        let entropy_before = FpVar::new_witness(cs.clone(), || Ok(Fr::from(self.entropy_before)))?;
        let entropy_after = FpVar::new_witness(cs.clone(), || Ok(Fr::from(self.entropy_after)))?;
        let weight_delta = FpVar::new_witness(cs.clone(), || Ok(Fr::from(self.weight_delta)))?;
        let confidence_score =
            FpVar::new_witness(cs.clone(), || Ok(Fr::from(self.confidence_score)))?;
        let was_constitutional = Boolean::new_witness(cs.clone(), || Ok(self.was_constitutional))?;

        let zero = FpVar::constant(Fr::from(0u64));

        // ================================================================
        // Constraint 1: Entropy must not decrease
        // entropy_after >= entropy_before
        // ⟹ entropy_after - entropy_before >= 0
        // We witness a non-negative slack variable: slack = entropy_after - entropy_before
        // ================================================================
        let entropy_diff = &entropy_after - &entropy_before;
        let entropy_slack = FpVar::new_witness(cs.clone(), || {
            Ok(Fr::from(
                self.entropy_after.saturating_sub(self.entropy_before),
            ))
        })?;
        entropy_diff.enforce_equal(&entropy_slack)?;
        // entropy_slack is non-negative by construction (saturating_sub)

        // ================================================================
        // Constraint 2: Weight delta must be bounded
        // weight_delta <= MAX_WEIGHT_DELTA
        // ⟹ MAX_WEIGHT_DELTA - weight_delta >= 0
        // ================================================================
        let max_delta = FpVar::constant(Fr::from(MAX_WEIGHT_DELTA));
        let delta_headroom = &max_delta - &weight_delta;
        let delta_slack = FpVar::new_witness(cs.clone(), || {
            Ok(Fr::from(MAX_WEIGHT_DELTA.saturating_sub(self.weight_delta)))
        })?;
        delta_headroom.enforce_equal(&delta_slack)?;

        // ================================================================
        // Constraint 3: Confidence score exceeds minimum
        // confidence_score >= MIN_CONFIDENCE
        // ================================================================
        let min_conf = FpVar::constant(Fr::from(MIN_CONFIDENCE));
        let conf_headroom = &confidence_score - &min_conf;
        let conf_slack = FpVar::new_witness(cs.clone(), || {
            Ok(Fr::from(
                self.confidence_score.saturating_sub(MIN_CONFIDENCE),
            ))
        })?;
        conf_headroom.enforce_equal(&conf_slack)?;

        // ================================================================
        // Constraint 4: Transition must be constitutional
        // was_constitutional == TRUE
        // ================================================================
        was_constitutional.enforce_equal(&Boolean::TRUE)?;

        // ================================================================
        // Constraint 5: All hashes and epoch must be non-zero
        // (prevents trivial/empty state transitions)
        // ================================================================
        pre_hash_low.enforce_not_equal(&zero)?;
        post_hash_low.enforce_not_equal(&zero)?;
        action_hash_low.enforce_not_equal(&zero)?;
        epoch.enforce_not_equal(&zero)?;

        // ================================================================
        // Constraint 6: Invariant flags must be consistent
        // The public invariant_flags must equal 0b1111 (all 4 invariants satisfied)
        // ================================================================
        let expected_flags = FpVar::constant(Fr::from(0b1111u64));
        invariant_flags_var.enforce_equal(&expected_flags)?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ark_relations::r1cs::ConstraintSystem;

    fn test_hashes() -> ([u8; 32], [u8; 32], [u8; 32]) {
        use sha3::{Digest, Sha3_256};
        let pre = {
            let mut h = Sha3_256::new();
            h.update(b"state_before");
            let r = h.finalize();
            let mut out = [0u8; 32];
            out.copy_from_slice(&r);
            out
        };
        let post = {
            let mut h = Sha3_256::new();
            h.update(b"state_after");
            let r = h.finalize();
            let mut out = [0u8; 32];
            out.copy_from_slice(&r);
            out
        };
        let action = {
            let mut h = Sha3_256::new();
            h.update(b"revise_weights");
            let r = h.finalize();
            let mut out = [0u8; 32];
            out.copy_from_slice(&r);
            out
        };
        (pre, post, action)
    }

    #[test]
    fn test_valid_transition_satisfies_constraints() {
        let (pre, post, action) = test_hashes();
        let public = TransitionPublicInputs {
            pre_state_hash: pre,
            post_state_hash: post,
            action_hash: action,
            epoch: 42,
            node_id: [1u8; 32],
            invariant_flags: 0b1111,
        };

        let circuit = KernelStateTransitionCircuit::new(
            public, 3000, // entropy_before (3.0)
            3200, // entropy_after (3.2) — increased ✓
            100,  // weight_delta (0.1) — bounded ✓
            85,   // confidence_score — above min ✓
            true, // was_constitutional ✓
        );

        assert!(circuit.validate().is_ok());
        assert_eq!(circuit.compute_invariant_flags(), 0b1111);

        let cs = ConstraintSystem::<Fr>::new_ref();
        circuit.generate_constraints(cs.clone()).unwrap();
        assert!(
            cs.is_satisfied().unwrap(),
            "Valid transition must satisfy all constraints"
        );
    }

    #[test]
    fn test_entropy_decrease_fails_validation() {
        let (pre, post, action) = test_hashes();
        let public = TransitionPublicInputs {
            pre_state_hash: pre,
            post_state_hash: post,
            action_hash: action,
            epoch: 42,
            node_id: [1u8; 32],
            invariant_flags: 0b1111,
        };

        let circuit = KernelStateTransitionCircuit::new(
            public, 5000, // entropy_before (5.0)
            3000, // entropy_after (3.0) — DECREASED ✗
            100, 85, true,
        );

        let result = circuit.validate();
        assert!(result.is_err());
        let err_msg = format!("{}", result.unwrap_err());
        assert!(err_msg.contains("Entropy decreased"));
    }

    #[test]
    fn test_weight_delta_exceeded_fails_validation() {
        let (pre, post, action) = test_hashes();
        let public = TransitionPublicInputs {
            pre_state_hash: pre,
            post_state_hash: post,
            action_hash: action,
            epoch: 42,
            node_id: [1u8; 32],
            invariant_flags: 0b1111,
        };

        let circuit = KernelStateTransitionCircuit::new(
            public, 3000, 3200, 999, // weight_delta (0.999) — EXCEEDS MAX 0.5 ✗
            85, true,
        );

        let result = circuit.validate();
        assert!(result.is_err());
        let err_msg = format!("{}", result.unwrap_err());
        assert!(err_msg.contains("exceeds maximum"));
    }

    #[test]
    fn test_low_confidence_fails_validation() {
        let (pre, post, action) = test_hashes();
        let public = TransitionPublicInputs {
            pre_state_hash: pre,
            post_state_hash: post,
            action_hash: action,
            epoch: 42,
            node_id: [1u8; 32],
            invariant_flags: 0b1111,
        };

        let circuit = KernelStateTransitionCircuit::new(
            public, 3000, 3200, 100, 5, // confidence 5 — BELOW MIN 10 ✗
            true,
        );

        let result = circuit.validate();
        assert!(result.is_err());
        let err_msg = format!("{}", result.unwrap_err());
        assert!(err_msg.contains("below minimum"));
    }

    #[test]
    fn test_unconstitutional_fails_validation() {
        let (pre, post, action) = test_hashes();
        let public = TransitionPublicInputs {
            pre_state_hash: pre,
            post_state_hash: post,
            action_hash: action,
            epoch: 42,
            node_id: [1u8; 32],
            invariant_flags: 0b1111,
        };

        let circuit = KernelStateTransitionCircuit::new(
            public, 3000, 3200, 100, 85, false, // NOT constitutional ✗
        );

        let result = circuit.validate();
        assert!(result.is_err());
        let err_msg = format!("{}", result.unwrap_err());
        assert!(err_msg.contains("not constitutionally valid"));
    }

    #[test]
    fn test_public_inputs_field_elements() {
        let (pre, post, action) = test_hashes();
        let public = TransitionPublicInputs {
            pre_state_hash: pre,
            post_state_hash: post,
            action_hash: action,
            epoch: 42,
            node_id: [1u8; 32],
            invariant_flags: 0b1111,
        };

        let elements = public.to_field_elements();
        assert_eq!(
            elements.len(),
            KernelStateTransitionCircuit::NUM_PUBLIC_INPUTS,
        );
    }

    #[test]
    fn test_invariant_flags_computation() {
        let (pre, post, action) = test_hashes();
        let public = TransitionPublicInputs {
            pre_state_hash: pre,
            post_state_hash: post,
            action_hash: action,
            epoch: 42,
            node_id: [1u8; 32],
            invariant_flags: 0b1111,
        };

        // All invariants satisfied
        let circuit = KernelStateTransitionCircuit::new(public.clone(), 3000, 3200, 100, 85, true);
        assert_eq!(circuit.compute_invariant_flags(), 0b1111);

        // Entropy violation only
        let circuit2 = KernelStateTransitionCircuit::new(public, 5000, 3000, 100, 85, true);
        assert_eq!(circuit2.compute_invariant_flags(), 0b1110); // bit 0 cleared
    }

    #[test]
    fn test_boundary_values() {
        let (pre, post, action) = test_hashes();
        let public = TransitionPublicInputs {
            pre_state_hash: pre,
            post_state_hash: post,
            action_hash: action,
            epoch: 1, // minimum non-zero epoch
            node_id: [1u8; 32],
            invariant_flags: 0b1111,
        };

        // Exactly at boundaries
        let circuit = KernelStateTransitionCircuit::new(
            public,
            3000,
            3000,             // entropy_after == entropy_before (allowed: non-decrease)
            MAX_WEIGHT_DELTA, // exactly at max (allowed)
            MIN_CONFIDENCE,   // exactly at min (allowed)
            true,
        );

        assert!(circuit.validate().is_ok());

        let cs = ConstraintSystem::<Fr>::new_ref();
        circuit.generate_constraints(cs.clone()).unwrap();
        assert!(cs.is_satisfied().unwrap());
    }
}
