// Copyright 2026 espressolee

//! P2P Veto Synchronization
//!
//! Handles the propagation and verification of Veto events across the
//! distributed swarm of nodes.

use crate::governance::{GovernanceDecision, GovernanceObserver, VetoEngine};
use std::sync::Arc;

/// Coordinator for network-wide Veto synchronization
pub struct VetoSyncHandler {
    engine: Arc<VetoEngine>,
}

impl VetoSyncHandler {
    #[must_use]
    pub fn new(engine: Arc<VetoEngine>) -> Self {
        Self { engine }
    }

    /// Process a governance decision received from the network
    pub fn process_network_decision(
        &self,
        decision: &GovernanceDecision,
        peer_node_id: [u8; 32],
    ) -> Result<(), String> {
        #[cfg(feature = "std")]
        println!(
            "🌐 [VetoSync] Received decision from Peer {:x?}: {:?}",
            hex::encode(peer_node_id),
            decision.verdict
        );

        // 1. Verify the ZK proof attached to the decision
        #[cfg(feature = "zk")]
        {
            if !self.engine.verify_decision(decision)? {
                return Err(format!(
                    "Invalid ZK proof from peer {:x?}",
                    hex::encode(peer_node_id)
                ));
            }
        }

        // 2. If it's a VetoLock or CriticalHalt, we MUST obey it if it's verified
        if decision.verdict.is_halt() && !self.engine.is_veto_active() {
            #[cfg(feature = "std")]
            println!("[VetoSync] Remote VETO detected! Synchronizing local state...");

            self.engine.activate_veto(
                decision.tick,
                &format!(
                    "Remote Veto from Peer {:x?}: {}",
                    hex::encode(peer_node_id),
                    decision.reason
                ),
                decision.context_hash,
            );
        }

        Ok(())
    }
}

impl GovernanceObserver for VetoSyncHandler {
    fn on_veto_activated(&self, _tick: u64, _reason: &str, _hash: [u8; 32]) {
        // Broadcast local veto to the network
        // In a real implementation, this would trigger the Gossip engine
        #[cfg(feature = "std")]
        println!("[VetoSync] Local VETO activated. Broadcasting to swarm...");
    }

    fn on_veto_reset(&self, threshold_met: bool) {
        #[cfg(feature = "std")]
        if threshold_met {
            println!("[VetoSync] threshold met for reset. Broadcasting reset signal...");
        }
    }

    fn on_remote_decision(&self, decision: &GovernanceDecision, node_id: [u8; 32]) {
        let _ = self.process_network_decision(decision, node_id);
    }

    fn on_decision_made(&self, _decision: &GovernanceDecision) {
        // VetoSyncHandler can also trigger broadcasting if it had network access
    }
}
