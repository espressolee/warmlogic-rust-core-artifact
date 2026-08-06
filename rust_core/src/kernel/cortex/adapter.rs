use super::deep::{DeepBrain, DeepIntent};
use super::mesh::NeuralMesh;
use super::reflex::{FlightMode, ReflexBrain};
use std::time::Instant;

#[derive(Debug, Clone)]
pub enum AutonomousAction {
    SafetyOverride(FlightMode),
    Plan(String),
    Deferred(String),
}

#[derive(Debug, Clone)]
pub struct ReflexTrace {
    pub input: String,
    pub action: AutonomousAction,
    pub source: CortexSource,
    pub latency_us: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CortexSource {
    Reflex,
    MeshCache,
    Deep,
}

#[derive(Debug)]
pub struct CortexAdapter {
    reflex: ReflexBrain,
    deep: DeepBrain,
    mesh: NeuralMesh,
}

impl CortexAdapter {
    #[must_use]
    pub fn new(local_id: crate::net::kademlia::NodeId) -> Self {
        Self {
            reflex: ReflexBrain::new(),
            deep: DeepBrain::new(),
            mesh: NeuralMesh::new(local_id, 100),
        }
    }

    #[must_use]
    pub fn process_intent(&mut self, input: &str) -> ReflexTrace {
        let start = Instant::now();

        // 1. Fast path: Reflex
        if let Some(mode) = self.reflex.evaluate(input) {
            return ReflexTrace {
                input: input.to_string(),
                action: AutonomousAction::SafetyOverride(mode),
                source: CortexSource::Reflex,
                latency_us: start.elapsed().as_micros() as u64,
            };
        }

        // 2. Medium path: Mesh Cache
        if let Some(insight) = self.mesh.lookup_insight(input) {
            if insight.confidence > 0.8 {
                return ReflexTrace {
                    input: input.to_string(),
                    action: AutonomousAction::Plan(insight.plan.clone()),
                    source: CortexSource::MeshCache,
                    latency_us: start.elapsed().as_micros() as u64,
                };
            }
        }

        // 3. Slow path: DeepBrain
        let deep_result = self.deep.infer(input);
        let action = match deep_result {
            DeepIntent::Plan(plan) => {
                // Publish to mesh for other nodes
                self.mesh.publish_insight(input, &plan, 0.9);
                AutonomousAction::Plan(plan)
            }
            DeepIntent::Deferred(msg) => AutonomousAction::Deferred(msg),
        };

        ReflexTrace {
            input: input.to_string(),
            action,
            source: CortexSource::Deep,
            latency_us: start.elapsed().as_micros() as u64,
        }
    }
}
