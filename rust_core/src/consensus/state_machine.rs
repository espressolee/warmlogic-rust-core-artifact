//! [Ironclad] Raft State Machine Abstraction
//!
//! This module defines the trait for state machines that can be managed by the Raft engine.

use serde::{Deserialize, Serialize};

/// Represents the state of a state machine at a point in time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateMachineState {
    pub data: String,
    pub cumulative_hash: String,
    pub poseidon_hash: String,
}

/// The StateMachine trait: Implement this to define consensus logic.
pub trait StateMachine: Send + Sync {
    /// Applies a command to the state machine.
    /// Returns the new state index or updated data.
    fn apply(&mut self, index: usize, data: &str) -> String;

    /// Returns a snapshot of the current state.
    fn get_snapshot(&self) -> String;

    /// Restores the state from a snapshot.
    fn restore(&mut self, data: &str);
}

/// A default "Aegis" State Machine for Swarm Mission Logic.
pub struct AegisStateMachine {
    pub mission_data: String,
    pub mission_poseidon_hash: String,
}

impl AegisStateMachine {
    #[must_use]
    pub fn new() -> Self {
        Self {
            mission_data: "MISSION:INITIALIZED".to_string(),
            mission_poseidon_hash: "0".repeat(64),
        }
    }
}

impl StateMachine for AegisStateMachine {
    #[allow(unused_assignments)]
    fn apply(&mut self, _index: usize, data: &str) -> String {
        #[allow(unused)]
        let mut mission_updated = false;
        if let Some(target) = data.strip_prefix("TARGET:") {
            self.mission_data = format!("MISSION:MOVE_TO_TARGET:{}", target);
            println!("[AEGIS] Mission Update: Target Locked -> {}", target);
            mission_updated = true;
        } else if let Some(formation) = data.strip_prefix("PHALANX:") {
            self.mission_data = format!("MISSION:PHALANX_FORMATION:{}", formation);
            println!(
                "🛡️ [AEGIS] Mission Update: Phalanx Formation -> radius {}",
                formation
            );
            mission_updated = true;
        } else if data.starts_with("LAND") {
            self.mission_data = "MISSION:LANDED".to_string();
            println!("[AEGIS] Mission Update: Landing Sequence Confirmed.");
            mission_updated = true;
        } else if !data.starts_with("CONF:") {
            self.mission_data = data.to_string();
        }

        #[cfg(feature = "zk")]
        if mission_updated {
            use ark_bn254::Fr;
            use ark_ff::PrimeField;
            use sha2::Digest;

            // Update rolling Poseidon hash of mission transitions
            let prev_bytes = hex::decode(&self.mission_poseidon_hash).unwrap_or(vec![0u8; 32]);
            let mut p_bytes = [0u8; 32];
            let len = prev_bytes.len().min(32);
            p_bytes[32 - len..].copy_from_slice(&prev_bytes[..len]);
            let prev_h = Fr::from_be_bytes_mod_order(&p_bytes);

            let mut data_hasher = sha2::Sha256::new();
            data_hasher.update(data.as_bytes());
            let res = data_hasher.finalize();
            let mut bytes = [0u8; 32];
            bytes.copy_from_slice(&res);
            let cmd_h = Fr::from_be_bytes_mod_order(&bytes);

            let new_h = crate::consensus::poseidon::poseidon_hash(prev_h, cmd_h);
            self.mission_poseidon_hash = new_h.to_string();
        }

        self.mission_data.clone()
    }

    fn get_snapshot(&self) -> String {
        self.mission_data.clone()
    }

    fn restore(&mut self, data: &str) {
        self.mission_data = data.to_string();
    }
}
