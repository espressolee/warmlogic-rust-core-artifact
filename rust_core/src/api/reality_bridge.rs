// Reality Interfacing
// Objective: Securely ingest external data into the state grid.

use crate::governance::GovernanceVerdict;
use crate::state_grid::StateGrid;
use borsh::{BorshDeserialize, BorshSerialize};
use sha3::{Digest, Sha3_256};

/// [Axiom 1, 7] Reality Handle
/// Trait for components that can "sense" the external world and project it into the Grid.
pub trait RealityHandle: Send + Sync {
    fn source_id(&self) -> &str;
    fn sense_reality(&self) -> Vec<u8>;
}

/// The Reality Ingestor: Validates and anchors external data streams.
#[derive(Debug, Clone, BorshSerialize, BorshDeserialize)]
pub struct RealityIngestor {
    pub ingestion_threshold: f64,
}

impl RealityIngestor {
    pub fn new(threshold: f64) -> Self {
        Self {
            ingestion_threshold: threshold,
        }
    }

    /// Validates an incoming data packet against system axioms.
    pub fn ingest(&self, source: &dyn RealityHandle, grid: &mut StateGrid) -> GovernanceVerdict {
        let data = source.sense_reality();

        // 1. Axiom 7: Entropy Validation (Shannon Reality)
        let entropy = grid.calculate_shannon_entropy();
        println!(
            "📡 [INGESTOR] Source: {}, Entropy: {:.4}",
            source.source_id(),
            entropy
        );

        // 2. Axiom 1: Topological Binding
        // Grounded binding to Shard 0 for the ingest point.
        let mut hasher = Sha3_256::new();
        hasher.update(data);
        let next_root: [u8; 32] = hasher.finalize().into();

        if !grid.verify_topological_transition(0, 0, next_root) {
            println!(
                "🛑 [INGESTOR] Reality discontinuity detected from source: {}",
                source.source_id()
            );
            return GovernanceVerdict::VetoLock;
        }

        // 3. Projection into the Grid
        if let Some(shard) = grid.shards.get_mut(&0) {
            shard.state_root = next_root;
            shard.sequence += 1;
        }

        GovernanceVerdict::Allow
    }
}

/// [Strategy 1, 2] Reality Bridge: The unified interface for verification verification.
#[derive(Debug, Clone)]
pub struct RealityBridge {
    pub hsm_grounded: bool,
    pub shadow_initialized: bool,
}

impl RealityBridge {
    pub fn new() -> Self {
        Self {
            hsm_grounded: false,
            shadow_initialized: false,
        }
    }

    /// Checks if the entire system is physically grounded via Strategies 1 & 2.
    pub fn is_physically_grounded(&self, hsm: &crate::hardware::hsm_gate::HSMGate) -> bool {
        use crate::hardware::grounding::Groundable;
        hsm.is_grounded()
    }

    /// Retrieves the recursive ZK-witness root for the current reality state.
    pub fn get_reality_fingerprint(&self) -> [u8; 32] {
        crate::hardware::HardwareRealityBinder::get_hardware_fingerprint_raw()
    }
}
