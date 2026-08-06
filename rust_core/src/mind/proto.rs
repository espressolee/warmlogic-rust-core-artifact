//! rust_core/src/mind/proto.rs

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[derive(borsh::BorshSerialize, borsh::BorshDeserialize, Debug, Clone)]
#[cfg_attr(feature = "python", pyclass(get_all))]
pub enum KernelPacket {
    Telemetry {
        heap_used: u64,
        heap_total: u64,
        task_count: u32,
        ticks: u64,
    },
    Decision {
        verdict: String,
        action: u8, // 0: Optimal, 1: Anomaly, 2: ScaleUp, 3: ScaleDown
        amount: u32,
    },
    Heartbeat {
        uptime_ms: u64,
        integrity_hash: [u8; 32],
    },
    LedgerUpdate {
        balance: f64,
        epoch: u64,
    },
}

impl KernelPacket {
    pub const MAGIC: [u8; 4] = [0x53, 0x4F, 0x56, 0x31]; // "SOV1"
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn decode_packet(data: Vec<u8>) -> PyResult<KernelPacket> {
    borsh::from_slice(&data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Borsh Decode Error: {}", e)))
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn encode_packet(packet: KernelPacket) -> PyResult<Vec<u8>> {
    borsh::to_vec(&packet)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Borsh Encode Error: {}", e)))
}
