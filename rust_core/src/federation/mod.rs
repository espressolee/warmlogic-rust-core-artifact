//! rust_core/src/federation/mod.rs
//! Multi-Region Federation for Global State Synchronization.
//!
//! Implements cross-region state synchronization:
//! - Vector clock causal ordering
//! - Conflict detection and resolution
//! - Merkle tree state verification
//! - Delta synchronization protocol

pub mod state_sync;
pub mod vector_clock;

pub use state_sync::*;
pub use vector_clock::*;
