//! rust_core/src/net/fragmentation.rs
//! UDP Fragmentation Layer for Large Message Support.
//!
//! Enables transmission of messages larger than UDP MTU (8KB default).
//! Used for block propagation (up to 4MB blocks).
//!
//! Protocol:
//! - Fragment header: 12 bytes (message_id, index, total, flags, checksum)
//! - Fragment payload: up to 7KB per fragment
//! - Reassembly with timeout and deduplication

use sha3::{Digest, Sha3_256};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

/// Maximum payload per fragment (leaves room for header in 8KB UDP message)
pub const MAX_FRAGMENT_PAYLOAD: usize = 7168; // 7 KB

/// Fragment header size in bytes
pub const FRAGMENT_HEADER_SIZE: usize = 12;

/// Maximum fragments per message (prevents memory exhaustion)
pub const MAX_FRAGMENTS_PER_MESSAGE: u16 = 600; // ~4.2 MB max message

/// Reassembly timeout in seconds
pub const REASSEMBLY_TIMEOUT_SECS: u64 = 30;

/// Maximum concurrent reassembly sessions per peer
pub const MAX_REASSEMBLY_SESSIONS_PER_PEER: usize = 10;

/// Fragment header flags
pub mod flags {
    /// First fragment of message
    pub const FIRST: u8 = 0x01;
    /// Last fragment of message
    pub const LAST: u8 = 0x02;
    /// Message requires acknowledgment
    pub const ACK_REQUIRED: u8 = 0x04;
    /// High priority message (block proposals, commits)
    pub const HIGH_PRIORITY: u8 = 0x08;
}

/// Fragment header structure (12 bytes)
/// Layout: [message_id: 4][index: 2][total: 2][flags: 1][checksum: 3]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FragmentHeader {
    /// Unique message identifier (per sender)
    pub message_id: u32,
    /// Fragment index (0-based)
    pub fragment_index: u16,
    /// Total number of fragments
    pub total_fragments: u16,
    /// Flags (FIRST, LAST, ACK_REQUIRED, HIGH_PRIORITY)
    pub flags: u8,
    /// First 3 bytes of SHA3 hash of payload (for validation)
    pub checksum: [u8; 3],
}

impl FragmentHeader {
    /// Create a new fragment header
    #[must_use]
    pub fn new(message_id: u32, fragment_index: u16, total_fragments: u16, payload: &[u8]) -> Self {
        let mut flags = 0u8;
        if fragment_index == 0 {
            flags |= flags::FIRST;
        }
        if fragment_index == total_fragments.saturating_sub(1) {
            flags |= flags::LAST;
        }

        // Compute checksum (first 3 bytes of SHA3-256)
        let hash = Sha3_256::digest(payload);
        let checksum = [hash[0], hash[1], hash[2]];

        FragmentHeader {
            message_id,
            fragment_index,
            total_fragments,
            flags,
            checksum,
        }
    }

    /// Serialize header to bytes (12 bytes)
    #[must_use]
    pub fn to_bytes(&self) -> [u8; FRAGMENT_HEADER_SIZE] {
        let mut buf = [0u8; FRAGMENT_HEADER_SIZE];
        buf[0..4].copy_from_slice(&self.message_id.to_be_bytes());
        buf[4..6].copy_from_slice(&self.fragment_index.to_be_bytes());
        buf[6..8].copy_from_slice(&self.total_fragments.to_be_bytes());
        buf[8] = self.flags;
        buf[9..12].copy_from_slice(&self.checksum);
        buf
    }

    /// Deserialize header from bytes
    pub fn from_bytes(buf: &[u8]) -> Result<Self, FragmentError> {
        if buf.len() < FRAGMENT_HEADER_SIZE {
            return Err(FragmentError::HeaderTooShort);
        }

        let message_id = u32::from_be_bytes([buf[0], buf[1], buf[2], buf[3]]);
        let fragment_index = u16::from_be_bytes([buf[4], buf[5]]);
        let total_fragments = u16::from_be_bytes([buf[6], buf[7]]);
        let flags = buf[8];
        let checksum = [buf[9], buf[10], buf[11]];

        // Validate header
        if total_fragments == 0 {
            return Err(FragmentError::InvalidTotalFragments);
        }
        if total_fragments > MAX_FRAGMENTS_PER_MESSAGE {
            return Err(FragmentError::TooManyFragments);
        }
        if fragment_index >= total_fragments {
            return Err(FragmentError::InvalidFragmentIndex);
        }

        Ok(FragmentHeader {
            message_id,
            fragment_index,
            total_fragments,
            flags,
            checksum,
        })
    }

    /// Verify payload checksum
    #[must_use]
    pub fn verify_checksum(&self, payload: &[u8]) -> bool {
        let hash = Sha3_256::digest(payload);
        self.checksum == [hash[0], hash[1], hash[2]]
    }

    /// Check if this is a high priority fragment
    #[must_use]
    pub fn is_high_priority(&self) -> bool {
        self.flags & flags::HIGH_PRIORITY != 0
    }

    /// Check if this is the first fragment
    #[must_use]
    pub fn is_first(&self) -> bool {
        self.flags & flags::FIRST != 0
    }

    /// Check if this is the last fragment
    #[must_use]
    pub fn is_last(&self) -> bool {
        self.flags & flags::LAST != 0
    }
}

/// Fragmentation errors
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FragmentError {
    /// Header is too short
    HeaderTooShort,
    /// Invalid total fragments count
    InvalidTotalFragments,
    /// Too many fragments (exceeds limit)
    TooManyFragments,
    /// Invalid fragment index
    InvalidFragmentIndex,
    /// Checksum verification failed
    ChecksumMismatch,
    /// Message too large to fragment
    MessageTooLarge,
    /// Reassembly timeout
    ReassemblyTimeout,
    /// Too many concurrent reassembly sessions
    TooManySessions,
    /// Duplicate fragment received
    DuplicateFragment,
}

impl std::fmt::Display for FragmentError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::HeaderTooShort => write!(f, "Fragment header too short"),
            Self::InvalidTotalFragments => write!(f, "Invalid total fragments count"),
            Self::TooManyFragments => write!(f, "Too many fragments"),
            Self::InvalidFragmentIndex => write!(f, "Invalid fragment index"),
            Self::ChecksumMismatch => write!(f, "Fragment checksum mismatch"),
            Self::MessageTooLarge => write!(f, "Message too large to fragment"),
            Self::ReassemblyTimeout => write!(f, "Reassembly timeout"),
            Self::TooManySessions => write!(f, "Too many concurrent reassembly sessions"),
            Self::DuplicateFragment => write!(f, "Duplicate fragment received"),
        }
    }
}

impl std::error::Error for FragmentError {}

/// Fragment a large message into smaller pieces
pub fn fragment_message(
    message: &[u8],
    message_id: u32,
    high_priority: bool,
) -> Result<Vec<Vec<u8>>, FragmentError> {
    let max_message_size = MAX_FRAGMENT_PAYLOAD * MAX_FRAGMENTS_PER_MESSAGE as usize;
    if message.len() > max_message_size {
        return Err(FragmentError::MessageTooLarge);
    }

    // Single fragment if small enough
    if message.len() <= MAX_FRAGMENT_PAYLOAD {
        let mut header = FragmentHeader::new(message_id, 0, 1, message);
        if high_priority {
            header.flags |= flags::HIGH_PRIORITY;
        }
        let mut fragment = header.to_bytes().to_vec();
        fragment.extend_from_slice(message);
        return Ok(vec![fragment]);
    }

    // Calculate number of fragments needed
    let total_fragments = message.len().div_ceil(MAX_FRAGMENT_PAYLOAD) as u16;

    let mut fragments = Vec::with_capacity(total_fragments as usize);

    for i in 0..total_fragments {
        let start = i as usize * MAX_FRAGMENT_PAYLOAD;
        let end = std::cmp::min(start + MAX_FRAGMENT_PAYLOAD, message.len());
        let payload = &message[start..end];

        let mut header = FragmentHeader::new(message_id, i, total_fragments, payload);
        if high_priority {
            header.flags |= flags::HIGH_PRIORITY;
        }

        let mut fragment = header.to_bytes().to_vec();
        fragment.extend_from_slice(payload);
        fragments.push(fragment);
    }

    Ok(fragments)
}

/// State for reassembling a fragmented message
#[derive(Debug)]
struct ReassemblyState {
    /// Expected total fragments
    total_fragments: u16,
    /// Received fragments (indexed by fragment_index)
    fragments: HashMap<u16, Vec<u8>>,
    /// Timestamp when first fragment was received
    started_at: Instant,
    /// Is this a high priority message?
    #[allow(dead_code)]
    high_priority: bool,
}

impl ReassemblyState {
    fn new(total_fragments: u16, high_priority: bool) -> Self {
        ReassemblyState {
            total_fragments,
            fragments: HashMap::with_capacity(total_fragments as usize),
            started_at: Instant::now(),
            high_priority,
        }
    }

    fn is_complete(&self) -> bool {
        self.fragments.len() == self.total_fragments as usize
    }

    fn is_expired(&self, timeout: Duration) -> bool {
        self.started_at.elapsed() > timeout
    }

    /// Assemble complete message from fragments
    fn assemble(&self) -> Option<Vec<u8>> {
        if !self.is_complete() {
            return None;
        }

        let mut message = Vec::new();
        for i in 0..self.total_fragments {
            if let Some(payload) = self.fragments.get(&i) {
                message.extend_from_slice(payload);
            } else {
                return None; // Missing fragment
            }
        }
        Some(message)
    }
}

/// Key for reassembly sessions: (source address, message_id)
type ReassemblyKey = (SocketAddr, u32);

/// Reassembly buffer for incoming fragments
pub struct ReassemblyBuffer {
    /// Active reassembly sessions
    sessions: Mutex<HashMap<ReassemblyKey, ReassemblyState>>,
    /// Reassembly timeout
    timeout: Duration,
    /// Statistics
    stats: Mutex<ReassemblyStats>,
}

/// Statistics for reassembly operations
#[derive(Debug, Default, Clone)]
pub struct ReassemblyStats {
    /// Total fragments received
    pub fragments_received: u64,
    /// Complete messages reassembled
    pub messages_reassembled: u64,
    /// Fragments dropped due to timeout
    pub fragments_timeout: u64,
    /// Fragments dropped due to checksum mismatch
    pub fragments_checksum_failed: u64,
    /// Duplicate fragments received
    pub fragments_duplicate: u64,
    /// Sessions rejected due to limit
    pub sessions_rejected: u64,
}

impl ReassemblyBuffer {
    /// Create a new reassembly buffer
    #[must_use]
    pub fn new() -> Self {
        ReassemblyBuffer {
            sessions: Mutex::new(HashMap::new()),
            timeout: Duration::from_secs(REASSEMBLY_TIMEOUT_SECS),
            stats: Mutex::new(ReassemblyStats::default()),
        }
    }

    /// Create with custom timeout
    #[must_use]
    pub fn with_timeout(timeout_secs: u64) -> Self {
        ReassemblyBuffer {
            sessions: Mutex::new(HashMap::new()),
            timeout: Duration::from_secs(timeout_secs),
            stats: Mutex::new(ReassemblyStats::default()),
        }
    }

    /// Process an incoming fragment
    /// Returns Some(complete_message) if reassembly is complete
    pub fn process_fragment(
        &self,
        source: SocketAddr,
        data: &[u8],
    ) -> Result<Option<Vec<u8>>, FragmentError> {
        // Parse header
        let header = FragmentHeader::from_bytes(data)?;
        let payload = &data[FRAGMENT_HEADER_SIZE..];

        // Verify checksum
        if !header.verify_checksum(payload) {
            if let Ok(mut stats) = self.stats.lock() {
                stats.fragments_checksum_failed += 1;
            }
            return Err(FragmentError::ChecksumMismatch);
        }

        // Update stats
        if let Ok(mut stats) = self.stats.lock() {
            stats.fragments_received += 1;
        }

        let key = (source, header.message_id);

        let mut sessions = self
            .sessions
            .lock()
            .map_err(|_| FragmentError::TooManySessions)?;

        // Clean up expired sessions first
        self.cleanup_expired_sessions(&mut sessions);

        // Check session limits per peer
        let peer_sessions: usize = sessions.keys().filter(|(addr, _)| *addr == source).count();
        if peer_sessions >= MAX_REASSEMBLY_SESSIONS_PER_PEER && !sessions.contains_key(&key) {
            if let Ok(mut stats) = self.stats.lock() {
                stats.sessions_rejected += 1;
            }
            return Err(FragmentError::TooManySessions);
        }

        // Get or create session
        let session = sessions.entry(key).or_insert_with(|| {
            ReassemblyState::new(header.total_fragments, header.is_high_priority())
        });

        // Validate total_fragments matches
        if session.total_fragments != header.total_fragments {
            return Err(FragmentError::InvalidTotalFragments);
        }

        // Check for duplicate
        if session.fragments.contains_key(&header.fragment_index) {
            if let Ok(mut stats) = self.stats.lock() {
                stats.fragments_duplicate += 1;
            }
            // Not an error, just ignore duplicate
            return Ok(None);
        }

        // Store fragment payload
        session
            .fragments
            .insert(header.fragment_index, payload.to_vec());

        // Check if complete
        if session.is_complete() {
            let message = session.assemble();
            sessions.remove(&key);

            if let Ok(mut stats) = self.stats.lock() {
                stats.messages_reassembled += 1;
            }

            return Ok(message);
        }

        Ok(None)
    }

    /// Clean up expired reassembly sessions
    fn cleanup_expired_sessions(&self, sessions: &mut HashMap<ReassemblyKey, ReassemblyState>) {
        let timeout = self.timeout;
        let expired: Vec<ReassemblyKey> = sessions
            .iter()
            .filter(|(_, state)| state.is_expired(timeout))
            .map(|(key, _)| *key)
            .collect();

        let expired_count = expired.len() as u64;
        for key in expired {
            sessions.remove(&key);
        }

        if expired_count > 0 {
            if let Ok(mut stats) = self.stats.lock() {
                stats.fragments_timeout += expired_count;
            }
        }
    }

    /// Get current statistics
    #[must_use]
    pub fn stats(&self) -> ReassemblyStats {
        self.stats.lock().map_or_else(|e| e.into_inner().clone(), |s| s.clone())
    }

    /// Get number of active reassembly sessions
    #[must_use]
    pub fn active_sessions(&self) -> usize {
        self.sessions.lock().map_or(0, |s| s.len())
    }

    /// Force cleanup of all expired sessions (for maintenance)
    pub fn cleanup(&self) {
        if let Ok(mut sessions) = self.sessions.lock() {
            self.cleanup_expired_sessions(&mut sessions);
        }
    }
}

impl Default for ReassemblyBuffer {
    fn default() -> Self {
        Self::new()
    }
}

/// Message fragmenter with automatic ID generation
pub struct Fragmenter {
    /// Next message ID
    next_id: Mutex<u32>,
    /// Reassembly buffer for incoming fragments
    reassembly: Arc<ReassemblyBuffer>,
}

impl Fragmenter {
    /// Create a new fragmenter
    #[must_use]
    pub fn new() -> Self {
        Fragmenter {
            next_id: Mutex::new(0),
            reassembly: Arc::new(ReassemblyBuffer::new()),
        }
    }

    /// Fragment a message for sending
    pub fn fragment(
        &self,
        message: &[u8],
        high_priority: bool,
    ) -> Result<Vec<Vec<u8>>, FragmentError> {
        let id = {
            let mut id_guard = self
                .next_id
                .lock()
                .map_err(|_| FragmentError::MessageTooLarge)?;
            let id = *id_guard;
            *id_guard = id_guard.wrapping_add(1);
            id
        };
        fragment_message(message, id, high_priority)
    }

    /// Process an incoming fragment
    pub fn defragment(
        &self,
        source: SocketAddr,
        data: &[u8],
    ) -> Result<Option<Vec<u8>>, FragmentError> {
        self.reassembly.process_fragment(source, data)
    }

    /// Get reassembly statistics
    #[must_use]
    pub fn stats(&self) -> ReassemblyStats {
        self.reassembly.stats()
    }

    /// Get reference to reassembly buffer
    #[must_use]
    pub fn reassembly_buffer(&self) -> Arc<ReassemblyBuffer> {
        self.reassembly.clone()
    }
}

impl Default for Fragmenter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fragment_header_roundtrip() {
        let payload = b"test payload data";
        let header = FragmentHeader::new(12345, 0, 3, payload);

        let bytes = header.to_bytes();
        assert_eq!(bytes.len(), FRAGMENT_HEADER_SIZE);

        let decoded = FragmentHeader::from_bytes(&bytes).unwrap();
        assert_eq!(decoded.message_id, 12345);
        assert_eq!(decoded.fragment_index, 0);
        assert_eq!(decoded.total_fragments, 3);
        assert!(decoded.is_first());
        assert!(!decoded.is_last());
        assert!(decoded.verify_checksum(payload));
    }

    #[test]
    fn test_fragment_header_last_fragment() {
        let payload = b"last fragment";
        let header = FragmentHeader::new(1, 2, 3, payload);
        assert!(!header.is_first());
        assert!(header.is_last());
    }

    #[test]
    fn test_fragment_small_message() {
        let message = b"small message";
        let fragments = fragment_message(message, 1, false).unwrap();

        assert_eq!(fragments.len(), 1);
        assert_eq!(fragments[0].len(), FRAGMENT_HEADER_SIZE + message.len());
    }

    #[test]
    fn test_fragment_large_message() {
        let message = vec![0xABu8; MAX_FRAGMENT_PAYLOAD * 3 + 100];
        let fragments = fragment_message(&message, 1, true).unwrap();

        assert_eq!(fragments.len(), 4);

        // Verify headers
        for (i, frag) in fragments.iter().enumerate() {
            let header = FragmentHeader::from_bytes(frag).unwrap();
            assert_eq!(header.message_id, 1);
            assert_eq!(header.fragment_index, i as u16);
            assert_eq!(header.total_fragments, 4);
            assert!(header.is_high_priority());
        }
    }

    #[test]
    fn test_reassembly_complete() {
        let message = vec![0xCDu8; MAX_FRAGMENT_PAYLOAD * 2 + 500];
        let fragments = fragment_message(&message, 42, false).unwrap();

        let buffer = ReassemblyBuffer::new();
        let source = "127.0.0.1:8080".parse().unwrap();

        // Process all fragments
        let mut result = None;
        for frag in &fragments {
            result = buffer.process_fragment(source, frag).unwrap();
        }

        // Should have complete message
        assert!(result.is_some());
        assert_eq!(result.unwrap(), message);

        // Session should be cleaned up
        assert_eq!(buffer.active_sessions(), 0);
    }

    #[test]
    fn test_reassembly_out_of_order() {
        let message = vec![0xEFu8; MAX_FRAGMENT_PAYLOAD * 3];
        let mut fragments = fragment_message(&message, 99, false).unwrap();

        // Shuffle fragments
        fragments.reverse();

        let buffer = ReassemblyBuffer::new();
        let source = "127.0.0.1:9000".parse().unwrap();

        let mut result = None;
        for frag in &fragments {
            result = buffer.process_fragment(source, frag).unwrap();
        }

        assert!(result.is_some());
        assert_eq!(result.unwrap(), message);
    }

    #[test]
    fn test_reassembly_duplicate_fragment() {
        let message = vec![0x11u8; MAX_FRAGMENT_PAYLOAD * 2];
        let fragments = fragment_message(&message, 1, false).unwrap();

        let buffer = ReassemblyBuffer::new();
        let source = "127.0.0.1:8080".parse().unwrap();

        // Process first fragment
        buffer.process_fragment(source, &fragments[0]).unwrap();

        // Process first fragment again (duplicate)
        let result = buffer.process_fragment(source, &fragments[0]).unwrap();
        assert!(result.is_none()); // Should ignore duplicate

        // Stats should show duplicate
        assert_eq!(buffer.stats().fragments_duplicate, 1);
    }

    #[test]
    fn test_checksum_mismatch() {
        let message = b"test message";
        let mut fragments = fragment_message(message, 1, false).unwrap();

        // Corrupt the payload
        let last_idx = fragments[0].len() - 1;
        fragments[0][last_idx] ^= 0xFF;

        let buffer = ReassemblyBuffer::new();
        let source = "127.0.0.1:8080".parse().unwrap();

        let result = buffer.process_fragment(source, &fragments[0]);
        assert!(matches!(result, Err(FragmentError::ChecksumMismatch)));
    }

    #[test]
    fn test_too_many_fragments_rejected() {
        let mut header_bytes =
            FragmentHeader::new(1, 0, MAX_FRAGMENTS_PER_MESSAGE + 1, b"x").to_bytes();
        // Manually set total_fragments to exceed limit
        let total = (MAX_FRAGMENTS_PER_MESSAGE + 1).to_be_bytes();
        header_bytes[6] = total[0];
        header_bytes[7] = total[1];

        let result = FragmentHeader::from_bytes(&header_bytes);
        assert!(matches!(result, Err(FragmentError::TooManyFragments)));
    }

    #[test]
    fn test_fragmenter_auto_id() {
        let fragmenter = Fragmenter::new();

        let _msg1 = fragment_message(b"message 1", 0, false).unwrap();
        let frags1 = fragmenter.fragment(b"message 1", false).unwrap();
        let frags2 = fragmenter.fragment(b"message 2", false).unwrap();

        // IDs should be different
        let h1 = FragmentHeader::from_bytes(&frags1[0]).unwrap();
        let h2 = FragmentHeader::from_bytes(&frags2[0]).unwrap();
        assert_ne!(h1.message_id, h2.message_id);
    }

    #[test]
    fn test_session_limit_per_peer() {
        let buffer = ReassemblyBuffer::new();
        let source = "127.0.0.1:8080".parse().unwrap();

        // Create MAX_REASSEMBLY_SESSIONS_PER_PEER incomplete sessions
        for i in 0..MAX_REASSEMBLY_SESSIONS_PER_PEER {
            let message = vec![0u8; MAX_FRAGMENT_PAYLOAD * 2];
            let fragments = fragment_message(&message, i as u32, false).unwrap();
            // Only process first fragment (leave incomplete)
            buffer.process_fragment(source, &fragments[0]).unwrap();
        }

        // Next session should be rejected
        let message = vec![0u8; MAX_FRAGMENT_PAYLOAD * 2];
        let fragments = fragment_message(&message, 999, false).unwrap();
        let result = buffer.process_fragment(source, &fragments[0]);
        assert!(matches!(result, Err(FragmentError::TooManySessions)));
    }
}
