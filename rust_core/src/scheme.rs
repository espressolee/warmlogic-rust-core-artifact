#![allow(dead_code)]
#[cfg(not(feature = "std"))]
use alloc::collections::BTreeMap as Map;
#[cfg(feature = "std")]
use std::collections::HashMap as Map;

use crate::ledger::RustReplicatedLedger;

#[cfg(not(feature = "std"))]
use alloc::boxed::Box;
#[cfg(not(feature = "std"))]
use alloc::string::{String, ToString};

#[cfg(feature = "python")]
use pyo3::prelude::*;

pub trait Scheme {
    #[cfg(feature = "python")]
    fn open(&self, url: &str) -> PyResult<String>;
    #[cfg(not(feature = "python"))]
    fn open(&self, url: &str) -> Result<alloc::string::String, ()>;

    #[cfg(feature = "python")]
    fn read(&self, handle: &str) -> PyResult<Vec<u8>>;
    #[cfg(not(feature = "python"))]
    fn read(&self, handle: &str) -> Result<alloc::vec::Vec<u8>, ()>;
}

#[cfg_attr(feature = "python", pyclass)]
pub struct KernelScheme {
    schemes: Map<String, Box<dyn Scheme + Send + Sync>>,
}

impl KernelScheme {
    pub fn new() -> Self {
        KernelScheme {
            schemes: Map::new(),
        }
    }

    pub fn register<S: Scheme + Send + Sync + 'static>(&mut self, name: &str, scheme: S) {
        self.schemes.insert(name.to_string(), Box::new(scheme));
    }
}

#[cfg(not(feature = "std"))]
use alloc::sync::Arc;
#[cfg(not(feature = "std"))]
use spin::Mutex;
#[cfg(feature = "std")]
use std::sync::{Arc, Mutex};

pub struct LedgerScheme {
    pub ledger: Arc<Mutex<RustReplicatedLedger>>,
}

impl Scheme for LedgerScheme {
    #[cfg(feature = "python")]
    fn open(&self, url: &str) -> PyResult<String> {
        // Example: ledger://balance/ALICE
        if let Some(addr) = url.strip_prefix("ledger://balance/") {
            let ledger = self.ledger.lock().map_err(|_| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Ledger Lock Poisoned")
            })?;
            let bal = ledger.get_balance(addr);
            return Ok(bal.to_string());
        }
        Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Invalid ledger URL",
        ))
    }

    #[cfg(not(feature = "python"))]
    fn open(&self, url: &str) -> Result<alloc::string::String, ()> {
        if let Some(addr) = url.strip_prefix("ledger://balance/") {
            let ledger = self.ledger.lock().map_err(|_| ())?;
            let bal = ledger.get_balance(addr);
            return Ok(bal.to_string());
        }
        Err(())
    }

    #[cfg(feature = "python")]
    fn read(&self, _handle: &str) -> PyResult<Vec<u8>> {
        Ok(vec![])
    }

    #[cfg(not(feature = "python"))]
    fn read(&self, _handle: &str) -> Result<alloc::vec::Vec<u8>, ()> {
        Ok(alloc::vec![])
    }
}
