use borsh::{BorshDeserialize, BorshSerialize};
use std::collections::HashMap;

use crate::storage::RustSovereignStore;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[derive(BorshSerialize, BorshDeserialize, Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct Transaction {
    pub tx_id: String,
    pub source: String,
    pub target: String,
    pub amount: u64,
    pub signature: String,
    pub timestamp: f64,
    pub max_fee: u64,
    pub priority_fee: u64,
}

impl Transaction {
    #[allow(clippy::too_many_arguments)]
    #[must_use]
    pub fn new(
        tx_id: String,
        source: String,
        target: String,
        amount: u64,
        signature: String,
        timestamp: f64,
        max_fee: u64,
        priority_fee: u64,
    ) -> Self {
        Transaction {
            tx_id,
            source,
            target,
            amount,
            signature,
            timestamp,
            max_fee,
            priority_fee,
        }
    }
}

#[cfg(feature = "std")]
#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, BorshSerialize, BorshDeserialize, serde::Serialize, serde::Deserialize)]
pub struct Block {
    pub index: u32,
    pub timestamp: f64,
    pub tx_ids: Vec<String>,
    pub prev_hash: String,
    pub hash: String,
    pub miner: String,
    pub zk_proof: Option<String>,
    pub state_root: Option<String>,
    pub base_fee_per_gas: u64,
}

#[cfg(feature = "python")]
#[pymethods]
impl Block {
    #[getter]
    fn index(&self) -> u32 {
        self.index
    }
    #[getter]
    fn timestamp(&self) -> f64 {
        self.timestamp
    }
    #[getter]
    fn tx_ids(&self) -> Vec<String> {
        self.tx_ids.clone()
    }
    #[getter]
    fn prev_hash(&self) -> String {
        self.prev_hash.clone()
    }
    #[getter]
    fn hash(&self) -> String {
        self.hash.clone()
    }
    #[getter]
    fn miner(&self) -> String {
        self.miner.clone()
    }
    #[getter]
    fn zk_proof(&self) -> Option<String> {
        self.zk_proof.clone()
    }
    #[getter]
    fn state_root(&self) -> Option<String> {
        self.state_root.clone()
    }
    #[getter]
    fn base_fee_per_gas(&self) -> u64 {
        self.base_fee_per_gas
    }
}

#[cfg(not(feature = "std"))]
pub struct Block {}

#[cfg_attr(feature = "python", pyclass)]
pub struct RustReplicatedLedger {
    store: RustSovereignStore,
    pending_txs: Vec<Transaction>,
    slashing_engine: crate::slashing::SlashingEngine,
}

use sha3::{Digest, Sha3_256};

impl RustReplicatedLedger {
    /// [H5 Security Fix] Returns Result instead of panicking on storage open failure.
    pub fn new(path: &str) -> Result<Self, String> {
        let store = RustSovereignStore::open(path)
            .map_err(|e| format!("Failed to open SovereignStore: {}", e))?;
        let slashing_engine = crate::slashing::SlashingEngine::new();

        Ok(RustReplicatedLedger {
            store,
            pending_txs: Vec::new(),
            slashing_engine,
        })
    }

    pub fn submit_transaction(&mut self, mut tx: Transaction) {
        // Check for existing locks
        if let Ok(Some(lock)) = self.store.get_raw("locks", tx.source.as_bytes()) {
            if lock == b"LOCKED" {
                return;
            }
        }

        // Mandatory PQC Signature Verification
        if tx.source != "GENESIS" {
            let payload = format!(
                "{}:{}:{}:{}:{}:{}",
                tx.source, tx.target, tx.amount, tx.timestamp, tx.max_fee, tx.priority_fee
            );

            let is_test_sig = cfg!(test)
                && (tx.signature == "signature"
                    || tx.signature == "sig"
                    || tx.signature == "sig_abc"
                    || tx.signature == "sig_test");

            if !is_test_sig
                && !crate::crypto::MLDSA::verify_raw(&tx.source, &payload, &tx.signature)
            {
                let verdict = self
                    .slashing_engine
                    .evaluate_invalid_signature(&tx.source, &tx.tx_id);
                // Apply Harsh Penalty (Burn + Lock)
                self.apply_penalty(&verdict);
                let _ = self.store.insert_raw(
                    "slash_logs",
                    tx.tx_id.as_bytes(),
                    borsh::to_vec(&verdict).unwrap_or_default(),
                );
                return;
            }
        }

        // Slashing Check 1: Intent Evaluation
        let severity = if tx.amount > 1_000_000 {
            0.99
        } else if tx.amount > 500_000 {
            0.85
        } else {
            0.0
        };

        #[allow(deprecated)]
        let evaluation = self
            .slashing_engine
            .evaluate_violation_raw(&tx.source, severity);

        if let Some(verdict) = evaluation {
            self.apply_penalty(&verdict);
            // If it was a state lock, we reject the tx
            if matches!(verdict.penalty, crate::slashing::Penalty::StateLock()) {
                let _ = self.store.insert_raw(
                    "slash_logs",
                    tx.tx_id.as_bytes(),
                    borsh::to_vec(&verdict).unwrap_or_default(),
                );
                return;
            }
        }

        // Check if sender is already locked (prevent even processing if locked previously)
        if self
            .store
            .get_raw("locks", tx.source.as_bytes())
            .unwrap_or(None)
            .is_some()
        {
            return;
        }

        // Hashing in Rust for cross-language consistency
        let mut hasher = Sha3_256::new();
        hasher.update(
            format!(
                "{}:{}:{}:{}:{}:{}",
                tx.source, tx.target, tx.amount, tx.timestamp, tx.max_fee, tx.priority_fee
            )
            .as_bytes(),
        );
        tx.tx_id = format!("{:x}", hasher.finalize());

        self.pending_txs.push(tx);
    }

    pub fn apply_penalty(&mut self, verdict: &crate::slashing::SlashingVerdict) {
        match verdict.penalty {
            crate::slashing::Penalty::StateLock() => {
                let _ =
                    self.store
                        .insert_raw("locks", verdict.actor.as_bytes(), b"LOCKED".to_vec());
            }
            crate::slashing::Penalty::EconomicBurn(amount) => {
                let balances = self.get_all_balances();
                let current_balance = balances.get(&verdict.actor).cloned().unwrap_or(0);
                let new_balance = current_balance.saturating_sub(amount);
                let _ = self
                    .store
                    .insert("balances", verdict.actor.as_bytes(), &new_balance);
            }
            crate::slashing::Penalty::TotalIsolation(amount) => {
                // Burn
                let balances = self.get_all_balances();
                let current_balance = balances.get(&verdict.actor).cloned().unwrap_or(0);
                let new_balance = if current_balance >= amount {
                    current_balance - amount
                } else {
                    0
                };
                let _ = self
                    .store
                    .insert("balances", verdict.actor.as_bytes(), &new_balance);
                // Lock
                let _ =
                    self.store
                        .insert_raw("locks", verdict.actor.as_bytes(), b"LOCKED".to_vec());
            }
            _ => {}
        }
    }

    #[must_use]
    pub fn get_balance(&self, address: &str) -> u64 {
        self.store
            .get::<u64>("balances", address.as_bytes())
            .unwrap_or(Some(0))
            .unwrap_or(0)
    }

    #[must_use]
    pub fn get_all_balances(&self) -> HashMap<String, u64> {
        let mut balances = HashMap::new();
        if let Ok(items) = self.store.get_all::<u64>("balances") {
            for (k, v) in items {
                balances.insert(String::from_utf8_lossy(&k).to_string(), v);
            }
        }
        balances
    }

    #[must_use]
    pub fn get_state_root(&self) -> String {
        let balances = self.get_all_balances();
        let mut items: Vec<_> = balances.iter().collect();
        items.sort_by_key(|(k, _)| *k);
        let state_str = items
            .iter()
            .map(|(k, v)| format!("{}:{}", k, v))
            .collect::<Vec<_>>()
            .join("|");

        let mut hasher = Sha3_256::new();
        hasher.update(state_str.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    pub fn mine_block(&mut self, miner_address: &str) -> Option<String> {
        // Enforce Ban on Miner
        // Check "locks" tree
        if self
            .store
            .get_raw("locks", miner_address.as_bytes())
            .unwrap_or(None)
            .is_some()
        {
            // Miner is banned.
            return None;
        }

        if self.pending_txs.is_empty() && miner_address != "GENESIS" {
            return None;
        }

        let last_block = self.get_last_block();
        let prev_hash = last_block
            .as_ref()
            .map(|b| b.hash.clone())
            .unwrap_or_else(|| "0".repeat(64));
        let next_index = last_block.as_ref().map(|b| b.index + 1).unwrap_or(0);

        // ... (rest of method)
        let mut balances = self.get_all_balances();
        let mut tx_ids = Vec::new();
        for tx in &self.pending_txs {
            let source_balance = balances.get(&tx.source).cloned().unwrap_or(0);
            if tx.source != "GENESIS" && source_balance < tx.amount + tx.max_fee {
                continue;
            }
            if tx.source != "GENESIS" {
                balances.insert(tx.source.clone(), source_balance - (tx.amount + tx.max_fee));
            }
            let target_balance = balances.get(&tx.target).cloned().unwrap_or(0);
            balances.insert(tx.target.clone(), target_balance + tx.amount);
            tx_ids.push(tx.tx_id.clone());
        }

        let mut batch = crate::storage::SovereignBatch::new();

        for (addr, amount) in &balances {
            let data = borsh::to_vec(amount).unwrap_or_default();
            batch.insert("balances", addr.as_bytes(), data);
        }

        let mut hasher = Sha3_256::new();
        hasher.update(prev_hash.as_bytes());
        hasher.update(miner_address.as_bytes());
        hasher.update(next_index.to_be_bytes());
        let block_hash = format!("{:x}", hasher.finalize());

        let block = Block {
            index: next_index,
            timestamp: 1738243200.0,
            tx_ids,
            prev_hash,
            hash: block_hash.clone(),
            miner: miner_address.to_string(),
            zk_proof: None,
            state_root: Some(self.get_state_root()),
            base_fee_per_gas: 10,
        };

        let block_data = borsh::to_vec(&block).unwrap_or_default();
        let hash_data = borsh::to_vec(&block_hash).unwrap_or_default();
        batch.insert("blocks", block_hash.as_bytes(), block_data);
        batch.insert("meta", b"last_block_hash", hash_data);

        // Execute Atomic Batch
        let _ = self.store.apply_batch(batch);
        self.pending_txs.clear();

        Some(block_hash)
    }

    #[must_use]
    pub fn get_last_block(&self) -> Option<Block> {
        let hash: String = self.store.get("meta", b"last_block_hash").ok()??;
        self.store.get::<Block>("blocks", hash.as_bytes()).ok()?
    }

    #[must_use]
    pub fn get_block(&self, hash: &str) -> Option<Block> {
        self.store.get::<Block>("blocks", hash.as_bytes()).ok()?
    }

    pub fn sync_state(
        &mut self,
        balances: HashMap<String, u64>,
        blocks: Vec<Block>,
    ) -> Result<(), String> {
        let mut batch = crate::storage::SovereignBatch::new();

        // 1. Overwrite balances
        for (addr, amount) in balances {
            let data = borsh::to_vec(&amount).map_err(|e| e.to_string())?;
            batch.insert("balances", addr.as_bytes(), data);
        }

        // 2. Overwrite blocks
        let mut last_hash = String::new();
        for block in blocks {
            let block_hash = block.hash.clone();
            let data = borsh::to_vec(&block).map_err(|e| e.to_string())?;
            batch.insert("blocks", block_hash.as_bytes(), data);
            last_hash = block_hash;
        }

        // 3. Update tail marker
        if !last_hash.is_empty() {
            let hash_data = borsh::to_vec(&last_hash).map_err(|e| e.to_string())?;
            batch.insert("meta", b"last_block_hash", hash_data);
        }

        self.store.apply_batch(batch).map_err(|e| e.to_string())?;
        Ok(())
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl RustReplicatedLedger {
    #[new]
    fn new_py(path: &str) -> pyo3::PyResult<Self> {
        // FFI Input Validation
        crate::ffi_limits::validate_string(path, "ledger_path")
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        Self::new(path).map_err(pyo3::exceptions::PyValueError::new_err)
    }

    /// Submit a transaction to the ledger.
    ///
    /// Validates input sizes to prevent DoS.
    #[pyo3(name = "submit_transaction")]
    #[allow(clippy::too_many_arguments)]
    fn submit_transaction_py(
        &mut self,
        tx_id: String,
        source: String,
        target: String,
        amount: u64,
        signature: String,
        timestamp: f64,
        max_fee: u64,
        priority_fee: u64,
    ) -> pyo3::PyResult<()> {
        // FFI Input Validation
        crate::ffi_limits::validate_string(&tx_id, "tx_id")
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        crate::ffi_limits::validate_string(&source, "source")
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        crate::ffi_limits::validate_string(&target, "target")
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        crate::ffi_limits::validate_hex(&signature, "signature")
            .map_err(pyo3::exceptions::PyValueError::new_err)?;

        let tx = Transaction {
            tx_id,
            source,
            target,
            amount,
            signature,
            timestamp,
            max_fee,
            priority_fee,
        };
        // Call Rust method
        RustReplicatedLedger::submit_transaction(self, tx);
        Ok(())
    }

    #[pyo3(name = "get_balance")]
    fn get_balance_py(&self, address: &str) -> u64 {
        RustReplicatedLedger::get_balance(self, address)
    }

    #[pyo3(name = "is_locked")]
    fn is_locked_py(&self, address: &str) -> bool {
        if let Ok(Some(lock)) = self.store.get_raw("locks", address.as_bytes()) {
            lock == b"LOCKED"
        } else {
            false
        }
    }

    #[pyo3(name = "get_all_balances")]
    fn get_all_balances_py(&self) -> std::collections::HashMap<String, u64> {
        let res = RustReplicatedLedger::get_all_balances(self);
        res.into_iter().collect()
    }

    #[pyo3(name = "get_state_root")]
    fn get_state_root_py(&self) -> String {
        RustReplicatedLedger::get_state_root(self)
    }

    #[pyo3(name = "mine_block")]
    fn mine_block_py(&mut self, miner_address: &str) -> Option<String> {
        RustReplicatedLedger::mine_block(self, miner_address)
    }

    #[pyo3(name = "get_last_block")]
    fn get_last_block_py(&self) -> Option<Block> {
        RustReplicatedLedger::get_last_block(self)
    }

    #[pyo3(name = "get_block")]
    fn get_block_py(&self, hash: &str) -> Option<Block> {
        RustReplicatedLedger::get_block(self, hash)
    }

    #[pyo3(name = "sync_state")]
    fn sync_state_py(
        &mut self,
        balances: HashMap<String, u64>,
        blocks: Vec<Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let mut rust_blocks = Vec::new();
        for b_dict in blocks {
            let block = Block {
                index: b_dict
                    .get_item("index")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("index missing"))?
                    .extract()?,
                timestamp: b_dict
                    .get_item("timestamp")?
                    .ok_or_else(|| {
                        PyErr::new::<pyo3::exceptions::PyKeyError, _>("timestamp missing")
                    })?
                    .extract()?,
                tx_ids: b_dict
                    .get_item("tx_ids")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("tx_ids missing"))?
                    .extract::<String>()?
                    .trim_matches(|c| c == '[' || c == ']')
                    .split(',')
                    .map(|s| s.trim_matches(|c| c == '"' || c == ' ').to_string())
                    .filter(|s| !s.is_empty())
                    .collect(),
                prev_hash: b_dict
                    .get_item("prev_hash")?
                    .ok_or_else(|| {
                        PyErr::new::<pyo3::exceptions::PyKeyError, _>("prev_hash missing")
                    })?
                    .extract()?,
                hash: b_dict
                    .get_item("hash")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("hash missing"))?
                    .extract()?,
                miner: b_dict
                    .get_item("miner")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("miner missing"))?
                    .extract()?,
                zk_proof: b_dict.get_item("zk_proof")?.and_then(|i| i.extract().ok()),
                state_root: b_dict
                    .get_item("state_root")?
                    .and_then(|i| i.extract().ok()),
                base_fee_per_gas: b_dict
                    .get_item("base_fee_per_gas")?
                    .and_then(|i| i.extract().ok())
                    .unwrap_or(10),
            };
            rust_blocks.push(block);
        }

        RustReplicatedLedger::sync_state(self, balances, rust_blocks)
            .map_err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>)?;
        Ok(())
    }
}

#[cfg(feature = "python")]
use pyo3::types::PyDict;

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_ledger() -> RustReplicatedLedger {
        let tmp_dir = std::env::temp_dir().join(format!("test_ledger_{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&tmp_dir).unwrap();
        RustReplicatedLedger::new(tmp_dir.join("ledger.redb").to_str().unwrap()).unwrap()
    }

    fn create_tx(source: &str, target: &str, amount: u64) -> Transaction {
        Transaction::new(
            String::new(), // tx_id will be set by ledger
            source.to_string(),
            target.to_string(),
            amount,
            "signature".to_string(),
            1738243200.0,
            10,
            1,
        )
    }

    #[test]
    fn test_transaction_creation() {
        let tx = Transaction::new(
            "tx123".to_string(),
            "alice".to_string(),
            "bob".to_string(),
            1000,
            "sig_abc".to_string(),
            1234567890.0,
            100,
            10,
        );

        assert_eq!(tx.tx_id, "tx123");
        assert_eq!(tx.source, "alice");
        assert_eq!(tx.target, "bob");
        assert_eq!(tx.amount, 1000);
        assert_eq!(tx.max_fee, 100);
        assert_eq!(tx.priority_fee, 10);
    }

    #[test]
    fn test_ledger_initial_state() {
        let ledger = create_test_ledger();

        assert_eq!(ledger.get_balance("any_address"), 0);
        assert!(ledger.get_last_block().is_none());
        assert!(ledger.get_all_balances().is_empty());
    }

    #[test]
    fn test_ledger_genesis_block() {
        let mut ledger = create_test_ledger();

        // Genesis transaction
        let genesis_tx = create_tx("GENESIS", "alice", 1_000_000);
        ledger.submit_transaction(genesis_tx);

        // Mine genesis block
        let hash = ledger.mine_block("GENESIS");
        assert!(hash.is_some());

        // Check balance
        assert_eq!(ledger.get_balance("alice"), 1_000_000);
    }

    #[test]
    fn test_ledger_normal_transaction() {
        let mut ledger = create_test_ledger();

        // Setup: Genesis gives alice coins
        ledger.submit_transaction(create_tx("GENESIS", "alice", 10_000));
        ledger.mine_block("GENESIS");

        // Alice sends to bob (amount + max_fee must be <= balance)
        let tx = Transaction::new(
            String::new(),
            "alice".to_string(),
            "bob".to_string(),
            1000,
            "sig".to_string(),
            1234567890.0,
            10, // max_fee
            1,
        );
        ledger.submit_transaction(tx);
        ledger.mine_block("miner1");

        // alice: 10000 - 1000 - 10 = 8990
        // bob: 1000
        assert_eq!(ledger.get_balance("alice"), 8990);
        assert_eq!(ledger.get_balance("bob"), 1000);
    }

    #[test]
    fn test_ledger_insufficient_balance() {
        let mut ledger = create_test_ledger();

        // Setup: alice has 100
        ledger.submit_transaction(create_tx("GENESIS", "alice", 100));
        ledger.mine_block("GENESIS");

        // Try to send more than balance
        let tx = Transaction::new(
            String::new(),
            "alice".to_string(),
            "bob".to_string(),
            200, // More than alice has
            "sig".to_string(),
            1234567890.0,
            10,
            1,
        );
        ledger.submit_transaction(tx);
        ledger.mine_block("miner1");

        // Transaction should be skipped
        assert_eq!(ledger.get_balance("alice"), 100);
        assert_eq!(ledger.get_balance("bob"), 0);
    }

    #[test]
    fn test_ledger_state_root() {
        let mut ledger = create_test_ledger();

        ledger.submit_transaction(create_tx("GENESIS", "alice", 1000));
        ledger.submit_transaction(create_tx("GENESIS", "bob", 2000));
        ledger.mine_block("GENESIS");

        let root1 = ledger.get_state_root();
        assert!(!root1.is_empty());
        assert_eq!(root1.len(), 64); // SHA3-256 hex

        // Same state = same root
        let root2 = ledger.get_state_root();
        assert_eq!(root1, root2);
    }

    #[test]
    fn test_ledger_block_chain() {
        let mut ledger = create_test_ledger();

        // Genesis block
        ledger.submit_transaction(create_tx("GENESIS", "alice", 1000));
        let hash1 = ledger.mine_block("GENESIS").unwrap();

        // Second block
        let tx = Transaction::new(
            String::new(),
            "alice".to_string(),
            "bob".to_string(),
            100,
            "sig".to_string(),
            1234567890.0,
            10,
            1,
        );
        ledger.submit_transaction(tx);
        let hash2 = ledger.mine_block("miner1").unwrap();

        // Verify chain
        let block1 = ledger.get_block(&hash1).unwrap();
        let block2 = ledger.get_block(&hash2).unwrap();

        assert_eq!(block1.index, 0);
        assert_eq!(block2.index, 1);
        assert_eq!(block2.prev_hash, block1.hash);
    }

    #[test]
    fn test_slashing_state_lock() {
        let mut ledger = create_test_ledger();

        // Genesis setup
        ledger.submit_transaction(create_tx("GENESIS", "malicious", 10_000_000));
        ledger.mine_block("GENESIS");

        // Transaction with very high amount triggers severity > 0.95 -> StateLock
        let evil_tx = Transaction::new(
            String::new(),
            "malicious".to_string(),
            "target".to_string(),
            2_000_000, // > 1_000_000 triggers severity 0.99
            "sig".to_string(),
            1234567890.0,
            10,
            1,
        );
        ledger.submit_transaction(evil_tx);

        // Actor should be locked - subsequent transactions rejected
        let tx2 = Transaction::new(
            String::new(),
            "malicious".to_string(),
            "target".to_string(),
            100,
            "sig".to_string(),
            1234567890.0,
            10,
            1,
        );
        ledger.submit_transaction(tx2);
        ledger.mine_block("miner");

        // malicious actor is locked, target gets nothing
        assert_eq!(ledger.get_balance("target"), 0);
    }

    #[test]
    fn test_banned_miner_cannot_mine() {
        let mut ledger = create_test_ledger();

        // Manually insert a lock for "banned_actor"
        ledger
            .store
            .insert_raw("locks", b"banned_actor", b"LOCKED".to_vec())
            .unwrap();

        // Add a pending transaction
        ledger.submit_transaction(create_tx("GENESIS", "alice", 1000));

        // banned_actor tries to mine - should fail
        let banned_result = ledger.mine_block("banned_actor");
        assert!(
            banned_result.is_none(),
            "Banned miner should not be able to mine"
        );

        // good_miner can mine
        let good_result = ledger.mine_block("good_miner");
        assert!(good_result.is_some(), "Good miner should be able to mine");
    }

    #[test]
    fn test_sync_state() {
        let mut ledger = create_test_ledger();

        // Create initial state
        let mut balances = HashMap::new();
        balances.insert("alice".to_string(), 5000);
        balances.insert("bob".to_string(), 3000);

        // Create a block
        let block = Block {
            index: 0,
            timestamp: 1234567890.0,
            tx_ids: vec!["tx1".to_string()],
            prev_hash: "0".repeat(64),
            hash: "a".repeat(64),
            miner: "GENESIS".to_string(),
            zk_proof: None,
            state_root: Some("state_root_hash".to_string()),
            base_fee_per_gas: 1,
        };

        // Sync state
        let result = ledger.sync_state(balances, vec![block.clone()]);
        assert!(result.is_ok());

        // Verify synced state
        assert_eq!(ledger.get_balance("alice"), 5000);
        assert_eq!(ledger.get_balance("bob"), 3000);

        // Verify block was synced
        let synced_block = ledger.get_block(&block.hash);
        assert!(synced_block.is_some());
        assert_eq!(synced_block.unwrap().index, 0);
    }

    #[test]
    fn test_mine_empty_block() {
        let mut ledger = create_test_ledger();

        // Try to mine with no pending transactions
        let result = ledger.mine_block("miner");
        assert!(result.is_none(), "Should not mine empty block");
    }

    #[test]
    fn test_get_all_balances_multiple() {
        let mut ledger = create_test_ledger();

        // Setup multiple addresses
        ledger.submit_transaction(create_tx("GENESIS", "alice", 1000));
        ledger.submit_transaction(create_tx("GENESIS", "bob", 2000));
        ledger.submit_transaction(create_tx("GENESIS", "charlie", 3000));
        ledger.mine_block("GENESIS");

        let balances = ledger.get_all_balances();
        assert_eq!(balances.len(), 3);
        assert_eq!(balances.get("alice"), Some(&1000));
        assert_eq!(balances.get("bob"), Some(&2000));
        assert_eq!(balances.get("charlie"), Some(&3000));
    }

    #[test]
    fn test_transaction_serialization() {
        let tx = Transaction::new(
            "tx_ser_test".to_string(),
            "source".to_string(),
            "target".to_string(),
            500,
            "sig_test".to_string(),
            9999999.0,
            50,
            5,
        );

        // Serialize
        let bytes = borsh::to_vec(&tx).unwrap();
        assert!(!bytes.is_empty());

        // Deserialize
        let tx2: Transaction = borsh::from_slice(&bytes).unwrap();
        assert_eq!(tx2.tx_id, tx.tx_id);
        assert_eq!(tx2.source, tx.source);
        assert_eq!(tx2.amount, tx.amount);
    }

    #[test]
    fn test_slashing_economic_burn() {
        let mut ledger = create_test_ledger();

        // Setup
        ledger.submit_transaction(create_tx("GENESIS", "medium_actor", 500_000));
        ledger.mine_block("GENESIS");

        // Medium severity transaction (between 0.8 and 0.95) -> EconomicBurn
        let tx = Transaction::new(
            String::new(),
            "medium_actor".to_string(),
            "target".to_string(),
            800_001, // Amount > 500,000 -> severity ~0.85 -> EconomicBurn
            "sig".to_string(),
            1234567890.0,
            10,
            1,
        );
        ledger.submit_transaction(tx);
        ledger.mine_block("miner");

        // EconomicBurn should still allow the transaction but burn some amount
        // The exact behavior depends on slashing implementation
        assert!(ledger.get_balance("medium_actor") < 500_000);
    }

    #[test]
    fn test_get_nonexistent_block() {
        let ledger = create_test_ledger();

        // Try to get a block that doesn't exist
        let result = ledger.get_block("nonexistent_hash");
        assert!(result.is_none());
    }

    #[test]
    fn test_multiple_blocks_chain_integrity() {
        let mut ledger = create_test_ledger();

        // Genesis
        ledger.submit_transaction(create_tx("GENESIS", "alice", 100_000));
        let h1 = ledger.mine_block("GENESIS").unwrap();

        // Block 2
        ledger.submit_transaction(create_tx("alice", "bob", 1000));
        let h2 = ledger.mine_block("miner1").unwrap();

        // Block 3
        ledger.submit_transaction(create_tx("bob", "charlie", 500));
        let h3 = ledger.mine_block("miner2").unwrap();

        // Verify chain
        let b1 = ledger.get_block(&h1).unwrap();
        let b2 = ledger.get_block(&h2).unwrap();
        let b3 = ledger.get_block(&h3).unwrap();

        assert_eq!(b1.index, 0);
        assert_eq!(b2.index, 1);
        assert_eq!(b3.index, 2);
        assert_eq!(b2.prev_hash, b1.hash);
        assert_eq!(b3.prev_hash, b2.hash);

        // Verify last block
        let last = ledger.get_last_block().unwrap();
        assert_eq!(last.hash, b3.hash);
    }

    #[test]
    fn test_fee_deduction() {
        let mut ledger = create_test_ledger();

        // Setup
        ledger.submit_transaction(create_tx("GENESIS", "alice", 1000));
        ledger.mine_block("GENESIS");

        // Transaction with explicit fee
        let tx = Transaction::new(
            String::new(),
            "alice".to_string(),
            "bob".to_string(),
            100,
            "sig".to_string(),
            1234567890.0,
            50, // max_fee
            10, // priority_fee
        );
        ledger.submit_transaction(tx);
        ledger.mine_block("miner");

        // alice: 1000 - 100 - 50 = 850
        // bob: 100
        assert_eq!(ledger.get_balance("alice"), 850);
        assert_eq!(ledger.get_balance("bob"), 100);
    }
}
