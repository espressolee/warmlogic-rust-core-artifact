//! rust_core/src/net/kademlia.rs
//! Kademlia DHT Types for P2P Networking.

use serde::{Deserialize, Serialize};

/// 256-bit Node Identifier (Standard for WarmLogic Mesh)
pub type NodeId = [u8; 32];

/// Represents a peer in the Kademlia DHT.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Peer {
    pub id: NodeId,
    pub address: String,
    pub port: u16,
}

impl Peer {
    #[must_use]
    pub fn new(id: NodeId, address: String, port: u16) -> Self {
        Self { id, address, port }
    }
}

#[derive(Debug, Clone)]
pub struct RoutingTable {
    pub local_id: NodeId,
}

impl RoutingTable {
    #[must_use]
    pub fn new(local_id: NodeId) -> Self {
        Self { local_id }
    }

    pub fn remove_node(&mut self, _id: &NodeId) {
        // Simple stub since the full Kademlia logic is likely complex or elsewhere
    }
}
