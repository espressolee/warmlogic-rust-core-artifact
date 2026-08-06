//! Raft Data Types
//!
//! Shared core structures for Raft consensus engine and storage.

use borsh::{BorshDeserialize, BorshSerialize};
use serde::{Deserialize, Serialize};

#[cfg(feature = "python")]
#[cfg(feature = "python")]
use crate::pyo3::prelude::*;

#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Serialize, Deserialize, BorshSerialize, BorshDeserialize, Debug, Clone)]
pub struct LogEntry {
    pub term: u64,
    pub data: String,
    pub signature: String,
    pub voter_id: String,
    pub cumulative_hash: String,
    pub poseidon_hash: String,
    pub zk_proof: Vec<u8>, // [Phase 29] Axiomatic truth proof for the transition
    #[serde(default)]
    pub index: usize,
}

#[cfg(feature = "python")]
#[pymethods]
impl LogEntry {
    #[new]
    pub fn new(
        term: u64,
        data: String,
        signature: String,
        voter_id: String,
        cumulative_hash: String,
        poseidon_hash: String,
        zk_proof: Vec<u8>,
    ) -> Self {
        LogEntry {
            term,
            data,
            signature,
            voter_id,
            cumulative_hash,
            poseidon_hash,
            zk_proof,
            index: 0,
        }
    }
}

#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Serialize, Deserialize, BorshSerialize, BorshDeserialize, Debug, Clone)]
pub struct RaftRPC {
    pub rpc_type: String, // "AppendEntries", "RequestVote", "InstallSnapshot"
    pub term: u64,
    pub sender_id: String,
    pub target_id: Option<String>, // Some(id) for unicast, None for broadcast
    pub payload: String,           // JSON-encoded specifics
    pub signature: String,
    pub poseidon_hash: String,
}

#[cfg(feature = "python")]
#[pymethods]
impl RaftRPC {
    #[new]
    #[pyo3(signature = (rpc_type, term, sender_id, payload, signature, poseidon_hash="".to_string(), target_id=None))]
    pub fn new(
        rpc_type: String,
        term: u64,
        sender_id: String,
        payload: String,
        signature: String,
        poseidon_hash: String,
        target_id: Option<String>,
    ) -> Self {
        RaftRPC {
            rpc_type,
            term,
            sender_id,
            payload,
            signature,
            target_id,
            poseidon_hash,
        }
    }
}

#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Serialize, Deserialize, BorshSerialize, BorshDeserialize, Debug, Clone)]
pub struct RaftSnapshot {
    pub data: String, // State machine data
    pub last_included_index: usize,
    pub last_included_term: u64,
    pub cumulative_hash: String,
    pub poseidon_hash: String,
}

#[cfg_attr(feature = "python", pyclass(eq, eq_int))]
#[derive(
    Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, BorshSerialize, BorshDeserialize,
)]
pub enum RaftState {
    Follower,
    Candidate,
    Leader,
}

#[cfg(feature = "python")]
#[pymethods]
impl RaftState {
    #[getter]
    pub fn name(&self) -> String {
        format!("{:?}", self)
    }
}

#[derive(Serialize, Deserialize, BorshSerialize, BorshDeserialize, Debug, Clone)]
pub struct RaftMetadata {
    pub current_term: u64,
    pub voted_for: Option<String>,
    #[serde(default)]
    pub peers: Vec<String>, // Persist swarm configuration
}
