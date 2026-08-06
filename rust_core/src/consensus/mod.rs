//! rust_core/src/consensus/mod.rs
//!
//! Byzantine Fault Tolerant Consensus with Slashing Integration.
//!
//! Collective Decision Protocol

pub mod bft;
pub mod byzantine;
pub mod eth_bridge;
pub mod latent_aggregator;
#[cfg(feature = "quinn")]
pub mod p2p;
#[cfg(feature = "zk")]
pub mod poseidon;
pub mod raft;
pub mod raft_pure;
pub mod state_machine;
pub mod storage;
pub mod types;
