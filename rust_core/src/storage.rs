#![allow(dead_code)]
#![allow(clippy::type_complexity)]
use borsh::{BorshDeserialize, BorshSerialize};
#[cfg(feature = "std")]
use std::path::Path;

#[cfg(feature = "std")]
use std::{
    collections::BTreeMap,
    string::String,
    sync::{Arc, Mutex, MutexGuard, PoisonError},
    vec::Vec,
};

#[cfg(feature = "python")]
use pyo3::prelude::*;

/// [H5 Security Fix] Helper to recover from poisoned locks.
#[cfg(feature = "std")]
fn recover_lock<'a, T>(
    result: Result<MutexGuard<'a, T>, PoisonError<MutexGuard<'a, T>>>,
) -> MutexGuard<'a, T> {
    match result {
        Ok(guard) => guard,
        Err(poisoned) => poisoned.into_inner(),
    }
}

#[cfg(not(feature = "std"))]
fn recover_lock<T>(guard: T) -> T {
    guard
}

#[cfg(not(feature = "std"))]
use alloc::{
    collections::BTreeMap,
    string::{String, ToString},
    sync::Arc,
    vec::Vec,
};
#[cfg(not(feature = "std"))]
use spin::Mutex;

/// Unified Storage Trait for Sovereign OS.
/// Support for std (redb) and no_std (Memory/Flash).
/// Migrated from sled to redb for security (RUSTSEC-2025-0057, RUSTSEC-2024-0384).
pub trait SovereignStorage: Send + Sync {
    fn insert_raw(
        &self,
        tree: &str,
        key: &[u8],
        value: Vec<u8>,
    ) -> core::result::Result<(), String>;
    fn get_raw(&self, tree: &str, key: &[u8]) -> core::result::Result<Option<Vec<u8>>, String>;
    fn get_all_raw(&self, tree: &str) -> core::result::Result<Vec<(Vec<u8>, Vec<u8>)>, String>;
    fn apply_batch(&self, batch: SovereignBatch) -> core::result::Result<(), String>;
    fn flush(&self) -> core::result::Result<(), String>;
}

#[derive(Default)]
pub struct SovereignBatch {
    pub ops: Vec<BatchOp>,
}

pub enum BatchOp {
    Insert {
        tree: String,
        key: Vec<u8>,
        value: Vec<u8>,
    },
    Remove {
        tree: String,
        key: Vec<u8>,
    },
}

impl SovereignBatch {
    #[must_use]
    pub fn new() -> Self {
        SovereignBatch { ops: Vec::new() }
    }

    pub fn insert(&mut self, tree: &str, key: &[u8], value: Vec<u8>) {
        self.ops.push(BatchOp::Insert {
            tree: tree.to_string(),
            key: key.to_vec(),
            value,
        });
    }
}

#[cfg(feature = "persistence")]
use redb::{Database, ReadableTable, TableDefinition};

#[cfg(feature = "persistence")]
const DEFAULT_TABLE: TableDefinition<&[u8], &[u8]> = TableDefinition::new("default");

/// RedbStore - Persistent storage backed by redb (replaces sled).
/// redb provides better safety guarantees and is actively maintained.
#[cfg(feature = "persistence")]
pub struct RedbStore {
    db: Database,
}

#[cfg(feature = "persistence")]
impl RedbStore {
    pub fn open<P: AsRef<Path>>(path: P) -> core::result::Result<Self, String> {
        let db = Database::create(path).map_err(|e| e.to_string())?;
        Ok(RedbStore { db })
    }

    /// Get or create a table definition for a tree name.
    /// Note: redb requires compile-time table definitions, so we use a single table
    /// with prefixed keys to emulate multiple trees.
    fn prefixed_key(tree: &str, key: &[u8]) -> Vec<u8> {
        let mut prefixed = tree.as_bytes().to_vec();
        prefixed.push(0); // null separator
        prefixed.extend_from_slice(key);
        prefixed
    }

    fn unprefix_key(tree: &str, prefixed: &[u8]) -> Option<Vec<u8>> {
        let prefix = tree.as_bytes();
        if prefixed.len() > prefix.len() + 1
            && &prefixed[..prefix.len()] == prefix
            && prefixed[prefix.len()] == 0
        {
            Some(prefixed[prefix.len() + 1..].to_vec())
        } else {
            None
        }
    }
}

#[cfg(feature = "persistence")]
impl SovereignStorage for RedbStore {
    fn insert_raw(
        &self,
        tree: &str,
        key: &[u8],
        value: Vec<u8>,
    ) -> core::result::Result<(), String> {
        let write_txn = self.db.begin_write().map_err(|e| e.to_string())?;
        {
            let mut table = write_txn
                .open_table(DEFAULT_TABLE)
                .map_err(|e| e.to_string())?;
            let prefixed = Self::prefixed_key(tree, key);
            table
                .insert(prefixed.as_slice(), value.as_slice())
                .map_err(|e| e.to_string())?;
        }
        write_txn.commit().map_err(|e| e.to_string())?;
        Ok(())
    }

    fn get_raw(&self, tree: &str, key: &[u8]) -> core::result::Result<Option<Vec<u8>>, String> {
        let read_txn = self.db.begin_read().map_err(|e| e.to_string())?;
        let table_res = read_txn.open_table(DEFAULT_TABLE);
        if let Err(_) = table_res {
            return Ok(None); // Table doesn't exist yet, so no value
        }
        let table = table_res.map_err(|e| e.to_string())?;
        let prefixed = Self::prefixed_key(tree, key);
        match table.get(prefixed.as_slice()) {
            Ok(Some(value)) => Ok(Some(value.value().to_vec())),
            Ok(None) => Ok(None),
            Err(e) => Err(e.to_string()),
        }
    }

    fn get_all_raw(&self, tree: &str) -> core::result::Result<Vec<(Vec<u8>, Vec<u8>)>, String> {
        let read_txn = self.db.begin_read().map_err(|e| e.to_string())?;
        let table_res = read_txn.open_table(DEFAULT_TABLE);
        if let Err(_) = table_res {
            return Ok(Vec::new()); // Table doesn't exist yet
        }
        let table = table_res.map_err(|e| e.to_string())?;

        let mut results: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();

        for item in table.iter().map_err(|e| e.to_string())? {
            let (k, v) = item.map_err(|e| e.to_string())?;
            let key_bytes = k.value();
            if let Some(unprefixed) = Self::unprefix_key(tree, key_bytes) {
                results.push((unprefixed, v.value().to_vec()));
            }
        }
        Ok(results)
    }

    fn apply_batch(&self, batch: SovereignBatch) -> core::result::Result<(), String> {
        let write_txn = self.db.begin_write().map_err(|e| e.to_string())?;
        {
            let mut table = write_txn
                .open_table(DEFAULT_TABLE)
                .map_err(|e| e.to_string())?;
            for op in batch.ops {
                match op {
                    BatchOp::Insert { tree, key, value } => {
                        let prefixed = Self::prefixed_key(&tree, &key);
                        table
                            .insert(prefixed.as_slice(), value.as_slice())
                            .map_err(|e| e.to_string())?;
                    }
                    BatchOp::Remove { tree, key } => {
                        let prefixed = Self::prefixed_key(&tree, &key);
                        table
                            .remove(prefixed.as_slice())
                            .map_err(|e| e.to_string())?;
                    }
                }
            }
        }
        write_txn.commit().map_err(|e| e.to_string())?;
        Ok(())
    }

    fn flush(&self) -> core::result::Result<(), String> {
        // redb automatically flushes on commit - no explicit flush needed
        // Note: compact() requires &mut self, so we skip it here
        Ok(())
    }
}

pub struct MemoryStore {
    // tree -> (key -> value)
    data: Mutex<BTreeMap<String, BTreeMap<Vec<u8>, Vec<u8>>>>,
}

impl MemoryStore {
    #[must_use]
    pub fn new() -> Self {
        MemoryStore {
            data: Mutex::new(BTreeMap::new()),
        }
    }

    #[cfg(feature = "std")]
    fn lock(&self) -> std::sync::MutexGuard<'_, BTreeMap<String, BTreeMap<Vec<u8>, Vec<u8>>>> {
        recover_lock(self.data.lock())
    }

    #[cfg(not(feature = "std"))]
    fn lock(&self) -> spin::MutexGuard<'_, BTreeMap<String, BTreeMap<Vec<u8>, Vec<u8>>>> {
        self.data.lock()
    }
}

impl Default for MemoryStore {
    fn default() -> Self {
        Self::new()
    }
}

impl SovereignStorage for MemoryStore {
    fn insert_raw(
        &self,
        tree: &str,
        key: &[u8],
        value: Vec<u8>,
    ) -> core::result::Result<(), String> {
        let mut guard = self.lock();
        let tree_map = guard.entry(tree.to_string()).or_default();
        tree_map.insert(key.to_vec(), value);
        Ok(())
    }

    fn get_raw(&self, tree: &str, key: &[u8]) -> core::result::Result<Option<Vec<u8>>, String> {
        let guard = self.lock();
        if let Some(tree_map) = guard.get(tree) {
            let val: Option<Vec<u8>> = tree_map.get(key).cloned();
            Ok(val)
        } else {
            Ok(None)
        }
    }

    fn get_all_raw(&self, tree: &str) -> core::result::Result<Vec<(Vec<u8>, Vec<u8>)>, String> {
        let guard = self.lock();
        if let Some(tree_map) = guard.get(tree) {
            let res: Vec<(Vec<u8>, Vec<u8>)> = tree_map
                .iter()
                .map(|(k, v)| (k.clone(), v.clone()))
                .collect();
            Ok(res)
        } else {
            Ok(Vec::new())
        }
    }

    fn apply_batch(&self, batch: SovereignBatch) -> core::result::Result<(), String> {
        let mut guard = self.lock();
        for op in batch.ops {
            match op {
                BatchOp::Insert { tree, key, value } => {
                    let tree_map = guard.entry(tree).or_default();
                    tree_map.insert(key, value);
                }
                BatchOp::Remove { tree, key } => {
                    if let Some(tree_map) = guard.get_mut(&tree) {
                        tree_map.remove(&key);
                    }
                }
            }
        }
        Ok(())
    }

    fn flush(&self) -> core::result::Result<(), String> {
        Ok(())
    }
}

#[cfg(feature = "std")]
use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Key, Nonce,
};

#[cfg(feature = "std")]
pub struct EncryptedStore<S: SovereignStorage> {
    inner: S,
    key: [u8; 32],
}

#[cfg(feature = "std")]
impl<S: SovereignStorage> EncryptedStore<S> {
    pub fn new(inner: S, key: [u8; 32]) -> Self {
        Self { inner, key }
    }

    fn encrypt(&self, data: &[u8]) -> Result<Vec<u8>, String> {
        let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(&self.key));
        let nonce = Nonce::from_slice(b"UNIQUE-NONCE"); // 12 bytes
        let ciphertext = cipher
            .encrypt(nonce, data)
            .map_err(|e| format!("Encryption error: {:?}", e))?;
        Ok(ciphertext)
    }

    fn decrypt(&self, data: &[u8]) -> Result<Vec<u8>, String> {
        let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(&self.key));
        let nonce = Nonce::from_slice(b"UNIQUE-NONCE");
        let plaintext = cipher
            .decrypt(nonce, data)
            .map_err(|e| format!("Decryption error: {:?}", e))?;
        Ok(plaintext)
    }
}

#[cfg(feature = "std")]
impl<S: SovereignStorage> SovereignStorage for EncryptedStore<S> {
    fn insert_raw(
        &self,
        tree: &str,
        key: &[u8],
        value: Vec<u8>,
    ) -> core::result::Result<(), String> {
        let encrypted = self.encrypt(&value)?;
        self.inner.insert_raw(tree, key, encrypted)
    }

    fn get_raw(&self, tree: &str, key: &[u8]) -> core::result::Result<Option<Vec<u8>>, String> {
        match self.inner.get_raw(tree, key)? {
            Some(encrypted) => Ok(Some(self.decrypt(&encrypted)?)),
            None => Ok(None),
        }
    }

    fn get_all_raw(&self, tree: &str) -> core::result::Result<Vec<(Vec<u8>, Vec<u8>)>, String> {
        let raw = self.inner.get_all_raw(tree)?;
        let mut decrypted = Vec::new();
        for (k, v) in raw {
            decrypted.push((k, self.decrypt(&v)?));
        }
        Ok(decrypted)
    }

    fn apply_batch(&self, batch: SovereignBatch) -> core::result::Result<(), String> {
        let mut encrypted_ops = Vec::new();
        for op in batch.ops {
            match op {
                BatchOp::Insert { tree, key, value } => {
                    let encrypted = self.encrypt(&value)?;
                    encrypted_ops.push(BatchOp::Insert {
                        tree,
                        key,
                        value: encrypted,
                    });
                }
                BatchOp::Remove { tree, key } => {
                    encrypted_ops.push(BatchOp::Remove { tree, key });
                }
            }
        }
        self.inner
            .apply_batch(SovereignBatch { ops: encrypted_ops })
    }

    fn flush(&self) -> core::result::Result<(), String> {
        self.inner.flush()
    }
}

#[cfg_attr(feature = "python", pyclass(name = "SovereignStore"))]
pub struct RustSovereignStore {
    inner: Arc<dyn SovereignStorage>,
}

#[cfg(feature = "python")]
#[pymethods]
impl RustSovereignStore {
    #[new]
    #[pyo3(signature = (path, key=None))]
    pub fn py_new(path: String, key: Option<Vec<u8>>) -> PyResult<Self> {
        if let Some(k) = key {
            if k.len() != 32 {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Encryption key must be 32 bytes",
                ));
            }
            let mut key_arr = [0u8; 32];
            key_arr.copy_from_slice(&k);
            Self::open_encrypted(path, key_arr)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
        } else {
            Self::open(path).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
        }
    }

    #[pyo3(name = "put", signature = (key, value, tree="default"))]
    pub fn py_put(
        &self,
        key: Bound<'_, PyAny>,
        value: Bound<'_, PyAny>,
        tree: &str,
    ) -> PyResult<()> {
        let key_bytes = if let Ok(b) = key.cast::<pyo3::types::PyBytes>() {
            b.as_bytes().to_vec()
        } else if let Ok(s) = key.extract::<String>() {
            s.as_bytes().to_vec()
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "key must be bytes or string",
            ));
        };

        let value_bytes = if let Ok(b) = value.cast::<pyo3::types::PyBytes>() {
            b.as_bytes().to_vec()
        } else if let Ok(s) = value.extract::<String>() {
            s.as_bytes().to_vec()
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "value must be bytes or string",
            ));
        };

        self.inner
            .insert_raw(tree, &key_bytes, value_bytes)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    }

    #[pyo3(name = "insert")]
    pub fn py_insert(
        &self,
        tree: &str,
        key: Bound<'_, pyo3::types::PyBytes>,
        value: Bound<'_, pyo3::types::PyBytes>,
    ) -> PyResult<()> {
        self.inner
            .insert_raw(tree, key.as_bytes(), value.as_bytes().to_vec())
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    }

    #[pyo3(name = "get", signature = (key_or_tree, key=None))]
    pub fn py_get<'py>(
        &self,
        py: Python<'py>,
        key_or_tree: Bound<'_, PyAny>,
        key: Option<Bound<'_, PyAny>>,
    ) -> PyResult<Option<Bound<'py, PyAny>>> {
        let (tree, target_key) = if let Some(k) = key {
            // Called as get(tree, key)
            let t = key_or_tree.extract::<String>()?;
            (t, k)
        } else {
            // Called as get(key)
            ("default".to_string(), key_or_tree)
        };

        let key_bytes = if let Ok(b) = target_key.cast::<pyo3::types::PyBytes>() {
            b.as_bytes().to_vec()
        } else if let Ok(s) = target_key.extract::<String>() {
            s.as_bytes().to_vec()
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "key must be bytes or string",
            ));
        };

        match self.inner.get_raw(&tree, &key_bytes) {
            Ok(Some(data)) => {
                // If it looks like valid UTF-8, return as string. Otherwise return as bytes.
                if let Ok(s) = String::from_utf8(data.clone()) {
                    Ok(Some(pyo3::types::PyString::new(py, &s).into_any()))
                } else {
                    Ok(Some(pyo3::types::PyBytes::new(py, &data).into_any()))
                }
            }
            Ok(None) => Ok(None),
            Err(e) => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e)),
        }
    }

    #[pyo3(name = "flush")]
    pub fn py_flush(&self) -> PyResult<()> {
        self.inner
            .flush()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    }
}

impl RustSovereignStore {
    #[cfg(feature = "persistence")]
    pub fn open<P: AsRef<Path>>(path: P) -> core::result::Result<Self, String> {
        let store = RedbStore::open(path)?;
        Ok(RustSovereignStore {
            inner: Arc::new(store),
        })
    }

    #[cfg(feature = "persistence")]
    pub fn open_encrypted<P: AsRef<Path>>(
        path: P,
        key: [u8; 32],
    ) -> core::result::Result<Self, String> {
        let store = RedbStore::open(path)?;
        Ok(RustSovereignStore {
            inner: Arc::new(EncryptedStore::new(store, key)),
        })
    }

    #[cfg(all(feature = "std", not(feature = "persistence")))]
    pub fn open_encrypted<P: AsRef<Path>>(
        _path: P,
        key: [u8; 32],
    ) -> core::result::Result<Self, String> {
        Ok(RustSovereignStore {
            inner: Arc::new(EncryptedStore::new(MemoryStore::new(), key)),
        })
    }

    #[cfg(all(feature = "std", not(feature = "persistence")))]
    pub fn open<P: AsRef<Path>>(_path: P) -> core::result::Result<Self, String> {
        Ok(RustSovereignStore {
            inner: Arc::new(MemoryStore::new()),
        })
    }

    #[cfg(not(feature = "std"))]
    pub fn open(_path: &str) -> core::result::Result<Self, String> {
        Ok(RustSovereignStore {
            inner: Arc::new(MemoryStore::new()),
        })
    }

    pub fn insert<T: BorshSerialize>(
        &self,
        tree: &str,
        key: &[u8],
        value: &T,
    ) -> core::result::Result<(), String> {
        let data = borsh::to_vec(value).map_err(|e| e.to_string())?;
        self.inner.insert_raw(tree, key, data)
    }

    pub fn get<T: BorshDeserialize>(
        &self,
        tree: &str,
        key: &[u8],
    ) -> core::result::Result<Option<T>, String> {
        let opt_data: Option<Vec<u8>> = self.inner.get_raw(tree, key)?;
        if let Some(data) = opt_data {
            let val = borsh::from_slice(&data).map_err(|e| e.to_string())?;
            Ok(Some(val))
        } else {
            Ok(None)
        }
    }

    pub fn get_all<T: BorshDeserialize>(
        &self,
        tree: &str,
    ) -> core::result::Result<Vec<(Vec<u8>, T)>, String> {
        let raw: Vec<(Vec<u8>, Vec<u8>)> = self.inner.get_all_raw(tree)?;
        let mut results = Vec::new();
        for item in raw {
            let (k, v) = item;
            let val = borsh::from_slice(&v).map_err(|e| e.to_string())?;
            results.push((k, val));
        }
        Ok(results)
    }

    pub fn insert_raw(
        &self,
        tree: &str,
        key: &[u8],
        value: Vec<u8>,
    ) -> core::result::Result<(), String> {
        self.inner.insert_raw(tree, key, value)
    }

    pub fn get_raw(&self, tree: &str, key: &[u8]) -> core::result::Result<Option<Vec<u8>>, String> {
        self.inner.get_raw(tree, key)
    }

    pub fn get_all_raw(&self, tree: &str) -> core::result::Result<Vec<(Vec<u8>, Vec<u8>)>, String> {
        self.inner.get_all_raw(tree)
    }

    pub fn apply_batch(&self, batch: SovereignBatch) -> core::result::Result<(), String> {
        self.inner.apply_batch(batch)
    }

    pub fn flush(&self) -> core::result::Result<(), String> {
        self.inner.flush()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_memory_store_basic() {
        let store = MemoryStore::new();
        store
            .insert_raw("tree1", b"key1", b"value1".to_vec())
            .unwrap();
        let res = store.get_raw("tree1", b"key1").unwrap();
        assert_eq!(res, Some(b"value1".to_vec()));

        let all = store.get_all_raw("tree1").unwrap();
        assert_eq!(all.len(), 1);
        assert_eq!(all[0].0, b"key1");
        assert_eq!(all[0].1, b"value1");
    }

    #[test]
    #[cfg(feature = "persistence")]
    fn test_rust_sovereign_store_redb() {
        // Use a temporary directory for redb
        let tmp_dir = std::env::temp_dir().join("test_sovereign_redb");
        if tmp_dir.exists() {
            std::fs::remove_dir_all(&tmp_dir).unwrap();
        }
        std::fs::create_dir_all(&tmp_dir).unwrap();

        let db_path = tmp_dir.join("test.redb");
        let store = RustSovereignStore::open(&db_path).unwrap();
        store
            .insert("test_tree", b"k1", &"hello".to_string())
            .unwrap();
        let res: Option<String> = store.get("test_tree", b"k1").unwrap();
        assert_eq!(res, Some("hello".to_string()));

        std::fs::remove_dir_all(&tmp_dir).unwrap();
    }

    #[test]
    #[cfg(feature = "persistence")]
    fn test_redb_key_prefixing() {
        let prefixed = RedbStore::prefixed_key("mytree", b"mykey");
        assert!(prefixed.starts_with(b"mytree\0"));

        let unprefixed = RedbStore::unprefix_key("mytree", &prefixed);
        assert_eq!(unprefixed, Some(b"mykey".to_vec()));

        // Wrong tree should return None
        let wrong = RedbStore::unprefix_key("othertree", &prefixed);
        assert_eq!(wrong, None);
    }
}
