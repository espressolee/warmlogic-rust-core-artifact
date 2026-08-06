//! rust_core/src/net/gossip.rs
//! Phase 4: Decentralized Collective Sovereign Gossip.
//!
//! Added Block Propagation messages for true P2P consensus.

use crate::net::kademlia::NodeId;
use serde::{Deserialize, Serialize};

#[cfg(feature = "python")]
use serde_json;

// ============================================================================
// BLOCK PROPAGATION MESSAGES
// ============================================================================

/// Block proposal from the current leader.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockProposal {
    /// View number (for View Change protocol)
    pub view: u64,
    /// Round number within the view
    pub round: u64,
    /// Leader node ID
    pub leader_id: NodeId,
    /// Block hash
    pub block_hash: [u8; 32],
    /// Block data (serialized transactions, state root, etc.)
    pub block_data: Vec<u8>,
    /// Previous block hash
    pub prev_hash: [u8; 32],
    /// Timestamp (Unix epoch milliseconds)
    pub timestamp_ms: u64,
    /// Leader's ML-DSA-65 signature over the block
    pub signature: Vec<u8>,
    /// [Phase 32] ZK-Temporal Anchor Proof (None = proof not yet generated)
    /// [Phase 2.2] Changed to Option to make empty proof state explicit
    pub temporal_proof: Option<Vec<u8>>,
}

/// Vote on a block proposal.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockVote {
    /// View number
    pub view: u64,
    /// Round number
    pub round: u64,
    /// Voter node ID
    pub voter_id: NodeId,
    /// Block hash being voted on
    pub block_hash: [u8; 32],
    /// Voter's ML-DSA-65 signature
    pub signature: Vec<u8>,
}

/// Announcement that a block has been committed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockCommit {
    /// View number
    pub view: u64,
    /// Round number
    pub round: u64,
    /// Committed block hash
    pub block_hash: [u8; 32],
    /// Quorum of vote signatures (proof of consensus)
    pub vote_signatures: Vec<BlockVote>,
    /// State root after this block
    pub state_root: [u8; 32],
}

/// View Change message for P2P broadcast.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct P2PViewChange {
    /// New view being proposed
    pub new_view: u64,
    /// Sender node ID
    pub sender_id: NodeId,
    /// Last prepared round in previous view
    pub last_prepared_round: Option<u64>,
    /// Last prepared block hash
    pub last_prepared_block: Option<[u8; 32]>,
    /// Timestamp
    pub timestamp_ms: u64,
    /// ML-DSA-65 signature
    pub signature: Vec<u8>,
    /// [Phase 32] ZK-Temporal Anchor Proof (None = proof not yet generated)
    /// [Phase 2.2] Changed to Option to make empty proof state explicit
    pub temporal_proof: Option<Vec<u8>>,
}

/// New View message from the new leader.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct P2PNewView {
    /// New view number
    pub view: u64,
    /// New leader node ID
    pub leader_id: NodeId,
    /// View change proofs (signatures from quorum of nodes)
    pub view_change_proofs: Vec<P2PViewChange>,
    /// Starting round for new view
    pub starting_round: u64,
    /// Prepared block to continue from (if any)
    pub prepared_block: Option<[u8; 32]>,
    /// Leader's signature
    pub signature: Vec<u8>,
}

// ============================================================================
// GOSSIP MESSAGE ENUM
// ============================================================================

/// Governance Gossip Message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum GossipMessage {
    /// Propagation of a local VETO_LOCK event
    VetoLocked {
        sender_id: NodeId,
        tick: u64,
        reason: String,
        context_hash: [u8; 32],
        /// Mandatory PQC signature from the sender
        signature: Vec<u8>,
    },
    /// Verifiable Governance decision propagation
    GovernanceDecisionBroadcast {
        decision: crate::governance::GovernanceDecision,
        node_id: [u8; 32],
    },
    /// Propagation of a multi-sig reset fragment
    VetoResetFragment {
        sender_id: NodeId,
        public_key: Vec<u8>,
        signature: Vec<u8>,
    },
    /// Request for current governance state (for late joiners)
    StateRequest { requester_id: NodeId },
    /// DHT: Store a value
    Store {
        key: [u8; 32],
        value: Vec<u8>,
        /// Mandatory PQC signature covering (key, value)
        signature: Vec<u8>,
    },
    /// DHT: Find a value
    FindValue { key: [u8; 32] },
    /// DHT: FindValue Response
    FoundValue { key: [u8; 32], value: Vec<u8> },
    /// Kademlia: Find closest nodes to target
    FindNode { target: NodeId },
    /// Kademlia: FindNode Response
    FoundNodes {
        target: NodeId,
        nodes: Vec<crate::net::kademlia::Peer>,
    },
    /// Handshake request with PoW puzzle
    Handshake {
        sender_id: NodeId,
        public_key: Vec<u8>,
        silicon_id: [u8; 32], // [Phase 29] Physical Identity binding
        nonce: u64,
        /// Optional: Fleet name or challenge nonce
        fleet_token: String,
    },
    /// Handshake Response (Acknowledge)
    HandshakeAck {
        responder_id: NodeId,
        silicon_id: [u8; 32], // [Phase 29] Reciprocal binding
        head_hash: [u8; 32],
    },
    /// Request missing Merkle-DAG blocks
    DagSyncRequest { missing_hashes: Vec<[u8; 32]> },
    /// Response with Merkle-DAG blocks
    DagSyncResponse {
        blocks: Vec<crate::net::merkle_dag::DagBlock>,
    },
    /// Propose a new policy for quorum voting
    PolicyProposal {
        proposal_id: [u8; 32],
        policy_hash: [u8; 32],
        details: String,
    },
    /// BFT Vote for a policy
    PolicyVote {
        proposal_id: [u8; 32],
        vote: crate::consensus::bft::Vote,
    },
    /// Anonymous BFT Vote for a policy
    AnonymousPolicyVote {
        proposal_id: [u8; 32],
        vote: crate::consensus::bft::AnonymousVote,
    },
    // ========================================================================
    // BLOCK PROPAGATION MESSAGES
    // ========================================================================
    /// Block proposal from leader
    BlockProposal(BlockProposal),
    /// Vote on a block proposal
    BlockVote(BlockVote),
    /// Block commit announcement
    BlockCommit(BlockCommit),
    /// View change request
    ViewChange(P2PViewChange),
    /// New view announcement from new leader
    NewView(P2PNewView),
    /// [Phase 29] Distributed Witness Fragment for recursive proving
    WitnessFragment {
        fragment_index: u32,
        total_fragments: u32,
        claim_hash: [u8; 32],
        data: Vec<u8>,
    },
}

/// Generic wrapper for P2P messages
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct P2PMessage {
    pub sender_id: NodeId,
    /// Public key of the sender (to verify signature)
    pub public_key: Vec<u8>,
    pub payload: GossipMessage,
}

// ============================================================================
// PYTHON BINDINGS (Phase 6.1b)
// ============================================================================

#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use std::collections::VecDeque;
#[cfg(feature = "python")]
use std::sync::{Arc, Mutex};

/// Python-exposed gossip subscriber for receiving gossip messages.
/// Uses a queue-based pattern for message delivery to Python callbacks.
#[cfg(feature = "python")]
#[cfg_attr(feature = "python", pyclass)]
pub struct GossipSubscriber {
    /// Internal message queue for poll-based retrieval
    message_queue: Arc<Mutex<VecDeque<P2PMessage>>>,
    /// Maximum queue size to prevent memory exhaustion
    max_queue_size: usize,
    /// Filter for message types (empty = subscribe to all)
    message_filter: Arc<Mutex<Vec<String>>>,
}

#[cfg(feature = "python")]
impl Default for GossipSubscriber {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(feature = "python")]
impl GossipSubscriber {
    /// Create a new gossip subscriber with default settings
    pub fn new() -> Self {
        Self {
            message_queue: Arc::new(Mutex::new(VecDeque::new())),
            max_queue_size: 1000,
            message_filter: Arc::new(Mutex::new(Vec::new())),
        }
    }

    /// Internal method to push a message to the queue
    /// Returns false if queue is full (message dropped)
    pub fn push_message(&self, message: P2PMessage) -> bool {
        if let Ok(mut queue) = self.message_queue.lock() {
            if queue.len() >= self.max_queue_size {
                return false; // Queue full, drop message
            }
            queue.push_back(message);
            true
        } else {
            false // Lock poisoned
        }
    }

    /// Get message type as string for filtering
    fn get_message_type(msg: &GossipMessage) -> &'static str {
        match msg {
            GossipMessage::VetoLocked { .. } => "VetoLock",
            GossipMessage::GovernanceDecisionBroadcast { .. } => "GovernanceDecision",
            GossipMessage::VetoResetFragment { .. } => "VetoReset",
            GossipMessage::StateRequest { .. } => "StateRequest",
            GossipMessage::Store { .. } => "DHTStore",
            GossipMessage::FindValue { .. } => "DHTFindValue",
            GossipMessage::FoundValue { .. } => "DHTFoundValue",
            GossipMessage::FindNode { .. } => "FindNode",
            GossipMessage::FoundNodes { .. } => "FoundNodes",
            GossipMessage::Handshake { .. } => "Handshake",
            GossipMessage::HandshakeAck { .. } => "HandshakeAck",
            GossipMessage::DagSyncRequest { .. } => "DagSyncRequest",
            GossipMessage::DagSyncResponse { .. } => "DagSyncResponse",
            GossipMessage::PolicyProposal { .. } => "PolicyProposal",
            GossipMessage::PolicyVote { .. } => "PolicyVote",
            GossipMessage::AnonymousPolicyVote { .. } => "AnonymousPolicyVote",
            GossipMessage::BlockProposal(_) => "BlockProposal",
            GossipMessage::BlockVote(_) => "BlockVote",
            GossipMessage::BlockCommit(_) => "BlockCommit",
            GossipMessage::ViewChange(_) => "P2PViewChange",
            GossipMessage::NewView(_) => "P2PNewView",
            GossipMessage::WitnessFragment { .. } => "WitnessFragment",
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl GossipSubscriber {
    /// Create a new gossip subscriber
    #[new]
    pub fn py_new() -> Self {
        Self::new()
    }

    /// Subscribe to specific message types
    ///
    /// # Arguments
    /// * `message_types` - List of message type strings to subscribe to:
    ///   - "BlockProposal", "BlockVote", "BlockCommit"
    ///   - "P2PViewChange", "P2PNewView"
    ///   - "DHTStore", "DHTFindValue"
    ///   - "VetoLock"
    ///   - Or empty list to subscribe to all types
    ///
    /// # Example
    /// ```python
    /// subscriber = GossipSubscriber()
    /// subscriber.subscribe(["BlockProposal", "BlockVote"])
    /// ```
    pub fn subscribe(&self, message_types: Vec<String>) -> PyResult<()> {
        if let Ok(mut filter) = self.message_filter.lock() {
            *filter = message_types;
            Ok(())
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Failed to acquire lock",
            ))
        }
    }

    /// Unsubscribe from all message types (clears filter)
    pub fn unsubscribe(&self) -> PyResult<()> {
        if let Ok(mut filter) = self.message_filter.lock() {
            filter.clear();
            Ok(())
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Failed to acquire lock",
            ))
        }
    }

    /// Poll for the next available message (non-blocking)
    ///
    /// Returns a dictionary with message details or None if queue is empty:
    /// {
    ///   "sender_id": bytes,
    ///   "public_key": bytes,
    ///   "message_type": str,
    ///   "payload_json": str
    /// }
    pub fn poll_message(&self, py: Python) -> PyResult<Option<Py<PyAny>>> {
        if let Ok(mut queue) = self.message_queue.lock() {
            if let Some(msg) = queue.pop_front() {
                // Convert P2PMessage to Python dict
                let dict = pyo3::types::PyDict::new(py);
                dict.set_item("sender_id", msg.sender_id.as_ref())?;
                dict.set_item("public_key", msg.public_key)?;
                dict.set_item("message_type", Self::get_message_type(&msg.payload))?;

                // Serialize payload to JSON for Python
                let payload_json = serde_json::to_string(&msg.payload).map_err(|e| {
                    pyo3::exceptions::PyValueError::new_err(format!(
                        "JSON serialization failed: {}",
                        e
                    ))
                })?;
                dict.set_item("payload_json", payload_json)?;

                Ok(Some(dict.into()))
            } else {
                Ok(None)
            }
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Failed to acquire lock",
            ))
        }
    }

    /// Get current queue size
    pub fn queue_size(&self) -> PyResult<usize> {
        if let Ok(queue) = self.message_queue.lock() {
            Ok(queue.len())
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Failed to acquire lock",
            ))
        }
    }

    /// Clear all messages from the queue
    pub fn clear_queue(&self) -> PyResult<()> {
        if let Ok(mut queue) = self.message_queue.lock() {
            queue.clear();
            Ok(())
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Failed to acquire lock",
            ))
        }
    }

    /// Set maximum queue size (to prevent memory exhaustion)
    pub fn set_max_queue_size(&mut self, size: usize) -> PyResult<()> {
        if size == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Max queue size must be > 0",
            ));
        }
        self.max_queue_size = size;
        Ok(())
    }

    /// Get current message filter
    pub fn get_filter(&self) -> PyResult<Vec<String>> {
        if let Ok(filter) = self.message_filter.lock() {
            Ok(filter.clone())
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Failed to acquire lock",
            ))
        }
    }
}
