use crate::governance::GovernanceVerdict;
use crate::state_grid::StateGrid;

pub trait AxiomaticProgram: Send + Sync {
    /// Unique identifier for the program within the state grid.
    fn program_id(&self) -> &str;

    /// The primary execution hook called by the StateGrid during every tick.
    /// Returns a GovernanceVerdict to signal compliance or breach.
    fn tick_axiomatic(&mut self, tick: u64, grid: &mut StateGrid) -> GovernanceVerdict;

    /// Persistence: Allows the program to save its state into its dedicated shard.
    fn persist_state(&self) -> Vec<u8>;

    /// [Phase 31] Optional hook for self-evolution metadata.
    fn as_evolving(&self) -> Option<&dyn SelfEvolvingProgram> {
        None
    }
    fn as_evolving_mut(&mut self) -> Option<&mut dyn SelfEvolvingProgram> {
        None
    }
}

/// [Phase 31] Trait for programs that can autonomously optimize their logic.
pub trait SelfEvolvingProgram {
    /// Propose an optimized implementation candidate (e.g., ZK-Assembly)
    fn propose_optimization(&self) -> OptimizationCandidate;

    /// Hot-patch the program with a verified implementation.
    fn hot_patch(&mut self, patch: VerifiedPatch);
}

#[derive(Clone, Debug)]
pub struct OptimizationCandidate {
    pub target_id: String,
    pub logic_hash: [u8; 32],
    pub code: Vec<u8>,
}

#[derive(Clone, Debug)]
pub struct VerifiedPatch {
    pub code: Vec<u8>,
    pub tv_proof: Vec<u8>, // Translation Validation Proof
}

pub mod oracle;
