//! src/bin/bootloader.rs
//! The Iron Foundation.
//! This binary replaces the Python entry point.

use pyo3::prelude::*;
use std::time::Instant;
use warm_logic_rs::hardware::tpm::HardwareTPM;

fn main() -> PyResult<()> {
    let start = Instant::now();
    println!("[bootloader] Bootloader Sequence Initiated...");

    // 1. Hardware Binding (Pure Rust)
    let tpm_ready = if cfg!(feature = "tpm") {
        HardwareTPM::is_available()
    } else {
        println!("[bootloader] TPM Feature Disabled (Compiling without 'tpm' feature).");
        false
    };

    if tpm_ready {
        println!("[bootloader] TPM 2.0 Detected & Bound.");
        // In real we would unseal keys here BEFORE Python starts.
    } else {
        println!("[bootloader] TPM Missing. Falling back to Simulation Mode.");
    }

    let rust_duration = start.elapsed();
    println!(
        "⏱️ [bootloader] Rust Init Time: {:.2} ms",
        rust_duration.as_secs_f64() * 1000.0
    );

    // 2. Launch Mind (Python Embedding)
    println!("[bootloader] Awakening the Mind (Python Kernel)...");

    Python::attach(|py| {
        let sys = py.import("sys")?;
        sys.getattr("path")?.call_method1("append", ("../",))?; // Add project root to path

        // Import the Python bootloader module
        let bootloader = py.import("warm_logic.kernel.bootloader")?;

        // Call the entry point
        println!("[bootloader] Jump to Kernel...");
        bootloader.call_method0("boot_system")?;

        Ok(())
    })
}
