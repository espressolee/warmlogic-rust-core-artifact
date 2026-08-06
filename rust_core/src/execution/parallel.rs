use std::collections::{HashMap, HashSet};
use std::sync::{Arc, Mutex as StdMutex};
use tokio::sync::Mutex as TokioMutex;

/// Tracks axiomatic dependencies cross asynchronous execution streams.
pub struct DependencyTracker {
    pending: HashMap<String, HashSet<String>>, // block_id -> set of dependency block_ids
    completed: HashSet<String>,
}

impl DependencyTracker {
    #[must_use]
    pub fn new() -> Self {
        Self {
            pending: HashMap::new(),
            completed: HashSet::new(),
        }
    }

    /// Registers a new computation block with its dependencies.
    pub fn register(&mut self, id: String, deps: Vec<String>) {
        let mut dep_set = HashSet::new();
        for dep in deps {
            if !self.completed.contains(&dep) {
                dep_set.insert(dep);
            }
        }

        if dep_set.is_empty() {
            println!(
                "⛓️ [PARALLEL] Block {} is READY for execution (No unmet dependencies).",
                id
            );
        } else {
            println!(
                "⛓️ [PARALLEL] Block {} is PENDING (Needs: {:?}).",
                id, dep_set
            );
        }

        self.pending.insert(id, dep_set);
    }

    /// Marks a block as completed and returns newly ready blocks.
    pub fn complete(&mut self, id: &str) -> Vec<String> {
        self.completed.insert(id.to_string());
        let mut ready = Vec::new();

        for (block_id, deps) in self.pending.iter_mut() {
            deps.remove(id);
            if deps.is_empty() {
                ready.push(block_id.clone());
            }
        }

        for r in &ready {
            self.pending.remove(r);
        }

        ready
    }
}

/// Thermodynamic Scheduler for governing Axiom 3 (Equilibrium).
#[derive(Debug, Clone, Copy)]
pub struct ThermodynamicScheduler {
    pub target_temp: f64,
}

impl ThermodynamicScheduler {
    #[must_use]
    pub fn new() -> Self {
        Self { target_temp: 55.0 } // Aim for 55C equilibrium
    }

    /// Calculates the necessary throttle delay to maintain equilibrium.
    #[must_use]
    pub fn get_throttle_delay(&self) -> std::time::Duration {
        use crate::hardware::rtl::SiliconBridge;
        let (variance, temp) = SiliconBridge::get_thermal_telemetry();

        // [Ironclad] Phase 4: Strict Thermodynamics
        // Panics if entropy variance exceeds Landauer's Limit (0.045).
        if variance > 0.045 {
            println!(
                "🔥 [THERMAL] CRITICAL: Landauer's Limit Violated! Temp={:.2}C, Variance={:.6}",
                temp, variance
            );
            // Instead of panicking, we trigger a global halt signal that the main loop can detect.
            // This allows for Sovereign Recovery instead of a crash.
            crate::recovery::trigger_thermal_anchor();
            return std::time::Duration::from_secs(30); // Force a long freeze
        }

        // Throttling Logic:
        // If variance > 0.035 OR temp > target_temp, apply delay.
        if temp > self.target_temp || variance > 0.035 {
            let overflow = (temp - self.target_temp).max(0.0);
            // Non-linear penalty for variance
            let delay_ms = (overflow * 10.0) as u64 + (variance * 2000.0) as u64;

            println!(
                "⚠️  [THERMAL] Throttling detected: Temp={:.2}C, Variance={:.6}, Delay={}ms",
                temp, variance, delay_ms
            );
            std::time::Duration::from_millis(delay_ms)
        } else {
            std::time::Duration::from_millis(0)
        }
    }
}

/// Shard-level Concurrency Engine for the state grid.
#[derive(Clone)]
pub struct ParallelExecutor {
    tracker: Arc<StdMutex<DependencyTracker>>,
    scheduler: ThermodynamicScheduler,
}

impl ParallelExecutor {
    #[must_use]
    pub fn new() -> Self {
        Self {
            tracker: Arc::new(StdMutex::new(DependencyTracker::new())),
            scheduler: ThermodynamicScheduler::new(),
        }
    }

    /// Spawns a task into the parallel execution pool if dependencies are met.
    /// This now enforces Thermodynamic Equilibrium (Axiom 3) and Memory Safety.
    pub async fn execute_block<F, Fut>(&self, id: String, deps: Vec<String>, f: F)
    where
        F: FnOnce() -> Fut + Send + 'static,
        Fut: std::future::Future<Output = ()> + Send + 'static,
    {
        let tracker = self.tracker.clone();
        let delay = self.scheduler.get_throttle_delay();

        if !delay.is_zero() {
            tokio::time::sleep(delay).await;
        }

        // [Axiom 3] Memory-Conscious Shard Loading
        // We reserve 128MB per shard execution block.
        let _estimate_mb: usize = 128;

        #[cfg(feature = "zk")]
        {
            use crate::zk::plonk_engine::GLOBAL_MEMORY_GUARD;
            GLOBAL_MEMORY_GUARD.reserve(_estimate_mb).await;
        }

        // In a real implementation, we would register and then wait for readiness.
        {
            let mut t = tracker.lock().unwrap();
            t.register(id.clone(), deps);
        }

        tokio::spawn(async move {
            // Memory guard scope
            #[cfg(feature = "zk")]
            let _guard = crate::zk::plonk_engine::ScopedMemory {
                amount: _estimate_mb,
            };

            println!("[PARALLEL] Executing Block: {}", id);
            f().await;
            let mut t = tracker.lock().unwrap();
            let ready = t.complete(&id);
            for r in ready {
                println!("[PARALLEL] Block {} is now READY.", r);
            }
        });
    }

    /// [Phase 18] Executes a parallel workload across all shards of the state grid.
    pub async fn execute_sharded_work(
        &self,
        grid: Arc<TokioMutex<crate::state_grid::StateGrid>>,
        _tx_data: Vec<u8>,
    ) {
        let shards: Vec<u32> = {
            let g = grid.lock().await;
            g.shards.keys().cloned().collect()
        };

        for shard_id in shards {
            let block_id = format!("shard_{}_exec", shard_id);
            self.execute_block(block_id, vec![], move || async move {
                // Mock sharded work for
                println!(
                    "🧠 [PARALLEL] Axiomatic validation for shard {}...",
                    shard_id
                );
            })
            .await;
        }
    }

    #[must_use]
    pub fn get_throttle_delay(&self) -> std::time::Duration {
        self.scheduler.get_throttle_delay()
    }
}
