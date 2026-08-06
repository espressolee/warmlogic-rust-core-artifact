//! Sovereign ABI v1.0
//!
//! Defines the strict schema for INTER-PROCESS communication between
//! the Sovereign Kernel and external agents (Python, WASM, etc).
//!
//! Stability Guarantee: Verified

use serde::{Deserialize, Serialize};

#[cfg(feature = "python")]
use pyo3::prelude::*;

/// Standardized intent format for all agents
#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "python", pyclass)]
#[repr(C)]
pub struct SovereignIntent {
    /// Integrity of the agent (Principal ID)
    pub agent_id: String,
    /// Type of action (e.g. "fs_write", "net_connect")
    pub action_type: String,
    /// Action parameters (JSON or Bincode bytes)
    pub payload: String,
    /// Cryptographic signature (optional for research prototype, mandatory for v1.0)
    pub signature: Option<String>,
    /// Cryptographic proofs or other metadata
    pub metadata: Vec<u8>,
}

#[cfg(feature = "python")]
#[pymethods]
impl SovereignIntent {
    #[new]
    #[pyo3(signature = (agent_id, action_type, payload, signature=None))]
    pub fn py_new(
        agent_id: String,
        action_type: String,
        payload: String,
        signature: Option<String>,
    ) -> Self {
        Self {
            agent_id,
            action_type,
            payload,
            signature,
            metadata: Vec::new(),
        }
    }
}

impl SovereignIntent {
    #[must_use]
    pub fn new(agent_id: String, action_type: String, payload: String) -> Self {
        Self {
            agent_id,
            action_type,
            payload,
            signature: None,
            metadata: Vec::new(),
        }
    }

    #[must_use]
    pub fn with_signature(mut self, signature: String) -> Self {
        self.signature = Some(signature);
        self
    }
}

/// Standardized verdict format from the Kernel
#[derive(Debug, Clone, Serialize, Deserialize)]
#[cfg_attr(feature = "python", pyclass)]
#[repr(C)]
pub struct SovereignVerdict {
    /// Whether the action is permitted
    pub is_allowed: bool,
    /// Explanation or Policy ID citation
    pub reason: String,
    /// Deterministic Verdict Enum String (e.g. "Allow", "VetoLock")
    pub verdict_type: String,
    /// Hash of the verdict for ZK linking
    pub verdict_hash: [u8; 32],
    /// Cryptographic proof of the decision (Merkle Root or ZK Hash)
    pub proof_hash: Option<[u8; 32]>,
}

#[cfg(feature = "python")]
#[pymethods]
impl SovereignVerdict {
    #[getter]
    pub fn is_allowed(&self) -> bool {
        self.is_allowed
    }

    #[getter]
    pub fn reason(&self) -> String {
        self.reason.clone()
    }

    #[getter]
    pub fn proof_hash_hex(&self) -> Option<String> {
        self.proof_hash.map(hex::encode)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_intent_serialization() {
        let intent = SovereignIntent::new(
            "agent_007".to_string(),
            "read_file".to_string(),
            "{ \"path\": \"/etc/shadow\" }".to_string(),
        );

        let json = serde_json::to_string(&intent).unwrap();
        assert!(json.contains("agent_007"));
        assert!(json.contains("read_file"));

        let deserialized: SovereignIntent = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.agent_id, "agent_007");
    }

    #[test]
    fn test_verdict_serialization() {
        let verdict = SovereignVerdict {
            is_allowed: false,
            reason: "Policy Breach".to_string(),
            verdict_type: "VetoLock".to_string(),
            verdict_hash: [0u8; 32],
            proof_hash: Some([0u8; 32]),
        };

        let json = serde_json::to_string(&verdict).unwrap();
        assert!(json.contains("VetoLock"));

        let deserialized: SovereignVerdict = serde_json::from_str(&json).unwrap();
        assert!(!deserialized.is_allowed);
        assert_eq!(deserialized.verdict_type, "VetoLock");
    }
}
