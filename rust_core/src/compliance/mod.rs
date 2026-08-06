//! rust_core/src/compliance/mod.rs
//! Compliance Export for EU AI Act and Regulatory Requirements.
//!
//! Generates standardized compliance reports including:
//! - Governance decision audit trails
//! - Safety metrics and risk assessments
//! - Model behavior documentation
//! - Incident response records

pub mod eu_ai_act;
pub mod report;

pub use eu_ai_act::*;
pub use report::*;
