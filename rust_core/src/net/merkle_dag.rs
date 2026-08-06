//! rust_core/src/net/merkle_dag.rs
//! Partial implementation of Merkle-DAG for decentralized storage.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DagBlock {
    pub hash: [u8; 32],
    pub data: Vec<u8>,
    pub parents: Vec<[u8; 32]>,
}

impl DagBlock {
    #[must_use]
    pub fn new(data: Vec<u8>, parents: Vec<[u8; 32]>) -> Self {
        use sha3::{Digest, Sha3_256};
        let mut hasher = Sha3_256::new();
        hasher.update(&data);
        for parent in &parents {
            hasher.update(parent);
        }
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&hasher.finalize());
        DagBlock {
            hash,
            data,
            parents,
        }
    }
}
