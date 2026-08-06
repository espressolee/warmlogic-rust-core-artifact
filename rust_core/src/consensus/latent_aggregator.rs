//! Latent Aggregator Module
//! [Phase 17] Multi-Zone Convergence for distributed consensus.

use borsh::{BorshDeserialize, BorshSerialize};

#[cfg(not(feature = "std"))]
use alloc::collections::BTreeMap;
#[cfg(not(feature = "std"))]
use alloc::string::String;
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;
#[cfg(feature = "std")]
use std::collections::BTreeMap;

/// Aggregates latent state across multiple temporal zones
#[derive(Debug, Clone, Default, BorshSerialize, BorshDeserialize)]
pub struct LatentAggregator {
    /// Zone-specific latent states
    pub zone_states: BTreeMap<String, LatentState>,
    /// Global convergence threshold
    pub convergence_threshold: f64,
    /// Last aggregation timestamp
    pub last_aggregation: u64,
}

/// Represents latent state for a single zone
#[derive(Debug, Clone, Default, BorshSerialize, BorshDeserialize)]
pub struct LatentState {
    pub zone_id: String,
    pub state_root: [u8; 32],
    pub entropy: f64,
    pub sequence: u64,
}

impl LatentAggregator {
    #[must_use]
    pub fn new() -> Self {
        Self {
            zone_states: BTreeMap::new(),
            convergence_threshold: 0.95,
            last_aggregation: 0,
        }
    }

    /// Update latent state for a zone
    pub fn update_zone(&mut self, zone_id: String, state: LatentState) {
        self.zone_states.insert(zone_id, state);
    }

    /// Check if all zones have converged
    #[must_use]
    pub fn has_converged(&self) -> bool {
        if self.zone_states.is_empty() {
            return true;
        }

        // Check entropy alignment across zones
        let entropies: Vec<f64> = self.zone_states.values().map(|s| s.entropy).collect();
        if entropies.is_empty() {
            return true;
        }

        let avg = entropies.iter().sum::<f64>() / entropies.len() as f64;
        let variance =
            entropies.iter().map(|e| (e - avg).powi(2)).sum::<f64>() / entropies.len() as f64;

        variance < (1.0 - self.convergence_threshold)
    }

    /// Aggregate all zone states into a global state root
    pub fn aggregate(&mut self) -> [u8; 32] {
        use sha2::{Digest, Sha256};

        let mut hasher = Sha256::new();
        for (zone_id, state) in &self.zone_states {
            hasher.update(zone_id.as_bytes());
            hasher.update(&state.state_root);
        }

        let result = hasher.finalize();
        let mut root = [0u8; 32];
        root.copy_from_slice(&result);

        self.last_aggregation = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        root
    }
}
