use crate::state_grid::StateGrid;
use crate::hardware::HardwareAttestation;

pub struct LogosInit;

impl LogosInit {
    /// The primary bootstrap sequence for a new node.
    pub fn bootstrap(snapshot: &[u8]) -> Result<StateGrid, String> {
        println!("[LOGOS-INIT] Initiating Autonomous Bootstrap...");

        // 1. Verify Hardware RoT
        let report = HardwareAttestation::generate_report_raw();
        if report.pcr_hash == "0000000000000000000000000000000000000000" {
            return Err("Hardware RoT Attestation Failed: Insecure Environment.".to_string());
        }
        println!("[LOGOS-INIT] Hardware Attested (Provider: {}).", report.provider);

        // 2. Reconstruct Grid from Axiomatic Snapshot
        let grid = StateGrid::from_snapshot(snapshot)
            .map_err(|e| format!("Axiomatic Reconstruction Failed: {}", e))?;

        println!("[LOGOS-INIT] Grid Reconstructed. Integrity Hash: {}", hex::encode(grid.integrity_hash));
        println!("[LOGOS-INIT] Node is now SOVEREIGN.");

        Ok(grid)
    }
}
