//! rust_core/src/evolution/mod.rs
#[cfg(feature = "ml")]
pub mod distillery;
pub mod selection;

#[cfg(feature = "ml")]
pub use distillery::WeightDistillery;
pub use selection::GeneticSelector;
