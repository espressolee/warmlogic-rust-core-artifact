//! rust_core/src/net/mod.rs
#[cfg(feature = "std")]
pub mod block_propagator; // P2P Block Propagation
#[cfg(feature = "std")]
pub mod gossip;
#[cfg(feature = "std")]
pub mod kademlia;
#[cfg(feature = "std")]
pub mod merkle_dag;
#[cfg(feature = "std")]
pub mod nat; // NAT Traversal (STUN/ICE)
#[cfg(feature = "std")]
pub mod noise; // Post-Quantum Noise Protocol
#[cfg(feature = "std")]
pub mod raft_net;
pub mod shadow;
#[cfg(feature = "std")]
pub mod transport;
pub mod veto_sync; // P2P Veto Coordination // Strategy 2: Shadow Grounding

// Phase 6.1b: Re-export GossipSubscriber for Python bindings
#[cfg(feature = "python")]
pub use gossip::GossipSubscriber;
