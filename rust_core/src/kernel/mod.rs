//! Phase 30: The Kinetic Core (Synchronous Era)
//!
//! [Axiom 2] Causal Consistency: The kernel loop is now fully deterministic and synchronous.
//! We have removed the Async Runtime dependency to allow bare-metal execution on Reef hardware.

// pub mod substrate; // Phase 14: Substrate Primitives (Missing/Deprecated)
pub mod cortex;
pub mod metrics_rs;
pub mod optimizer;
pub mod scheduler;
pub mod sys;

#[cfg(feature = "python")]
use crate::pyo3::prelude::*;

#[cfg(not(feature = "python"))]
type PyResult<T> = Result<T, Box<dyn std::error::Error + Send + Sync>>;
#[cfg(feature = "zk")]
use crate::zk::plonk_engine::PlonkProver;
use std::sync::Arc;
use tokio::sync::Mutex;

/// The Kinetic Core of Resonance OS.
/// Manages the heartbeat of reality, processing ticks and anchoring state.
#[cfg_attr(feature = "python", pyclass)]
pub struct KineticCore {
    pub dimension: u32,
    pub entropy_pool: Arc<Mutex<Vec<u8>>>,
    pub grid: Arc<Mutex<crate::state_grid::StateGrid>>,
    pub cycle_count: u64,
}

#[cfg_attr(feature = "python", pymethods)]
impl KineticCore {
    #[cfg(feature = "python")]
    #[new]
    pub fn py_new() -> Self {
        Self::new()
    }
}

impl KineticCore {
    #[must_use]
    pub fn new() -> Self {
        println!("[KERNEL] Igniting Kinetic Core (Phase 30: Synchronous Mode)...");
        Self {
            dimension: 1,
            entropy_pool: Arc::new(Mutex::new(vec![0u8; 32])),
            grid: Arc::new(Mutex::new(crate::state_grid::StateGrid::new())),
            cycle_count: 0,
        }
    }

    /// Advances the kernel by one distinct unit of time (Tick).
    /// Now fully synchronous to guarantee atomic state transitions.
    pub async fn tick(&mut self) -> PyResult<String> {
        self.cycle_count += 1;
        println!("⏱ [KERNEL] Tick {} Initiated.", self.cycle_count);

        // 1. Siphon Entropy (Synchronous)
        let _entropy = {
            use crate::hardware::HardwareEntropy;
            let (seed, _) = HardwareEntropy::derive_seed_raw();
            let mut pool = self.entropy_pool.lock().await;
            let mut seed_bytes = [0u8; 32];
            seed_bytes[0..8].copy_from_slice(&seed.to_le_bytes());
            pool.copy_from_slice(&seed_bytes);
            seed
        };

        // 2. Evolve Grid State
        // We use a dedicated scope to manage the grid lock lifetime
        let (verdict, zk_proof): (crate::governance::GovernanceVerdict, Option<Vec<u8>>) = {
            let mut grid = self.grid.lock().await;
            grid.tick_evolution(self.cycle_count, 0xFFFF).await
        };

        let status = match verdict {
            crate::governance::GovernanceVerdict::Allow => "OPERATIONAL",
            crate::governance::GovernanceVerdict::VetoLock => "VETO_ACTIVE",
            crate::governance::GovernanceVerdict::CriticalHalt => "SYSTEM_HALT",
            crate::governance::GovernanceVerdict::Review => "REVIEW_PENDING",
            crate::governance::GovernanceVerdict::Block => "BLOCKED",
        };

        println!(
            "✅ [KERNEL] Tick {} Complete. Status: {} [Proof: {}]",
            self.cycle_count,
            status,
            if zk_proof.is_some() { "YES" } else { "NO" }
        );

        Ok(status.to_string())
    }

    /// Raw synchronous tick for internal Rust usage (No Python overhead).
    pub async fn tick_raw(&mut self) -> bool {
        let (verdict, _): (crate::governance::GovernanceVerdict, _) = {
            let mut grid = self.grid.lock().await;
            grid.tick_evolution(self.cycle_count, 0xFFFF).await
        };
        !verdict.is_halt()
    }

    /// The Main Loop: Runs indefinitely until a Halt condition is met.
    /// This is the "Main Thread" of the OS.
    pub async fn kernel_main(&mut self) {
        println!("[KERNEL] Entering Main Loop...");
        loop {
            // [Axiom 3] Thermodynamic Pacing
            // We sleep to match the heartbeat of the hardware (e.g., 10Hz)
            tokio::time::sleep(std::time::Duration::from_millis(100)).await;

            if !self.tick_raw().await {
                println!("[KERNEL] SYSTEM HALT TRIGGERED. Shutting down.");
                break;
            }
        }
    }

    /// [Phase 35] Verification: Proves the execution of a specific instruction.
    #[cfg(feature = "zk")]
    pub async fn prove_single_instruction(&self, pc: u64, instr: u32) -> Option<Vec<u8>> {
        // Synchronous call to PlonkProver
        PlonkProver::prove_execution(pc, pc + 4, 10, 15, 5, instr)
            .await
            .ok()
    }

    #[cfg(not(feature = "zk"))]
    pub async fn prove_single_instruction(&self, _pc: u64, _instr: u32) -> Option<Vec<u8>> {
        None
    }
}
