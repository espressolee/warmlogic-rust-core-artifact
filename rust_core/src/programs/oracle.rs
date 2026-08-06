use crate::governance::GovernanceVerdict;
use crate::programs::AxiomaticProgram;
use crate::state_grid::StateGrid;
use sha3::{Digest, Sha3_256};
use std::collections::BTreeMap;

pub struct AbyssalOracle {
    pub shard_id: u32,
    pub entropy_threshold: f64,
    pub observations: BTreeMap<u64, [u8; 32]>, // Deterministic persistence
}

impl AbyssalOracle {
    #[must_use]
    pub fn new(shard_id: u32, threshold: f64) -> Self {
        Self {
            shard_id,
            entropy_threshold: threshold,
            observations: BTreeMap::new(),
        }
    }

    fn calculate_entropy(&self, data: &[u8]) -> f64 {
        // Phase 12.7: full state wipe - Real Shannon Entropy Reality
        let mut counts = [0usize; 256];
        for &b in data {
            counts[b as usize] += 1;
        }

        let len = data.len() as f64;
        let mut entropy = 0.0;

        for &count in &counts {
            if count > 0 {
                let p = count as f64 / len;
                entropy -= p * p.log2();
            }
        }

        // Normalize to [0.0, 1.0] where 1.0 is maximum chaos
        let normalized = entropy / 8.0;
        println!(
            "🔮 [ORACLE] Reality Entropy Calculated: {:.4} (Normalized)",
            normalized
        );
        normalized
    }
}

impl AxiomaticProgram for AbyssalOracle {
    fn program_id(&self) -> &str {
        "ABYSSAL_ORACLE_01"
    }

    fn tick_axiomatic(&mut self, tick: u64, grid: &mut StateGrid) -> GovernanceVerdict {
        println!("[ORACLE] Processing Tick {}...", tick);

        // 1. Execute external data ingestion (Axiomatic Sensing)
        let data = format!("REALITY_SENSE_{}", tick);
        let entropy = self.calculate_entropy(data.as_bytes());

        // 2. Axiom 4: Ethics Guard
        if entropy > self.entropy_threshold {
            println!(
                "⚠️ [ORACLE] ETHICS BREACH: Entropy {:.4} > {:.4}",
                entropy, self.entropy_threshold
            );
            return GovernanceVerdict::VetoLock;
        }

        // 3. Update internal state (Deterministic)
        let mut hasher = Sha3_256::new();
        hasher.update(data.as_bytes());
        let hash: [u8; 32] = hasher.finalize().into();
        self.observations.insert(tick, hash);

        // 4. Persistence: Projection into the state grid Shard
        if let Some(shard) = grid.shards.get_mut(&self.shard_id) {
            shard.state_root = hash;
            shard.sequence += 1;
        }

        GovernanceVerdict::Allow
    }

    fn persist_state(&self) -> Vec<u8> {
        // Simplified serialization for demonstration
        format!("ORACLE_STATE_{}", self.observations.len()).into_bytes()
    }
}
