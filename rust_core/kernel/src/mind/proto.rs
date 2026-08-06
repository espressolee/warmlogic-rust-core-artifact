use borsh::{BorshSerialize, BorshDeserialize};
use alloc::string::String;

#[derive(BorshSerialize, BorshDeserialize, Debug, Clone)]
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
