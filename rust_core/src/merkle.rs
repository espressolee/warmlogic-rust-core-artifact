//! rust_core/src/merkle.rs
//! [Phase 27] Pure Rust Merkle Tree Implementation.
//!
//! Replaces Python hashlib dependency for data integrity proofs.
//! All hashing done via SHA3-256 (Keccak) for quantum resistance.

#[cfg(feature = "std")]
use std::vec::Vec;

#[cfg(not(feature = "std"))]
use alloc::{string::String, vec::Vec};

use sha3::{Digest, Sha3_256};

#[cfg(feature = "python")]
use pyo3::prelude::*;

/// Pure Rust Merkle Tree.
///
/// Provides cryptographic data integrity proofs with SHA3-256 hashing.
/// All operations are deterministic and thread-safe.
#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, Default)]
pub struct MerkleTree {
    leaves: Vec<[u8; 32]>,
}

impl MerkleTree {
    /// Create a new empty Merkle Tree.
    #[must_use]
    pub fn new() -> Self {
        MerkleTree { leaves: Vec::new() }
    }

    /// Add a data item to the tree (will be hashed to create leaf).
    pub fn add_leaf(&mut self, data: &[u8]) {
        let mut hasher = Sha3_256::new();
        hasher.update(data);
        let result = hasher.finalize();
        let mut leaf = [0u8; 32];
        leaf.copy_from_slice(&result);
        self.leaves.push(leaf);
    }

    /// Calculate and return the Merkle Root as hex string.
    /// Returns empty string if tree has no leaves.
    #[must_use]
    pub fn get_root(&self) -> String {
        if self.leaves.is_empty() {
            return String::new();
        }

        let mut current_level: Vec<[u8; 32]> = self.leaves.clone();

        while current_level.len() > 1 {
            let mut next_level = Vec::new();
            let mut i = 0;
            while i < current_level.len() {
                let left = &current_level[i];
                let right = if i + 1 < current_level.len() {
                    &current_level[i + 1]
                } else {
                    // Duplicate last if odd number of nodes
                    left
                };

                let mut hasher = Sha3_256::new();
                hasher.update(left);
                hasher.update(right);
                let result = hasher.finalize();
                let mut combined = [0u8; 32];
                combined.copy_from_slice(&result);
                next_level.push(combined);
                i += 2;
            }
            current_level = next_level;
        }

        hex::encode(current_level[0])
    }

    /// Generate Merkle Proof for leaf at given index.
    /// Returns list of hex hashes representing sibling path to root.
    #[must_use]
    pub fn get_proof(&self, index: usize) -> Vec<String> {
        if self.leaves.is_empty() || index >= self.leaves.len() {
            return Vec::new();
        }

        let mut proof = Vec::new();
        let mut current_level: Vec<[u8; 32]> = self.leaves.clone();
        let mut current_index = index;

        while current_level.len() > 1 {
            let sibling_index = if current_index % 2 == 1 {
                current_index - 1
            } else {
                current_index + 1
            };

            // Add sibling to proof
            if sibling_index < current_level.len() {
                proof.push(hex::encode(current_level[sibling_index]));
            } else {
                // Odd node at end - sibling is itself
                proof.push(hex::encode(current_level[current_index]));
            }

            // Build next level
            let mut next_level = Vec::new();
            let mut i = 0;
            while i < current_level.len() {
                let left = &current_level[i];
                let right = if i + 1 < current_level.len() {
                    &current_level[i + 1]
                } else {
                    left
                };

                let mut hasher = Sha3_256::new();
                hasher.update(left);
                hasher.update(right);
                let result = hasher.finalize();
                let mut combined = [0u8; 32];
                combined.copy_from_slice(&result);
                next_level.push(combined);
                i += 2;
            }

            current_level = next_level;
            current_index /= 2;
        }

        proof
    }

    /// Verify a Merkle Proof.
    ///
    /// # Arguments
    /// * `leaf_data` - Original data item (will be hashed)
    /// * `proof` - List of sibling hashes (hex strings)
    /// * `root_hex` - Expected Merkle Root (hex)
    /// * `index` - Leaf index (determines concatenation order)
    ///
    /// # Returns
    /// `true` if proof is valid
    #[must_use]
    pub fn verify_proof(leaf_data: &[u8], proof: &[String], root_hex: &str, index: usize) -> bool {
        if root_hex.is_empty() {
            return false;
        }

        // Hash the leaf data
        let mut hasher = Sha3_256::new();
        hasher.update(leaf_data);
        let result = hasher.finalize();
        let mut current_hash = [0u8; 32];
        current_hash.copy_from_slice(&result);

        let mut current_index = index;

        for sibling_hex in proof {
            let sibling = match hex::decode(sibling_hex) {
                Ok(bytes) if bytes.len() == 32 => {
                    let mut arr = [0u8; 32];
                    arr.copy_from_slice(&bytes);
                    arr
                }
                _ => return false,
            };

            let is_right_child = current_index % 2 == 1;

            let mut hasher = Sha3_256::new();
            if is_right_child {
                // We are right, sibling is left
                hasher.update(&sibling);
                hasher.update(&current_hash);
            } else {
                // We are left, sibling is right
                hasher.update(&current_hash);
                hasher.update(&sibling);
            }

            let result = hasher.finalize();
            current_hash.copy_from_slice(&result);
            current_index /= 2;
        }

        hex::encode(current_hash) == root_hex
    }

    /// Get the number of leaves in the tree.
    #[must_use]
    pub fn len(&self) -> usize {
        self.leaves.len()
    }

    /// Check if the tree is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.leaves.is_empty()
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl MerkleTree {
    #[new]
    fn py_new() -> Self {
        MerkleTree::new()
    }

    /// Add a data item to the tree (will be hashed).
    #[pyo3(name = "add_leaf")]
    fn py_add_leaf(&mut self, data: &[u8]) {
        self.add_leaf(data);
    }

    /// Get the Merkle Root as hex string.
    #[pyo3(name = "get_root")]
    fn py_get_root(&self) -> String {
        self.get_root()
    }

    /// Get proof for leaf at index.
    #[pyo3(name = "get_proof")]
    fn py_get_proof(&self, index: usize) -> Vec<String> {
        self.get_proof(index)
    }

    /// Verify a Merkle proof.
    #[staticmethod]
    #[pyo3(name = "verify_proof")]
    fn py_verify_proof(
        leaf_data: &[u8],
        proof: Vec<String>,
        root_hex: String,
        index: usize,
    ) -> bool {
        MerkleTree::verify_proof(leaf_data, &proof, &root_hex, index)
    }

    /// Get number of leaves.
    fn __len__(&self) -> usize {
        self.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_tree() {
        let tree = MerkleTree::new();
        assert_eq!(tree.get_root(), "");
        assert!(tree.is_empty());
    }

    #[test]
    fn test_single_leaf() {
        let mut tree = MerkleTree::new();
        tree.add_leaf(b"hello");
        assert!(!tree.get_root().is_empty());
        assert_eq!(tree.len(), 1);
    }

    #[test]
    fn test_two_leaves() {
        let mut tree = MerkleTree::new();
        tree.add_leaf(b"hello");
        tree.add_leaf(b"world");
        let root = tree.get_root();
        assert!(!root.is_empty());
        assert_eq!(root.len(), 64); // SHA3-256 = 32 bytes = 64 hex chars
    }

    #[test]
    fn test_proof_verification() {
        let mut tree = MerkleTree::new();
        tree.add_leaf(b"item0");
        tree.add_leaf(b"item1");
        tree.add_leaf(b"item2");
        tree.add_leaf(b"item3");

        let root = tree.get_root();

        // Verify proof for each leaf
        for i in 0..4 {
            let proof = tree.get_proof(i);
            let data = format!("item{}", i);
            assert!(
                MerkleTree::verify_proof(data.as_bytes(), &proof, &root, i),
                "Proof verification failed for index {}",
                i
            );
        }
    }

    #[test]
    fn test_invalid_proof() {
        let mut tree = MerkleTree::new();
        tree.add_leaf(b"item0");
        tree.add_leaf(b"item1");

        let root = tree.get_root();
        let proof = tree.get_proof(0);

        // Wrong data should fail
        assert!(!MerkleTree::verify_proof(b"wrong_data", &proof, &root, 0));

        // Wrong index should fail
        assert!(!MerkleTree::verify_proof(b"item0", &proof, &root, 1));
    }

    #[test]
    fn test_odd_number_of_leaves() {
        let mut tree = MerkleTree::new();
        tree.add_leaf(b"a");
        tree.add_leaf(b"b");
        tree.add_leaf(b"c");

        let root = tree.get_root();
        assert!(!root.is_empty());

        // Verify all proofs work
        for i in 0..3 {
            let proof = tree.get_proof(i);
            let data = match i {
                0 => b"a".as_slice(),
                1 => b"b".as_slice(),
                _ => b"c".as_slice(),
            };
            assert!(MerkleTree::verify_proof(data, &proof, &root, i));
        }
    }
}
