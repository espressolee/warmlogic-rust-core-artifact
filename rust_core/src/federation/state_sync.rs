//! rust_core/src/federation/state_sync.rs
//! Cross-Region State Synchronization Engine.
//!
//! Implements eventual consistency for multi-region federation:
//! - Decision replication with causal ordering
//! - Conflict detection and resolution
//! - Merkle tree-based state verification
//! - Bandwidth-efficient delta sync

use super::vector_clock::{CausalOrder, VectorClock};
use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_256};
use std::collections::{HashMap, HashSet};

// ============================================================================
// CONFIGURATION
// ============================================================================

/// Maximum entries per sync batch
pub const MAX_SYNC_BATCH_SIZE: usize = 1000;

/// Maximum pending operations before forced flush
pub const MAX_PENDING_OPS: usize = 10_000;

/// Sync interval in milliseconds
pub const DEFAULT_SYNC_INTERVAL_MS: u64 = 1000;

// ============================================================================
// SYNC STATUS
// ============================================================================

/// Status of a synchronization operation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SyncStatus {
    /// Sync pending
    Pending,
    /// Sync in progress
    InProgress,
    /// Sync completed successfully
    Completed,
    /// Sync failed
    Failed,
    /// Conflict detected
    Conflict,
}

/// Conflict resolution strategy
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConflictStrategy {
    /// Last writer wins (based on wall clock)
    LastWriterWins,
    /// Use vector clock (causal ordering)
    VectorClock,
    /// Require manual resolution
    Manual,
    /// Keep both versions
    KeepBoth,
}

// ============================================================================
// STATE ENTRY
// ============================================================================

/// A single state entry with full metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateEntry {
    /// Entry key
    pub key: String,
    /// Entry value (serialized)
    pub value: Vec<u8>,
    /// Vector clock timestamp
    pub clock: VectorClock,
    /// Physical timestamp (milliseconds)
    pub timestamp_ms: u64,
    /// Origin region
    pub origin_region: String,
    /// Entry hash (SHA3-256)
    pub hash: [u8; 32],
    /// Tombstone flag (deleted entry)
    pub deleted: bool,
}

impl StateEntry {
    /// Create a new state entry
    #[must_use]
    pub fn new(key: String, value: Vec<u8>, clock: VectorClock, origin_region: String) -> Self {
        let timestamp_ms = current_time_ms();
        let hash = compute_entry_hash(&key, &value, &clock, timestamp_ms);

        Self {
            key,
            value,
            clock,
            timestamp_ms,
            origin_region,
            hash,
            deleted: false,
        }
    }

    /// Create a tombstone (deletion marker)
    #[must_use]
    pub fn tombstone(key: String, clock: VectorClock, origin_region: String) -> Self {
        let timestamp_ms = current_time_ms();
        let hash = compute_entry_hash(&key, &[], &clock, timestamp_ms);

        Self {
            key,
            value: Vec::new(),
            clock,
            timestamp_ms,
            origin_region,
            hash,
            deleted: true,
        }
    }

    /// Check if this entry supersedes another
    #[must_use]
    pub fn supersedes(&self, other: &StateEntry) -> bool {
        other.clock.happens_before(&self.clock)
    }

    /// Check if entries are concurrent
    #[must_use]
    pub fn is_concurrent(&self, other: &StateEntry) -> bool {
        self.clock.is_concurrent(&other.clock)
    }
}

fn compute_entry_hash(key: &str, value: &[u8], clock: &VectorClock, timestamp: u64) -> [u8; 32] {
    let mut hasher = Sha3_256::new();
    hasher.update(key.as_bytes());
    hasher.update(value);
    hasher.update(clock.to_bytes());
    hasher.update(timestamp.to_le_bytes());
    let result = hasher.finalize();
    let mut hash = [0u8; 32];
    hash.copy_from_slice(&result);
    hash
}

fn current_time_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

// ============================================================================
// CONFLICT
// ============================================================================

/// A conflict between two concurrent entries
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Conflict {
    /// Conflict ID
    pub id: String,
    /// Key with conflict
    pub key: String,
    /// Local entry
    pub local: StateEntry,
    /// Remote entry
    pub remote: StateEntry,
    /// Resolution status
    pub resolved: bool,
    /// Winning entry (if resolved)
    pub winner: Option<String>,
}

impl Conflict {
    /// Create a new conflict
    #[must_use]
    pub fn new(local: StateEntry, remote: StateEntry) -> Self {
        let id = format!(
            "CONFLICT-{}-{}",
            hex::encode(&local.hash[..4]),
            hex::encode(&remote.hash[..4])
        );

        Self {
            id,
            key: local.key.clone(),
            local,
            remote,
            resolved: false,
            winner: None,
        }
    }

    /// Resolve using last-writer-wins
    pub fn resolve_lww(&mut self) -> &StateEntry {
        self.resolved = true;
        if self.local.timestamp_ms >= self.remote.timestamp_ms {
            self.winner = Some("local".to_string());
            &self.local
        } else {
            self.winner = Some("remote".to_string());
            &self.remote
        }
    }

    /// Resolve by choosing local
    pub fn resolve_local(&mut self) -> &StateEntry {
        self.resolved = true;
        self.winner = Some("local".to_string());
        &self.local
    }

    /// Resolve by choosing remote
    pub fn resolve_remote(&mut self) -> &StateEntry {
        self.resolved = true;
        self.winner = Some("remote".to_string());
        &self.remote
    }
}

// ============================================================================
// MERKLE TREE NODE
// ============================================================================

/// Merkle tree node for state verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleNode {
    /// Node hash
    pub hash: [u8; 32],
    /// Left child hash (if internal node)
    pub left: Option<[u8; 32]>,
    /// Right child hash (if internal node)
    pub right: Option<[u8; 32]>,
    /// Key range start
    pub key_start: Option<String>,
    /// Key range end
    pub key_end: Option<String>,
    /// Number of entries in subtree
    pub entry_count: usize,
}

impl MerkleNode {
    /// Create a leaf node
    #[must_use]
    pub fn leaf(entry: &StateEntry) -> Self {
        Self {
            hash: entry.hash,
            left: None,
            right: None,
            key_start: Some(entry.key.clone()),
            key_end: Some(entry.key.clone()),
            entry_count: 1,
        }
    }

    /// Create an internal node
    #[must_use]
    pub fn internal(left: &MerkleNode, right: &MerkleNode) -> Self {
        let mut hasher = Sha3_256::new();
        hasher.update(left.hash);
        hasher.update(right.hash);
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);

        Self {
            hash,
            left: Some(left.hash),
            right: Some(right.hash),
            key_start: left.key_start.clone(),
            key_end: right.key_end.clone(),
            entry_count: left.entry_count + right.entry_count,
        }
    }

    /// Check if this is a leaf node
    #[must_use]
    pub fn is_leaf(&self) -> bool {
        self.left.is_none() && self.right.is_none()
    }
}

// ============================================================================
// STATE SYNC ENGINE
// ============================================================================

/// Multi-region state synchronization engine
#[derive(Debug)]
pub struct StateSyncEngine {
    /// Our region ID
    region_id: String,
    /// Current vector clock
    clock: VectorClock,
    /// Local state store
    state: HashMap<String, StateEntry>,
    /// Pending outbound changes
    outbound: Vec<StateEntry>,
    /// Unresolved conflicts
    conflicts: HashMap<String, Conflict>,
    /// Known peer regions
    peers: HashSet<String>,
    /// Conflict resolution strategy
    strategy: ConflictStrategy,
    /// Last sync time per peer
    last_sync: HashMap<String, u64>,
    /// Merkle tree root (cached)
    merkle_root: Option<MerkleNode>,
    /// Merkle tree dirty flag
    merkle_dirty: bool,
}

impl StateSyncEngine {
    /// Create a new state sync engine
    #[must_use]
    pub fn new(region_id: String, strategy: ConflictStrategy) -> Self {
        let mut clock = VectorClock::new();
        clock.increment(&region_id);

        Self {
            region_id: region_id.clone(),
            clock,
            state: HashMap::new(),
            outbound: Vec::new(),
            conflicts: HashMap::new(),
            peers: HashSet::new(),
            strategy,
            last_sync: HashMap::new(),
            merkle_root: None,
            merkle_dirty: true,
        }
    }

    /// Add a peer region
    pub fn add_peer(&mut self, peer_id: String) {
        self.peers.insert(peer_id);
    }

    /// Get our region ID
    #[must_use]
    pub fn region_id(&self) -> &str {
        &self.region_id
    }

    /// Get current vector clock
    #[must_use]
    pub fn clock(&self) -> &VectorClock {
        &self.clock
    }

    // ========================================================================
    // LOCAL OPERATIONS
    // ========================================================================

    /// Put a value (local write)
    pub fn put(&mut self, key: String, value: Vec<u8>) -> StateEntry {
        self.clock.increment(&self.region_id);
        let entry = StateEntry::new(
            key.clone(),
            value,
            self.clock.clone(),
            self.region_id.clone(),
        );

        self.state.insert(key, entry.clone());
        self.outbound.push(entry.clone());
        self.merkle_dirty = true;

        entry
    }

    /// Delete a key (local delete)
    pub fn delete(&mut self, key: &str) -> Option<StateEntry> {
        if !self.state.contains_key(key) {
            return None;
        }

        self.clock.increment(&self.region_id);
        let tombstone =
            StateEntry::tombstone(key.to_string(), self.clock.clone(), self.region_id.clone());

        self.state.insert(key.to_string(), tombstone.clone());
        self.outbound.push(tombstone.clone());
        self.merkle_dirty = true;

        Some(tombstone)
    }

    /// Get a value
    #[must_use]
    pub fn get(&self, key: &str) -> Option<&StateEntry> {
        self.state.get(key).filter(|e| !e.deleted)
    }

    /// Check if a key exists
    #[must_use]
    pub fn contains(&self, key: &str) -> bool {
        self.state.get(key).map(|e| !e.deleted).unwrap_or(false)
    }

    /// Get all keys
    #[must_use]
    pub fn keys(&self) -> Vec<&String> {
        self.state
            .iter()
            .filter(|(_, e)| !e.deleted)
            .map(|(k, _)| k)
            .collect()
    }

    /// Get state size
    #[must_use]
    pub fn len(&self) -> usize {
        self.state.iter().filter(|(_, e)| !e.deleted).count()
    }

    /// Check if empty
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    // ========================================================================
    // SYNC OPERATIONS
    // ========================================================================

    /// Apply a remote entry
    pub fn apply_remote(&mut self, entry: StateEntry) -> Result<SyncStatus, Conflict> {
        // Merge the remote clock
        self.clock = self.clock.merge(&entry.clock);

        // Check if we have a local entry
        if let Some(local) = self.state.get(&entry.key) {
            match super::vector_clock::compare_clocks(&local.clock, &entry.clock) {
                CausalOrder::Before => {
                    // Remote is newer, accept it
                    self.state.insert(entry.key.clone(), entry);
                    self.merkle_dirty = true;
                    Ok(SyncStatus::Completed)
                }
                CausalOrder::After => {
                    // Local is newer, ignore remote
                    Ok(SyncStatus::Completed)
                }
                CausalOrder::Equal => {
                    // Same version, no change needed
                    Ok(SyncStatus::Completed)
                }
                CausalOrder::Concurrent => {
                    // Conflict!
                    self.handle_conflict(local.clone(), entry)
                }
            }
        } else {
            // No local entry, accept remote
            self.state.insert(entry.key.clone(), entry);
            self.merkle_dirty = true;
            Ok(SyncStatus::Completed)
        }
    }

    /// Handle a conflict between local and remote entries
    fn handle_conflict(
        &mut self,
        local: StateEntry,
        remote: StateEntry,
    ) -> Result<SyncStatus, Conflict> {
        match self.strategy {
            ConflictStrategy::LastWriterWins => {
                let winner = if local.timestamp_ms >= remote.timestamp_ms {
                    local
                } else {
                    remote
                };
                self.state.insert(winner.key.clone(), winner);
                self.merkle_dirty = true;
                Ok(SyncStatus::Completed)
            }
            ConflictStrategy::VectorClock => {
                // Already handled by causal ordering, shouldn't reach here
                // Fall back to LWW
                let winner = if local.timestamp_ms >= remote.timestamp_ms {
                    local
                } else {
                    remote
                };
                self.state.insert(winner.key.clone(), winner);
                self.merkle_dirty = true;
                Ok(SyncStatus::Completed)
            }
            ConflictStrategy::Manual => {
                let conflict = Conflict::new(local, remote);
                self.conflicts
                    .insert(conflict.key.clone(), conflict.clone());
                Err(conflict)
            }
            ConflictStrategy::KeepBoth => {
                // Keep local, store remote with modified key
                let remote_key = format!(
                    "{}__conflict_{}",
                    remote.key,
                    hex::encode(&remote.hash[..4])
                );
                let mut remote_modified = remote;
                remote_modified.key = remote_key.clone();
                self.state.insert(remote_key, remote_modified);
                self.merkle_dirty = true;
                Ok(SyncStatus::Conflict)
            }
        }
    }

    /// Get pending outbound changes
    pub fn drain_outbound(&mut self) -> Vec<StateEntry> {
        std::mem::take(&mut self.outbound)
    }

    /// Get pending outbound changes without draining
    #[must_use]
    pub fn peek_outbound(&self) -> &[StateEntry] {
        &self.outbound
    }

    /// Get unresolved conflicts
    #[must_use]
    pub fn conflicts(&self) -> Vec<&Conflict> {
        self.conflicts.values().collect()
    }

    /// Resolve a conflict manually
    pub fn resolve_conflict(&mut self, key: &str, choose_local: bool) -> Option<StateEntry> {
        if let Some(mut conflict) = self.conflicts.remove(key) {
            let winner = if choose_local {
                conflict.resolve_local().clone()
            } else {
                conflict.resolve_remote().clone()
            };
            self.state.insert(key.to_string(), winner.clone());
            self.merkle_dirty = true;
            Some(winner)
        } else {
            None
        }
    }

    // ========================================================================
    // MERKLE TREE
    // ========================================================================

    /// Build Merkle tree for state verification
    pub fn build_merkle_tree(&mut self) -> Option<&MerkleNode> {
        if !self.merkle_dirty && self.merkle_root.is_some() {
            return self.merkle_root.as_ref();
        }

        let mut entries: Vec<_> = self.state.values().collect();
        if entries.is_empty() {
            self.merkle_root = None;
            self.merkle_dirty = false;
            return None;
        }

        entries.sort_by(|a, b| a.key.cmp(&b.key));

        let leaves: Vec<MerkleNode> = entries.iter().map(|e| MerkleNode::leaf(e)).collect();
        let root = build_tree_level(leaves);

        self.merkle_root = Some(root);
        self.merkle_dirty = false;

        self.merkle_root.as_ref()
    }

    /// Get Merkle root hash
    pub fn merkle_root_hash(&mut self) -> Option<[u8; 32]> {
        self.build_merkle_tree().map(|n| n.hash)
    }

    /// Compare Merkle roots with another engine
    pub fn compare_merkle_roots(&mut self, other_root: [u8; 32]) -> bool {
        self.merkle_root_hash()
            .map(|our_root| our_root == other_root)
            .unwrap_or(false)
    }

    // ========================================================================
    // DELTA SYNC
    // ========================================================================

    /// Get entries changed since a given clock
    #[must_use]
    pub fn get_delta(&self, since: &VectorClock) -> Vec<&StateEntry> {
        self.state
            .values()
            .filter(|e| since.happens_before(&e.clock))
            .collect()
    }

    /// Get entries for a specific key range
    #[must_use]
    pub fn get_range(&self, start: &str, end: &str) -> Vec<&StateEntry> {
        self.state
            .values()
            .filter(|e| e.key.as_str() >= start && e.key.as_str() <= end && !e.deleted)
            .collect()
    }

    /// Record sync completion with a peer
    pub fn record_sync(&mut self, peer: &str) {
        self.last_sync.insert(peer.to_string(), current_time_ms());
    }

    /// Get time since last sync with a peer (milliseconds)
    #[must_use]
    pub fn time_since_sync(&self, peer: &str) -> Option<u64> {
        self.last_sync
            .get(peer)
            .map(|last| current_time_ms().saturating_sub(*last))
    }
}

/// Build a Merkle tree level from nodes
fn build_tree_level(mut nodes: Vec<MerkleNode>) -> MerkleNode {
    if nodes.len() == 1 {
        return nodes.remove(0);
    }

    let mut next_level = Vec::new();

    while nodes.len() > 1 {
        let right = nodes.pop().unwrap();
        let left = nodes.pop().unwrap();
        next_level.push(MerkleNode::internal(&left, &right));
    }

    // Handle odd node
    if let Some(odd) = nodes.pop() {
        next_level.push(odd);
    }

    build_tree_level(next_level)
}

// ============================================================================
// SYNC MESSAGE
// ============================================================================

/// Message types for sync protocol
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SyncMessage {
    /// Request sync with clock
    SyncRequest {
        from_region: String,
        clock: VectorClock,
        merkle_root: Option<[u8; 32]>,
    },
    /// Sync response with entries
    SyncResponse {
        from_region: String,
        entries: Vec<StateEntry>,
        clock: VectorClock,
        merkle_root: Option<[u8; 32]>,
    },
    /// Acknowledge sync completion
    SyncAck {
        from_region: String,
        clock: VectorClock,
    },
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_state_entry_creation() {
        let clock = VectorClock::new().tick("r1");
        let entry = StateEntry::new(
            "key1".to_string(),
            b"value1".to_vec(),
            clock,
            "r1".to_string(),
        );

        assert_eq!(entry.key, "key1");
        assert_eq!(entry.value, b"value1");
        assert!(!entry.deleted);
        assert!(entry.timestamp_ms > 0);
    }

    #[test]
    fn test_tombstone() {
        let clock = VectorClock::new().tick("r1");
        let tombstone = StateEntry::tombstone("key1".to_string(), clock, "r1".to_string());

        assert_eq!(tombstone.key, "key1");
        assert!(tombstone.value.is_empty());
        assert!(tombstone.deleted);
    }

    #[test]
    fn test_engine_put_get() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);

        engine.put("user:1".to_string(), b"alice".to_vec());
        engine.put("user:2".to_string(), b"bob".to_vec());

        assert_eq!(engine.len(), 2);
        assert!(engine.contains("user:1"));
        assert_eq!(engine.get("user:1").unwrap().value, b"alice");
    }

    #[test]
    fn test_engine_delete() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);

        engine.put("key1".to_string(), b"value".to_vec());
        assert!(engine.contains("key1"));

        engine.delete("key1");
        assert!(!engine.contains("key1"));
        assert!(engine.get("key1").is_none());
    }

    #[test]
    fn test_apply_remote_newer() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);

        // Local write
        engine.put("key1".to_string(), b"local".to_vec());

        // Remote entry with newer clock
        let remote_clock = engine.clock().tick("eu-west").tick("eu-west");
        let remote = StateEntry::new(
            "key1".to_string(),
            b"remote".to_vec(),
            remote_clock,
            "eu-west".to_string(),
        );

        let result = engine.apply_remote(remote);
        assert!(result.is_ok());
        assert_eq!(engine.get("key1").unwrap().value, b"remote");
    }

    #[test]
    fn test_apply_remote_older() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);

        // Make several local writes to advance clock
        engine.put("key1".to_string(), b"v1".to_vec());
        engine.put("key1".to_string(), b"v2".to_vec());
        engine.put("key1".to_string(), b"local".to_vec());

        // Remote entry with older clock
        let remote_clock = VectorClock::new().tick("eu-west");
        let mut remote = StateEntry::new(
            "key1".to_string(),
            b"remote".to_vec(),
            remote_clock,
            "eu-west".to_string(),
        );
        remote.timestamp_ms = 0; // Force older timestamp to ensure local wins LWW

        let result = engine.apply_remote(remote);
        assert!(result.is_ok());
        assert_eq!(engine.get("key1").unwrap().value, b"local"); // Local preserved
    }

    #[test]
    fn test_conflict_lww() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);

        // Local write
        let local_clock = VectorClock::new().tick("us-east");
        let local = StateEntry::new(
            "key1".to_string(),
            b"local".to_vec(),
            local_clock,
            "us-east".to_string(),
        );
        engine.state.insert("key1".to_string(), local);

        // Concurrent remote write
        let remote_clock = VectorClock::new().tick("eu-west");
        let mut remote = StateEntry::new(
            "key1".to_string(),
            b"remote".to_vec(),
            remote_clock,
            "eu-west".to_string(),
        );
        // Make remote timestamp newer
        remote.timestamp_ms = current_time_ms() + 1000;

        let result = engine.apply_remote(remote);
        assert!(result.is_ok());
        // LWW should choose remote (newer timestamp)
        assert_eq!(engine.get("key1").unwrap().value, b"remote");
    }

    #[test]
    fn test_conflict_manual() {
        let mut engine = StateSyncEngine::new("us-east".to_string(), ConflictStrategy::Manual);

        // Local write
        let local_clock = VectorClock::new().tick("us-east");
        let local = StateEntry::new(
            "key1".to_string(),
            b"local".to_vec(),
            local_clock,
            "us-east".to_string(),
        );
        engine.state.insert("key1".to_string(), local);

        // Concurrent remote write
        let remote_clock = VectorClock::new().tick("eu-west");
        let remote = StateEntry::new(
            "key1".to_string(),
            b"remote".to_vec(),
            remote_clock,
            "eu-west".to_string(),
        );

        let result = engine.apply_remote(remote);
        assert!(result.is_err()); // Returns conflict

        let conflict = result.unwrap_err();
        assert_eq!(conflict.key, "key1");
        assert!(!conflict.resolved);

        // Resolve manually
        let winner = engine.resolve_conflict("key1", true); // Choose local
        assert!(winner.is_some());
        assert_eq!(engine.get("key1").unwrap().value, b"local");
    }

    #[test]
    fn test_merkle_tree() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);

        engine.put("a".to_string(), b"1".to_vec());
        engine.put("b".to_string(), b"2".to_vec());
        engine.put("c".to_string(), b"3".to_vec());

        let root = engine.build_merkle_tree();
        assert!(root.is_some());
        assert_eq!(root.unwrap().entry_count, 3);

        let hash1 = engine.merkle_root_hash();
        assert!(hash1.is_some());

        // Modifying state should change root
        engine.put("d".to_string(), b"4".to_vec());
        let hash2 = engine.merkle_root_hash();
        assert!(hash2.is_some());
        assert_ne!(hash1.unwrap(), hash2.unwrap());
    }

    #[test]
    fn test_get_delta() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);

        let checkpoint = engine.clock().clone();

        engine.put("a".to_string(), b"1".to_vec());
        engine.put("b".to_string(), b"2".to_vec());

        let delta = engine.get_delta(&checkpoint);
        assert_eq!(delta.len(), 2);
    }

    #[test]
    fn test_outbound_drain() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);

        engine.put("a".to_string(), b"1".to_vec());
        engine.put("b".to_string(), b"2".to_vec());

        assert_eq!(engine.peek_outbound().len(), 2);

        let outbound = engine.drain_outbound();
        assert_eq!(outbound.len(), 2);
        assert_eq!(engine.peek_outbound().len(), 0);
    }

    #[test]
    fn test_sync_recording() {
        let mut engine =
            StateSyncEngine::new("us-east".to_string(), ConflictStrategy::LastWriterWins);
        engine.add_peer("eu-west".to_string());

        assert!(engine.time_since_sync("eu-west").is_none());

        engine.record_sync("eu-west");
        let elapsed = engine.time_since_sync("eu-west");
        assert!(elapsed.is_some());
        assert!(elapsed.unwrap() < 100); // Should be very recent
    }
}
