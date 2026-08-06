//! rust_core/src/hardware/entropy.rs
//! Shim for HardwareEntropy (Legacy compatibility)

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg_attr(feature = "python", pyclass)]
pub struct HardwareEntropy;

#[cfg(feature = "python")]
#[pymethods]
impl HardwareEntropy {
    #[new]
    pub fn new() -> Self {
        HardwareEntropy
    }

    pub fn get_bytes(&self, num: usize) -> String {
        use rand::RngCore;
        let mut b = vec![0u8; num];
        rand::thread_rng().fill_bytes(&mut b);
        hex::encode(b)
    }
}
