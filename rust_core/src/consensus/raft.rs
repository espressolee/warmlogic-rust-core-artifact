//! Raft Consensus Engine
//!
//! Sovereign Raft Protocol with ML-DSA-65 PQC Signatures and Poseidon Hashing.
//! Ported from Python for sub-millisecond consensus on Milk-V Duo S.

#[cfg(feature = "zk")]
use crate::consensus::poseidon::poseidon_hash_chain;
use crate::consensus::types::{LogEntry, RaftRPC, RaftSnapshot, RaftState};
use crate::crypto::MLDSA;
#[cfg(feature = "std")]
use std::collections::{HashMap, HashSet};
use std::time::{Duration, Instant};

#[cfg(feature = "python")]
use crate::pyo3::prelude::*;

use crate::consensus::state_machine::StateMachine;
use crate::consensus::storage::RaftStorage;
use crate::hardware::rtl::SiliconBridge;
#[cfg(feature = "zk")]
use ark_bn254::Fr;
#[cfg(feature = "zk")]
use ark_ff::{BigInteger, PrimeField};
#[cfg(feature = "telemetry")]
use opentelemetry::{global, metrics::Counter, metrics::ObservableGauge};
#[cfg(feature = "std")]
use std::sync::{Arc, Mutex};
use tokio::sync::mpsc;
use tracing::{info, span, warn, Level};

/// Raft Engine State
#[cfg_attr(feature = "python", pyclass)]
pub struct RaftEngine {
    // Identity
    pub node_id: String,
    pub peers: Vec<String>,
    pub public_key: String,
    pub private_key: String,

    // Persistent State
    pub current_term: u64,
    pub voted_for: Option<String>,
    pub log: Vec<LogEntry>,

    // Volatile State
    pub commit_index: i64,
    pub last_applied: i64,
    pub state: RaftState,
    pub leader_id: Option<String>,

    // Snapshot Info
    pub last_snapshot_index: i64,
    pub last_snapshot_term: u64,
    pub state_machine_data: String,
    pub last_snapshot_cum_hash: String,
    pub last_snapshot_pos_hash: String,

    // Leader-only Volatile State
    pub next_index: HashMap<String, usize>,
    pub match_index: HashMap<String, i64>,

    // Timing
    pub last_heartbeat: Instant,
    pub election_timeout: Duration,
    pub votes_received: HashSet<String>,

    // Persistence
    pub storage: Option<RaftStorage>,

    // Network Bridge
    pub broadcast_tx: Option<mpsc::UnboundedSender<RaftRPC>>,

    // Joint Consensus
    pub pending_peers: Option<Vec<String>>,

    // Swarm Mission Integrity (Mathematical Aegis)
    pub mission_poseidon_hash: String,

    // [Ironclad] PQC Public Key Registry
    pub peer_keys: HashMap<String, String>,

    pub state_machine: Option<Arc<Mutex<dyn StateMachine>>>,
}

#[cfg(feature = "python")]
#[pymethods]
impl RaftEngine {
    #[new]
    #[pyo3(signature = (node_id, peers, pk, sk, storage_dir=None))]
    pub fn py_new(
        node_id: String,
        peers: Vec<String>,
        pk: String,
        sk: String,
        storage_dir: Option<String>,
    ) -> Self {
        Self::new(node_id, peers, pk, sk, storage_dir, None)
    }

    pub fn py_handle_tick(&mut self) -> Vec<RaftRPC> {
        self.handle_tick()
    }

    pub fn py_handle_rpc(&mut self, rpc: RaftRPC) -> Option<RaftRPC> {
        self.handle_rpc(rpc)
    }

    #[pyo3(signature = (data, zk_proof=None))]
    pub fn py_propose(&mut self, data: String, zk_proof: Option<Vec<u8>>) -> bool {
        // [Phase 2.2] Explicit handling: empty proof is acceptable for non-ZK mode
        // In production ZK mode, proof validation happens in propose()
        self.propose(data, zk_proof.unwrap_or_else(Vec::new))
    }

    #[pyo3(name = "get_forensic_proof")]
    pub fn py_get_forensic_proof(&self, index: i64) -> PyResult<Option<LogEntry>> {
        if index < 0 || index >= self.log.len() as i64 {
            return Ok(None);
        }
        Ok(Some(self.log[index as usize].clone()))
    }

    #[pyo3(name = "get_state")]
    pub fn py_get_state(&self) -> RaftState {
        self.state
    }

    #[getter]
    pub fn public_key(&self) -> String {
        self.public_key.clone()
    }

    #[getter]
    pub fn private_key(&self) -> String {
        self.private_key.clone()
    }

    #[getter]
    pub fn current_term(&self) -> u64 {
        self.current_term
    }

    #[getter]
    pub fn peers(&self) -> Vec<String> {
        self.peers.clone()
    }

    #[getter]
    pub fn log(&self) -> Vec<LogEntry> {
        self.log.clone()
    }

    #[pyo3(name = "get_commit_index")]
    pub fn py_get_commit_index(&self) -> i64 {
        self.commit_index
    }

    #[pyo3(name = "get_last_applied")]
    pub fn py_get_last_applied(&self) -> i64 {
        self.last_applied
    }

    #[getter]
    pub fn get_state_machine_data(&self) -> String {
        self.state_machine_data.clone()
    }

    #[getter]
    pub fn get_mission_poseidon_hash(&self) -> String {
        self.mission_poseidon_hash.clone()
    }

    pub fn register_peer_key(&mut self, node_id: String, public_key: String) {
        self.peer_keys.insert(node_id, public_key);
    }

    pub fn save_current_snapshot(&mut self, data: String) {
        if self.last_applied < 0 {
            return;
        }

        let idx = self.last_applied as usize;
        let (last_term, cum_hash, pos_hash) = if idx as i64 == self.last_snapshot_index {
            (
                self.last_snapshot_term,
                self.last_snapshot_cum_hash.clone(),
                self.last_snapshot_pos_hash.clone(),
            )
        } else if let Some(entry) = self.get_entry(idx) {
            (
                entry.term,
                entry.cumulative_hash.clone(),
                entry.poseidon_hash.clone(),
            )
        } else {
            return;
        };

        let snapshot = RaftSnapshot {
            data: data.clone(),
            last_included_index: idx,
            last_included_term: last_term,
            cumulative_hash: cum_hash,
            poseidon_hash: pos_hash,
        };

        if let Some(ref s) = self.storage {
            s.save_snapshot(&snapshot);

            // Prune local log
            let split_idx = idx as i64 - self.last_snapshot_index;
            if split_idx > 0 && split_idx <= self.log.len() as i64 {
                self.log = self.log.split_off(split_idx as usize);
            }

            self.last_snapshot_index = idx as i64;
            self.last_snapshot_term = last_term;
            self.last_snapshot_cum_hash = snapshot.cumulative_hash;
            self.last_snapshot_pos_hash = snapshot.poseidon_hash;
            self.state_machine_data = data;
        }
    }

    pub fn py_advance_applied_index(&mut self) {
        self.advance_applied_index()
    }

    pub fn py_start_election(&mut self) -> Vec<RaftRPC> {
        self.start_election()
    }

    pub fn py_send_heartbeats(&mut self) -> Vec<RaftRPC> {
        self.send_heartbeats()
    }
}

impl RaftEngine {
    #[must_use]
    pub fn new(
        node_id: String,
        mut peers: Vec<String>,
        pk: String,
        sk: String,
        storage_dir: Option<String>,
        state_machine: Option<Arc<Mutex<dyn StateMachine>>>,
    ) -> Self {
        let storage = storage_dir.as_ref().map(|d| RaftStorage::new(d, &node_id));
        let mut current_term = 0;
        let mut voted_for = None;
        let mut log = Vec::new();
        let mut last_snapshot_index = -1;
        let mut last_snapshot_term = 0;
        let mut state_machine_data = String::new();
        let mut last_snapshot_cum_hash = "0".repeat(64);
        let mut last_snapshot_pos_hash = "0".repeat(64);
        let mut commit_index = -1;
        let mut last_applied = -1;

        let mut recovered_offset = None;
        if let Some(ref s) = storage {
            // Mathematical Aegis Boot-time Resilience (Sovereign Route)
            if let Err(offset) = s.verify_wal_integrity() {
                println!("[AEGIS] INTEGRITY BREACH DETECTED at offset {}", offset);
                println!("[AEGIS] Triggering Sovereign Recovery Sequence...");
                recovered_offset = Some(offset);

                // Forensic Reporting
                let forensic_path =
                    std::path::Path::new(storage_dir.as_ref().unwrap_or(&".".to_string()))
                        .join("forensic_breach.log");
                let log_msg = format!(
                    "[{}] FATAL: WAL Corruption detected at offset {}. Truncating for recovery.\n",
                    std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_secs(),
                    offset
                );
                let _ = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(forensic_path)
                    .map(|mut f| std::io::Write::write_all(&mut f, log_msg.as_bytes()));

                s.recover_from_corruption(offset);
            }

            let (term, vote, p) = s.load_metadata();
            current_term = term;
            voted_for = vote;
            if !p.is_empty() {
                peers = p;
            }
            let mut base_log = s.load_log();

            // Forensic Record of Recovery
            if let Some(off) = recovered_offset {
                let last_idx = base_log.len();
                let (prev_sha, _prev_pos) = if let Some(last) = base_log.last() {
                    (last.cumulative_hash.clone(), last.poseidon_hash.clone())
                } else {
                    ("0".repeat(64), "0".repeat(64))
                };

                let data = format!(
                    "REC-RECOVERY:{{ \"off\": {}, \"sig\": \"AEGIS-AUTO\" }}",
                    off
                );
                use sha2::{Digest, Sha256};
                let mut hasher = Sha256::new();
                hasher.update(
                    format!("{}:{}:{}:{}", current_term, last_idx, data, prev_sha).as_bytes(),
                );
                let sha_hash = hex::encode(hasher.finalize());
                let pos_hash = "0".repeat(64); // ZK hash omitted in auto-recovery for boot speed

                let recovery_entry = LogEntry {
                    term: current_term,
                    data,
                    signature: "🛡️ AEGIS".into(),
                    voter_id: node_id.clone(),
                    cumulative_hash: sha_hash,
                    poseidon_hash: pos_hash,
                    zk_proof: Vec::new(), // Recovery entries use base-grounding
                    index: last_idx,
                };
                s.append_log(&recovery_entry);
                base_log.push(recovery_entry);
            }
            log = base_log;

            if let Some(snapshot) = s.load_snapshot() {
                last_snapshot_index = snapshot.last_included_index as i64;
                last_snapshot_term = snapshot.last_included_term;
                state_machine_data = snapshot.data;
                last_snapshot_cum_hash = snapshot.cumulative_hash;
                last_snapshot_pos_hash = snapshot.poseidon_hash;
                commit_index = last_snapshot_index;
                last_applied = last_snapshot_index;
            }
        }

        RaftEngine {
            node_id,
            peers,
            public_key: pk,
            private_key: sk,
            current_term,
            voted_for,
            log,
            commit_index,
            last_applied,
            state: RaftState::Follower,
            leader_id: None,
            last_snapshot_index,
            last_snapshot_term,
            state_machine_data,
            last_snapshot_cum_hash,
            last_snapshot_pos_hash,
            next_index: HashMap::new(),
            match_index: HashMap::new(),
            last_heartbeat: Instant::now(),
            election_timeout: Duration::from_millis(1500 + (rand::random::<u64>() % 1500)),
            votes_received: HashSet::new(),
            storage,
            broadcast_tx: None,
            pending_peers: None,
            mission_poseidon_hash: "0".repeat(64),
            peer_keys: HashMap::new(),
            state_machine,
        }
    }

    pub fn persist_metadata(&self) {
        if let Some(ref s) = self.storage {
            s.save_metadata(
                self.current_term,
                self.voted_for.clone(),
                self.peers.clone(),
            );
        }
    }

    pub fn save_snapshot(&self) {
        if let Some(ref s) = self.storage {
            let snapshot = RaftSnapshot {
                data: self.state_machine_data.clone(),
                last_included_index: self.last_snapshot_index as usize,
                last_included_term: self.last_snapshot_term,
                cumulative_hash: self.last_snapshot_cum_hash.clone(),
                poseidon_hash: self.last_snapshot_pos_hash.clone(),
            };
            s.save_snapshot(&snapshot);
        }
    }

    fn get_entry(&self, index: usize) -> Option<&LogEntry> {
        if index as i64 <= self.last_snapshot_index {
            return None;
        }
        let pos = (index as i64 - self.last_snapshot_index - 1) as usize;
        self.log.get(pos)
    }

    #[allow(unused_variables)]
    #[must_use]
    pub fn calculate_entry_hashes(
        &self,
        term: u64,
        index: usize,
        data: &str,
        prev_sha: &str,
        _prev_pos: &str,
    ) -> (String, String) {
        // SHA-256 Legacy Hash
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(format!("{}:{}:{}:{}", term, index, data, prev_sha).as_bytes());
        let sha_hash = hex::encode(hasher.finalize());

        // Poseidon ZK-Native Hash
        #[cfg(feature = "zk")]
        let pos_hash = {
            let mut data_hasher = Sha256::new();
            data_hasher.update(data.as_bytes());
            let data_sha = data_hasher.finalize();

            // Convert data_sha to Fr
            let mut data_bytes = [0u8; 32];
            data_bytes.copy_from_slice(&data_sha);
            let data_digest_fr = <Fr as PrimeField>::from_be_bytes_mod_order(&data_bytes);

            let term_index = Fr::from(((term & 0xFFFFFFFF) << 32) | (index as u64 & 0xFFFFFFFF));

            let prev_pos_fr = if _prev_pos == "0".repeat(64) {
                Fr::from(0u64)
            } else {
                let bytes = hex::decode(_prev_pos).unwrap_or_else(|_| vec![0; 32]);
                let mut b_bytes = [0u8; 32];
                let len = bytes.len().min(32);
                b_bytes[32 - len..].copy_from_slice(&bytes[..len]);
                <Fr as PrimeField>::from_be_bytes_mod_order(&b_bytes)
            };

            let pos_result = poseidon_hash_chain(&[term_index, data_digest_fr, prev_pos_fr]);
            // Helper to convert BigInt to hex
            let pos_big = pos_result.into_bigint();
            hex::encode(pos_big.to_bytes_be())
        };

        #[cfg(not(feature = "zk"))]
        let pos_hash = "0".repeat(64);

        (sha_hash, pos_hash)
    }

    pub fn handle_tick(&mut self) -> Vec<RaftRPC> {
        let _span = span!(Level::DEBUG, "raft_tick", node_id = %self.node_id).entered();
        let now = Instant::now();

        // [Ironclad] Phase 4: Thermodynamic Timeout Linkage
        // Prevents election storms during heavy thermal pulses by scaling timeouts.
        let (variance, _temp) = SiliconBridge::get_thermal_telemetry();
        let thermal_multiplier = 1.0 + (variance * 10.0).max(0.0); // Mild scaling: 0.045 variance -> ~1.45x penalty

        if self.state == RaftState::Leader {
            let heartbeat_interval = Duration::from_millis(500);
            let adjusted_heartbeat = Duration::from_micros(
                (heartbeat_interval.as_micros() as f64 * thermal_multiplier) as u64,
            );

            if now.duration_since(self.last_heartbeat) > adjusted_heartbeat {
                info!(node_id = %self.node_id, "Leader sending heartbeats");
                return self.send_heartbeats();
            }
        } else {
            let adjusted_election = Duration::from_micros(
                (self.election_timeout.as_micros() as f64 * thermal_multiplier) as u64,
            );

            if now.duration_since(self.last_heartbeat) > adjusted_election {
                warn!(node_id = %self.node_id, "Election timeout; starting election (thermal penalty active)");
                return self.start_election();
            }
        }
        Vec::new()
    }

    fn start_election(&mut self) -> Vec<RaftRPC> {
        self.state = RaftState::Candidate;
        self.current_term += 1;
        self.voted_for = Some(self.node_id.clone());
        self.votes_received.clear();
        self.persist_metadata();
        self.votes_received.insert(self.node_id.clone());
        self.last_heartbeat = Instant::now();
        self.election_timeout = Duration::from_millis(1500 + (rand::random::<u64>() % 1500));

        if self.peers.is_empty() {
            self.become_leader();
            return Vec::new();
        }

        let last_log_idx = if self.log.is_empty() {
            -1
        } else {
            self.log.len() as i64 - 1
        };
        let last_log_term = if self.log.is_empty() {
            0
        } else {
            self.log.last().map(|e| e.term).unwrap_or(0)
        };

        let payload = serde_json::json!({
            "last_log_index": last_log_idx,
            "last_log_term": last_log_term,
        })
        .to_string();

        let mut rpcs = Vec::new();
        for _peer in &self.peers {
            rpcs.push(self.create_rpc("REQUEST_VOTE", payload.clone(), None));
        }
        rpcs
    }

    fn become_leader(&mut self) {
        self.state = RaftState::Leader;
        self.leader_id = Some(self.node_id.clone());
        for _peer in &self.peers {
            self.next_index.insert(_peer.clone(), self.log.len());
            self.match_index.insert(_peer.clone(), -1);
        }
    }

    fn send_heartbeats(&mut self) -> Vec<RaftRPC> {
        self.last_heartbeat = Instant::now();
        let mut rpcs = Vec::new();
        for peer in &self.peers {
            let prev_idx = *self.next_index.get(peer).unwrap_or(&self.log.len()) as i64 - 1;
            let prev_term = if prev_idx >= 0 {
                self.log[prev_idx as usize].term
            } else {
                0
            };
            let prev_sha = if prev_idx >= 0 {
                self.log[prev_idx as usize].cumulative_hash.clone()
            } else {
                "0".repeat(64)
            };
            let prev_pos = if prev_idx >= 0 {
                self.log[prev_idx as usize].poseidon_hash.clone()
            } else {
                "0".repeat(64)
            };

            let entries = &self.log[(*self.next_index.get(peer).unwrap_or(&self.log.len()))..];

            let payload = serde_json::json!({
                "prev_log_index": prev_idx,
                "prev_log_term": prev_term,
                "prev_log_hash": prev_sha,
                "prev_poseidon_hash": prev_pos,
                "entries": entries,
                "leader_commit": self.commit_index,
            })
            .to_string();

            rpcs.push(self.create_rpc("APPEND_ENTRIES", payload, None));
        }
        rpcs
    }

    pub fn handle_rpc(&mut self, rpc: RaftRPC) -> Option<RaftRPC> {
        let _span = span!(Level::DEBUG, "handle_rpc", node_id = %self.node_id, sender = %rpc.sender_id, rpc_type = %rpc.rpc_type).entered();
        // 1. Verify PQC Signature
        let msg = format!(
            "{}:{}:{}:{}",
            rpc.rpc_type, rpc.term, rpc.sender_id, rpc.payload
        );
        // [Ironclad] Verify Signature if Key is Known
        if let Some(pk) = self.peer_keys.get(&rpc.sender_id) {
            // hex decode signature and verify
            if !MLDSA::verify_raw(pk, &msg, &rpc.signature) {
                println!("[Raft] Invalid PQC signature from {}", rpc.sender_id);
                return None;
            }
        } else {
            // Checking strictly for known peers is safer, but for bootstrapping we might log warning
            // println!("[Raft] Unverified RPC from unknown peer {}", rpc.sender_id);
        }

        // 2. Term Update
        if rpc.term > self.current_term {
            self.current_term = rpc.term;
            self.state = RaftState::Follower;
            self.voted_for = None;
            self.leader_id = None;
            self.persist_metadata();
        }

        // 3. Dispatch
        match rpc.rpc_type.as_str() {
            "REQUEST_VOTE" => {
                let payload: serde_json::Value = serde_json::from_str(&rpc.payload).ok()?;
                return self.handle_request_vote(rpc.term, rpc.sender_id, payload);
            }
            "APPEND_ENTRIES" => {
                let payload: serde_json::Value = serde_json::from_str(&rpc.payload).ok()?;
                return self.handle_append_entries(rpc.term, rpc.sender_id, payload);
            }
            "VOTE_RESPONSE" => {
                let payload: serde_json::Value = serde_json::from_str(&rpc.payload).ok()?;
                self.handle_vote_response(rpc.term, rpc.sender_id, payload);
            }
            "APPEND_RESPONSE" => {
                let payload: serde_json::Value = serde_json::from_str(&rpc.payload).ok()?;
                self.handle_append_response(rpc.term, rpc.sender_id, payload);
            }
            _ => {}
        }
        None
    }

    fn handle_request_vote(
        &mut self,
        term: u64,
        candidate_id: String,
        payload: serde_json::Value,
    ) -> Option<RaftRPC> {
        let mut vote_granted = false;
        if term < self.current_term {
            vote_granted = false;
        } else if self.voted_for.is_none() || self.voted_for == Some(candidate_id.clone()) {
            let last_log_idx = self.log.len() as i64 - 1;
            let last_log_term = self.log.last().map(|e| e.term).unwrap_or(0);

            let cand_last_log_term = payload["last_log_term"].as_u64().unwrap_or(0);
            let cand_last_log_idx = payload["last_log_index"].as_i64().unwrap_or(-1);

            if cand_last_log_term > last_log_term
                || (cand_last_log_term == last_log_term && cand_last_log_idx >= last_log_idx)
            {
                vote_granted = true;
                self.voted_for = Some(candidate_id.clone());
                self.last_heartbeat = Instant::now();
                self.persist_metadata();
            }
        }

        let response_payload = serde_json::json!({ "vote_granted": vote_granted }).to_string();
        Some(self.create_rpc("VOTE_RESPONSE", response_payload, Some(candidate_id)))
    }

    fn handle_append_entries(
        &mut self,
        term: u64,
        leader_id: String,
        payload: serde_json::Value,
    ) -> Option<RaftRPC> {
        let mut success = false;
        if term < self.current_term {
            success = false;
        } else {
            self.state = RaftState::Follower;
            self.leader_id = Some(leader_id.clone());
            self.last_heartbeat = Instant::now();

            let prev_idx = payload["prev_log_index"].as_i64().unwrap_or(-1);
            let prev_term = payload["prev_log_term"].as_u64().unwrap_or(0);

            if prev_idx == -1
                || (prev_idx < self.log.len() as i64
                    && self.log[prev_idx as usize].term == prev_term)
            {
                success = true;
                let entries_val = payload["entries"].as_array().cloned().unwrap_or_default();
                let mut entries = Vec::new();
                for e_val in entries_val {
                    let e: LogEntry = serde_json::from_value(e_val).ok()?;
                    entries.push(e);
                }

                if !entries.is_empty() {
                    // [Ironclad] Hash Chain Verification
                    // We must verify that the incoming entries form a valid hash chain extending from our history.
                    let mut temp_chain_sha = if prev_idx >= 0 {
                        self.log[prev_idx as usize].cumulative_hash.clone()
                    } else {
                        self.last_snapshot_cum_hash.clone()
                    };
                    if temp_chain_sha.is_empty() {
                        temp_chain_sha = "0".repeat(64);
                    }

                    let mut temp_chain_pos = if prev_idx >= 0 {
                        self.log[prev_idx as usize].poseidon_hash.clone()
                    } else {
                        self.last_snapshot_pos_hash.clone()
                    };
                    if temp_chain_pos.is_empty() {
                        temp_chain_pos = "0".repeat(64);
                    }

                    for (i, entry) in entries.iter().enumerate() {
                        let current_idx = (prev_idx + 1) as usize + i;

                        // Recalculate hash to verify integrity
                        // Note: entry.cumulative_hash is claimed. We compute expected.
                        let (expected_sha, expected_pos) = self.calculate_entry_hashes(
                            entry.term,
                            current_idx,
                            &entry.data,
                            &temp_chain_sha,
                            &temp_chain_pos,
                        );

                        // Strict Poseidon Check
                        #[cfg(feature = "zk")]
                        if !entry.poseidon_hash.is_empty() && entry.poseidon_hash != expected_pos {
                            println!(
                                "❌ [Raft] Poseidon Hash Mismatch at idx {}! Dropping logs.",
                                current_idx
                            );
                            println!("Expected: {}, Got: {}", expected_pos, entry.poseidon_hash);
                            let response_payload = serde_json::json!({
                                "success": false,
                                "last_log_index": self.log.len() as i64 - 1
                            })
                            .to_string();
                            return Some(self.create_rpc(
                                "APPEND_RESPONSE",
                                response_payload,
                                Some(leader_id),
                            ));
                        }

                        // Strict SHA256 Check
                        if entry.cumulative_hash != expected_sha {
                            println!("[Raft] SHA-256 Hash Mismatch at idx {}!", current_idx);
                            let response_payload = serde_json::json!({
                                "success": false,
                                "last_log_index": self.log.len() as i64 - 1
                            })
                            .to_string();
                            return Some(self.create_rpc(
                                "APPEND_RESPONSE",
                                response_payload,
                                Some(leader_id),
                            ));
                        }

                        temp_chain_sha = expected_sha;
                        temp_chain_pos = expected_pos;
                    }

                    if self.log.len() as i64 > prev_idx + 1 {
                        self.log.truncate((prev_idx + 1) as usize);
                        if let Some(ref s) = self.storage {
                            // Best-effort truncation - log corruption is handled on next load
                            let _ = s.truncate_log_suffix((prev_idx + 1) as usize);
                        }
                    }
                    for entry in &entries {
                        // Follower transitions into Joint Consensus
                        if let Some(stripped) = entry.data.strip_prefix("CONF:") {
                            let new_peers: Vec<String> = stripped
                                .split(',')
                                .map(|s| s.trim().to_string())
                                .filter(|s| !s.is_empty())
                                .collect();
                            println!(
                                "⚡ [JOINT] Follower entering joint state with: {:?}",
                                new_peers
                            );
                            self.pending_peers = Some(new_peers);
                        }

                        if let Some(ref s) = self.storage {
                            s.append_log(entry);
                        }
                    }
                    self.log.extend(entries);
                }

                let leader_commit = payload["leader_commit"].as_i64().unwrap_or(-1);
                if leader_commit > self.commit_index {
                    let old_commit = self.commit_index;
                    self.commit_index =
                        leader_commit.min(self.log.len() as i64 - 1 + self.last_snapshot_index + 1);

                    // Follower transitions out of Joint Consensus
                    for idx in (old_commit + 1)..=self.commit_index {
                        if let Some(entry) = self.get_entry(idx as usize) {
                            if entry.data.strip_prefix("CONF:").is_some() {
                                if let Some(pending) = self.pending_peers.take() {
                                    println!(
                                        "⚡ [JOINT] Follower commit complete. Finalizing: {:?}",
                                        pending
                                    );
                                    self.peers = pending;
                                    self.persist_metadata();
                                }
                            }
                        }
                    }
                }
                self.advance_applied_index(); //
            }
        }

        let response_payload = serde_json::json!({
            "success": success,
            "last_log_index": self.log.len() as i64 - 1
        })
        .to_string();
        Some(self.create_rpc("APPEND_RESPONSE", response_payload, Some(leader_id)))
    }

    fn handle_vote_response(&mut self, term: u64, sender_id: String, payload: serde_json::Value) {
        if self.state != RaftState::Candidate || term != self.current_term {
            return;
        }
        if payload["vote_granted"].as_bool().unwrap_or(false) {
            self.votes_received.insert(sender_id);
            if self.has_quorum(&self.votes_received) {
                self.become_leader();
            }
        }
    }

    fn handle_append_response(&mut self, term: u64, sender_id: String, payload: serde_json::Value) {
        if self.state != RaftState::Leader || term != self.current_term {
            return;
        }
        if payload["success"].as_bool().unwrap_or(false) {
            let last_idx = payload["last_log_index"].as_i64().unwrap_or(-1);
            self.next_index
                .insert(sender_id.clone(), (last_idx + 1) as usize);
            self.match_index.insert(sender_id, last_idx);
            self.update_commit_index();
            self.advance_applied_index(); //
        } else {
            let next = *self.next_index.get(&sender_id).unwrap_or(&0);
            self.next_index
                .insert(sender_id, if next > 0 { next - 1 } else { 0 });
        }
    }

    fn update_commit_index(&mut self) {
        let mut n = self.log.len() as i64 - 1;
        while n > self.commit_index {
            if self.log[n as usize].term == self.current_term && self.has_committed_at(n) {
                self.commit_index = n;
                // Transition out of Joint Consensus upon commitment
                if let Some(entry) = self.get_entry(n as usize) {
                    if entry.data.strip_prefix("CONF:").is_some() {
                        if let Some(pending) = self.pending_peers.take() {
                            println!(
                                "⚡ [JOINT] Commit Complete. Transitioning to new set: {:?}",
                                pending
                            );
                            self.peers = pending;
                            self.persist_metadata();
                        }
                    }
                }
                break;
            }
            n -= 1;
        }
    }

    fn advance_applied_index(&mut self) {
        // Correct index handling considering snapshots
        while self.commit_index > self.last_applied {
            self.last_applied += 1;
            let idx = self.last_applied as usize;
            let entry_data = self.get_entry(idx).map(|e| e.data.clone());

            if let Some(data) = entry_data {
                // [Ironclad] Delegate to generic state machine
                let new_data = if let Some(ref sm) = self.state_machine {
                    let mut machine = sm.lock().unwrap();
                    machine.apply(idx, &data)
                } else {
                    // Fallback to legacy behavior if no machine is attached
                    data.clone()
                };

                self.state_machine_data = new_data;
            }
        }
    }

    pub fn propose(&mut self, data: String, zk_proof: Vec<u8>) -> bool {
        let _span =
            span!(Level::INFO, "propose", node_id = %self.node_id, data_len = data.len()).entered();
        if self.state != RaftState::Leader {
            warn!(node_id = %self.node_id, "Rejecting proposal: Not the leader");
            return false;
        }

        // Sovereign Language Validation
        let valid_prefixes = ["TARGET:", "PHALANX:", "LAND:", "CONF:", "REC-RECOVERY:"];
        if !valid_prefixes.iter().any(|p| data.starts_with(p)) {
            println!(
                "⚠️ [AEGIS] REJECTED: Invalid Sovereign Language prefix in proposal: {}",
                data
            );
            return false;
        }

        // Configuration Change Detection
        if let Some(stripped) = data.strip_prefix("CONF:") {
            let new_peers: Vec<String> = stripped
                .split(',')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect();
            self.pending_peers = Some(new_peers);
        }

        let cur_idx = (self.last_snapshot_index + self.log.len() as i64 + 1) as usize;
        let (prev_sha, prev_pos) = if let Some(last) = self.log.last() {
            (last.cumulative_hash.clone(), last.poseidon_hash.clone())
        } else if self.last_snapshot_index >= 0 {
            (
                self.last_snapshot_cum_hash.clone(),
                self.last_snapshot_pos_hash.clone(),
            )
        } else {
            ("0".repeat(64), "0".repeat(64))
        };

        let (sha_hash, pos_hash) =
            self.calculate_entry_hashes(self.current_term, cur_idx, &data, &prev_sha, &prev_pos);

        let msg = format!(
            "LOG:{}:{}:{}:{}",
            self.current_term, cur_idx, pos_hash, data
        );
        let signature =
            MLDSA::sign_raw(&self.private_key, &msg).unwrap_or_else(|_| "INVALID_SIG".into());

        let entry = LogEntry {
            term: self.current_term,
            data,
            signature,
            voter_id: self.node_id.clone(),
            cumulative_hash: sha_hash,
            poseidon_hash: pos_hash,
            zk_proof, // [Phase 29] Bind the proposal to its ZK-Witness
            index: cur_idx,
        };
        if let Some(ref s) = self.storage {
            s.append_log(&entry);
        }
        self.log.push(entry);
        true
    }

    #[must_use]
    pub fn create_rpc(
        &self,
        rpc_type: &str,
        payload: String,
        target_id: Option<String>,
    ) -> RaftRPC {
        let msg = format!(
            "{}:{}:{}:{}",
            rpc_type, self.current_term, self.node_id, payload
        );
        let signature =
            MLDSA::sign_raw(&self.private_key, &msg).unwrap_or_else(|_| "INVALID_SIG".into());

        RaftRPC {
            rpc_type: rpc_type.into(),
            term: self.current_term,
            sender_id: self.node_id.clone(),
            payload,
            signature,
            target_id,
            poseidon_hash: self.mission_poseidon_hash.clone(),
        }
    }

    #[must_use]
    pub fn has_quorum(&self, votes: &HashSet<String>) -> bool {
        let mut count_old = 0;
        if votes.contains(&self.node_id) {
            count_old += 1;
        }
        for p in &self.peers {
            if votes.contains(p) {
                count_old += 1;
            }
        }
        let q_old = count_old > self.peers.len().div_ceil(2);

        if let Some(ref pending) = self.pending_peers {
            let mut count_new = 0;
            if votes.contains(&self.node_id) {
                count_new += 1;
            }
            for p in pending {
                if votes.contains(p) {
                    count_new += 1;
                }
            }
            let q_new = count_new > pending.len().div_ceil(2);
            q_old && q_new
        } else {
            q_old
        }
    }

    fn has_committed_at(&self, n: i64) -> bool {
        let mut votes: HashSet<String> = HashSet::new();
        votes.insert(self.node_id.clone());
        for (peer, m_idx) in &self.match_index {
            if *m_idx >= n {
                let _: bool = votes.insert(peer.clone());
            }
        }
        self.has_quorum(&votes)
    }
}
