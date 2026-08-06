//! Unified error types for WarmLogic Rust Core.
//!
//! This module provides structured error types using `thiserror` for
//! better error handling and propagation.

use thiserror::Error;

#[cfg(not(feature = "std"))]
use alloc::string::{String, ToString};

/// Core WarmLogic error type
#[derive(Debug, Error)]
#[non_exhaustive]
pub enum WarmLogicError {
    /// Cryptographic operation failed
    #[error("crypto error: {0}")]
    Crypto(String),

    /// Ledger operation failed
    #[error("ledger error: {0}")]
    Ledger(String),

    /// Consensus protocol error
    #[error("consensus error: {0}")]
    Consensus(String),

    /// Hardware security module error
    #[error("HSM error: {0}")]
    Hsm(String),

    /// Network/DHT operation failed
    #[error("network error: {0}")]
    Network(String),

    /// Storage operation failed
    #[error("storage error: {0}")]
    Storage(String),

    /// Zero-knowledge proof error
    #[error("ZK error: {0}")]
    Zk(String),

    /// Configuration error
    #[error("config error: {0}")]
    Config(String),

    /// Serialization/deserialization error
    #[error("serialization error: {0}")]
    Serialization(String),

    /// Invalid input provided
    #[error("invalid input: {0}")]
    InvalidInput(String),

    /// Operation not supported
    #[error("not supported: {0}")]
    NotSupported(String),

    /// Internal error (should not happen)
    #[error("internal error: {0}")]
    Internal(String),
}

/// Result type alias using WarmLogicError
pub type WarmLogicResult<T> = Result<T, WarmLogicError>;

/// Hardware-specific errors
#[derive(Debug, Error)]
#[non_exhaustive]
pub enum HardwareError {
    /// Secure Enclave not available
    #[error("Secure Enclave not available: {0}")]
    SecureEnclaveUnavailable(String),

    /// TPM not available
    #[error("TPM not available: {0}")]
    TpmUnavailable(String),

    /// vHSM operation failed
    #[error("vHSM error: {0}")]
    VHsmError(String),

    /// Key generation failed
    #[error("key generation failed: {0}")]
    KeyGeneration(String),

    /// Signing operation failed
    #[error("signing failed: {0}")]
    SigningFailed(String),

    /// Verification failed
    #[error("verification failed: {0}")]
    VerificationFailed(String),

    /// Sealing/unsealing failed
    #[error("seal/unseal failed: {0}")]
    SealUnsealFailed(String),
}

impl From<HardwareError> for WarmLogicError {
    fn from(err: HardwareError) -> Self {
        WarmLogicError::Hsm(err.to_string())
    }
}

/// Consensus-specific errors
#[derive(Debug, Error)]
#[non_exhaustive]
pub enum ConsensusError {
    /// Vote was rejected
    #[error("vote rejected: {0}")]
    VoteRejected(String),

    /// Invalid signature
    #[error("invalid signature")]
    InvalidSignature,

    /// Round mismatch
    #[error("round mismatch: expected {expected}, got {got}")]
    RoundMismatch { expected: u64, got: u64 },

    /// Block hash mismatch
    #[error("vote for wrong block")]
    WrongBlock,

    /// Max votes exceeded
    #[error("max votes per round exceeded")]
    MaxVotesExceeded,
}

impl From<ConsensusError> for WarmLogicError {
    fn from(err: ConsensusError) -> Self {
        WarmLogicError::Consensus(err.to_string())
    }
}

/// Network-specific errors
#[derive(Debug, Error)]
#[non_exhaustive]
pub enum NetworkError {
    /// Peer verification failed
    #[error("peer verification failed: {0}")]
    PeerVerificationFailed(String),

    /// Connection failed
    #[error("connection failed: {0}")]
    ConnectionFailed(String),

    /// Rate limited
    #[error("rate limited: {0}")]
    RateLimited(String),

    /// Invalid node ID
    #[error("invalid node ID: {0}")]
    InvalidNodeId(String),

    /// Network not started
    #[error("network not started")]
    NotStarted,
}

impl From<NetworkError> for WarmLogicError {
    fn from(err: NetworkError) -> Self {
        WarmLogicError::Network(err.to_string())
    }
}

/// Convert from String errors for backwards compatibility
impl From<String> for WarmLogicError {
    fn from(s: String) -> Self {
        WarmLogicError::Internal(s)
    }
}

impl From<&str> for WarmLogicError {
    fn from(s: &str) -> Self {
        WarmLogicError::Internal(s.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_display() {
        let err = WarmLogicError::Crypto("key generation failed".to_string());
        assert_eq!(format!("{}", err), "crypto error: key generation failed");
    }

    #[test]
    fn test_hardware_error_conversion() {
        let hw_err = HardwareError::SecureEnclaveUnavailable("not macOS".to_string());
        let wl_err: WarmLogicError = hw_err.into();
        assert!(matches!(wl_err, WarmLogicError::Hsm(_)));
    }

    #[test]
    fn test_consensus_error_conversion() {
        let cons_err = ConsensusError::RoundMismatch {
            expected: 5,
            got: 3,
        };
        let wl_err: WarmLogicError = cons_err.into();
        assert!(matches!(wl_err, WarmLogicError::Consensus(_)));
    }

    #[test]
    fn test_string_conversion() {
        let err: WarmLogicError = "something went wrong".into();
        assert!(matches!(err, WarmLogicError::Internal(_)));
    }
}
