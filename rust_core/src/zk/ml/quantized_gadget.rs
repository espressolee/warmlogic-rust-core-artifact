use crate::zk::circuit::gadgets;
use crate::zk::types::Fr;
use ark_r1cs_std::fields::fp::FpVar;
use ark_r1cs_std::fields::FieldVar;
use ark_r1cs_std::{alloc::AllocVar, eq::EqGadget, R1CSVar};
use ark_relations::r1cs::{ConstraintSystemRef, SynthesisError};

/// Gadget representing an 8-bit quantized tensor or field element execution.
/// Follows Sovereign Purity principles by enforcing perfect mathematical boundaries.
pub struct ArkQuantizedGadget;

impl ArkQuantizedGadget {
    /// Enforces that a given field variable represents a valid 8-bit unsigned integer [0, 255].
    pub fn enforce_u8_range(
        cs: ConstraintSystemRef<Fr>,
        val: &FpVar<Fr>,
    ) -> Result<(), SynthesisError> {
        gadgets::enforce_range(cs, val, 8)
    }

    /// Enforces that a given field variable represents a valid 8-bit signed integer [-128, 127].
    /// In the prime field, we shift this by 128: `val_shifted = val + 128`, and assert `0 <= val_shifted <= 255`.
    pub fn enforce_i8_range(
        cs: ConstraintSystemRef<Fr>,
        val: &FpVar<Fr>,
    ) -> Result<(), SynthesisError> {
        // Construct the constant 128
        let shift = FpVar::constant(Fr::from(128u64));
        // Shift the value to the positive u8 domain.
        let val_shifted = val + shift;
        // Verify it sits comfortably in [0, 255]
        gadgets::enforce_range(cs, &val_shifted, 8)
    }

    /// Performs multiplication and simulates 8-bit fixed-point scaling.
    /// Computes: `(a * b) / Q_SCALE` with truncation/rounding logic in ZK constraints.
    /// Because exact division in R1CS requires quotient/remainder witnesses,
    /// we define `a * b = result * Q_SCALE + rem`, where `rem < Q_SCALE`.
    pub fn mul_and_scale(
        cs: ConstraintSystemRef<Fr>,
        a: &FpVar<Fr>,
        b: &FpVar<Fr>,
        q_scale: u64,
    ) -> Result<FpVar<Fr>, SynthesisError> {
        // Compute the native product
        let a_val = a.value().unwrap_or_else(|_| Fr::from(0u64));
        let b_val = b.value().unwrap_or_else(|_| Fr::from(0u64));
        use ark_ff::PrimeField;

        // This is a simplified 8-bit scaling logic.
        // Convert to signed integers for scaling to simulate a real ML framework.
        // Correct conversion for 8-bit prototype scaling:
        let a_int = a_val.into_bigint().as_ref()[0] as u64;
        let b_int = b_val.into_bigint().as_ref()[0] as u64;
        let product_int = a_int * b_int;
        let quotient_int = product_int / q_scale;
        let rem_int = product_int % q_scale;

        // Allocate quotient and remainder as witnesses
        let quotient = FpVar::new_witness(cs.clone(), || Ok(Fr::from(quotient_int)))?;
        let rem = FpVar::new_witness(cs.clone(), || Ok(Fr::from(rem_int)))?;

        // Construct scale constant
        let scale_var = FpVar::constant(Fr::from(q_scale));

        // Constraint 1: a * b = quotient * Q_SCALE + rem
        let product = a * b;
        let reconstructed = (&quotient * &scale_var) + &rem;
        product.enforce_equal(&reconstructed)?;

        // Constraint 2: rem < Q_SCALE
        // Since we are dealing with non-negative constraints here,
        // we enforce that rem is bounded [0, q_scale)
        // A minimal range check suffices since Q_SCALE is small (e.g., 128)
        gadgets::enforce_range(cs.clone(), &rem, 8)?;
        gadgets::enforce_less_than(cs, &rem, &scale_var)?;

        Ok(quotient)
    }

    /// Adds two quantized field variables together.
    pub fn add(
        _cs: ConstraintSystemRef<Fr>,
        a: &FpVar<Fr>,
        b: &FpVar<Fr>,
    ) -> Result<FpVar<Fr>, SynthesisError> {
        Ok(a + b)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ark_relations::r1cs::ConstraintSystem;

    #[test]
    fn test_enforce_u8_range() {
        let cs = ConstraintSystem::<Fr>::new_ref();
        let valid_val = FpVar::new_witness(cs.clone(), || Ok(Fr::from(200u64))).unwrap();
        ArkQuantizedGadget::enforce_u8_range(cs.clone(), &valid_val).unwrap();
        assert!(cs.is_satisfied().unwrap());

        let cs2 = ConstraintSystem::<Fr>::new_ref();
        let invalid_val = FpVar::new_witness(cs2.clone(), || Ok(Fr::from(256u64))).unwrap();
        ArkQuantizedGadget::enforce_u8_range(cs2.clone(), &invalid_val).unwrap();
        assert!(!cs2.is_satisfied().unwrap());
    }

    #[test]
    fn test_mul_and_scale() {
        let cs = ConstraintSystem::<Fr>::new_ref();
        // Assume Q=128 (7 fractional bits)
        // a = 64 (0.5), b = 64 (0.5). a * b = 4096. 4096 / 128 = 32 (0.25).
        let a = FpVar::new_witness(cs.clone(), || Ok(Fr::from(64u64))).unwrap();
        let b = FpVar::new_witness(cs.clone(), || Ok(Fr::from(64u64))).unwrap();

        let quotient = ArkQuantizedGadget::mul_and_scale(cs.clone(), &a, &b, 128).unwrap();
        assert!(cs.is_satisfied().unwrap());
        assert_eq!(quotient.value().unwrap(), Fr::from(32u64));
    }
}
