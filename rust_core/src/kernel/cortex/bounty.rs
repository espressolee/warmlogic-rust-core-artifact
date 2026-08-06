//! Phase 24: Sovereign Arbitrage (Cognitive Bounty Market)
//!
//! Allows resource-constrained drones to issue bounties for complex intent
//! inference, creating a federated market for cognitive labor.

use serde::{Deserialize, Serialize};

/// Represents an active bounty for cognitive labor.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CognitiveBounty {
    /// Unique identifier for this bounty.
    pub bounty_id: String,
    /// The complex text intent that needs parsing/inference.
    pub intent: String,
    /// The reward in COGNIT credits offered.
    pub reward_cognit: u64,
    /// The node issuing this request.
    pub issuer_id: crate::net::kademlia::NodeId,
    /// Epoch timestamp when issued.
    pub timestamp: u64,
}

/// A solver's claim on an active bounty.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BountyClaim {
    pub bounty_id: String,
    /// The node claiming to have solved the bounty.
    pub solver_id: crate::net::kademlia::NodeId,
    /// The resolved cognitive insight.
    pub insight: crate::kernel::cortex::mesh::CognitiveInsight,
}

/// Manages active cognitive bounties on a local node.
#[derive(Debug, Clone, Default)]
pub struct BountyMarket {
    /// List of open bounties broadcast by the swarm.
    pub open_bounties: std::collections::HashMap<String, CognitiveBounty>,
}

impl BountyMarket {
    #[must_use]
    pub fn new() -> Self {
        Self {
            open_bounties: std::collections::HashMap::new(),
        }
    }

    /// Registers a new incoming bounty from the swarm.
    pub fn register_bounty(&mut self, bounty: CognitiveBounty) {
        println!(
            "💎 [BOUNTY] New Market Request: '{}' (Reward: {} COGNIT)",
            if bounty.intent.len() > 30 {
                &bounty.intent[..30]
            } else {
                &bounty.intent
            },
            bounty.reward_cognit
        );
        self.open_bounties.insert(bounty.bounty_id.clone(), bounty);
    }

    /// Retrieves an open bounty if it exists.
    #[must_use]
    pub fn get_bounty(&self, bounty_id: &str) -> Option<&CognitiveBounty> {
        self.open_bounties.get(bounty_id)
    }

    /// Removes a bounty once it has been claimed and settled.
    pub fn remove_bounty(&mut self, bounty_id: &str) {
        self.open_bounties.remove(bounty_id);
    }

    /// Generates a unique bounty ID.
    #[must_use]
    pub fn generate_id(intent: &str, issuer: &crate::net::kademlia::NodeId) -> String {
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let hash = crate::kernel::cortex::mesh::NeuralMesh::hash_intent(intent);
        format!("BTY-{:x}-{}-{}", hash, issuer[0], ts)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bounty_id_generation() {
        let issuer: crate::net::kademlia::NodeId = [0xAA; 32];
        let intent = "optimize swarm path";
        let id1 = BountyMarket::generate_id(intent, &issuer);
        let id2 = BountyMarket::generate_id("different intent", &issuer);

        assert!(id1.starts_with("BTY-"));
        assert_ne!(id1, id2);
    }

    #[test]
    fn test_bounty_market_lifecycle() {
        let mut market = BountyMarket::new();
        let issuer: crate::net::kademlia::NodeId = [0xBB; 32];
        let intent = "analyze thermal map";
        let id = BountyMarket::generate_id(intent, &issuer);

        let bounty = CognitiveBounty {
            bounty_id: id.clone(),
            intent: intent.to_string(),
            reward_cognit: 50,
            issuer_id: issuer.clone(),
            timestamp: 1000,
        };

        market.register_bounty(bounty.clone());
        assert_eq!(market.open_bounties.len(), 1);

        let retrieved = market.get_bounty(&id);
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().reward_cognit, 50);

        market.remove_bounty(&id);
        assert_eq!(market.open_bounties.len(), 0);
        assert!(market.get_bounty(&id).is_none());
    }
}
