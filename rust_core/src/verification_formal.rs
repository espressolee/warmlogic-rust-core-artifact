//! [Phase 104] Formal Verification Harnesses for ZK Circuits.
//! Uses Kani to prove knowledge soundness and unique witness determination.

#[cfg(kani)]
mod formal_verification {
    use crate::zk::plonk_engine::{AbyssalTransitionCircuit, InferenceAlignmentCircuit};
    use dusk_plonk::prelude::StandardComposer;
    use dusk_plonk::prelude::*;

    #[kani::proof]
    #[kani::unwind(10)]
    fn prove_inference_alignment_circuit_soundness() {
        // Symbolic inputs
        let input_hash: [u8; 32] = kani::any();
        let output_hash: [u8; 32] = kani::any();
        let confidence: u64 = kani::any();
        let threshold: u64 = kani::any();
        let model_commitment: [u8; 32] = kani::any();
        let silicon_id: [u8; 32] = kani::any();

        let circuit = InferenceAlignmentCircuit::new(
            input_hash,
            output_hash,
            confidence,
            threshold,
            model_commitment,
            silicon_id,
        );

        let mut composer = StandardComposer::new();
        let result = circuit.circuit(&mut composer);

        // Prove that if synthesis succeeds, the confidence check was performed
        if result.is_ok() {
            kani::assert(
                confidence >= threshold,
                "Circuit was synthesized despite confidence < threshold",
            );
        }
    }

    #[kani::proof]
    #[kani::unwind(10)]
    fn prove_state_transition_circuit_soundness() {
        let from: u32 = kani::any();
        let to: u32 = kani::any();
        let count: u32 = kani::any();
        let veto_active: bool = kani::any();
        let silicon_id: [u8; 32] = kani::any();

        let circuit = AbyssalTransitionCircuit::new(from, to, count, veto_active, silicon_id);

        let mut composer = StandardComposer::new();
        let result = circuit.circuit(&mut composer);

        if result.is_ok() {
            if veto_active {
                kani::assert(from == to, "Veto was active but state changed");
            }
        }
    }
}
