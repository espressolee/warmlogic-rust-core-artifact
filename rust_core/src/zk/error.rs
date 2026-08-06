//! ZK error types for WarmLogic.

use thiserror::Error;

/// Result type for ZK operations
pub type ZKResult<T> = Result<T, ZKError>;

/// ZK operation errors
#[derive(Debug, Clone, Error)]
#[non_exhaustive]
pub enum ZKError {
    /// Circuit constraint violation
    #[error("Constraint violation: {0}")]
    ConstraintViolation(String),
    /// Witness generation failed
    #[error("Circuit error: {0}")]
    CircuitError(String),
    #[error("Simulation Detected: {0}")]
    SimulationDetected(String),
    /// Proving error
    #[error("Proving error: {0}")]
    ProvingError(String),
    /// Proof verification failed
    #[error("Proof verification failed")]
    VerificationFailed,
    /// Serialization error
    #[error("Serialization error: {0}")]
    SerializationError(String),
    /// Invalid public inputs
    #[error("Invalid public inputs: {0}")]
    InvalidPublicInputs(String),
    /// Setup error (trusted setup)
    #[error("Setup error: {0}")]
    SetupError(String),
    /// Circuit not found
    #[error("Circuit not found: {0}")]
    CircuitNotFound(String),
    /// Invalid parameters
    #[error("Invalid parameters: {0}")]
    InvalidParameters(String),
    /// Kernel state transition invariant violation
    #[error("State transition violation: {0}")]
    StateTransitionViolation(String),
    /// Invalid witness data (attestation circuit)
    #[error("Invalid witness: {0}")]
    InvalidWitness(String),
    /// Witness generation failure
    #[error("Witness generation failed: {0}")]
    WitnessError(String),
}

impl From<ark_serialize::SerializationError> for ZKError {
    fn from(err: ark_serialize::SerializationError) -> Self {
        Self::SerializationError(format!("{:?}", err))
    }
}

impl From<ark_relations::r1cs::SynthesisError> for ZKError {
    fn from(err: ark_relations::r1cs::SynthesisError) -> Self {
        Self::ConstraintViolation(format!("{:?}", err))
    }
}
