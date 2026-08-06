use crate::zk::ml::quantized_gadget::ArkQuantizedGadget;
use crate::zk::types::Fr;
use ark_r1cs_std::alloc::AllocVar;
use ark_r1cs_std::fields::fp::FpVar;
use ark_relations::r1cs::{ConstraintSynthesizer, ConstraintSystemRef, SynthesisError};

/// Represents an 8-bit Quantized Multi-Layer Perceptron (MLP).
/// Specifically designed to enforce valid inference logic on 8-bit weights and activations.
#[derive(Clone)]
pub struct MLPCircuit {
    /// Flattened input vector (private)
    pub inputs: Vec<u64>,
    /// Hidden layer weights (public) [hidden_dim][input_dim]
    pub w_hidden: Vec<Vec<u64>>,
    /// Hidden layer biases (public) [hidden_dim]
    pub b_hidden: Vec<u64>,
    /// Output layer weights (public) [output_dim][hidden_dim]
    pub w_out: Vec<Vec<u64>>,
    /// Output layer biases (public) [output_dim]
    pub b_out: Vec<u64>,
    /// Fixed-point scaling factor (e.g., 128 for 7 fractional bits)
    pub q_scale: u64,
}

impl ConstraintSynthesizer<Fr> for MLPCircuit {
    fn generate_constraints(self, cs: ConstraintSystemRef<Fr>) -> Result<(), SynthesisError> {
        let input_dim = self.inputs.len();
        let hidden_dim = self.b_hidden.len();
        let output_dim = self.b_out.len();

        // 1. Allocate inputs (Private Variables)
        let mut input_vars = Vec::with_capacity(input_dim);
        for i in 0..input_dim {
            let var = FpVar::new_witness(cs.clone(), || Ok(Fr::from(self.inputs[i])))?;
            // Enforce input sits in 8-bit range
            ArkQuantizedGadget::enforce_u8_range(cs.clone(), &var)?;
            input_vars.push(var);
        }

        // 2. Hidden Layer Calculation
        let mut hidden_vars = Vec::with_capacity(hidden_dim);
        for i in 0..hidden_dim {
            // base = bias
            let bias_var = FpVar::new_input(cs.clone(), || Ok(Fr::from(self.b_hidden[i])))?;
            // Ensure bias is within 8-bit range
            ArkQuantizedGadget::enforce_u8_range(cs.clone(), &bias_var)?;

            let mut accumulator = bias_var;

            // MAC operation: accumulator += (weight * input) / q_scale
            for j in 0..input_dim {
                let weight_var =
                    FpVar::new_input(cs.clone(), || Ok(Fr::from(self.w_hidden[i][j])))?;
                ArkQuantizedGadget::enforce_u8_range(cs.clone(), &weight_var)?;

                let mac_term = ArkQuantizedGadget::mul_and_scale(
                    cs.clone(),
                    &weight_var,
                    &input_vars[j],
                    self.q_scale,
                )?;
                accumulator = ArkQuantizedGadget::add(cs.clone(), &accumulator, &mac_term)?;
            }

            // ReLU Activation
            ArkQuantizedGadget::enforce_u8_range(cs.clone(), &accumulator)?;
            hidden_vars.push(accumulator);
        }

        // 3. Output Layer Calculation
        let mut output_vars = Vec::with_capacity(output_dim);
        for i in 0..output_dim {
            let bias_var = FpVar::new_input(cs.clone(), || Ok(Fr::from(self.b_out[i])))?;
            ArkQuantizedGadget::enforce_u8_range(cs.clone(), &bias_var)?;

            let mut accumulator = bias_var;

            // MAC operation
            for j in 0..hidden_dim {
                let weight_var = FpVar::new_input(cs.clone(), || Ok(Fr::from(self.w_out[i][j])))?;
                ArkQuantizedGadget::enforce_u8_range(cs.clone(), &weight_var)?;

                let mac_term = ArkQuantizedGadget::mul_and_scale(
                    cs.clone(),
                    &weight_var,
                    &hidden_vars[j],
                    self.q_scale,
                )?;
                accumulator = ArkQuantizedGadget::add(cs.clone(), &accumulator, &mac_term)?;
            }

            // Enforce final output in 8-bit range
            ArkQuantizedGadget::enforce_u8_range(cs.clone(), &accumulator)?;
            output_vars.push(accumulator);
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ark_relations::r1cs::ConstraintSystem;

    #[test]
    fn test_mlp_circuit_satisfaction() {
        let q_scale = 128;

        let circuit = MLPCircuit {
            inputs: vec![64, 64],
            w_hidden: vec![vec![64, 64], vec![128, 0]],
            b_hidden: vec![0, 0],
            w_out: vec![vec![128, 128]],
            b_out: vec![0],
            q_scale,
        };

        let cs = ConstraintSystem::<Fr>::new_ref();
        circuit.generate_constraints(cs.clone()).unwrap();

        assert!(cs.is_satisfied().unwrap());
        println!(
            "Number of constraints for 2-2-1 MLP: {}",
            cs.num_constraints()
        );
    }
}
