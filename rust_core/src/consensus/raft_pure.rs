//! Pure Rust Raft Consensus Engine (Operation Ironclad)
//!
//! A high-performance, async-first implementation of Raft, decoupled from Python.
//! Designed for the multi-relativistic timeline.

use crate::consensus::types::{LogEntry, RaftRPC, RaftState};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashSet};
use std::time::{Duration, Instant};
use tokio::sync::mpsc;

/// Internal events for the Raft Core loop
#[derive(Debug)]
pub enum RaftEvent {
    Tick,
    RPC(RaftRPC),
    ClientRequest(Vec<u8>), // Command to apply
    AdminCommand(String),   // e.g., "snapshot", "add_peer"
}

/// The pure Rust Raft Core state machine
pub struct RaftCore {
    // Identity
    pub node_id: String,
    pub peers: HashSet<String>,

    // Persistent State
    pub current_term: u64,
    pub voted_for: Option<String>,
    pub log: Vec<LogEntry>,

    // Volatile State
    pub commit_index: usize,
    pub last_applied: usize,
    pub state: RaftState,

    // Leader State
    pub next_index: BTreeMap<String, usize>,
    pub match_index: BTreeMap<String, usize>,

    // [Quick Win 1] Current leader tracking for client redirects
    pub leader_id: Option<String>,

    // Timers
    pub election_timeout: Duration,
    pub heartbeat_interval: Duration,
    pub last_heartbeat: Instant,

    // Channels
    pub inbox: mpsc::Receiver<RaftEvent>,
    pub outbound: mpsc::Sender<RaftRPC>, // To Networking Layer
}

impl RaftCore {
    #[must_use]
    pub fn new(
        node_id: String,
        peers: Vec<String>,
        inbox: mpsc::Receiver<RaftEvent>,
        outbound: mpsc::Sender<RaftRPC>,
    ) -> Self {
        Self {
            node_id,
            peers: peers.into_iter().collect(),
            current_term: 0,
            voted_for: None,
            log: Vec::new(),
            commit_index: 0,
            last_applied: 0,
            state: RaftState::Follower,
            next_index: BTreeMap::new(),
            match_index: BTreeMap::new(),
            leader_id: None, // [Quick Win 1] Initialized as None
            election_timeout: Duration::from_millis(1500), // Default, will be dynamic
            heartbeat_interval: Duration::from_millis(500),
            last_heartbeat: Instant::now(),
            inbox,
            outbound,
        }
    }

    /// Main Event Loop
    pub async fn run(&mut self) {
        let tick_interval = Duration::from_millis(100);
        let mut ticker = tokio::time::interval(tick_interval);

        loop {
            tokio::select! {
                _ = ticker.tick() => {
                    self.tick().await;
                }
                Some(event) = self.inbox.recv() => {
                    self.handle_event(event).await;
                }
            }
        }
    }

    async fn handle_event(&mut self, event: RaftEvent) {
        match event {
            RaftEvent::Tick => self.tick().await,
            RaftEvent::RPC(rpc) => self.handle_rpc(rpc).await,
            RaftEvent::ClientRequest(data) => self.handle_client_request(data).await,
            RaftEvent::AdminCommand(cmd) => {
                println!("[RaftCore] Admin command received: {}", cmd)
            }
        }
    }

    async fn tick(&mut self) {
        let now = Instant::now();
        match self.state {
            RaftState::Follower | RaftState::Candidate => {
                if now.duration_since(self.last_heartbeat) > self.election_timeout {
                    self.start_election().await;
                }
            }
            RaftState::Leader => {
                if now.duration_since(self.last_heartbeat) > self.heartbeat_interval {
                    self.send_heartbeats().await;
                    self.last_heartbeat = now;
                }
            }
        }
    }

    async fn start_election(&mut self) {
        println!(
            "🗳️ [RaftCore] Election Timeout! Starting election for term {}",
            self.current_term + 1
        );
        self.state = RaftState::Candidate;
        self.current_term += 1;
        self.voted_for = Some(self.node_id.clone());
        self.last_heartbeat = Instant::now(); // Reset timer

        // Vote for self
        let mut _votes_received = 1;

        // Request votes from peers
        let _last_log_idx = self.log.len().saturating_sub(1);
        let _last_log_term = self.log.last().map(|e| e.term).unwrap_or(0);

        // TODO: Broadcast RequestVote RPC
        // For now, placeholders for pure logic
    }

    async fn send_heartbeats(&mut self) {
        // Broadcast AppendEntries (Heartbeat)
    }

    async fn handle_rpc(&mut self, rpc: RaftRPC) {
        match rpc.rpc_type.as_str() {
            "RequestVote" => self.handle_request_vote(rpc).await,
            "AppendEntries" => self.handle_append_entries(rpc).await,
            _ => println!("[RaftCore] Unknown RPC type: {}", rpc.rpc_type),
        }
    }
}

/// DTOs for Raft RPC Payloads
#[derive(Debug, Serialize, Deserialize)]
pub struct RequestVoteDTO {
    pub term: u64,
    pub candidate_id: String,
    pub last_log_index: i64,
    pub last_log_term: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RequestVoteResponseDTO {
    pub term: u64,
    pub vote_granted: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AppendEntriesDTO {
    pub term: u64,
    pub leader_id: String,
    pub prev_log_index: i64,
    pub prev_log_term: u64,
    pub entries: Vec<LogEntry>,
    pub leader_commit: i64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AppendEntriesResponseDTO {
    pub term: u64,
    pub success: bool,
    pub match_index: i64,
}

impl RaftCore {
    // ... (new and run methods unchanged) ...

    fn create_rpc(&self, rpc_type: &str, payload: String, target: Option<String>) -> RaftRPC {
        RaftRPC {
            rpc_type: rpc_type.to_string(),
            term: self.current_term,
            sender_id: self.node_id.clone(),
            target_id: target,
            payload,
            signature: String::new(), // TODO: Sign with Hardware Key
            poseidon_hash: String::new(),
        }
    }

    async fn handle_request_vote(&mut self, rpc: RaftRPC) {
        let request: RequestVoteDTO = match serde_json::from_str(&rpc.payload) {
            Ok(req) => req,
            Err(e) => {
                println!("[RaftCore] Failed to parse RequestVote payload: {}", e);
                return;
            }
        };

        println!(
            "🗳️ [RaftCore] Received RequestVote from {} for term {}",
            request.candidate_id, request.term
        );

        if request.term > self.current_term {
            self.current_term = request.term;
            self.state = RaftState::Follower;
            self.voted_for = None;
        }

        let mut vote_granted = false;

        if request.term < self.current_term {
            println!(
                "❌ [RaftCore] Vote denied: Candidate term {} < Current term {}",
                request.term, self.current_term
            );
        } else if self.voted_for.is_none() || self.voted_for == Some(request.candidate_id.clone()) {
            // Check log up-to-dateness
            let last_log_idx = self.log.len() as i64 - 1;
            let last_log_term = self.log.last().map(|e| e.term).unwrap_or(0);

            if request.last_log_term > last_log_term
                || (request.last_log_term == last_log_term
                    && request.last_log_index >= last_log_idx)
            {
                vote_granted = true;
                self.voted_for = Some(request.candidate_id.clone());
                self.last_heartbeat = Instant::now(); // Reset election timer
                println!("[RaftCore] Vote granted to {}", request.candidate_id);
            } else {
                println!("[RaftCore] Vote denied: Log not up-to-date");
            }
        } else {
            println!(
                "❌ [RaftCore] Vote denied: Already voted for {:?}",
                self.voted_for
            );
        }

        let response = RequestVoteResponseDTO {
            term: self.current_term,
            vote_granted,
        };

        let response_rpc = self.create_rpc(
            "RequestVoteResponse",
            serde_json::to_string(&response).unwrap(),
            Some(rpc.sender_id),
        );

        if let Err(e) = self.outbound.send(response_rpc).await {
            eprintln!("[RaftCore] Failed to send VoteResponse: {}", e);
        }
    }

    async fn handle_append_entries(&mut self, rpc: RaftRPC) {
        let request: AppendEntriesDTO = match serde_json::from_str(&rpc.payload) {
            Ok(req) => req,
            Err(e) => {
                println!("[RaftCore] Failed to parse AppendEntries payload: {}", e);
                return;
            }
        };

        if request.term > self.current_term {
            self.current_term = request.term;
            self.state = RaftState::Follower;
            self.voted_for = None;
        }

        let mut success = false;
        let mut match_index = 0;

        if request.term < self.current_term {
            println!(
                "❌ [RaftCore] AppendEntries denied: Leader term {} < Current term {}",
                request.term, self.current_term
            );
        } else {
            self.state = RaftState::Follower;
            self.leader_id = Some(request.leader_id.clone()); // [Quick Win 1] Track current leader
            self.last_heartbeat = Instant::now();

            let prev_idx = request.prev_log_index;
            let prev_term = request.prev_log_term;

            // Check log consistency
            let log_len = self.log.len() as i64;

            // Log verification logic
            // 1. If prev_idx == -1, it's the start of the log (genesis)
            // 2. Or, we have an entry at prev_idx with matching term
            if prev_idx == -1
                || (prev_idx < log_len && self.log[prev_idx as usize].term == prev_term)
            {
                success = true;

                // Truncate mismatching logs if necessary (optimization: find mismatch point)
                // For simplicity, strict Raft: if new entries conflict, delete existing.
                // Here we just append.

                let mut current_idx = prev_idx + 1;
                for entry in request.entries {
                    if current_idx < self.log.len() as i64 {
                        if self.log[current_idx as usize].term != entry.term {
                            // Conflict: Delete this and all following
                            self.log.truncate(current_idx as usize);
                            self.log.push(entry);
                        }
                        // Else: match, skip (already have it)
                    } else {
                        // Append new entry
                        self.log.push(entry);
                    }
                    current_idx += 1;
                }

                match_index = self.log.len() as i64 - 1;

                // Update commit index
                if request.leader_commit > self.commit_index as i64 {
                    self.commit_index = request.leader_commit.min(match_index) as usize;
                    // TODO: Apply to State Machine
                }
            } else {
                println!(
                    "❌ [RaftCore] Log inconsistency: prev_idx={}, log_len={}, stored_term={}",
                    prev_idx,
                    log_len,
                    if prev_idx >= 0 && prev_idx < log_len {
                        self.log[prev_idx as usize].term
                    } else {
                        0
                    }
                );
            }
        }

        let response = AppendEntriesResponseDTO {
            term: self.current_term,
            success,
            match_index,
        };

        let response_rpc = self.create_rpc(
            "AppendEntriesResponse",
            serde_json::to_string(&response).unwrap(),
            Some(rpc.sender_id),
        );

        if let Err(e) = self.outbound.send(response_rpc).await {
            eprintln!("[RaftCore] Failed to send AppendResponse: {}", e);
        }
    }

    async fn handle_client_request(&mut self, _data: Vec<u8>) {
        if self.state != RaftState::Leader {
            // Redirect to leader?
            return;
        }
        // Append to log and replicate
    }
}
