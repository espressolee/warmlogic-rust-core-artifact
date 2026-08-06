/*
 * Copyright 2026 espressolee. Licensed under the Apache License, Version 2.0.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

use std::env;
use std::panic;
use std::process;
use std::thread;
use std::time::Duration;

fn main() {
    // 1. Harsh Panic Hook for Headless Debugging
    panic::set_hook(Box::new(|info| {
        println!("[CRITICAL] KERNEL PANIC DETECTED ");
        if let Some(s) = info.payload().downcast_ref::<&str>() {
            println!("   Reason: {}", s);
        } else if let Some(s) = info.payload().downcast_ref::<String>() {
            println!("   Reason: {}", s);
        } else {
            println!("   Reason: Unknown");
        }
        if let Some(location) = info.location() {
            println!(
                "   Location: {}:{}:{}",
                location.file(),
                location.line(),
                location.column()
            );
        }
        println!("Halting System to prevent corruption.");
        // In real hardware, we might trigger a watchdog reset here.
        process::exit(101);
    }));

    #[cfg(target_arch = "riscv64")]
    println!("[WarmLogic] RISC-V Sovereign Seed Boot Sequence Initiated...");

    #[cfg(target_arch = "aarch64")]
    println!("[WarmLogic] ARM64 Sovereign Boot Sequence Initiated...");

    #[cfg(not(any(target_arch = "riscv64", target_arch = "aarch64")))]
    println!(
        "🚀 [WarmLogic] Sovereign Boot Sequence (Unknown Arch: {}) Initiated...",
        env::consts::ARCH
    );

    println!("ℹ [WarmLogic] Architecture: {}", env::consts::ARCH);
    println!("ℹ [WarmLogic] OS: {}", env::consts::OS);

    // 2. Hardware Health Check (Simulated)
    println!("[WarmLogic] Initializing peripherals...");
    if !perform_health_check() {
        panic!("Hardware Integrity Check Failed!");
    }

    // 3. Launch Mind (Harsh Supervisor Mode)
    // We utilize std::process to avoid PyO3 cross-linking hell on simple embedded targets.
    println!("[WarmLogic] Awakening the Mind (Python Kernel)...");

    let python_bin = "python3"; // Assumes env is set correctly
    let kernel_module = "warm_logic.kernel.bootloader";

    loop {
        println!("[Supervisor] Spawning Kernel...");
        let start_time = std::time::Instant::now();

        let mut child = process::Command::new(python_bin)
            .arg("-m")
            .arg(kernel_module)
            .spawn()
            .expect("Failed to spawn Python Kernel");

        let status = child.wait().expect("Failed to wait on Kernel");

        let uptime = start_time.elapsed();
        println!("[Supervisor] Kernel exited with: {}", status);
        println!("⏱[Supervisor] Kernel Uptime: {:?}", uptime);

        if !status.success() {
            println!("[CRITICAL] Kernel Died via Error!");
            // In Harsh Mode, if the Mind dies quickly (< 10s), we panic the Body.
            if uptime.as_secs() < 10 {
                panic!("Mind collapsed too quickly! Integrity compromised.");
            }
        } else {
            println!("[Supervisor] Kernel exited cleanly (Shutdown).");
            break;
        }

        println!("[Supervisor] Restarting Kernel in 1s...");
        thread::sleep(Duration::from_secs(1));
    }

    println!("[WarmLogic] System Shutdown Complete.");
}

fn perform_health_check() -> bool {
    // Simulate checking sensors/storage
    print!("   - Checking Storage Integrity: ");
    thread::sleep(Duration::from_millis(50));
    println!("OK");

    print!("   - Checking Cryptographic Accelerator: ");
    thread::sleep(Duration::from_millis(50));
    // In strict mode, we might verify /dev/hwrng or TPM presence
    println!("OK (Simulated)");

    true
}
