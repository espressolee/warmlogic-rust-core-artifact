//! Circuit builder for R1CS constraints.
//!
//! This module provides a high-level interface for building R1CS circuits
//! that can be used with Groth16.

use ark_r1cs_std::prelude::*;
use ark_relations::r1cs::{ConstraintSynthesizer, ConstraintSystemRef, SynthesisError};
use ark_std::vec::Vec;

use super::error::ZKResult;
use super::types::Fr;

/// Variable in the circuit (wrapper around ark R1CS variable)
#[derive(Debug, Clone, Copy)]
pub struct Variable {
    /// Internal index
    pub index: usize,
    /// Whether this is a public input
    pub is_public: bool,
}

/// Constraint in the circuit
#[derive(Debug, Clone)]
pub struct Constraint {
    /// A coefficients (left side of multiplication)
    pub a: Vec<(usize, Fr)>,
    /// B coefficients (right side of multiplication)
    pub b: Vec<(usize, Fr)>,
    /// C coefficients (output)
    pub c: Vec<(usize, Fr)>,
}

/// Circuit builder for constructing R1CS constraints
pub struct CircuitBuilder {
    /// Number of public inputs
    pub num_public_inputs: usize,
    /// Number of private witnesses
    pub num_private_witnesses: usize,
    /// Constraints
    pub constraints: Vec<Constraint>,
    /// Circuit identifier
    pub circuit_id: String,
}

impl CircuitBuilder {
    /// Create a new circuit builder
    #[must_use]
    pub fn new(circuit_id: &str) -> Self {
        Self {
            num_public_inputs: 0,
            num_private_witnesses: 0,
            constraints: Vec::new(),
            circuit_id: circuit_id.to_string(),
        }
    }

    /// Allocate a public input variable
    pub fn alloc_public(&mut self) -> Variable {
        let index = self.num_public_inputs;
        self.num_public_inputs += 1;
        Variable {
            index,
            is_public: true,
        }
    }

    /// Allocate a private witness variable
    pub fn alloc_private(&mut self) -> Variable {
        let index = self.num_public_inputs + self.num_private_witnesses;
        self.num_private_witnesses += 1;
        Variable {
            index,
            is_public: false,
        }
    }

    /// Add a constraint: A * B = C
    pub fn add_constraint(
        &mut self,
        a: Vec<(usize, Fr)>,
        b: Vec<(usize, Fr)>,
        c: Vec<(usize, Fr)>,
    ) {
        self.constraints.push(Constraint { a, b, c });
    }

    /// Add an equality constraint: var1 = var2
    pub fn enforce_equal(&mut self, var1: Variable, var2: Variable) {
        use ark_ff::One;
        // var1 * 1 = var2
        self.add_constraint(
            vec![(var1.index, Fr::one())],
            vec![(0, Fr::one())], // constant 1
            vec![(var2.index, Fr::one())],
        );
    }

    /// Add a boolean constraint: var * var = var (var is 0 or 1)
    pub fn enforce_boolean(&mut self, var: Variable) {
        use ark_ff::One;
        // var * var = var
        self.add_constraint(
            vec![(var.index, Fr::one())],
            vec![(var.index, Fr::one())],
            vec![(var.index, Fr::one())],
        );
    }

    /// Get the total number of variables
    #[must_use]
    pub fn num_variables(&self) -> usize {
        self.num_public_inputs + self.num_private_witnesses
    }

    /// Get the number of constraints
    #[must_use]
    pub fn num_constraints(&self) -> usize {
        self.constraints.len()
    }
}

/// Trait for circuits that can be synthesized
pub trait WarmLogicCircuit: Clone {
    /// Get the circuit identifier
    fn circuit_id(&self) -> &str;

    /// Get the number of public inputs
    fn num_public_inputs(&self) -> usize;

    /// Generate witness values for the circuit
    fn generate_witness(&self) -> ZKResult<Vec<Fr>>;

    /// Get the public inputs
    fn public_inputs(&self) -> ZKResult<Vec<Fr>>;

    /// Synthesize the circuit constraints
    fn synthesize<CS: ConstraintSynthesizer<Fr>>(&self) -> ZKResult<()>;
}

/// Gadget for hash comparison (used in governance circuits)
pub mod gadgets {
    use super::*;
    use ark_r1cs_std::eq::EqGadget;
    use ark_r1cs_std::fields::fp::FpVar;
    use ark_r1cs_std::fields::FieldVar as FieldVarTrait;

    /// Boolean variable gadget
    pub type BoolVar = Boolean<Fr>;

    /// Field variable gadget (alias for `FpVar<Fr>`)
    pub type FrVar = FpVar<Fr>;

    /// Enforce that two field variables are equal
    pub fn enforce_equal_field(
        _cs: ConstraintSystemRef<Fr>,
        a: &FrVar,
        b: &FrVar,
    ) -> Result<(), SynthesisError> {
        a.enforce_equal(b)
    }

    /// Enforce that a field variable equals a constant
    pub fn enforce_equal_constant(
        _cs: ConstraintSystemRef<Fr>,
        var: &FrVar,
        constant: Fr,
    ) -> Result<(), SynthesisError> {
        let constant_var = FrVar::constant(constant);
        var.enforce_equal(&constant_var)
    }

    /// Enforce boolean constraint (var is 0 or 1)
    pub fn enforce_boolean(
        cs: ConstraintSystemRef<Fr>,
        var: &FrVar,
    ) -> Result<BoolVar, SynthesisError> {
        // var * (1 - var) = 0
        // Equivalent to: var is 0 or 1
        use ark_ff::One;
        let one = FrVar::constant(Fr::one());
        let one_minus_var = &one - var;
        let product = var * &one_minus_var;
        let zero = FrVar::constant(Fr::from(0u64));
        product.enforce_equal(&zero)?;

        // Return as boolean
        let bool_var = Boolean::new_witness(cs, || {
            let val = var.value().unwrap_or_else(|_| Fr::from(0u64));
            Ok(val == Fr::one())
        })?;

        Ok(bool_var)
    }

    /// Number of bits for range proofs (supports values up to 2^64 - 1)
    pub const RANGE_PROOF_BITS: usize = 64;

    /// Decompose a field element into bits and enforce each bit is boolean.
    /// Returns the bit variables (LSB first).
    ///
    /// # UC Security Property
    /// This implements knowledge soundness: the prover must know a valid
    /// bit decomposition, proving the value is in [0, 2^num_bits).
    pub fn bit_decomposition(
        cs: ConstraintSystemRef<Fr>,
        value: &FrVar,
        num_bits: usize,
    ) -> Result<Vec<BoolVar>, SynthesisError> {
        use ark_ff::{BigInteger, PrimeField};

        let value_native = value.value().unwrap_or_else(|_| Fr::from(0u64));
        let bits_native = value_native.into_bigint().to_bits_le();

        let mut bit_vars = Vec::with_capacity(num_bits);
        let mut reconstructed = FrVar::constant(Fr::from(0u64));
        let mut power_of_two = FrVar::constant(Fr::from(1u64));
        let two = FrVar::constant(Fr::from(2u64));

        for i in 0..num_bits {
            // Get native bit value (default to false if out of range)
            let bit_val = bits_native.get(i).copied().unwrap_or(false);

            // Allocate bit as witness and enforce boolean constraint
            let bit_var = Boolean::new_witness(cs.clone(), || Ok(bit_val))?;
            bit_vars.push(bit_var.clone());

            // Reconstruct: reconstructed += bit * 2^i
            let bit_as_field = FrVar::from(bit_var);
            reconstructed = &reconstructed + &(&bit_as_field * &power_of_two);

            // Update power of two for next iteration
            power_of_two = &power_of_two * &two;
        }

        // Enforce that the reconstructed value equals the original
        // This ensures the bit decomposition is correct
        value.enforce_equal(&reconstructed)?;

        Ok(bit_vars)
    }

    /// Prove that a value is in range [0, 2^num_bits).
    ///
    /// # UC Security Property
    /// This is a complete range proof with knowledge soundness.
    /// The prover cannot succeed unless they know a value in the valid range.
    pub fn enforce_range(
        cs: ConstraintSystemRef<Fr>,
        value: &FrVar,
        num_bits: usize,
    ) -> Result<(), SynthesisError> {
        // Bit decomposition automatically enforces the range
        // because if value >= 2^num_bits, reconstruction will fail
        let _bits = bit_decomposition(cs, value, num_bits)?;
        Ok(())
    }

    /// Enforce that a >= b (for u64 range) with UC-secure range proof.
    ///
    /// # UC Security Property
    /// Uses bit decomposition to prove non-negativity of (a - b).
    /// Sound: prover cannot succeed if a < b.
    /// Complete: honest prover always succeeds if a >= b.
    /// Zero-knowledge: proof reveals nothing except a >= b.
    pub fn enforce_greater_or_equal(
        cs: ConstraintSystemRef<Fr>,
        a: &FrVar,
        b: &FrVar,
    ) -> Result<(), SynthesisError> {
        // Compute diff = a - b
        let diff = a - b;

        // Prove diff is in range [0, 2^64)
        // If a < b, diff would wrap around and exceed 2^64, failing the range check
        enforce_range(cs, &diff, RANGE_PROOF_BITS)?;

        Ok(())
    }

    /// Enforce that a > b (strict inequality).
    ///
    /// # UC Security Property
    /// Proves a - b - 1 is non-negative, i.e., a >= b + 1.
    pub fn enforce_greater_than(
        cs: ConstraintSystemRef<Fr>,
        a: &FrVar,
        b: &FrVar,
    ) -> Result<(), SynthesisError> {
        use ark_ff::One;

        // a > b <==> a - b - 1 >= 0
        let diff = a - b - FrVar::constant(Fr::one());
        enforce_range(cs, &diff, RANGE_PROOF_BITS)?;

        Ok(())
    }

    /// Enforce that a <= b.
    pub fn enforce_less_or_equal(
        cs: ConstraintSystemRef<Fr>,
        a: &FrVar,
        b: &FrVar,
    ) -> Result<(), SynthesisError> {
        enforce_greater_or_equal(cs, b, a)
    }

    /// Enforce that a < b.
    pub fn enforce_less_than(
        cs: ConstraintSystemRef<Fr>,
        a: &FrVar,
        b: &FrVar,
    ) -> Result<(), SynthesisError> {
        enforce_greater_than(cs, b, a)
    }

    /// Prove value is non-zero.
    ///
    /// # UC Security Property
    /// Uses multiplicative inverse to prove non-zero.
    pub fn enforce_non_zero(
        cs: ConstraintSystemRef<Fr>,
        value: &FrVar,
    ) -> Result<(), SynthesisError> {
        use ark_ff::Field;

        // Compute inverse
        let value_native = value.value().unwrap_or_else(|_| Fr::from(0u64));
        let inv_native = value_native.inverse().unwrap_or_else(|| Fr::from(1u64));

        // Allocate inverse as witness
        let inv_var = FrVar::new_witness(cs, || Ok(inv_native))?;

        // Enforce value * inv = 1
        let product = value * &inv_var;
        let one = FrVar::constant(Fr::from(1u64));
        product.enforce_equal(&one)?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ark_relations::r1cs::ConstraintSystem;

    #[test]
    fn test_circuit_builder_allocation() {
        let mut builder = CircuitBuilder::new("test_circuit");

        let pub1 = builder.alloc_public();
        let pub2 = builder.alloc_public();
        let priv1 = builder.alloc_private();

        assert!(pub1.is_public);
        assert!(pub2.is_public);
        assert!(!priv1.is_public);
        assert_eq!(builder.num_public_inputs, 2);
        assert_eq!(builder.num_private_witnesses, 1);
        assert_eq!(builder.num_variables(), 3);
    }

    #[test]
    fn test_circuit_builder_constraints() {
        let mut builder = CircuitBuilder::new("test_circuit");
        use ark_ff::One;

        let a = builder.alloc_public();
        let b = builder.alloc_private();
        let c = builder.alloc_private();

        // a * b = c
        builder.add_constraint(
            vec![(a.index, Fr::one())],
            vec![(b.index, Fr::one())],
            vec![(c.index, Fr::one())],
        );

        assert_eq!(builder.num_constraints(), 1);
    }

    #[test]
    fn test_bit_decomposition_small_value() {
        use gadgets::*;

        let cs = ConstraintSystem::<Fr>::new_ref();
        let value = FrVar::new_witness(cs.clone(), || Ok(Fr::from(42u64))).unwrap();

        let bits = bit_decomposition(cs.clone(), &value, 8).unwrap();

        // 42 = 0b00101010
        assert_eq!(bits.len(), 8);
        assert!(cs.is_satisfied().unwrap());
    }

    #[test]
    fn test_bit_decomposition_max_u64() {
        use gadgets::*;

        let cs = ConstraintSystem::<Fr>::new_ref();
        let max_val = u64::MAX;
        let value = FrVar::new_witness(cs.clone(), || Ok(Fr::from(max_val))).unwrap();

        let bits = bit_decomposition(cs.clone(), &value, 64).unwrap();

        assert_eq!(bits.len(), 64);
        assert!(cs.is_satisfied().unwrap());
    }

    #[test]
    fn test_enforce_range_valid() {
        use gadgets::*;

        let cs = ConstraintSystem::<Fr>::new_ref();
        let value = FrVar::new_witness(cs.clone(), || Ok(Fr::from(1000u64))).unwrap();

        let result = enforce_range(cs.clone(), &value, 16);
        assert!(result.is_ok());
        assert!(cs.is_satisfied().unwrap());
    }

    #[test]
    fn test_enforce_greater_or_equal_satisfied() {
        use gadgets::*;

        let cs = ConstraintSystem::<Fr>::new_ref();
        let a = FrVar::new_witness(cs.clone(), || Ok(Fr::from(100u64))).unwrap();
        let b = FrVar::new_witness(cs.clone(), || Ok(Fr::from(50u64))).unwrap();

        let result = enforce_greater_or_equal(cs.clone(), &a, &b);
        assert!(result.is_ok());
        assert!(cs.is_satisfied().unwrap());
    }

    #[test]
    fn test_enforce_greater_or_equal_equal_values() {
        use gadgets::*;

        let cs = ConstraintSystem::<Fr>::new_ref();
        let a = FrVar::new_witness(cs.clone(), || Ok(Fr::from(100u64))).unwrap();
        let b = FrVar::new_witness(cs.clone(), || Ok(Fr::from(100u64))).unwrap();

        let result = enforce_greater_or_equal(cs.clone(), &a, &b);
        assert!(result.is_ok());
        assert!(cs.is_satisfied().unwrap());
    }

    #[test]
    fn test_enforce_greater_than_satisfied() {
        use gadgets::*;

        let cs = ConstraintSystem::<Fr>::new_ref();
        let a = FrVar::new_witness(cs.clone(), || Ok(Fr::from(100u64))).unwrap();
        let b = FrVar::new_witness(cs.clone(), || Ok(Fr::from(50u64))).unwrap();

        let result = enforce_greater_than(cs.clone(), &a, &b);
        assert!(result.is_ok());
        assert!(cs.is_satisfied().unwrap());
    }

    #[test]
    fn test_enforce_non_zero() {
        use gadgets::*;

        let cs = ConstraintSystem::<Fr>::new_ref();
        let value = FrVar::new_witness(cs.clone(), || Ok(Fr::from(42u64))).unwrap();

        let result = enforce_non_zero(cs.clone(), &value);
        assert!(result.is_ok());
        assert!(cs.is_satisfied().unwrap());
    }

    #[test]
    fn test_enforce_less_than_satisfied() {
        use gadgets::*;

        let cs = ConstraintSystem::<Fr>::new_ref();
        let a = FrVar::new_witness(cs.clone(), || Ok(Fr::from(50u64))).unwrap();
        let b = FrVar::new_witness(cs.clone(), || Ok(Fr::from(100u64))).unwrap();

        let result = enforce_less_than(cs.clone(), &a, &b);
        assert!(result.is_ok());
        assert!(cs.is_satisfied().unwrap());
    }
}
