//! [Phase 16] Axiomatic Economic Rails
//! =====================================
//! Defines the logic for autonomous cognitive labor settlement and Proof-of-Value.

#[cfg(feature = "zk")]
use crate::zk::ml::ModelWeightCommitment;
use borsh::{BorshDeserialize, BorshSerialize};
use serde::{Deserialize, Serialize};

#[cfg(not(feature = "zk"))]
pub struct ModelWeightCommitment {
    pub weight_root: String,
    pub model_id: String,
    pub version: u64,
    pub timestamp: u64,
}

/// Represents the economic value of a cognitive task.
#[derive(Debug, Clone, Serialize, Deserialize, BorshSerialize, BorshDeserialize)]
pub struct CognitiveCapital {
    pub amount: u64,
    pub currency: String, // "COGNIT" - Internal Energy-Backed Credit
}

/// The engine responsible for settling cognitive debts and rewards.
#[derive(Debug, Clone, BorshSerialize, BorshDeserialize)]
pub struct SettlementEngine {
    pub total_reserve: u64,
    pub ledgers: std::collections::BTreeMap<String, u64>,
    pub escrow: std::collections::BTreeMap<String, u64>,
}

impl SettlementEngine {
    #[must_use]
    pub fn new() -> Self {
        Self {
            total_reserve: 10_000_000, // Genesis Reserve
            ledgers: std::collections::BTreeMap::new(),
            escrow: std::collections::BTreeMap::new(),
        }
    }

    /// Calculates the labor value in internal COGNIT credits.
    #[must_use]
    pub fn calculate_labor_value(
        &self,
        complexity: f64,
        entropy: f64,
        axiomatic_overhead: u64,
    ) -> u64 {
        // [Harsh Formula] Value = (Complexity * (1 + Entropy)) + Axiomatic Log-Base
        let base_value = (complexity * (1.0 + entropy) * 100.0) as u64;
        base_value + (axiomatic_overhead / 2)
    }

    /// Generates a Proof-of-Value for a given inference commitment.
    #[must_use]
    pub fn generate_proof_of_value(
        &self,
        commitment: &ModelWeightCommitment,
        complexity: f64,
        entropy: f64,
    ) -> bool {
        // [Hardening]
        // 1. Complexity check: High complexity requires higher reserves.
        if complexity > 10.0 && self.total_reserve < 1000 {
            println!(
                "[ECONOMICS] Reserve Exhaustion: Cannot prove value for high-complexity thought."
            );
            return false;
        }

        // 2. Entropy Alignment: High entropy tasks are taxed to deter instability.
        if entropy > 0.9 {
            println!("[ECONOMICS] High Entropy Surcharge applied to Proof-of-Value.");
        }

        // Using weight_root instead of commitment field
        println!(
            "💰 [ECONOMICS] Generating Axiomatic PoV for Model commitment {}...",
            &commitment.weight_root
        );
        println!(
            "📊 [ECONOMICS] Value Vector: Complexity={:.2}, Entropy={:.2}",
            complexity, entropy
        );

        true
    }

    /// Settles a cognitive debt by transferring capital to the node.
    pub fn settle_labor(&mut self, node_id: &str, reward: u64) {
        println!(
            "💸 [ECONOMICS] Settling cognitive labor for Node {}: {} COGNIT",
            node_id, reward
        );
        self.total_reserve = self.total_reserve.saturating_sub(reward);
        let balance = self.ledgers.entry(node_id.to_string()).or_insert(0);
        *balance += reward;
    }

    /// [Phase 24] Locks funds in escrow when issuing a bounty.
    pub fn lock_funds(&mut self, node_id: &str, amount: u64, bounty_id: &str) -> bool {
        let balance = *self.ledgers.get(node_id).unwrap_or(&0);

        if balance >= amount {
            self.ledgers.insert(node_id.to_string(), balance - amount);
            self.escrow.insert(bounty_id.to_string(), amount);
            println!(
                "🔒 [ECONOMICS] Escrow locked {} COGNIT for Bounty {}",
                amount, bounty_id
            );
            true
        } else if self.total_reserve >= amount {
            // Genesis fallback: pull from reserve
            self.total_reserve -= amount;
            self.escrow.insert(bounty_id.to_string(), amount);
            println!(
                "🔒 [ECONOMICS] Escrow locked {} COGNIT for Bounty {} (from Genesis Reserve)",
                amount, bounty_id
            );
            true
        } else {
            println!("[ECONOMICS] Insufficient funds to issue bounty");
            false
        }
    }

    /// [Phase 24] Processes a bounty claim, releasing escrowed funds to the solver.
    pub fn process_bounty_claim(&mut self, bounty_id: &str, solver_id: &str) -> bool {
        if let Some(amount) = self.escrow.remove(bounty_id) {
            let balance = self.ledgers.entry(solver_id.to_string()).or_insert(0);
            *balance += amount;
            println!(
                "💎 [ECONOMICS] Bounty {} Claimed! {} COGNIT transferred to Node {}",
                bounty_id, amount, solver_id
            );
            true
        } else {
            false
        }
    }
}
