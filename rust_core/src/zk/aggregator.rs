//! Axiom 6: Recursive Aggregation
//!
//! Resonance OS - High-Throughput Proof Folding
//!
//! This module implements the Aggregator Switch, which routes proofs
//! into a recursive folding hierarchy (Merkle Proof Tree).

use crate::zk::{ZKProof, ZKResult};
use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

/// The Aggregator Switch: Manages the flow of proofs into the folding engine.
pub struct AggregatorSwitch {
    pub proof_queue: Arc<Mutex<VecDeque<ZKProof>>>,
}

impl AggregatorSwitch {
    pub fn new() -> Self {
        Self {
            proof_queue: Arc::new(Mutex::new(VecDeque::new())),
        }
    }

    /// Ingests a raw proof into the aggregation queue.
    pub fn ingest_proof(&self, proof: ZKProof) {
        let mut queue = self.proof_queue.lock().unwrap();
        queue.push_back(proof);
    }

    /// [Phase 29] Performs a full recursive aggregation of all pending proofs.
    /// Reduces N proofs to 1 root proof (O(log N) complexity).
    pub async fn aggregate_all(
        &self,
        prover: &crate::zk::recursive::RecursiveProver,
    ) -> ZKResult<ZKProof> {
        println!("[AGGREGATOR] Starting Recursive Fold...");

        let mut current_layer: Vec<ZKProof> = {
            let mut queue = self.proof_queue.lock().unwrap();
            queue.drain(..).collect()
        };

        if current_layer.is_empty() {
            return Err(crate::zk::ZKError::ProvingError(
                "No proofs to aggregate".to_string(),
            ));
        }

        println!("[AGGREGATOR] Layer 0: {} proofs.", current_layer.len());

        while current_layer.len() > 1 {
            let mut next_layer = Vec::new();
            println!(
                "🌀 [AGGREGATOR] Layer Processing: {} proofs remaining.",
                current_layer.len()
            );

            for chunk in current_layer.chunks(2) {
                if chunk.len() == 2 {
                    // Synchronous aggregation
                    let aggregated = prover.aggregate_proofs(chunk).await;
                    next_layer.push(aggregated);
                } else {
                    // Carry over the odd proof to the next layer
                    next_layer.push(chunk[0].clone());
                }
            }
            current_layer = next_layer;
        }

        println!("[AGGREGATOR] Root Proof Derived.");
        Ok(current_layer[0].clone())
    }
}

pub async fn run_aggregator_test() {
    println!("[TEST] Running Aggregator Switch Test...");
    let switch = AggregatorSwitch::new();

    // Simulate high load
    for i in 0..8 {
        switch.ingest_proof(ZKProof {
            challenge: [i as u8; 32],
            z1: [0x11; 32],
            z2: [0x22; 32],
            commitment: [0x33; 32],
        });
    }

    let mut prover = crate::zk::recursive::RecursiveProver::new();
    prover
        .init_universal_setup(1024)
        .await
        .expect("Failed aggregator SRS setup");

    let res = switch.aggregate_all(&prover).await;
    match res {
        Ok(root) => println!(
            "✅ [TEST] Aggregation Success. Root: {:?}",
            &root.challenge[0..4]
        ),
        Err(e) => println!("[TEST] Aggregation Failed: {:?}", e),
    }
}
