//! rust_core/src/federation/vector_clock.rs
//! Vector Clock implementation for causal ordering.
//!
//! Provides logical timestamps for distributed systems:
//! - Causal ordering detection
//! - Concurrent event identification
//! - Conflict detection

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ============================================================================
// VECTOR CLOCK
// ============================================================================

/// Vector clock for distributed causal ordering.
///
/// Each entry maps a region/node ID to a logical timestamp.
/// Used to determine happens-before relationships between events.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct VectorClock {
    /// Map of region ID to logical timestamp
    clocks: HashMap<String, u64>,
}

impl VectorClock {
    /// Create a new empty vector clock
    #[must_use]
    pub fn new() -> Self {
        Self {
            clocks: HashMap::new(),
        }
    }

    /// Create a vector clock with initial regions
    #[must_use]
    pub fn with_regions(regions: &[&str]) -> Self {
        let mut clocks = HashMap::new();
        for region in regions {
            clocks.insert(region.to_string(), 0);
        }
        Self { clocks }
    }

    /// Get the timestamp for a specific region
    #[must_use]
    pub fn get(&self, region: &str) -> u64 {
        *self.clocks.get(region).unwrap_or(&0)
    }

    /// Increment the clock for a specific region
    pub fn increment(&mut self, region: &str) {
        let entry = self.clocks.entry(region.to_string()).or_insert(0);
        *entry += 1;
    }

    /// Create a new clock with one region incremented
    #[must_use]
    pub fn tick(&self, region: &str) -> Self {
        let mut new_clock = self.clone();
        new_clock.increment(region);
        new_clock
    }

    /// Merge with another vector clock (element-wise max)
    #[must_use]
    pub fn merge(&self, other: &VectorClock) -> Self {
        let mut merged = HashMap::new();

        // Get max for all keys in self
        for (region, &time) in &self.clocks {
            let other_time = other.clocks.get(region).unwrap_or(&0);
            merged.insert(region.clone(), time.max(*other_time));
        }

        // Get max for all keys only in other
        for (region, &time) in &other.clocks {
            if !self.clocks.contains_key(region) {
                merged.insert(region.clone(), time);
            }
        }

        Self { clocks: merged }
    }

    /// Check if this clock happens-before another (strict causal ordering)
    ///
    /// Returns true if this clock is strictly less than or equal to other
    /// and strictly less in at least one component.
    #[must_use]
    pub fn happens_before(&self, other: &VectorClock) -> bool {
        if self.clocks.is_empty() && !other.clocks.is_empty() {
            return true;
        }
        if self.clocks.is_empty() && other.clocks.is_empty() {
            return false;
        }

        let mut strictly_less = false;

        // Check all entries in self
        for (region, &time) in &self.clocks {
            let other_time = other.get(region);
            if time > other_time {
                return false; // Not happens-before
            }
            if time < other_time {
                strictly_less = true;
            }
        }

        // Check entries only in other (they would be > 0 in other, 0 in self)
        for (region, &time) in &other.clocks {
            if !self.clocks.contains_key(region) && time > 0 {
                strictly_less = true;
            }
        }

        strictly_less
    }

    /// Check if two clocks are concurrent (neither happens-before the other)
    #[must_use]
    pub fn is_concurrent(&self, other: &VectorClock) -> bool {
        !self.happens_before(other) && !other.happens_before(self) && self != other
    }

    /// Check if this clock equals or happens-before another
    #[must_use]
    pub fn happens_before_or_equal(&self, other: &VectorClock) -> bool {
        self == other || self.happens_before(other)
    }

    /// Get all regions in this clock
    #[must_use]
    pub fn regions(&self) -> Vec<&String> {
        self.clocks.keys().collect()
    }

    /// Get the total number of events across all regions
    #[must_use]
    pub fn total_events(&self) -> u64 {
        self.clocks.values().sum()
    }

    /// Serialize to bytes for network transmission
    #[must_use]
    pub fn to_bytes(&self) -> Vec<u8> {
        // Format: [num_entries: u32][entries...]
        // Entry: [key_len: u16][key: bytes][value: u64]
        let mut bytes = Vec::new();

        bytes.extend_from_slice(&(self.clocks.len() as u32).to_le_bytes());

        for (region, &time) in &self.clocks {
            let key_bytes = region.as_bytes();
            bytes.extend_from_slice(&(key_bytes.len() as u16).to_le_bytes());
            bytes.extend_from_slice(key_bytes);
            bytes.extend_from_slice(&time.to_le_bytes());
        }

        bytes
    }

    /// Deserialize from bytes
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, String> {
        if bytes.len() < 4 {
            return Err("Insufficient bytes for header".to_string());
        }

        let num_entries = u32::from_le_bytes(bytes[0..4].try_into().unwrap()) as usize;
        let mut clocks = HashMap::new();
        let mut offset = 4;

        for _ in 0..num_entries {
            if offset + 2 > bytes.len() {
                return Err("Insufficient bytes for key length".to_string());
            }
            let key_len =
                u16::from_le_bytes(bytes[offset..offset + 2].try_into().unwrap()) as usize;
            offset += 2;

            if offset + key_len + 8 > bytes.len() {
                return Err("Insufficient bytes for entry".to_string());
            }

            let key = String::from_utf8(bytes[offset..offset + key_len].to_vec())
                .map_err(|e| e.to_string())?;
            offset += key_len;

            let value = u64::from_le_bytes(bytes[offset..offset + 8].try_into().unwrap());
            offset += 8;

            clocks.insert(key, value);
        }

        Ok(Self { clocks })
    }
}

// ============================================================================
// CAUSAL ORDERING
// ============================================================================

/// Causal ordering relationship between two events
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CausalOrder {
    /// First event happens before second
    Before,
    /// Second event happens before first
    After,
    /// Events are concurrent (no causal relationship)
    Concurrent,
    /// Events are identical
    Equal,
}

/// Compare two vector clocks to determine causal ordering
#[must_use]
pub fn compare_clocks(a: &VectorClock, b: &VectorClock) -> CausalOrder {
    if a == b {
        CausalOrder::Equal
    } else if a.happens_before(b) {
        CausalOrder::Before
    } else if b.happens_before(a) {
        CausalOrder::After
    } else {
        CausalOrder::Concurrent
    }
}

// ============================================================================
// TIMESTAMPED VALUE
// ============================================================================

/// A value with an associated vector clock timestamp
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Timestamped<T> {
    pub value: T,
    pub clock: VectorClock,
    /// Physical timestamp for last-writer-wins fallback
    pub wall_time_ms: u64,
    /// Origin region
    pub origin: String,
}

impl<T> Timestamped<T> {
    /// Create a new timestamped value
    pub fn new(value: T, clock: VectorClock, origin: String) -> Self {
        Self {
            value,
            clock,
            wall_time_ms: current_time_ms(),
            origin,
        }
    }

    /// Check if this value supersedes another (happens-after)
    pub fn supersedes(&self, other: &Timestamped<T>) -> bool {
        other.clock.happens_before(&self.clock)
    }

    /// Check if values are concurrent
    pub fn is_concurrent(&self, other: &Timestamped<T>) -> bool {
        self.clock.is_concurrent(&other.clock)
    }
}

/// Get current time in milliseconds
fn current_time_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vector_clock_new() {
        let clock = VectorClock::new();
        assert_eq!(clock.get("region1"), 0);
        assert_eq!(clock.total_events(), 0);
    }

    #[test]
    fn test_vector_clock_with_regions() {
        let clock = VectorClock::with_regions(&["us-east", "eu-west", "ap-south"]);
        assert_eq!(clock.get("us-east"), 0);
        assert_eq!(clock.regions().len(), 3);
    }

    #[test]
    fn test_vector_clock_increment() {
        let mut clock = VectorClock::new();
        clock.increment("region1");
        assert_eq!(clock.get("region1"), 1);

        clock.increment("region1");
        assert_eq!(clock.get("region1"), 2);

        clock.increment("region2");
        assert_eq!(clock.get("region2"), 1);
    }

    #[test]
    fn test_vector_clock_tick() {
        let clock = VectorClock::new();
        let ticked = clock.tick("region1").tick("region1").tick("region2");

        assert_eq!(ticked.get("region1"), 2);
        assert_eq!(ticked.get("region2"), 1);
        assert_eq!(clock.get("region1"), 0); // Original unchanged
    }

    #[test]
    fn test_vector_clock_merge() {
        let mut clock1 = VectorClock::new();
        clock1.increment("r1");
        clock1.increment("r1");
        clock1.increment("r2");

        let mut clock2 = VectorClock::new();
        clock2.increment("r1");
        clock2.increment("r3");
        clock2.increment("r3");

        let merged = clock1.merge(&clock2);

        assert_eq!(merged.get("r1"), 2); // max(2, 1)
        assert_eq!(merged.get("r2"), 1); // max(1, 0)
        assert_eq!(merged.get("r3"), 2); // max(0, 2)
    }

    #[test]
    fn test_happens_before_simple() {
        let clock1 = VectorClock::new().tick("r1");
        let clock2 = clock1.tick("r1");

        assert!(clock1.happens_before(&clock2));
        assert!(!clock2.happens_before(&clock1));
    }

    #[test]
    fn test_happens_before_multi_region() {
        let mut clock1 = VectorClock::new();
        clock1.increment("r1");
        clock1.increment("r2");

        let mut clock2 = VectorClock::new();
        clock2.increment("r1");
        clock2.increment("r1");
        clock2.increment("r2");
        clock2.increment("r2");

        assert!(clock1.happens_before(&clock2));
        assert!(!clock2.happens_before(&clock1));
    }

    #[test]
    fn test_concurrent_clocks() {
        // Concurrent: r1=2,r2=1 vs r1=1,r2=2
        let mut clock1 = VectorClock::new();
        clock1.increment("r1");
        clock1.increment("r1");
        clock1.increment("r2");

        let mut clock2 = VectorClock::new();
        clock2.increment("r1");
        clock2.increment("r2");
        clock2.increment("r2");

        assert!(!clock1.happens_before(&clock2));
        assert!(!clock2.happens_before(&clock1));
        assert!(clock1.is_concurrent(&clock2));
    }

    #[test]
    fn test_equal_clocks() {
        let clock1 = VectorClock::new().tick("r1").tick("r2");
        let clock2 = VectorClock::new().tick("r1").tick("r2");

        assert!(!clock1.happens_before(&clock2));
        assert!(!clock2.happens_before(&clock1));
        assert!(!clock1.is_concurrent(&clock2));
        assert_eq!(clock1, clock2);
    }

    #[test]
    fn test_compare_clocks() {
        let clock1 = VectorClock::new().tick("r1");
        let clock2 = clock1.tick("r1");
        let clock3 = VectorClock::new().tick("r2");

        assert_eq!(compare_clocks(&clock1, &clock2), CausalOrder::Before);
        assert_eq!(compare_clocks(&clock2, &clock1), CausalOrder::After);
        assert_eq!(compare_clocks(&clock1, &clock3), CausalOrder::Concurrent);
        assert_eq!(compare_clocks(&clock1, &clock1), CausalOrder::Equal);
    }

    #[test]
    fn test_serialization() {
        let mut clock = VectorClock::new();
        clock.increment("us-east");
        clock.increment("us-east");
        clock.increment("eu-west");

        let bytes = clock.to_bytes();
        let restored = VectorClock::from_bytes(&bytes).unwrap();

        assert_eq!(clock, restored);
    }

    #[test]
    fn test_timestamped_supersedes() {
        let clock1 = VectorClock::new().tick("r1");
        let clock2 = clock1.tick("r1");

        let val1 = Timestamped::new(42, clock1, "r1".to_string());
        let val2 = Timestamped::new(43, clock2, "r1".to_string());

        assert!(val2.supersedes(&val1));
        assert!(!val1.supersedes(&val2));
    }

    #[test]
    fn test_timestamped_concurrent() {
        let clock1 = VectorClock::new().tick("r1");
        let clock2 = VectorClock::new().tick("r2");

        let val1 = Timestamped::new(42, clock1, "r1".to_string());
        let val2 = Timestamped::new(43, clock2, "r2".to_string());

        assert!(val1.is_concurrent(&val2));
        assert!(!val1.supersedes(&val2));
        assert!(!val2.supersedes(&val1));
    }
}
