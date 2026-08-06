//! rust_core/src/mind/mod.rs
#[cfg(feature = "ml")]
pub mod bridge;
#[cfg(feature = "ml")]
pub mod engine;
#[cfg(feature = "std")]
pub mod proto;

#[cfg(feature = "ml")]
pub use bridge::RustMind;
#[cfg(feature = "std")]
pub use proto::KernelPacket;
#[cfg(all(feature = "std", feature = "python"))]
pub use proto::{decode_packet, encode_packet};
#[cfg(feature = "ml")]
pub mod gap_discovery;
pub mod memory;
pub mod oblivion;
