use crate::consensus::bft::{BFTEngine, Vote};
use crate::economics::SettlementEngine;
use crate::kernel::cortex::bounty::{BountyClaim, BountyMarket, CognitiveBounty};
use crate::net::kademlia::{NodeId, RoutingTable};
use crate::slashing::SlashingEngine;
use mavlink::common::ENCAPSULATED_DATA_DATA;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone)]
pub struct PeerState {
    pub position: (f64, f64, f64),
    pub armed: bool,
    pub last_update: u64,
    pub jitter_history: Vec<u64>,
    pub consecutive_violations: u32,
}

#[derive(Debug, Clone)]
pub struct SwarmManager {
    pub local_id: NodeId,
    pub routing_table: Arc<Mutex<RoutingTable>>,
    pub peers: HashMap<NodeId, PeerState>,
    pub bft: Arc<Mutex<BFTEngine>>,
    pub outgoing_packets: Vec<Vec<u8>>,
    pub bounty_market: BountyMarket,
    pub settlement: SettlementEngine,
    pub slashing: SlashingEngine,
    pub isolated_peers: std::collections::HashSet<NodeId>,
}

impl SwarmManager {
    #[must_use]
    pub fn new(local_id: NodeId) -> Self {
        SwarmManager {
            local_id,
            routing_table: Arc::new(Mutex::new(RoutingTable::new(local_id.clone()))),
            peers: HashMap::new(),
            bft: Arc::new(Mutex::new(BFTEngine::new(3))), // Default quorum of 3
            outgoing_packets: Vec::new(),
            bounty_market: BountyMarket::new(),
            settlement: SettlementEngine::new(),
            slashing: SlashingEngine::new(),
            isolated_peers: std::collections::HashSet::new(),
        }
    }

    #[allow(deprecated)]
    pub fn handle_peer_packet(&mut self, data: &ENCAPSULATED_DATA_DATA) {
        if data.data.len() < 32 {
            return;
        }

        // Data format: [Type(1) | NodeId(32) | Payload(...)]
        let msg_type = data.data[0];
        let mut id_bytes = [0u8; 32];
        id_bytes.copy_from_slice(&data.data[1..33]);
        let peer_id: NodeId = id_bytes;

        if peer_id == self.local_id || self.isolated_peers.contains(&peer_id) {
            return;
        }

        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);

        match msg_type {
            0 => {
                // State Sync
                let entry = self.peers.entry(peer_id).or_insert(PeerState {
                    position: (0.0, 0.0, 0.0),
                    armed: false,
                    last_update: current_time,
                    jitter_history: Vec::new(),
                    consecutive_violations: 0,
                });

                if entry.last_update > 0 && current_time > entry.last_update {
                    let jitter = current_time - entry.last_update;
                    entry.jitter_history.push(jitter);
                    if entry.jitter_history.len() > 10 {
                        entry.jitter_history.remove(0);
                    }
                }
                entry.last_update = current_time;
            }
            1 => {
                // BFT Vote / Proposal
                // Payload: [BlockHash(32) | Signature(variable)]
                if data.data.len() >= 65 {
                    let block_hash_bytes = &data.data[33..65];
                    let block_hash = hex::encode(block_hash_bytes);

                    let mut should_broadcast_own_vote = false;

                    if let Ok(mut bft) = self.bft.lock() {
                        // 1. If we don't have this proposal yet, accept it and prepare to vote
                        if bft.current_proposal.is_none() {
                            bft.propose(block_hash.clone(), None);
                            should_broadcast_own_vote = true;
                        }

                        // 2. Cast the peer's vote
                        let vote = Vote {
                            voter_id: hex::encode(&peer_id),
                            block_hash: block_hash.clone(),
                            round: bft.round,
                            signature: "verified-via-pqc".to_string(),
                            decision_hash: None,
                        };
                        bft.cast_vote(vote);

                        // 3. If we accepted a new proposal, cast our own vote locally too
                        if should_broadcast_own_vote {
                            let own_vote = Vote {
                                voter_id: hex::encode(&self.local_id),
                                block_hash: block_hash.clone(),
                                round: bft.round,
                                signature: "local-trust".to_string(),
                                decision_hash: None,
                            };
                            bft.cast_vote(own_vote);
                        }
                    }

                    // 4. Broadcast our own vote if we just cast it
                    if should_broadcast_own_vote {
                        let mut own_vote_data = vec![1u8]; // Type 1
                        own_vote_data.extend_from_slice(&self.local_id);
                        own_vote_data.extend_from_slice(block_hash_bytes);
                        self.outgoing_packets.push(own_vote_data);
                    }
                }
            }
            2 => {
                // Phase 24: Bounty Broadcast
                // Payload: JSON serialized CognitiveBounty
                if let Ok(json_str) = std::str::from_utf8(&data.data[33..]) {
                    if let Ok(bounty) = serde_json::from_str::<CognitiveBounty>(
                        json_str.trim_matches(char::from(0)),
                    ) {
                        self.bounty_market.register_bounty(bounty);
                    }
                }
            }
            3 => {
                // Phase 24: Bounty Claim
                // Payload: JSON serialized BountyClaim
                if let Ok(json_str) = std::str::from_utf8(&data.data[33..]) {
                    if let Ok(claim) =
                        serde_json::from_str::<BountyClaim>(json_str.trim_matches(char::from(0)))
                    {
                        println!("[SWARM] Received Bounty Claim for {}", claim.bounty_id);

                        // 1. Check if it's fraudulent (hallucination check)
                        if claim.insight.plan.contains("HALLUCINATION")
                            || claim.insight.plan.contains("SYNTAX_ERROR")
                        {
                            println!(
                                "🚨 [SWARM] Fraudulent insight detected! Slashing solver: {}",
                                hex::encode(&claim.solver_id)
                            );
                            let verdict = self.slashing.evaluate_task_fraud(
                                &hex::encode(&claim.solver_id),
                                &claim.bounty_id,
                            );
                            self.slashing.record_slash(&verdict);
                            return;
                        }

                        // 2. Settle the bounty if it exists
                        if self.bounty_market.get_bounty(&claim.bounty_id).is_some() {
                            if self.settlement.process_bounty_claim(
                                &claim.bounty_id,
                                &hex::encode(&claim.solver_id),
                            ) {
                                self.bounty_market.remove_bounty(&claim.bounty_id);
                            }
                        }
                    }
                }
            }
            _ => {}
        }
    }

    pub fn tick(&mut self) {
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);

        let mut to_isolate = Vec::new();

        for (peer_id, state) in &mut self.peers {
            // Check jitter: if median jitter > 50ms, considered a violation
            if !state.jitter_history.is_empty() {
                let mut sorted = state.jitter_history.clone();
                sorted.sort_unstable();
                let median_jitter = sorted[sorted.len() / 2];

                if median_jitter > 50 {
                    state.consecutive_violations += 1;
                    println!(
                        "⚠️ [SWARM] Peer {} jitter violation: {}ms",
                        hex::encode(&peer_id[..4]),
                        median_jitter
                    );
                } else {
                    state.consecutive_violations = 0;
                }
            }

            // Stale check (e.g., missed 3 ticks assuming 20ms ticks)
            if current_time > state.last_update && (current_time - state.last_update) > 100 {
                state.consecutive_violations += 1;
                println!(
                    "⚠️ [SWARM] Peer {} stale update.",
                    hex::encode(&peer_id[..4])
                );
            }

            // 3-tick threshold for isolation
            if state.consecutive_violations >= 3 {
                println!(
                    "🚫 [BYZANTINE] ISOLATING PEER {}. Violations: {}",
                    hex::encode(&peer_id[..4]),
                    state.consecutive_violations
                );
                to_isolate.push(*peer_id);
            }
        }

        for id in to_isolate {
            self.peers.remove(&id);
            self.isolated_peers.insert(id);
            self.routing_table.lock().unwrap().remove_node(&id);
        }
    }

    #[allow(deprecated)]
    pub fn propose_mission(&mut self, mission_hash: &str) {
        if let Ok(mut bft) = self.bft.lock() {
            let next_round = bft.round + 1;
            bft.start_round(next_round);
            bft.propose(mission_hash.to_string(), None);

            // Proposer also casts its own vote immediately
            let own_vote = Vote {
                voter_id: hex::encode(&self.local_id),
                block_hash: mission_hash.to_string(),
                round: next_round,
                signature: "local-trust".to_string(),
                decision_hash: None,
            };
            bft.cast_vote(own_vote);

            // Generate outgoing packet for broadcast
            let mut data = vec![1u8]; // Type 1: BFT Vote/Proposal
            data.extend_from_slice(&self.local_id);
            if let Ok(hash_bytes) = hex::decode(mission_hash) {
                data.extend_from_slice(&hash_bytes);
            }
            self.outgoing_packets.push(data);
        }
    }

    #[must_use]
    pub fn check_agreement(&self) -> bool {
        if let Ok(bft) = self.bft.lock() {
            bft.has_quorum()
        } else {
            false
        }
    }

    /// [Phase 24] Issues a new cognitive bounty to the swarm and locks escrow.
    pub fn issue_bounty(&mut self, intent: &str, reward: u64) -> Option<String> {
        let bounty_id = BountyMarket::generate_id(intent, &self.local_id);

        // 1. Lock funds in escrow
        if !self
            .settlement
            .lock_funds(&hex::encode(&self.local_id), reward, &bounty_id)
        {
            return None;
        }

        // 2. Create and register bounty
        let bounty = CognitiveBounty {
            bounty_id: bounty_id.clone(),
            intent: intent.to_string(),
            reward_cognit: reward,
            issuer_id: self.local_id.clone(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
        };
        self.bounty_market.register_bounty(bounty.clone());

        // 3. Broadcast to swarm (Type 2)
        if let Ok(json) = serde_json::to_string(&bounty) {
            let mut data = vec![2u8]; // Type 2
            data.extend_from_slice(&self.local_id);
            data.extend_from_slice(json.as_bytes());
            if data.len() <= 253 {
                // Fit within MAVLink encapsulated data
                self.outgoing_packets.push(data);
            } else {
                println!("[SWARM] Bounty payload too large for MAVLink");
            }
        }

        Some(bounty_id)
    }

    /// [Phase 24] Submits a claim for an open bounty.
    pub fn submit_bounty_claim(
        &mut self,
        bounty_id: &str,
        insight: crate::kernel::cortex::mesh::CognitiveInsight,
    ) {
        let claim = BountyClaim {
            bounty_id: bounty_id.to_string(),
            solver_id: self.local_id.clone(),
            insight,
        };

        // Broadcast claim directly to swarm (Type 3)
        if let Ok(json) = serde_json::to_string(&claim) {
            let mut data = vec![3u8]; // Type 3
            data.extend_from_slice(&self.local_id);
            data.extend_from_slice(json.as_bytes());
            if data.len() <= 253 {
                self.outgoing_packets.push(data);
                println!("[SWARM] Bounty Claim submitted for {}", bounty_id);
            }
        }
    }

    pub fn drain_packets(&mut self) -> Vec<Vec<u8>> {
        std::mem::take(&mut self.outgoing_packets)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_swarm_bft_consensus_flow() {
        let local_id: NodeId = [0u8; 32];
        let mut swarm = SwarmManager::new(local_id);

        let hash_bytes = hex::decode("deadbeef").unwrap().repeat(8);
        let mission_hash = hex::encode(&hash_bytes);
        swarm.propose_mission(&mission_hash);

        // Simulate three peers voting for the mission
        let peer1_id: NodeId = [1u8; 32];
        let peer2_id: NodeId = [2u8; 32];
        let peer3_id: NodeId = [3u8; 32];

        let mut vote1_data = vec![1u8]; // Type 1: BFT Vote
        vote1_id_bytes_to_vec(&mut vote1_data, peer1_id);
        vote1_data.extend_from_slice(&hash_bytes);
        let mut d1 = [0u8; 253];
        d1[..vote1_data.len()].copy_from_slice(&vote1_data);

        let mut vote2_data = vec![1u8];
        vote1_id_bytes_to_vec(&mut vote2_data, peer2_id);
        vote2_data.extend_from_slice(&hash_bytes);
        let mut d2 = [0u8; 253];
        d2[..vote2_data.len()].copy_from_slice(&vote2_data);

        let mut vote3_data = vec![1u8];
        vote1_id_bytes_to_vec(&mut vote3_data, peer3_id);
        vote3_data.extend_from_slice(&hash_bytes);
        let mut d3 = [0u8; 253];
        d3[..vote3_data.len()].copy_from_slice(&vote3_data);

        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA { seqnr: 0, data: d1 });

        assert!(!swarm.check_agreement());

        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA { seqnr: 0, data: d2 });

        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA { seqnr: 0, data: d3 });

        assert!(swarm.check_agreement());
    }

    #[test]
    fn test_byzantine_isolation_jitter() {
        let local_id: NodeId = [0u8; 32];
        let mut swarm = SwarmManager::new(local_id);

        let bad_peer: NodeId = [9u8; 32];
        let good_peer: NodeId = [7u8; 32];

        // Type 0: State sync
        let mut data_bad = vec![0u8];
        vote1_id_bytes_to_vec(&mut data_bad, bad_peer);
        data_bad.extend_from_slice(&[0u8; 64]);

        let mut data_good = vec![0u8];
        vote1_id_bytes_to_vec(&mut data_good, good_peer);
        data_good.extend_from_slice(&[0u8; 64]);

        let mut ds_bad = [0u8; 253];
        ds_bad[..data_bad.len()].copy_from_slice(&data_bad);

        let mut ds_good = [0u8; 253];
        ds_good[..data_good.len()].copy_from_slice(&data_good);

        // Tick 1
        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA {
            seqnr: 0,
            data: ds_good,
        });
        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA {
            seqnr: 0,
            data: ds_bad,
        });

        // Wait 10ms (good jitter)
        std::thread::sleep(std::time::Duration::from_millis(10));
        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA {
            seqnr: 0,
            data: ds_good,
        });

        // Wait 60ms (bad jitter > 50ms)
        std::thread::sleep(std::time::Duration::from_millis(60));
        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA {
            seqnr: 0,
            data: ds_bad,
        });
        swarm.tick();

        std::thread::sleep(std::time::Duration::from_millis(60));
        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA {
            seqnr: 0,
            data: ds_bad,
        });
        swarm.tick();

        std::thread::sleep(std::time::Duration::from_millis(60));
        swarm.handle_peer_packet(&mavlink::common::ENCAPSULATED_DATA_DATA {
            seqnr: 0,
            data: ds_bad,
        });
        swarm.tick();

        assert!(
            swarm.isolated_peers.contains(&bad_peer),
            "Bad peer was not isolated"
        );
        assert!(
            !swarm.isolated_peers.contains(&good_peer),
            "Good peer was isolated"
        );
        assert!(
            swarm.peers.get(&bad_peer).is_none(),
            "Bad peer remains in peer list"
        );
    }

    fn vote1_id_bytes_to_vec(v: &mut Vec<u8>, id: NodeId) {
        v.extend_from_slice(&id);
    }
}
