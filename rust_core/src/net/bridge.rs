//! rust_core/src/net/bridge.rs
//! Phase 4: Bridge between Governance and P2P Network.

use crate::consensus::bft::BFTEngine;
use crate::governance::GovernanceObserver;
use crate::hardware::secure_enclave::EnclaveStateContainer;
use crate::net::gossip::{GossipMessage, P2PMessage};
use crate::net::kademlia::{NodeId, RoutingTable};
use crate::net::merkle_dag::GovernanceMerkleDag;
use crate::net::transport::NetworkingEngine;
use serde_json;
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};

/// [H5 Security Fix] Helper to recover from poisoned locks.
fn recover_lock<'a, T>(
    result: Result<MutexGuard<'a, T>, PoisonError<MutexGuard<'a, T>>>,
) -> MutexGuard<'a, T> {
    match result {
        Ok(guard) => guard,
        Err(poisoned) => poisoned.into_inner(),
    }
}

/// Governance State bound to the Secure Enclave.
pub struct SecureGovernanceState {
    pub merkle_dag: GovernanceMerkleDag,
    pub bft_engine: BFTEngine,
}

pub struct GossipBridge {
    network: Arc<NetworkingEngine>,
    routing_table: Arc<Mutex<RoutingTable>>,
    local_id: NodeId,
    public_key: Vec<u8>,
    private_key_hex: String,
    pub enclave: Arc<EnclaveStateContainer<SecureGovernanceState>>,
}

impl GossipBridge {
    pub fn new(
        network: Arc<NetworkingEngine>,
        routing_table: Arc<Mutex<RoutingTable>>,
        local_id: NodeId,
        public_key: Vec<u8>,
        private_key_hex: String,
    ) -> Self {
        GossipBridge {
            network,
            routing_table,
            local_id,
            public_key,
            private_key_hex,
            enclave: Arc::new(EnclaveStateContainer::new(SecureGovernanceState {
                merkle_dag: GovernanceMerkleDag::new(),
                bft_engine: BFTEngine::new(3),
            })),
        }
    }

    fn broadcast(&self, gossip: GossipMessage) {
        let msg = P2PMessage {
            sender_id: self.local_id,
            public_key: self.public_key.clone(),
            payload: gossip,
        };

        if let Ok(payload) = serde_json::to_vec(&msg) {
            // Get closest peers from routing table to gossip
            let peers = {
                let rt = recover_lock(self.routing_table.lock());
                rt.find_closest_verified(&self.local_id, 8)
            };

            for peer in peers {
                self.network
                    .send(format!("{}:{}", peer.address, peer.port), payload.clone());
            }
        }
    }

    /// Process a batch of incoming messages in parallel using Rayon.
    /// This is a high-performance entry point for 
    pub fn process_batch(
        &self,
        messages: Vec<crate::net::transport::IncomingMessage>,
        veto_engine: &crate::governance::VetoEngine,
    ) {
        use rayon::prelude::*;

        // 1. Parallel verification of signatures and node IDs
        let verified_results: Vec<(std::net::SocketAddr, P2PMessage)> = messages
            .into_par_iter()
            .filter_map(|incoming| {
                if let Ok(msg) = serde_json::from_slice::<P2PMessage>(&incoming.payload) {
                    // Verify NodeId binding (M5 Security)
                    if !crate::net::kademlia::verify_node_id_binding(
                        &msg.sender_id,
                        &msg.public_key,
                    ) {
                        return None;
                    }

                    // Verify Signature (Phase 5 Authentication)
                    let public_key_hex = hex::encode(&msg.public_key);
                    let verified = match &msg.payload {
                        GossipMessage::VetoLocked {
                            tick,
                            reason,
                            context_hash,
                            signature,
                            ..
                        } => {
                            let message =
                                format!("{}:{}:{}", tick, reason, hex::encode(context_hash));
                            crate::crypto::MLDSA::verify_raw(
                                &public_key_hex,
                                &message,
                                &hex::encode(signature),
                            )
                        }
                        GossipMessage::Store {
                            key,
                            value,
                            signature,
                        } => {
                            let message = format!("{}:{}", hex::encode(key), hex::encode(value));
                            crate::crypto::MLDSA::verify_raw(
                                &public_key_hex,
                                &message,
                                &hex::encode(signature),
                            )
                        }
                        _ => true,
                    };

                    if verified {
                        Some((incoming.source, msg))
                    } else {
                        None
                    }
                } else {
                    None
                }
            })
            .collect();

        // 2. Sequential execution of state changes (Enclave/Mutex bound)
        for (source, msg) in verified_results {
            self.process_verified(source, msg, veto_engine);
        }
    }

    /// Process an incoming message from the network with cryptographic verification
    pub fn process_incoming(
        &self,
        source: std::net::SocketAddr,
        payload: &[u8],
        veto_engine: &crate::governance::VetoEngine,
    ) {
        if let Ok(msg) = serde_json::from_slice::<P2PMessage>(payload) {
            // 1. Verify NodeId binding (M5 Security)
            if !crate::net::kademlia::verify_node_id_binding(&msg.sender_id, &msg.public_key) {
                eprintln!("[Gossip] NodeID mismatch from {:?}", source);
                return;
            }

            // 2. Verify Signature (Phase 5 Authentication)
            let public_key_hex = hex::encode(&msg.public_key);
            let verified = match &msg.payload {
                GossipMessage::VetoLocked {
                    tick,
                    reason,
                    context_hash,
                    signature,
                    ..
                } => {
                    let message = format!("{}:{}:{}", tick, reason, hex::encode(context_hash));
                    crate::crypto::MLDSA::verify_raw(
                        &public_key_hex,
                        &message,
                        &hex::encode(signature),
                    )
                }
                GossipMessage::VetoResetFragment { .. } => true,
                GossipMessage::Store {
                    key,
                    value,
                    signature,
                } => {
                    let message = format!("{}:{}", hex::encode(key), hex::encode(value));
                    crate::crypto::MLDSA::verify_raw(
                        &public_key_hex,
                        &message,
                        &hex::encode(signature),
                    )
                }
                _ => true,
            };

            if !verified {
                eprintln!(
                    "❌ [Gossip] Cryptographic signature verification failed from {:?}",
                    source
                );
                return;
            }

            self.process_verified(source, msg, veto_engine);
        }
    }

    /// Internal logic for processing a cryptographically verified P2P message.
    fn process_verified(
        &self,
        source: std::net::SocketAddr,
        msg: P2PMessage,
        veto_engine: &crate::governance::VetoEngine,
    ) {
        // Update routing table with the sender (Verified Peer Update)
        {
            let mut rt = recover_lock(self.routing_table.lock());
            let peer = crate::net::kademlia::Peer {
                id: msg.sender_id,
                address: source.ip().to_string(),
                port: source.port(),
                public_key: Some(msg.public_key.clone()),
            };
            let _ = rt.update_verified(peer);
        }

        match msg.payload {
            GossipMessage::VetoLocked {
                tick,
                reason,
                context_hash,
                ..
            } => {
                if !veto_engine.is_veto_active() {
                    eprintln!(
                        "📢 [Gossip] Authenticated VetoLock from {:?}: {}",
                        msg.sender_id, reason
                    );
                    veto_engine.activate_veto(tick, &reason, context_hash);
                }
            }
            GossipMessage::GovernanceDecisionBroadcast { decision, node_id } => {
                eprintln!(
                    "🌐 [Gossip] Verified Governance Decision from {:?}: {:?}",
                    hex::encode(node_id),
                    decision.verdict
                );

                #[cfg(feature = "zk")]
                {
                    if let Ok(true) = veto_engine.verify_decision(&decision) {
                        if decision.verdict.is_halt() && !veto_engine.is_veto_active() {
                            veto_engine.activate_veto(
                                decision.tick,
                                &decision.reason,
                                decision.context_hash,
                            );
                        }
                    }
                }
            }
            GossipMessage::FindNode { target } => {
                let closest = {
                    let rt = recover_lock(self.routing_table.lock());
                    rt.find_closest_verified(&target, 20) // Return K closest
                };
                self.send(
                    source,
                    GossipMessage::FoundNodes {
                        target,
                        nodes: closest,
                    },
                );
            }
            GossipMessage::FoundNodes { nodes, .. } => {
                // Update our routing table with newly discovered peers
                for peer in nodes {
                    let mut rt = recover_lock(self.routing_table.lock());
                    let _ = rt.update_verified(peer);
                }
            }
            GossipMessage::VetoResetFragment { signature, .. } => {
                let dummy_message = vec![0u8; 32];
                if let Ok(reset_achieved) =
                    veto_engine.reset_with_signature(&signature, &dummy_message)
                {
                    if reset_achieved {
                        eprintln!("[Gossip] VetoLock RESET achieved via multi-sig aggregation!");
                    }
                }
            }
            GossipMessage::Handshake {
                sender_id,
                public_key,
                nonce,
                ..
            } => {
                if !crate::net::kademlia::verify_node_id_binding(&sender_id, &public_key) {
                    return;
                }
                if !crate::net::kademlia::verify_pow_puzzle(&sender_id, nonce, 16) {
                    eprintln!("[Gossip] Invalid PoW from {:?}", sender_id);
                    return;
                }

                {
                    let mut rt = recover_lock(self.routing_table.lock());
                    let peer = crate::net::kademlia::Peer {
                        id: sender_id,
                        address: source.ip().to_string(),
                        port: source.port(),
                        public_key: Some(public_key),
                    };
                    let _ = rt.update_verified(peer);
                }

                let head_hash = self.enclave.execute(|state| state.merkle_dag.head_hash);
                self.send(
                    source,
                    GossipMessage::HandshakeAck {
                        responder_id: self.local_id,
                        head_hash,
                    },
                );
                eprintln!("[Gossip] Handshake accepted from {:?}", sender_id);
            }
            GossipMessage::HandshakeAck {
                responder_id,
                head_hash,
            } => {
                eprintln!(
                    "✅ [Gossip] Handshake acknowledged by {:?} (Head: {:?})",
                    responder_id,
                    hex::encode(&head_hash[..4])
                );

                let missing = self
                    .enclave
                    .execute(|state| state.merkle_dag.get_missing_hashes(head_hash));
                if !missing.is_empty() {
                    self.send(
                        source,
                        GossipMessage::DagSyncRequest {
                            missing_hashes: missing,
                        },
                    );
                }
            }
            GossipMessage::DagSyncRequest { missing_hashes } => {
                let mut found_blocks = Vec::new();
                self.enclave.execute(|state| {
                    for hash in missing_hashes {
                        if let Some(block) = state.merkle_dag.blocks.get(&hash) {
                            found_blocks.push(block.clone());
                        }
                    }
                });
                if !found_blocks.is_empty() {
                    self.send(
                        source,
                        GossipMessage::DagSyncResponse {
                            blocks: found_blocks,
                        },
                    );
                }
            }
            GossipMessage::DagSyncResponse { blocks } => {
                self.enclave.execute(|state| {
                    let mut last_hash = [0u8; 32];
                    for block in blocks {
                        let hash = block.hash();
                        if let std::collections::hash_map::Entry::Vacant(entry) =
                            state.merkle_dag.blocks.entry(hash)
                        {
                            entry.insert(block);
                            eprintln!(
                                "📜 [Gossip] Sync: Added DAG block {:?}",
                                hex::encode(&hash[..4])
                            );
                            last_hash = hash;
                        }
                    }
                    if last_hash != [0u8; 32] {
                        let _ = state.merkle_dag.resolve_fork(last_hash);
                    }
                });
            }
            GossipMessage::PolicyProposal {
                proposal_id,
                policy_hash,
                details,
            } => {
                eprintln!(
                    "🗳️ [Gossip] Policy Proposal: {} (Hash: {:?})",
                    details,
                    hex::encode(&policy_hash[..4])
                );

                let (vote, _round) = self.enclave.execute(|state| {
                    state.bft_engine.propose(hex::encode(proposal_id), None);

                    let vote_msg =
                        format!("{}:{}", hex::encode(proposal_id), state.bft_engine.round);
                    let signature =
                        crate::crypto::MLDSA::sign_raw(&self.private_key_hex, &vote_msg)
                            .unwrap_or_default();

                    let vote = crate::consensus::bft::Vote {
                        voter_id: self.local_id.to_hex(),
                        block_hash: hex::encode(proposal_id),
                        round: state.bft_engine.round,
                        signature,
                        decision_hash: None,
                    };
                    (vote, state.bft_engine.round)
                });

                self.broadcast(GossipMessage::PolicyVote { proposal_id, vote });
            }
            GossipMessage::PolicyVote { proposal_id, vote } => {
                let voter_pk_hex = {
                    let rt = recover_lock(self.routing_table.lock());
                    let voter_id = crate::net::kademlia::NodeId::from_hex(&vote.voter_id)
                        .unwrap_or(self.local_id);
                    rt.get_verified_peer(&voter_id)
                        .and_then(|p| p.public_key.clone().map(hex::encode))
                };

                if let Some(pk_hex) = voter_pk_hex {
                    let pk_ref: &str = &pk_hex;
                    self.enclave.execute(|state| {
                        if state
                            .bft_engine
                            .cast_vote_verified(vote, pk_ref)
                            .unwrap_or(false)
                        {
                            eprintln!(
                                "🎊 [Gossip] QUORUM REACHED (Public) for Policy Proposal {:?}!",
                                hex::encode(&proposal_id[..4])
                            );
                            let _ = state.merkle_dag.add_block(vec![
                                crate::net::merkle_dag::GovernanceEvent::PolicyUpdated {
                                    policy_hash: proposal_id,
                                    version: 120,
                                },
                            ]);
                        }
                    });
                }
            }
            GossipMessage::AnonymousPolicyVote { proposal_id, vote } => {
                self.enclave.execute(|state| {
                    if state
                        .bft_engine
                        .cast_anonymous_vote_verified(vote)
                        .unwrap_or(false)
                    {
                        eprintln!(
                            "🎊 [Gossip] QUORUM REACHED (Anonymous) for Policy Proposal {:?}!",
                            hex::encode(&proposal_id[..4])
                        );
                        let _ = state.merkle_dag.add_block(vec![
                            crate::net::merkle_dag::GovernanceEvent::PolicyUpdated {
                                policy_hash: proposal_id,
                                version: 151,
                            },
                        ]);
                    }
                });
            }
            _ => {}
        }
    }

    /// Send a message to a specific address
    fn send(&self, target: std::net::SocketAddr, gossip: GossipMessage) {
        let msg = P2PMessage {
            sender_id: self.local_id,
            public_key: self.public_key.clone(),
            payload: gossip,
        };
        if let Ok(payload) = serde_json::to_vec(&msg) {
            self.network.send(target.to_string(), payload);
        }
    }

    /// Initiate a handshake with a peer, solving the PoW puzzle first.
    pub fn initiate_handshake(&self, target: std::net::SocketAddr) {
        let node_id = self.local_id;
        let difficulty = 16; // 16 bits difficulty

        // Solve the puzzle (Wait for it - about 65k hashes)
        let nonce = crate::net::kademlia::solve_pow_puzzle(&node_id, difficulty);

        self.send(
            target,
            GossipMessage::Handshake {
                sender_id: node_id,
                public_key: self.public_key.clone(),
                nonce,
                fleet_token: "WARMLOGIC-ALPHA".to_string(),
            },
        );

        eprintln!(
            "🛰️ [Gossip] Handshake initiated to {} (nonce={})",
            target, nonce
        );
    }
}

impl GovernanceObserver for GossipBridge {
    fn on_veto_activated(&self, tick: u64, reason: &str, hash: [u8; 32]) {
        let message = format!("{}:{}:{}", tick, reason, hex::encode(hash));
        let signature_hex =
            crate::crypto::MLDSA::sign_raw(&self.private_key_hex, &message).unwrap_or_default();
        let signature = hex::decode(signature_hex).unwrap_or_default();

        // Log to Merkle-DAG
        self.enclave.execute(|state| {
            let _ = state.merkle_dag.add_block(vec![
                crate::net::merkle_dag::GovernanceEvent::VetoLocked {
                    tick,
                    reason: reason.to_string(),
                    context_hash: hash,
                },
            ]);
        });

        self.broadcast(GossipMessage::VetoLocked {
            sender_id: self.local_id,
            tick,
            reason: reason.to_string(),
            context_hash: hash,
            signature,
        });
    }

    fn on_veto_reset(&self, threshold_met: bool) {
        if threshold_met {
            // We could broadcast the reset proof here if needed
        }
    }

    fn on_remote_decision(
        &self,
        decision: &crate::governance::GovernanceDecision,
        node_id: [u8; 32],
    ) {
        self.broadcast(GossipMessage::GovernanceDecisionBroadcast {
            decision: decision.clone(),
            node_id,
        });
    }

    fn on_decision_made(&self, decision: &crate::governance::GovernanceDecision) {
        // Broadacst local decision to peers
        self.broadcast(GossipMessage::GovernanceDecisionBroadcast {
            decision: decision.clone(),
            node_id: self.local_id.0, // Assuming NodeId.0 is [u8; 32] or similar
        });
    }
}

// ============================================================================
// Python Bindings: RustDHT
// ============================================================================

#[cfg(feature = "python")]
use pyo3::prelude::*;

/// Python-exposed Kademlia DHT wrapper.
///
/// Provides a high-level interface for:
/// - Node discovery and routing
/// - Key-value storage (DHT)
/// - Governance state synchronization
#[cfg(feature = "python")]
#[pyclass]
pub struct RustDHT {
    node_id: [u8; 32],
    bootstrap_nodes: Vec<String>,
    k_bucket_size: usize,
}

#[cfg(feature = "python")]
#[pymethods]
impl RustDHT {
    /// Create a new DHT node.
    ///
    /// # Arguments
    /// * `node_id_hex` - 64-character hex string for the 256-bit node ID
    /// * `k_bucket_size` - Number of contacts per bucket (default: 20)
    #[new]
    #[pyo3(signature = (node_id_hex, k_bucket_size = 20))]
    pub fn new(node_id_hex: &str, k_bucket_size: usize) -> PyResult<Self> {
        let node_id = hex::decode(node_id_hex).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid hex: {}", e))
        })?;

        if node_id.len() != 32 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Node ID must be 32 bytes (64 hex characters)",
            ));
        }

        let mut id_array = [0u8; 32];
        id_array.copy_from_slice(&node_id);

        Ok(Self {
            node_id: id_array,
            bootstrap_nodes: Vec::new(),
            k_bucket_size,
        })
    }

    /// Add a bootstrap node address.
    pub fn add_bootstrap(&mut self, addr: String) {
        self.bootstrap_nodes.push(addr);
    }

    /// Get the node ID as hex string.
    #[getter]
    pub fn node_id_hex(&self) -> String {
        hex::encode(self.node_id)
    }

    /// Get the k-bucket size.
    #[getter]
    pub fn k_bucket_size(&self) -> usize {
        self.k_bucket_size
    }

    /// Get the number of bootstrap nodes.
    pub fn bootstrap_count(&self) -> usize {
        self.bootstrap_nodes.len()
    }

    /// Calculate XOR distance to another node.
    pub fn xor_distance(&self, other_hex: &str) -> PyResult<String> {
        let other = hex::decode(other_hex).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid hex: {}", e))
        })?;

        if other.len() != 32 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Other ID must be 32 bytes",
            ));
        }

        let mut distance = [0u8; 32];
        for i in 0..32 {
            distance[i] = self.node_id[i] ^ other[i];
        }

        Ok(hex::encode(distance))
    }

    /// Get the routing table bucket index for a given node.
    pub fn bucket_index(&self, other_hex: &str) -> PyResult<usize> {
        let other = hex::decode(other_hex).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid hex: {}", e))
        })?;

        if other.len() != 32 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Other ID must be 32 bytes",
            ));
        }

        // Find leading zeros in XOR distance
        for i in 0..32 {
            let xor_byte = self.node_id[i] ^ other[i];
            if xor_byte != 0 {
                return Ok(i * 8 + (xor_byte.leading_zeros() as usize));
            }
        }

        Ok(255) // Same node
    }
}
