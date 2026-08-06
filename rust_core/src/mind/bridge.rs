//! rust_core/src/mind/bridge.rs
//! PyO3 Bridge for Synthetic Mind.
#![allow(dead_code)]

use crate::mind::engine::InferenceEngine;
#[cfg(feature = "python")]
use pyo3::prelude::*;
use std::sync::{Arc, Mutex};

#[cfg_attr(feature = "python", pyclass)]
pub struct RustMind {
    engine: Arc<Mutex<InferenceEngine>>,
}

#[cfg(feature = "python")]
#[pymethods]
impl RustMind {
    #[new]
    pub fn new() -> PyResult<Self> {
        let engine = InferenceEngine::new().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Mind Init Error: {}", e))
        })?;

        Ok(RustMind {
            engine: Arc::new(Mutex::new(engine)),
        })
    }

    /// Loads a quantized model file.
    pub fn load(&mut self, path: String) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.lock() {
            engine.load_model(path).map_err(|e| {
                pyo3::exceptions::PyIOError::new_err(format!("Model Load Error: {}", e))
            })?;
        }
        Ok(())
    }

    /// Primary inference entry point.
    pub fn think(&self, prompt: String) -> PyResult<String> {
        if let Ok(mut engine) = self.engine.lock() {
            engine.think(&prompt).map(|(s, _)| s).map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!("Inference Error: {}", e))
            })
        } else {
            Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Mind engine locked",
            ))
        }
    }
}
