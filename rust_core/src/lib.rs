#![cfg_attr(not(feature = "std"), no_std)]
#![deny(clippy::unwrap_used)]
#![deny(clippy::expect_used)]
#![warn(clippy::must_use_candidate)]

#[macro_use]
extern crate alloc;
#[cfg(feature = "bare-metal")]
extern crate getrandom;

#[cfg(not(feature = "std"))]
use alloc::{
    format,
    string::{String, ToString},
};
#[cfg(feature = "std")]
use std::string::String;

pub mod boot;
pub mod consensus;
pub mod debug;
pub mod drone;
pub mod economics;
pub mod error;
pub mod ffi_limits;
pub mod hardware;
pub mod kernel;
pub mod merkle;
pub mod physics;
pub mod programs;
pub mod recovery;
pub mod resilience;
pub mod sanctuary;
pub mod security;
pub mod slashing;
pub mod state_grid;
pub mod vector_std;

// Core grid and recovery implementations
pub mod merged_grid;
pub mod merged_recovery;

// Storage module for persistence
#[cfg(feature = "std")]
pub mod storage;

#[cfg(feature = "std")]
pub mod annihilation;
#[cfg(feature = "std")]
pub mod compliance;
#[cfg(feature = "std")]
pub mod evolution;
#[cfg(feature = "std")]
pub mod execution;
#[cfg(feature = "std")]
pub mod federation;
#[cfg(feature = "std")]
pub mod governance;
#[cfg(feature = "std")]
pub mod ledger;
#[cfg(feature = "std")]
pub mod mind;
#[cfg(feature = "std")]
pub mod net;
#[cfg(feature = "std")]
pub mod policy_engine;
#[cfg(feature = "std")]
pub mod verification_formal;
#[cfg(feature = "std")]
pub mod verification_kani;
#[cfg(feature = "std")]
pub mod voting;
// Phase 2.0: Kani + proptest verification harnesses
#[cfg(test)]
mod verification;

#[cfg(feature = "api")]
pub mod api;
#[cfg(feature = "persistence")]
pub mod persistence;
#[cfg(feature = "std")]
pub mod proof_zk; // DEPRECATED Sigma-protocol prover, still consumed from Python
pub mod sdk; // Moral Gateway ABI, consumed by warm_logic.sdk.bridge
#[cfg(feature = "telemetry")]
pub mod telemetry;
#[cfg(feature = "zk")]
pub mod zk;

#[cfg(any(feature = "std", feature = "bare-metal"))]
pub mod crypto;
#[cfg(not(any(feature = "std", feature = "bare-metal")))]
pub mod crypto_stub;
#[cfg(not(any(feature = "std", feature = "bare-metal")))]
pub use crypto_stub as crypto;

#[cfg(feature = "python")]
use core::hint::black_box;
#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use pyo3::{
    exceptions::{PyRuntimeError, PyTypeError},
    types::{PyAny, PyByteArray, PyBytes},
};
#[cfg(all(feature = "python", feature = "std"))]
use rand::{rngs::SmallRng, RngCore, SeedableRng};
#[cfg(feature = "python")]
use sha3::{Digest, Sha3_256};
#[cfg(all(feature = "python", feature = "std"))]
use std::{collections::HashMap, sync::Mutex};

// Re-export pyo3 for submodules to use as `crate::pyo3`
#[cfg(feature = "python")]
pub use pyo3;

// Re-export nalgebra/mavlink so external targets (benches) share the lib's
// instances; a separately-resolved unit makes their types non-identical.
#[cfg(feature = "mavlink")]
pub use mavlink;
#[cfg(feature = "nalgebra")]
pub use nalgebra;

#[cfg(feature = "python")]
use crate::consensus::bft::{BFTEngine, Vote};

#[cfg(all(feature = "python", feature = "std"))]
use crate::net::block_propagator::BlockPropagator;

// Phase 6.1b: Re-export GossipSubscriber for Python bindings
#[cfg(all(feature = "python", feature = "std"))]
pub use crate::net::GossipSubscriber;

// [C2 Security Fix] Using Real Hardware TRNG for CV1800B
#[cfg(feature = "bare-metal")]
pub use crate::hardware::trng::init_trng;

// --- Core Types ---
use borsh::{BorshDeserialize, BorshSerialize};

#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, BorshSerialize, BorshDeserialize)]
pub struct ModeDecision {
    pub mode: String,
    pub reason: String,
}

#[cfg(feature = "python")]
#[pymethods]
impl ModeDecision {
    #[getter]
    fn mode(&self) -> String {
        self.mode.clone()
    }
    #[getter]
    fn reason(&self) -> String {
        self.reason.clone()
    }
}

#[cfg_attr(feature = "python", pyclass)]
pub struct ReflectiveLoop {
    pub alpha: f64,
    pub beta: f64,
}

impl Default for ReflectiveLoop {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl ReflectiveLoop {
    #[new]
    fn py_new() -> Self {
        Self::new()
    }

    /// Governance mode decision from a metrics dict ({"epsilon_c": f64, "tau_ethics": f64}).
    /// Missing keys default to 0.0, matching the permissive dict(ctx.metrics) callers.
    fn compute_mode(&self, state: &Bound<'_, pyo3::types::PyDict>) -> PyResult<ModeDecision> {
        let get = |key: &str| -> PyResult<f64> {
            match state.get_item(key)? {
                Some(v) => v.extract(),
                None => Ok(0.0),
            }
        };
        Ok(self.compute_mode_raw(get("epsilon_c")?, get("tau_ethics")?))
    }
}

impl ReflectiveLoop {
    #[must_use]
    pub fn new() -> Self {
        ReflectiveLoop {
            alpha: 0.5,
            beta: 0.5,
        }
    }

    #[must_use]
    pub fn compute_mode_raw(&self, epsilon_c: f64, tau_ethics: f64) -> ModeDecision {
        let e_stab = self.alpha * epsilon_c + self.beta * (1.0 - tau_ethics);
        if tau_ethics > 0.85 {
            ModeDecision {
                mode: "VETO_LOCK".to_string(),
                reason: "TAU_ETHICS BREAK".to_string(),
            }
        } else if e_stab < 0.3 {
            ModeDecision {
                mode: "CRITICAL_HALT".to_string(),
                reason: "STABILITY FAILURE".to_string(),
            }
        } else {
            ModeDecision {
                mode: "NORMAL".to_string(),
                reason: "STABLE".to_string(),
            }
        }
    }
}

// ============================================================================
// PAPER 09 BRIDGE EVALUATION COMPAT LAYER
// ============================================================================

#[cfg(feature = "python")]
struct BytesVec(Vec<u8>);

#[cfg(feature = "python")]
fn _extract_bytes_like(data: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    if let Ok(pybytes) = data.cast::<PyBytes>() {
        return Ok(pybytes.as_bytes().to_vec());
    }
    if let Ok(bytearray) = data.cast::<PyByteArray>() {
        return Ok(unsafe { bytearray.as_bytes() }.to_vec());
    }
    let builtins = data.py().import("builtins")?;
    if let Ok(memoryview_obj) = builtins.getattr("memoryview")?.call1((data,)) {
        let format: String = memoryview_obj.getattr("format")?.extract()?;
        let itemsize: usize = memoryview_obj.getattr("itemsize")?.extract()?;
        let format_ok = format == "B" || format == "b" || format == "c";
        if itemsize == 1 && format_ok {
            let bytes_obj = memoryview_obj.call_method0("tobytes")?;
            let pybytes = bytes_obj.cast::<PyBytes>()?;
            return Ok(pybytes.as_bytes().to_vec());
        }
    }
    Err(PyTypeError::new_err(
        "expected bytes-like value (bytes, bytearray, memoryview, or buffer exporter)",
    ))
}

#[cfg(feature = "python")]
fn _buffer_len_bytes(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    if let Ok(pybytes) = data.cast::<PyBytes>() {
        return Ok(pybytes.as_bytes().len());
    }
    if let Ok(bytearray) = data.cast::<PyByteArray>() {
        return Ok(bytearray.len());
    }
    data.len()
}

#[cfg(feature = "python")]
fn _buffer_ptr_addr(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    if let Ok(pybytes) = data.cast::<PyBytes>() {
        return Ok(pybytes.as_bytes().as_ptr() as usize);
    }
    if let Ok(owner) = data.getattr("obj") {
        if let Ok(owner_bytes) = owner.cast::<PyBytes>() {
            return Ok(owner_bytes.as_bytes().as_ptr() as usize);
        }
    }
    Err(PyTypeError::new_err(
        "failed to resolve backing buffer pointer for this object",
    ))
}

#[cfg(feature = "python")]
impl<'a, 'py> FromPyObject<'a, 'py> for BytesVec {
    type Error = PyErr;

    fn extract(ob: pyo3::Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        Ok(Self(_extract_bytes_like(&ob)?))
    }
}

#[cfg(feature = "python")]
fn _sha3_digest(secret_key: &str, message: &[u8]) -> Vec<u8> {
    let mut hasher = Sha3_256::new();
    hasher.update(secret_key.as_bytes());
    hasher.update(message);
    hasher.finalize().to_vec()
}

#[cfg(feature = "python")]
fn _extract_sequence_u8(data: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    let iter = data.try_iter()?;
    let mut out = Vec::new();
    for item in iter {
        let value = item?.extract::<u8>()?;
        out.push(value);
    }
    Ok(out)
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_c_noop() -> usize {
    0
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_c_noop_pybytes(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes().len()
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_c_noop_any(_data: &Bound<'_, PyAny>) -> usize {
    0
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_zero_copy(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes().len()
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_acquire_buffer_len(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    _buffer_len_bytes(data)
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_zero_copy_buffer(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    Ok(_extract_bytes_like(data)?.len())
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_copy_bridge(data: &Bound<'_, PyBytes>) -> usize {
    let owned = data.as_bytes().to_vec();
    let len = owned.len();
    black_box(owned);
    len
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_copy_buffer_to_vec(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    let owned = _extract_bytes_like(data)?;
    let len = owned.len();
    black_box(owned);
    Ok(len)
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_copy_vec_arg(data: Vec<u8>) -> usize {
    data.len()
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_copy_sequence_to_vec_u8(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    Ok(_extract_sequence_u8(data)?.len())
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_copy_bytesvec_arg(data: BytesVec) -> usize {
    data.0.len()
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_bridge(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes().iter().map(|b| usize::from(*b)).sum()
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_buffer(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    let owned = _extract_bytes_like(data)?;
    Ok(owned.iter().map(|b| usize::from(*b)).sum())
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_step_1_len(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes().len()
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_step_2_touch_head(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes().first().map_or(0, |b| usize::from(*b))
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_step_3_touch_tail(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes().last().map_or(0, |b| usize::from(*b))
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_step_4_full_iter(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes()
        .iter()
        .fold(0usize, |acc, b| acc ^ usize::from(*b))
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_step_5_sum(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes().iter().map(|b| usize::from(*b)).sum()
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_step_6_hash(data: &Bound<'_, PyBytes>) -> usize {
    let digest = Sha3_256::digest(data.as_bytes());
    usize::from(digest[0])
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_step_5_sum_allow_threads(py: Python<'_>, data: &Bound<'_, PyBytes>) -> usize {
    let owned = data.as_bytes().to_vec();
    py.detach(move || owned.iter().map(|b| usize::from(*b)).sum())
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_bytesvec_allow_threads_sum(py: Python<'_>, data: BytesVec) -> usize {
    let owned = data.0;
    py.detach(move || owned.iter().map(|b| usize::from(*b)).sum())
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_vec_allow_threads_sum(py: Python<'_>, data: Vec<u8>) -> usize {
    py.detach(move || data.iter().map(|b| usize::from(*b)).sum())
}

#[cfg(feature = "python")]
#[pyfunction]
fn benchmark_consume_buffer_allow_threads_copy_sum(
    py: Python<'_>,
    data: &Bound<'_, PyAny>,
) -> PyResult<usize> {
    let owned = _extract_bytes_like(data)?;
    Ok(py.detach(move || owned.iter().map(|b| usize::from(*b)).sum()))
}

#[cfg(feature = "python")]
#[pyfunction]
fn get_pybytes_buf_ptr(data: &Bound<'_, PyBytes>) -> usize {
    data.as_bytes().as_ptr() as usize
}

#[cfg(feature = "python")]
#[pyfunction]
fn get_buffer_buf_ptr(data: &Bound<'_, PyAny>) -> PyResult<usize> {
    _buffer_ptr_addr(data)
}

#[cfg(feature = "python")]
#[pyfunction]
fn get_ptr_addr(data: &Bound<'_, PyBytes>) -> usize {
    get_pybytes_buf_ptr(data)
}

#[cfg(feature = "python")]
#[pyfunction]
fn generate_keypair() -> (String, String) {
    // Use proper ML-DSA-65 (FIPS 204) PQC key generation
    crypto::PQCKeypair::generate_raw()
}

// Module-level ML-DSA-65 helpers: warm_logic.security.pqc calls
// warm_logic_rs.sign/verify directly, not the MLDSA staticmethods.
#[cfg(feature = "python")]
#[pyfunction]
fn sign(private_key_hex: &str, message: &str) -> PyResult<String> {
    crypto::MLDSA::sign(private_key_hex, message)
}

#[cfg(feature = "python")]
#[pyfunction]
fn verify(public_key: &str, message: &str, signature: &str) -> bool {
    crypto::MLDSA::verify(public_key, message, signature)
}

#[cfg(feature = "python")]
#[pyfunction]
fn sign_bytes_view(py: Python<'_>, secret_key: &str, message: &Bound<'_, PyBytes>) -> Py<PyBytes> {
    let sig = _sha3_digest(secret_key, message.as_bytes());
    PyBytes::new(py, &sig).unbind()
}

#[cfg(feature = "python")]
#[pyfunction]
fn verify_bytes_view(
    public_key: &str,
    message: &Bound<'_, PyBytes>,
    signature: &Bound<'_, PyBytes>,
) -> bool {
    _sha3_digest(public_key, message.as_bytes()) == signature.as_bytes()
}

#[cfg(feature = "python")]
#[pyfunction]
fn sign_bytes_vec(py: Python<'_>, secret_key: &str, message: Vec<u8>) -> Py<PyBytes> {
    let sig = _sha3_digest(secret_key, &message);
    PyBytes::new(py, &sig).unbind()
}

#[cfg(feature = "python")]
#[pyfunction]
fn verify_bytes_vec(public_key: &str, message: Vec<u8>, signature: &Bound<'_, PyBytes>) -> bool {
    _sha3_digest(public_key, &message) == signature.as_bytes()
}

#[cfg(feature = "python")]
#[pyfunction]
fn sign_bytes_sequence(
    py: Python<'_>,
    secret_key: &str,
    message: &Bound<'_, PyAny>,
) -> PyResult<Py<PyBytes>> {
    let bytes = _extract_sequence_u8(message)?;
    let sig = _sha3_digest(secret_key, &bytes);
    Ok(PyBytes::new(py, &sig).unbind())
}

#[cfg(feature = "python")]
#[pyfunction]
fn verify_bytes_sequence(
    public_key: &str,
    message: &Bound<'_, PyAny>,
    signature: &Bound<'_, PyBytes>,
) -> PyResult<bool> {
    let bytes = _extract_sequence_u8(message)?;
    Ok(_sha3_digest(public_key, &bytes) == signature.as_bytes())
}

#[cfg(all(feature = "python", feature = "std"))]
#[pyclass]
pub struct SovereignKV {
    inner: Mutex<HashMap<String, Vec<u8>>>,
}

#[cfg(all(feature = "python", feature = "std"))]
#[pymethods]
impl SovereignKV {
    #[new]
    fn new() -> Self {
        Self {
            inner: Mutex::new(HashMap::new()),
        }
    }

    fn set_bytes(&self, key: String, data: &Bound<'_, PyBytes>) -> PyResult<()> {
        let mut guard = self
            .inner
            .lock()
            .map_err(|_| PyRuntimeError::new_err("SovereignKV lock poisoned"))?;
        guard.insert(key, data.as_bytes().to_vec());
        Ok(())
    }

    fn set_bytesvec(&self, key: String, data: BytesVec) -> PyResult<()> {
        let mut guard = self
            .inner
            .lock()
            .map_err(|_| PyRuntimeError::new_err("SovereignKV lock poisoned"))?;
        guard.insert(key, data.0);
        Ok(())
    }

    fn set_vec(&self, key: String, data: Vec<u8>) -> PyResult<()> {
        let mut guard = self
            .inner
            .lock()
            .map_err(|_| PyRuntimeError::new_err("SovereignKV lock poisoned"))?;
        guard.insert(key, data);
        Ok(())
    }

    fn get_bytes(&self, py: Python<'_>, key: String) -> PyResult<Option<Py<PyBytes>>> {
        let guard = self
            .inner
            .lock()
            .map_err(|_| PyRuntimeError::new_err("SovereignKV lock poisoned"))?;
        Ok(guard.get(&key).map(|v| PyBytes::new(py, v).unbind()))
    }
}

// ============================================================================
// PYTHON MODULE INITIALIZATION (Phase 6.1b)
// ============================================================================

/// Python module initialization for warm_logic_rs.
/// Registers all pyclass types for Python access.
#[cfg(feature = "python")]
#[pymodule]
fn warm_logic_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Core types from lib.rs
    m.add_class::<ModeDecision>()?;
    m.add_class::<ReflectiveLoop>()?;

    // Consensus types
    m.add_class::<consensus::bft::Vote>()?;
    m.add_class::<consensus::bft::AnonymousVote>()?;
    m.add_class::<consensus::bft::BFTEngine>()?;
    m.add_class::<consensus::raft::RaftEngine>()?;
    m.add_class::<consensus::types::RaftRPC>()?;
    m.add_class::<consensus::types::RaftState>()?;
    m.add_class::<consensus::types::LogEntry>()?;

    // Crypto types (requires std or bare-metal)
    #[cfg(any(feature = "std", feature = "bare-metal"))]
    {
        m.add_class::<crypto::PQCKeypair>()?;
        m.add_class::<crypto::MLDSA>()?;
        m.add_class::<crypto::MLKEM>()?;
    }

    // Governance types (requires std)
    #[cfg(feature = "std")]
    {
        m.add_class::<governance::GovernanceDecision>()?;
        m.add_class::<ledger::RustReplicatedLedger>()?;
        m.add_class::<policy_engine::PolicyEngine>()?;
        m.add_class::<storage::RustSovereignStore>()?;
    }

    // Network types (requires std) - Phase 6.1b
    #[cfg(feature = "std")]
    {
        m.add_class::<net::block_propagator::BlockPropagator>()?;
        m.add_class::<net::GossipSubscriber>()?;
    }

    // Kernel types
    m.add_class::<kernel::KineticCore>()?;
    m.add_class::<kernel::scheduler::RustKernelTask>()?;
    m.add_class::<kernel::scheduler::RustTaskScheduler>()?;
    m.add_class::<kernel::optimizer::RustResonanceOptimizer>()?;
    m.add_class::<kernel::sys::shield_v2::ShieldGuard>()?;
    m.add_class::<kernel::metrics_rs::RustPatchEfficiencyReport>()?;

    // Legacy Sigma-protocol ZK generator: deprecated in favour of the zk
    // module, but warm_logic.kernel.mesh.dht still constructs it by name.
    #[cfg(feature = "std")]
    {
        #[allow(deprecated)]
        m.add_class::<proof_zk::RustZKProofGenerator>()?;
    }

    // Merkle types
    m.add_class::<merkle::MerkleTree>()?;

    // Slashing types
    m.add_class::<slashing::SlashingEngine>()?;

    // Grid types
    m.add_class::<merged_grid::StateGrid>()?;

    // ZK types (python bindings, only when the zk feature is also enabled)
    #[cfg(all(feature = "python", feature = "zk"))]
    {
        m.add_class::<zk::PyZKGovernanceProver>()?;
        m.add_class::<zk::PyZKTransitionProver>()?;
        m.add_class::<zk::PyRecoveryProver>()?;
    }

    #[cfg(feature = "python")]
    {
        // Hardware types - Phase 103
        m.add_class::<hardware::HardwareRealityBinder>()?;
        m.add_class::<hardware::HardwareEntropy>()?;
        m.add_class::<hardware::HardwareAttestation>()?;
        m.add_class::<hardware::QuantumSiphon>()?;
        m.add_class::<hardware::v_hsm::VirtualHSM>()?;

        // sdk::MoralGateway is deliberately NOT registered: its evaluate path
        // hardcodes epsilon_c/tau_ethics (fail-open stub), and exposing it made
        // warm_logic.sdk prefer it over the Python gateway, ALLOWing intents
        // the documented SDK behaviour must DENY (tests/docs::TestSDKExamples).
        // Register it only once VetoEngine evaluates the real intent.
    }

    #[cfg(feature = "std")]
    {
        m.add_class::<SovereignKV>()?;
    }

    m.add_function(wrap_pyfunction!(benchmark_c_noop, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_c_noop_pybytes, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_c_noop_any, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_zero_copy, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_acquire_buffer_len, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_zero_copy_buffer, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_copy_bridge, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_copy_buffer_to_vec, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_copy_vec_arg, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_copy_sequence_to_vec_u8, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_copy_bytesvec_arg, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_consume_bridge, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_consume_buffer, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_consume_step_1_len, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_consume_step_2_touch_head, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_consume_step_3_touch_tail, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_consume_step_4_full_iter, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_consume_step_5_sum, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_consume_step_6_hash, m)?)?;
    m.add_function(wrap_pyfunction!(
        benchmark_consume_step_5_sum_allow_threads,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        benchmark_consume_bytesvec_allow_threads_sum,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        benchmark_consume_vec_allow_threads_sum,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        benchmark_consume_buffer_allow_threads_copy_sum,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(get_pybytes_buf_ptr, m)?)?;
    m.add_function(wrap_pyfunction!(get_buffer_buf_ptr, m)?)?;
    m.add_function(wrap_pyfunction!(get_ptr_addr, m)?)?;
    m.add_function(wrap_pyfunction!(generate_keypair, m)?)?;
    m.add_function(wrap_pyfunction!(sign, m)?)?;
    m.add_function(wrap_pyfunction!(verify, m)?)?;
    m.add_function(wrap_pyfunction!(kernel::metrics_rs::analyze_history, m)?)?;
    m.add_function(wrap_pyfunction!(sign_bytes_view, m)?)?;
    m.add_function(wrap_pyfunction!(verify_bytes_view, m)?)?;
    m.add_function(wrap_pyfunction!(sign_bytes_vec, m)?)?;
    m.add_function(wrap_pyfunction!(verify_bytes_vec, m)?)?;
    m.add_function(wrap_pyfunction!(sign_bytes_sequence, m)?)?;
    m.add_function(wrap_pyfunction!(verify_bytes_sequence, m)?)?;

    Ok(())
}
