//! # WarmLogic ZK-SNARK Module (Phase B1)
//!
//! Production-grade zero-knowledge proof system for governance decisions.
//! Uses arkworks Groth16 on BLS12-381 curve.
//!
//! ## Architecture
//!
//! ```text
//! +----------------------------------------------------------+
//! |                    ZK Proof Flow                          |
//! +----------------------------------------------------------+
//! |  Governance Decision                                      |
//! |        |                                                  |
//! |        v                                                  |
//! |  +-----------+     +-----------+     +-------------+     |
//! |  | Circuit   | --> | Witness   | --> | Groth16     |     |
//! |  | (R1CS)    |     | (Private) |     | Proof       |     |
//! |  +-----------+     +-----------+     +-------------+     |
//! |        |                                   |              |
//! |        v                                   v              |
//! |  +-----------+                      +-------------+      |
//! |  | Public    |                      | Evidence    |      |
//! |  | Inputs    | -------------------> | Bundle      |      |
//! |  +-----------+                      +-------------+      |
//! +----------------------------------------------------------+
//! ```
//!
//! ## Circuits
//!
//! - `GovernanceCircuit`: Proves policy compliance without revealing decision details
//! - `VetoCircuit`: Proves valid veto authority
//! - `QuorumCircuit`: Proves consensus threshold reached
//! - `ComplianceCircuit`: Proves regulatory compliance
//!
//! ## Usage
//!
//! ```rust,ignore
//! use warm_logic_rs::zk::{GovernanceCircuit, Prover, Verifier};
//!
//! // Create circuit for governance decision
//! let circuit = GovernanceCircuit::new(decision, policy);
//!
//! // Generate proof
//! let proof = Prover::prove(&circuit, &proving_key)?;
//!
//! // Verify proof (anyone can verify with public inputs only)
//! let valid = Verifier::verify(&proof, &public_inputs, &verifying_key)?;
//! ```

// Note: Feature gate is in lib.rs (#[cfg(feature = "zk")] pub mod zk;)

pub mod aggregator;
pub mod circuit;
pub mod error;
pub mod inference_witness;
pub mod isa_circuit;
pub mod ml;
pub mod prover;
pub mod recovery_circuit;
pub mod recursive;
pub mod transition;
pub mod types;
pub mod verifier;
pub mod zk_governance;

#[cfg(feature = "python")]
pub mod python;
#[cfg(feature = "python")]
pub use python::{PyRecoveryProver, PyZKGovernanceProver, PyZKTransitionProver};

// Re-exports for convenience
pub use self::zk_governance::{
    AttestationCircuit, CapabilityProofCircuit, GovernanceCircuit, QuorumCircuit, VetoCircuit,
};
pub use circuit::{CircuitBuilder, Constraint, Variable};
pub use error::{ZKError, ZKResult};
pub use prover::Prover;
pub use recovery_circuit::StateSnapshotCircuit;
pub use transition::KernelStateTransitionCircuit;
pub use types::{Fr, Proof, ProvingKey, VerifyingKey, ZKProof, G1, G2};
pub use verifier::Verifier;

#[cfg(test)]
mod tests;
