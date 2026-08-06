#![allow(dead_code)]
#![allow(clippy::needless_range_loop)]
#[cfg(feature = "python")]
use pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[cfg(feature = "python")]
use crate::ffi_limits;

/// Kademlia K-Parameter (Bucket Size)
const K_PARAM: usize = 20;
const KEY_SIZE: usize = 32; // 256 bits

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[cfg_attr(feature = "python", pyclass)]
pub struct Contact {
    pub id: Vec<u8>,
    pub address: String,
    pub port: u16,
}

#[cfg(feature = "python")]
#[pymethods]
impl Contact {
    #[new]
    fn new(id: Vec<u8>, address: String, port: u16) -> PyResult<Self> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&id, "Contact:id").map_err(PyValueError::new_err)?;
        ffi_limits::validate_string(&address, "Contact:address").map_err(PyValueError::new_err)?;
        Ok(Contact { id, address, port })
    }

    #[getter]
    fn id(&self) -> Vec<u8> {
        self.id.clone()
    }
    #[getter]
    fn address(&self) -> String {
        self.address.clone()
    }
    #[getter]
    fn port(&self) -> u16 {
        self.port
    }
}

impl Contact {
    pub fn xor_distance(&self, target: &[u8]) -> Vec<u8> {
        let len = std::cmp::min(self.id.len(), target.len());
        let mut distance = Vec::with_capacity(len);
        for i in 0..len {
            distance.push(self.id[i] ^ target[i]);
        }
        distance
    }
}

/// Replacement cache size per bucket (for when bucket is full)
const REPLACEMENT_CACHE_SIZE: usize = 5;

pub struct RoutingTable {
    local_id: Vec<u8>,
    // 256 buckets, index i corresponds to contacts sharing i leading bits (distance 2^(255-i))
    // Or simplified: index i corresponds to distance within range [2^i, 2^(i+1))
    // Let's use standard Kademlia: bucket i stores contacts where distance common prefix length is i.
    buckets: Vec<Vec<Contact>>,
    // Replacement caches for each bucket (used when bucket is full)
    replacement_caches: Vec<Vec<Contact>>,
    // Failure counts for contacts (node_id_hex -> failure_count)
    failure_counts: std::collections::HashMap<Vec<u8>, u8>,
}

/// Maximum failures before evicting a node
const MAX_FAILURES: u8 = 3;

impl RoutingTable {
    pub fn new(local_id: Vec<u8>) -> Self {
        let mut buckets = Vec::with_capacity(KEY_SIZE * 8);
        let mut replacement_caches = Vec::with_capacity(KEY_SIZE * 8);
        for _ in 0..(KEY_SIZE * 8) {
            buckets.push(Vec::with_capacity(K_PARAM));
            replacement_caches.push(Vec::with_capacity(REPLACEMENT_CACHE_SIZE));
        }
        RoutingTable {
            local_id,
            buckets,
            replacement_caches,
            failure_counts: std::collections::HashMap::new(),
        }
    }

    /// Get the total number of contacts in all buckets
    pub fn len(&self) -> usize {
        self.buckets.iter().map(|b| b.len()).sum()
    }

    /// Check if routing table is empty
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Calculate bucket index (number of leading zero bits in XOR distance)
    fn bucket_index(&self, target_id: &[u8]) -> usize {
        let mut prefix_len = 0;
        let len = self.local_id.len(); // 32

        for i in 0..len {
            let xor = self.local_id[i] ^ target_id[i];
            if xor == 0 {
                prefix_len += 8;
            } else {
                prefix_len += xor.leading_zeros() as usize;
                break;
            }
        }
        // Cap at 255
        if prefix_len >= (KEY_SIZE * 8) {
            return (KEY_SIZE * 8) - 1;
        }
        prefix_len
    }

    pub fn update(&mut self, contact: Contact) {
        if contact.id == self.local_id {
            return;
        }

        let idx = self.bucket_index(&contact.id);

        // Clear any failure count for this contact (it responded)
        self.failure_counts.remove(&contact.id);

        let bucket = match self.buckets.get_mut(idx) {
            Some(b) => b,
            None => return, // Invalid bucket index, skip update
        };

        // Check if exists in main bucket
        if let Some(pos) = bucket.iter().position(|c| c.id == contact.id) {
            // Move to tail (most recently seen)
            let c = bucket.remove(pos);
            bucket.push(c);
            return;
        }

        // Check if exists in replacement cache
        let cache = match self.replacement_caches.get_mut(idx) {
            Some(c) => c,
            None => return, // Invalid cache index
        };
        if let Some(pos) = cache.iter().position(|c| c.id == contact.id) {
            // Move to tail of cache
            let c = cache.remove(pos);
            cache.push(c);
        }

        // New contact - try to add to bucket
        if bucket.len() < K_PARAM {
            bucket.push(contact);
        } else {
            // Bucket full - add to replacement cache
            if let Some(cache) = self.replacement_caches.get_mut(idx) {
                if cache.len() >= REPLACEMENT_CACHE_SIZE {
                    cache.remove(0); // Remove oldest
                }
                cache.push(contact);
            }
        }
    }

    /// Record a failure for a contact (e.g., didn't respond to ping)
    /// Returns true if the contact was evicted
    pub fn record_failure(&mut self, node_id: &[u8]) -> bool {
        let count = self.failure_counts.entry(node_id.to_vec()).or_insert(0);
        *count += 1;

        if *count >= MAX_FAILURES {
            // Evict the node and promote from replacement cache
            self.evict_node(node_id);
            return true;
        }
        false
    }

    /// Evict a node and promote a replacement if available
    fn evict_node(&mut self, node_id: &[u8]) {
        let idx = self.bucket_index(node_id);

        let bucket = match self.buckets.get_mut(idx) {
            Some(b) => b,
            None => {
                self.failure_counts.remove(node_id);
                return;
            }
        };

        // Remove from bucket
        if let Some(pos) = bucket.iter().position(|c| c.id == node_id) {
            bucket.remove(pos);

            // Promote from replacement cache
            if let Some(cache) = self.replacement_caches.get_mut(idx) {
                if let Some(replacement) = cache.pop() {
                    bucket.push(replacement);
                }
            }
        }

        // Clean up failure count
        self.failure_counts.remove(node_id);
    }

    /// Remove a node explicitly (e.g., when known to be offline)
    pub fn remove(&mut self, node_id: &[u8]) {
        self.evict_node(node_id);
    }

    /// Get nodes that need refresh (oldest in each non-empty bucket)
    pub fn get_refresh_candidates(&self) -> Vec<Contact> {
        let mut candidates = Vec::new();
        for bucket in &self.buckets {
            if !bucket.is_empty() {
                // Oldest is at index 0
                candidates.push(bucket[0].clone());
            }
        }
        candidates
    }

    /// Get buckets that haven't been updated recently (for bucket refresh)
    /// Returns bucket indices that have contacts
    pub fn get_stale_bucket_indices(&self) -> Vec<usize> {
        self.buckets
            .iter()
            .enumerate()
            .filter(|(_, b)| !b.is_empty())
            .map(|(i, _)| i)
            .collect()
    }

    pub fn find_closest(&self, target_id: &[u8]) -> Vec<Contact> {
        let mut all_contacts: Vec<Contact> = Vec::new();

        // Naive gathering: gather from all buckets, then sort.
        // Optimization: Start from target bucket and expand out.
        // For simplicity and correctness first: gather all.
        for bucket in &self.buckets {
            for contact in bucket {
                all_contacts.push(contact.clone());
            }
        }

        all_contacts.sort_by(|a, b| {
            let dist_a = a.xor_distance(target_id);
            let dist_b = b.xor_distance(target_id);
            dist_a.cmp(&dist_b)
        });

        all_contacts.into_iter().take(K_PARAM).collect()
    }
}

#[cfg(feature = "python")]
#[pyclass(name = "RustRoutingTable")]
pub struct PyRoutingTable {
    inner: RoutingTable,
}

#[cfg(feature = "python")]
#[pymethods]
impl PyRoutingTable {
    #[new]
    fn new(local_id: Vec<u8>) -> PyResult<Self> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&local_id, "PyRoutingTable:local_id")
            .map_err(PyValueError::new_err)?;
        Ok(PyRoutingTable {
            inner: RoutingTable::new(local_id),
        })
    }

    fn update(&mut self, node_id: Vec<u8>, address: String, port: u16) -> PyResult<()> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&node_id, "PyRoutingTable.update:node_id")
            .map_err(PyValueError::new_err)?;
        ffi_limits::validate_string(&address, "PyRoutingTable.update:address")
            .map_err(PyValueError::new_err)?;
        let contact = Contact {
            id: node_id,
            address,
            port,
        };
        self.inner.update(contact);
        Ok(())
    }

    fn find_closest(&self, target_id: Vec<u8>) -> PyResult<Vec<(Vec<u8>, String, u16)>> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&target_id, "PyRoutingTable.find_closest:target_id")
            .map_err(PyValueError::new_err)?;
        Ok(self
            .inner
            .find_closest(&target_id)
            .into_iter()
            .map(|c| (c.id, c.address, c.port))
            .collect())
    }

    /// Record a failure for a node. Returns true if the node was evicted.
    fn record_failure(&mut self, node_id: Vec<u8>) -> PyResult<bool> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&node_id, "PyRoutingTable.record_failure:node_id")
            .map_err(PyValueError::new_err)?;
        Ok(self.inner.record_failure(&node_id))
    }

    /// Remove a node explicitly
    fn remove(&mut self, node_id: Vec<u8>) -> PyResult<()> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&node_id, "PyRoutingTable.remove:node_id")
            .map_err(PyValueError::new_err)?;
        self.inner.remove(&node_id);
        Ok(())
    }

    /// Get the number of contacts in the routing table
    fn len(&self) -> usize {
        self.inner.len()
    }

    /// Check if routing table is empty
    fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    /// Get contacts that should be pinged to verify they're still alive
    fn get_refresh_candidates(&self) -> Vec<(Vec<u8>, String, u16)> {
        self.inner
            .get_refresh_candidates()
            .into_iter()
            .map(|c| (c.id, c.address, c.port))
            .collect()
    }
}

// --- Peer Discovery (WarmP2P) ---

#[cfg(feature = "python")]
use std::collections::HashSet;

#[cfg(feature = "python")]
#[pyclass(name = "RustyDiscoveryAgent")]
pub struct RustyDiscoveryAgent {
    target_id: Vec<u8>,
    shortlist: Vec<Contact>, // Kept sorted
    queried: HashSet<Vec<u8>>,
    active_queries: HashSet<Vec<u8>>, // To avoid duplicate in-flight
    k_param: usize,
    alpha: usize,
}

#[cfg(feature = "python")]
#[pymethods]
impl RustyDiscoveryAgent {
    #[new]
    fn new(target_id: Vec<u8>, initial_peers: Vec<(Vec<u8>, String, u16)>) -> PyResult<Self> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&target_id, "RustyDiscoveryAgent:target_id")
            .map_err(PyValueError::new_err)?;
        ffi_limits::validate_array_len(initial_peers.len(), "RustyDiscoveryAgent:initial_peers")
            .map_err(PyValueError::new_err)?;
        for (id, addr, _) in &initial_peers {
            ffi_limits::validate_bytes(id, "RustyDiscoveryAgent:peer_id")
                .map_err(PyValueError::new_err)?;
            ffi_limits::validate_string(addr, "RustyDiscoveryAgent:peer_addr")
                .map_err(PyValueError::new_err)?;
        }
        let mut agent = RustyDiscoveryAgent {
            target_id,
            shortlist: Vec::new(),
            queried: HashSet::new(),
            active_queries: HashSet::new(),
            k_param: K_PARAM,
            alpha: 3, // Default ALPHA
        };

        // Convert tuples to Contact and add
        for (id, addr, port) in initial_peers {
            let c = Contact {
                id,
                address: addr,
                port,
            };
            agent.add_contact(c);
        }
        Ok(agent)
    }

    fn add_response(&mut self, peers: Vec<(Vec<u8>, String, u16)>) -> PyResult<()> {
        // FFI Input Validation 
        ffi_limits::validate_array_len(peers.len(), "RustyDiscoveryAgent.add_response:peers")
            .map_err(PyValueError::new_err)?;
        for (id, addr, port) in peers {
            ffi_limits::validate_bytes(&id, "RustyDiscoveryAgent.add_response:peer_id")
                .map_err(PyValueError::new_err)?;
            ffi_limits::validate_string(&addr, "RustyDiscoveryAgent.add_response:peer_addr")
                .map_err(PyValueError::new_err)?;
            let c = Contact {
                id,
                address: addr,
                port,
            };
            self.add_contact(c);
        }
        Ok(())
    }

    fn mark_queried(&mut self, node_id: Vec<u8>) -> PyResult<()> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&node_id, "RustyDiscoveryAgent.mark_queried:node_id")
            .map_err(PyValueError::new_err)?;
        self.queried.insert(node_id.clone());
        self.active_queries.remove(&node_id);
        Ok(())
    }

    fn mark_failed(&mut self, node_id: Vec<u8>) -> PyResult<()> {
        // FFI Input Validation 
        ffi_limits::validate_bytes(&node_id, "RustyDiscoveryAgent.mark_failed:node_id")
            .map_err(PyValueError::new_err)?;
        // Remove from shortlist? Or just mark queried (so we don't ask again)
        // Kademlia: remove if unreachable.
        self.queried.insert(node_id.clone());
        self.active_queries.remove(&node_id);

        if let Some(pos) = self.shortlist.iter().position(|c| c.id == node_id) {
            self.shortlist.remove(pos);
        }
        Ok(())
    }

    fn get_next_peers(&mut self) -> Vec<(Vec<u8>, String, u16)> {
        // Return up to alpha unqueried peers from the top of the shortlist
        // Logic: Iterate shortlist. If not queried and not active, take it.
        // Mark as active.

        let mut next_batch = Vec::new();
        let mut count = 0;

        // Shortlist is sorted by distance.
        // We clone contacts to return them (PyO3 boundaries generally prefer Owned data unless we use PyRef)

        for contact in &self.shortlist {
            if count >= self.alpha {
                break;
            }
            if !self.queried.contains(&contact.id) && !self.active_queries.contains(&contact.id) {
                next_batch.push((contact.id.clone(), contact.address.clone(), contact.port));
                self.active_queries.insert(contact.id.clone());
                count += 1;
            }
        }

        next_batch
    }

    fn is_finished(&self) -> bool {
        // Finished if no active queries AND (all top K in shortlist are queried OR no unqueried nodes remain in shortlist)
        // Simplified: Finished if no active queries and no unqueried nodes in top K.
        if !self.active_queries.is_empty() {
            return false;
        }

        // Check if any unqueried nodes exist in Shortlist (restricted to top K ideally, but usually just check entire shortlist)
        // If shortlist has unqueried nodes, we are not finished (we should query them).
        // Unless we have already found K closest and they are all queried.

        // Check top K
        let check_limit = std::cmp::min(self.shortlist.len(), self.k_param);
        for contact in self.shortlist.iter().take(check_limit) {
            if !self.queried.contains(&contact.id) {
                return false;
            }
        }

        true
    }

    fn get_k_closest(&self) -> Vec<(Vec<u8>, String, u16)> {
        self.shortlist
            .iter()
            .take(self.k_param)
            .map(|c| (c.id.clone(), c.address.clone(), c.port))
            .collect()
    }
}

#[cfg(feature = "python")]
impl RustyDiscoveryAgent {
    fn add_contact(&mut self, contact: Contact) {
        if contact.id == self.target_id {
            return;
        }
        if self.shortlist.iter().any(|c| c.id == contact.id) {
            return;
        }

        self.shortlist.push(contact);
        let target = self.target_id.clone();

        self.shortlist.sort_by(|a: &Contact, b: &Contact| {
            a.xor_distance(&target).cmp(&b.xor_distance(&target))
        });

        // Optional: truncate to maintain manageable size (e.g. K * 3)
        if self.shortlist.len() > self.k_param * 3 {
            self.shortlist.truncate(self.k_param * 3);
        }
    }
}

// ============================================================================
// Unit Tests
// ============================================================================
#[cfg(test)]
mod tests {
    use super::*;

    fn make_id(bytes: &[u8]) -> Vec<u8> {
        let mut id = vec![0u8; KEY_SIZE];
        for (i, b) in bytes.iter().enumerate() {
            if i < KEY_SIZE {
                id[i] = *b;
            }
        }
        id
    }

    // --- Contact Tests ---

    #[test]
    fn test_contact_xor_distance_identical() {
        let id = make_id(&[0x12, 0x34, 0x56]);
        let contact = Contact {
            id: id.clone(),
            address: "127.0.0.1".to_string(),
            port: 8080,
        };
        let distance = contact.xor_distance(&id);
        // XOR with self should be all zeros
        assert!(distance.iter().all(|&b| b == 0));
    }

    #[test]
    fn test_contact_xor_distance_different() {
        let id1 = make_id(&[0xFF, 0x00]);
        let id2 = make_id(&[0x00, 0xFF]);
        let contact = Contact {
            id: id1,
            address: "127.0.0.1".to_string(),
            port: 8080,
        };
        let distance = contact.xor_distance(&id2);
        assert_eq!(distance[0], 0xFF); // 0xFF ^ 0x00 = 0xFF
        assert_eq!(distance[1], 0xFF); // 0x00 ^ 0xFF = 0xFF
    }

    #[test]
    fn test_contact_xor_distance_single_bit() {
        let id1 = make_id(&[0b10000000]);
        let id2 = make_id(&[0b00000000]);
        let contact = Contact {
            id: id1,
            address: "localhost".to_string(),
            port: 9000,
        };
        let distance = contact.xor_distance(&id2);
        assert_eq!(distance[0], 0b10000000);
    }

    // --- RoutingTable Tests ---

    #[test]
    fn test_routing_table_initialization() {
        let local_id = make_id(&[0x01]);
        let table = RoutingTable::new(local_id);
        assert_eq!(table.buckets.len(), KEY_SIZE * 8); // 256 buckets
        assert!(table.buckets.iter().all(|b| b.is_empty()));
    }

    #[test]
    fn test_bucket_index_all_zeros() {
        // When XOR is all zeros except last byte, we expect high prefix length
        let local_id = make_id(&[]);
        let table = RoutingTable::new(local_id.clone());

        // Target with only last bit different
        let mut target = local_id.clone();
        target[KEY_SIZE - 1] = 0x01;

        let idx = table.bucket_index(&target);
        // 31 bytes of zeros = 248 bits, plus leading zeros in 0x01 (7 more)
        assert_eq!(idx, 255); // Capped at 255
    }

    #[test]
    fn test_bucket_index_first_bit_different() {
        let local_id = make_id(&[0x00]);
        let target = make_id(&[0x80]); // First bit is 1
        let table = RoutingTable::new(local_id);

        let idx = table.bucket_index(&target);
        // XOR = 0x80 = 0b10000000, leading zeros = 0
        assert_eq!(idx, 0);
    }

    #[test]
    fn test_bucket_index_eighth_bit_different() {
        let local_id = make_id(&[0x00]);
        let target = make_id(&[0x01]); // 8th bit is 1
        let table = RoutingTable::new(local_id);

        let idx = table.bucket_index(&target);
        // XOR = 0x01 = 0b00000001, leading zeros = 7
        assert_eq!(idx, 7);
    }

    #[test]
    fn test_bucket_index_second_byte() {
        let local_id = make_id(&[0x00, 0x00]);
        let target = make_id(&[0x00, 0x80]); // First bit of second byte
        let table = RoutingTable::new(local_id);

        let idx = table.bucket_index(&target);
        // First byte XOR = 0 (8 leading zeros), second byte = 0x80 (0 more)
        assert_eq!(idx, 8);
    }

    #[test]
    fn test_update_adds_new_contact() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        let contact = Contact {
            id: make_id(&[0x80]),
            address: "192.168.1.1".to_string(),
            port: 5000,
        };

        table.update(contact.clone());

        // Bucket 0 should have the contact
        assert_eq!(table.buckets[0].len(), 1);
        assert_eq!(table.buckets[0][0].address, "192.168.1.1");
    }

    #[test]
    fn test_update_ignores_self() {
        let local_id = make_id(&[0xAB, 0xCD]);
        let mut table = RoutingTable::new(local_id.clone());

        let contact = Contact {
            id: local_id,
            address: "self".to_string(),
            port: 1234,
        };

        table.update(contact);

        // No bucket should have the contact
        assert!(table.buckets.iter().all(|b| b.is_empty()));
    }

    #[test]
    fn test_update_moves_existing_to_tail() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        let contact1 = Contact {
            id: make_id(&[0x80]),
            address: "first".to_string(),
            port: 1000,
        };
        let contact2 = Contact {
            id: make_id(&[0x81]),
            address: "second".to_string(),
            port: 2000,
        };

        table.update(contact1.clone());
        table.update(contact2);
        table.update(contact1.clone()); // Re-add first

        // First contact should now be at tail
        let bucket = &table.buckets[0];
        assert_eq!(bucket.len(), 2);
        assert_eq!(bucket[1].address, "first");
    }

    #[test]
    fn test_update_bucket_capacity_limit() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        // Fill bucket 0 with K_PARAM contacts
        for i in 0..K_PARAM {
            let contact = Contact {
                id: make_id(&[0x80 | (i as u8 & 0x7F)]),
                address: format!("host{}", i),
                port: 1000 + i as u16,
            };
            table.update(contact);
        }

        assert_eq!(table.buckets[0].len(), K_PARAM);

        // Try to add one more
        let new_contact = Contact {
            id: make_id(&[0xC0]),
            address: "overflow".to_string(),
            port: 9999,
        };
        table.update(new_contact);

        // Bucket should still be at K_PARAM (new contact dropped)
        assert_eq!(table.buckets[0].len(), K_PARAM);
    }

    // --- find_closest Tests ---

    #[test]
    fn test_find_closest_empty_table() {
        let local_id = make_id(&[0x00]);
        let table = RoutingTable::new(local_id);

        let target = make_id(&[0xFF]);
        let closest = table.find_closest(&target);

        assert!(closest.is_empty());
    }

    #[test]
    fn test_find_closest_single_contact() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        let contact = Contact {
            id: make_id(&[0x10]),
            address: "only_one".to_string(),
            port: 5555,
        };
        table.update(contact);

        let target = make_id(&[0xFF]);
        let closest = table.find_closest(&target);

        assert_eq!(closest.len(), 1);
        assert_eq!(closest[0].address, "only_one");
    }

    #[test]
    fn test_find_closest_sorted_by_distance() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        // Target = 0x80
        // Contact A = 0x70 -> XOR distance = 0xF0
        // Contact B = 0x90 -> XOR distance = 0x10
        // Contact C = 0x81 -> XOR distance = 0x01

        let target = make_id(&[0x80]);

        table.update(Contact {
            id: make_id(&[0x70]),
            address: "far".to_string(),
            port: 1,
        });
        table.update(Contact {
            id: make_id(&[0x90]),
            address: "medium".to_string(),
            port: 2,
        });
        table.update(Contact {
            id: make_id(&[0x81]),
            address: "close".to_string(),
            port: 3,
        });

        let closest = table.find_closest(&target);

        assert_eq!(closest.len(), 3);
        assert_eq!(closest[0].address, "close"); // Distance 0x01
        assert_eq!(closest[1].address, "medium"); // Distance 0x10
        assert_eq!(closest[2].address, "far"); // Distance 0xF0
    }

    #[test]
    fn test_find_closest_limits_to_k() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        // Add more than K_PARAM contacts across different buckets
        for i in 0..(K_PARAM + 10) {
            let byte_val = ((i + 1) % 256) as u8;
            table.update(Contact {
                id: make_id(&[byte_val]),
                address: format!("node{}", i),
                port: i as u16,
            });
        }

        let target = make_id(&[0x50]);
        let closest = table.find_closest(&target);

        // Should return at most K_PARAM
        assert!(closest.len() <= K_PARAM);
    }

    // --- Replacement Cache Tests ---

    #[test]
    fn test_replacement_cache_used_when_bucket_full() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        // Fill bucket 0 with K_PARAM contacts (all have first bit = 1)
        for i in 0..K_PARAM {
            let id = make_id(&[0x80 | (i as u8 & 0x7F)]);
            table.update(Contact {
                id,
                address: format!("node{}", i),
                port: 1000 + i as u16,
            });
        }

        assert_eq!(table.buckets[0].len(), K_PARAM);

        // Add one more - should go to replacement cache
        let extra_id = make_id(&[0xC0]);
        table.update(Contact {
            id: extra_id.clone(),
            address: "extra".to_string(),
            port: 9999,
        });

        // Bucket still at K_PARAM
        assert_eq!(table.buckets[0].len(), K_PARAM);
        // Replacement cache should have the extra contact
        assert_eq!(table.replacement_caches[0].len(), 1);
        assert_eq!(table.replacement_caches[0][0].address, "extra");
    }

    #[test]
    fn test_record_failure_evicts_after_max() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        let node_id = make_id(&[0x80]);
        table.update(Contact {
            id: node_id.clone(),
            address: "failing_node".to_string(),
            port: 5000,
        });

        assert_eq!(table.len(), 1);

        // Record failures up to MAX_FAILURES - 1
        for _ in 0..(MAX_FAILURES - 1) {
            let evicted = table.record_failure(&node_id);
            assert!(!evicted, "Should not evict before MAX_FAILURES");
            assert_eq!(table.len(), 1);
        }

        // One more failure should evict
        let evicted = table.record_failure(&node_id);
        assert!(evicted, "Should evict at MAX_FAILURES");
        assert_eq!(table.len(), 0);
    }

    #[test]
    fn test_eviction_promotes_from_replacement_cache() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        // Fill bucket 0
        for i in 0..K_PARAM {
            let id = make_id(&[0x80 | (i as u8 & 0x7F)]);
            table.update(Contact {
                id,
                address: format!("main{}", i),
                port: 1000 + i as u16,
            });
        }

        // Add to replacement cache
        let replacement_id = make_id(&[0xC0]);
        table.update(Contact {
            id: replacement_id.clone(),
            address: "replacement".to_string(),
            port: 9999,
        });

        assert_eq!(table.buckets[0].len(), K_PARAM);
        assert_eq!(table.replacement_caches[0].len(), 1);

        // Remove a node from main bucket
        let node_to_remove = make_id(&[0x80]);
        table.remove(&node_to_remove);

        // Should still have K_PARAM (promoted from cache)
        // Actually it will be K_PARAM - 1 + 1 = K_PARAM... wait.
        // After removal: K_PARAM - 1 nodes + 1 promoted = K_PARAM
        // But bucket was full (20), we remove 1, add 1 from cache = 20
        // Wait, K_PARAM is 20, but we may not have added all to same bucket due to bucket_index

        // Actually, all contacts with first bit = 1 go to bucket index 0
        // So we should have K_PARAM in bucket[0]
        assert_eq!(table.buckets[0].len(), K_PARAM);

        // Replacement cache should be empty now
        assert_eq!(table.replacement_caches[0].len(), 0);

        // The replacement should now be in main bucket
        assert!(table.buckets[0].iter().any(|c| c.address == "replacement"));
    }

    #[test]
    fn test_remove_node() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        let node_id = make_id(&[0x80]);
        table.update(Contact {
            id: node_id.clone(),
            address: "to_remove".to_string(),
            port: 5000,
        });

        assert_eq!(table.len(), 1);

        table.remove(&node_id);
        assert_eq!(table.len(), 0);
    }

    #[test]
    fn test_get_refresh_candidates() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        // Add contacts to different buckets
        table.update(Contact {
            id: make_id(&[0x80]), // bucket 0
            address: "bucket0".to_string(),
            port: 1,
        });
        table.update(Contact {
            id: make_id(&[0x40]), // bucket 1
            address: "bucket1".to_string(),
            port: 2,
        });
        table.update(Contact {
            id: make_id(&[0x20]), // bucket 2
            address: "bucket2".to_string(),
            port: 3,
        });

        let candidates = table.get_refresh_candidates();

        // Should have one candidate per non-empty bucket
        assert_eq!(candidates.len(), 3);
    }

    #[test]
    fn test_len_and_is_empty() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        assert!(table.is_empty());
        assert_eq!(table.len(), 0);

        table.update(Contact {
            id: make_id(&[0x80]),
            address: "test".to_string(),
            port: 1,
        });

        assert!(!table.is_empty());
        assert_eq!(table.len(), 1);
    }

    #[test]
    fn test_update_clears_failure_count() {
        let local_id = make_id(&[0x00]);
        let mut table = RoutingTable::new(local_id);

        let node_id = make_id(&[0x80]);
        table.update(Contact {
            id: node_id.clone(),
            address: "node".to_string(),
            port: 5000,
        });

        // Record some failures
        table.record_failure(&node_id);
        table.record_failure(&node_id);
        assert_eq!(*table.failure_counts.get(&node_id).unwrap(), 2);

        // Update the contact (it responded!)
        table.update(Contact {
            id: node_id.clone(),
            address: "node".to_string(),
            port: 5000,
        });

        // Failure count should be cleared
        assert!(!table.failure_counts.contains_key(&node_id));
    }
}
