//! rust_core/src/evolution/distillery.rs
//! Neural Weight Optimization & Distillation Engine.
#![allow(dead_code)]
#![allow(unused_imports)]

use crate::zk::ZKProof;
use candle_core::Device;
use curve25519_dalek::scalar::Scalar;
#[cfg(feature = "python")]
use pyo3::prelude::*;
use rand::Rng;

#[cfg_attr(feature = "python", pyclass)]
pub struct WeightDistillery {
    _device: Device,
}

#[cfg(feature = "python")]
#[pymethods]
impl WeightDistillery {
    #[new]
    pub fn new() -> Self {
        let device = if cfg!(target_os = "macos") {
            Device::new_metal(0).unwrap_or(Device::Cpu)
        } else {
            Device::Cpu
        };
        WeightDistillery { _device: device }
    }

    /// Mutates a set of weights (Tensor) by adding random Gaussian noise.
    /// This is the "Mutation" step of the Genetic Algorithm for weights.
    pub fn jitter_weights(&self, weights: Vec<f32>, sigma: f32) -> Vec<f32> {
        let mut rng = rand::thread_rng();
        weights
            .into_iter()
            .map(|w| w + (rng.gen::<f32>() * 2.0 - 1.0) * sigma)
            .collect()
    }

    /// Prunes weights below a certain threshold.
    /// Hard-zeroes weights that don't contribute significantly.
    pub fn prune_weights(&self, weights: Vec<f32>, threshold: f32) -> Vec<f32> {
        weights
            .into_iter()
            .map(|w| if w.abs() < threshold { 0.0 } else { w })
            .collect()
    }

    /// [DEPRECATED] Generates a proof for a weight mutation.
    /// Phase 15 Hardening: Methods disabled to clear deprecation warnings.
    /// Migrate to crate::zk::GovernanceCircuit for production proofs.
    #[cfg(feature = "python")]
    pub fn generate_mutation_proof(
        &self,
        _py: Python<'_>,
        _value: u64,
        _blinding_hex: &str,
    ) -> PyResult<ZKProof> {
        Err(pyo3::exceptions::PyNotImplementedError::new_err(
            "Sigma Protocol (proof_zk) is deprecated. Use crate::zk.",
        ))
    }

    /// [DEPRECATED] Verifies a mutation proof against a commitment.
    #[cfg(feature = "python")]
    pub fn verify_mutation_proof(
        &self,
        _py: Python<'_>,
        _proof_str: &str,
        _commitment_hex: &str,
    ) -> PyResult<bool> {
        Err(pyo3::exceptions::PyNotImplementedError::new_err(
            "Sigma Protocol (proof_zk) is deprecated. Use crate::zk.",
        ))
    }
}
