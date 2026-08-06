#![no_std]
#![no_main]

extern crate alloc;

use alloc::format;
use alloc::string::ToString;
use core::panic::PanicInfo;
use warm_logic_rs::crypto::{PQCKeypair, MLDSA};
#[cfg(feature = "bare-metal")]
use warm_logic_rs::debug::profiler::CycleProfiler;
use warm_logic_rs::hardware::allocator;
use warm_logic_rs::kernel::KineticCore;

/// Serial port address (COM1 in QEMU)
pub const SERIAL_COM1: u16 = 0x3F8;
/// Primitive UART driver for QEMU logging.
pub struct SerialWriter {
    port: usize,
}

impl SerialWriter {
    pub const fn new(port: usize) -> Self {
        SerialWriter { port }
    }

    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    pub fn write_byte(&self, byte: u8) {
        unsafe {
            core::arch::asm!("out dx, al", in("dx") self.port as u16, in("al") byte, options(nomem, nostack, preserves_flags));
        }
    }

    #[cfg(target_arch = "riscv64")]
    pub fn write_byte(&self, byte: u8) {
        let uart = self.port as *mut u8;
        unsafe {
            // Write to UART THR (Transmitter Holding Register)
            core::ptr::write_volatile(uart, byte);
        }
    }

    #[cfg(not(any(target_arch = "x86", target_arch = "x86_64", target_arch = "riscv64")))]
    pub fn write_byte(&self, _byte: u8) {}

    pub fn write_string(&self, s: &str) {
        for byte in s.bytes() {
            self.write_byte(byte);
        }
    }
}

/// The entry point for the WarmLogic Kernel.
#[no_mangle]
pub extern "C" fn _start() -> ! {
    #[cfg(target_arch = "riscv64")]
    let port = 0x1000_0000; // QEMU Virt UART0
    #[cfg(not(target_arch = "riscv64"))]
    let port = SERIAL_COM1 as usize;

    let serial = SerialWriter::new(port);

    // Initialize Global Allocator (4MB Heap)
    allocator::init_heap();

    // Initialize Hardware TRNG (CV1800B Silicon)
    #[cfg(feature = "bare-metal")]
    unsafe {
        if let Err(e) = warm_logic_rs::hardware::trng::init_trng() {
            serial.write_string(&format!("[FATAL] TRNG Initialization Failed: {}\r\n", e));
            loop {}
        }
    }

    serial.write_string("\r\n=== WARM LOGIC KERNEL v2.0 (INSTRUMENTED) ===\r\n");
    serial.write_string("[INFO] Initializing Kinetic Core...\r\n");

    let mut kernel = KineticCore::new();
    let mut bft = warm_logic_rs::consensus::bft::BFTEngine::new(3); // Quorum of 3 Nodes

    serial.write_string("[INFO] Starting Hardware Calibration...\r\n");
    // Profile KeyGen and first Sign for Calibration
    #[cfg(feature = "bare-metal")]
    let mut profiler = CycleProfiler::new();

    #[cfg(feature = "bare-metal")]
    profiler.start();
    let (_pk, sk) = PQCKeypair::generate_raw();
    #[cfg(feature = "bare-metal")]
    let keygen_cycles = profiler.end();
    #[cfg(not(feature = "bare-metal"))]
    let keygen_cycles: u64 = 0;

    serial.write_string(&format!("[PERF] KeyGen Cycles: {}\r\n", keygen_cycles));

    #[cfg(feature = "bare-metal")]
    profiler.start();
    let _sig = MLDSA::sign_raw(&sk, "Calibrate").unwrap();
    #[cfg(feature = "bare-metal")]
    let pqc_sign_cycles = profiler.end();
    #[cfg(not(feature = "bare-metal"))]
    let pqc_sign_cycles: u64 = 0;

    serial.write_string(&format!("[PERF] PQC Sign Cycles: {}\r\n", pqc_sign_cycles));

    // Calibration: target 5% overhead for security at 400Hz
    // 400Hz @ 10MHz = 25,000 cycles budget. 5% = 1,250 cycles.
    // interval = pqc_sign_cycles / 1,250
    let target_amortized_budget = 1250;
    let pqc_interval = if pqc_sign_cycles > 0 {
        (pqc_sign_cycles + target_amortized_budget - 1) / target_amortized_budget
    } else {
        400 // Default to 1 second if no profiling
    };

    serial.write_string(&format!(
        "[INFO] Calibration Complete. PQC Interval: {} ticks.\r\n",
        pqc_interval
    ));

    let mut scheduler = warm_logic_rs::drone::security_scheduler::SecurityScheduler::new(
        warm_logic_rs::drone::security_scheduler::SecurityLevel::AmortizedPQC,
        pqc_interval,
    );

    let _message = "RealityGapCheck";
    let mut tick_count: u64 = 0;

    loop {
        tick_count += 1;

        // 1. Measure Control Logic (Tick)
        #[cfg(feature = "bare-metal")]
        profiler.start();

        let _decision = kernel.tick_raw(1.0, 0.0);

        // Hash current "sensor data" (Phase 12.10: Reality Grounding)
        let mut sensor_data = [0u8; 32];
        {
            use sha3::{Digest, Sha3_256};
            let mut hasher = Sha3_256::new();
            hasher.update(&tick_count.to_le_bytes());
            // Static anchor for sensor entropy (in a real system, this would read ADC)
            hasher.update(b"SILICON_NOISE_RESONANCE");
            sensor_data.copy_from_slice(&hasher.finalize());
        }
        let trigger_pqc = scheduler.tick(&sensor_data);

        #[cfg(feature = "bare-metal")]
        let control_cycles = profiler.end();
        #[cfg(not(feature = "bare-metal"))]
        let control_cycles: u64 = 0;

        // 2. Measure BFT Voting (Simulated node quorum)
        #[cfg(feature = "bare-metal")]
        profiler.start();

        let round_id = tick_count / 10;
        if tick_count % 10 == 0 {
            // Start a new BFT round every 10 ticks
            bft.start_round(round_id);
            bft.propose(format!("block_{}", tick_count), None);
        }

        // Phase 12.10: Reality-Grounded BFT Signature
        let block_id = format!("block_{}", round_id * 10);
        let sign_msg = format!("{}:{}", block_id, round_id);
        let sig = MLDSA::sign_raw(&sk, &sign_msg).unwrap_or_else(|_| "SIG_FAIL".into());

        // Simulate casting a vote for the proposal
        let vote = warm_logic_rs::consensus::bft::Vote {
            voter_id: "NodeActive".to_string(),
            block_hash: block_id,
            round: round_id,
            signature: sig,
            decision_hash: None,
        };

        let pk_hex = hex::encode(&_pk[..32]); // Assuming PK is large
        let quorum_reached = bft.cast_vote_verified(vote, &pk_hex).is_ok();

        #[cfg(feature = "bare-metal")]
        let bft_cycles = profiler.end();
        #[cfg(not(feature = "bare-metal"))]
        let bft_cycles: u64 = 0;

        // 3. Measure Crypto Logic (Sign) - only if triggered by scheduler
        let mut crypto_cycles: u64 = 0;
        if trigger_pqc {
            #[cfg(feature = "bare-metal")]
            {
                profiler.start();

                let payload = scheduler
                    .get_signing_payload()
                    .unwrap_or_else(|| "none".into());
                let sig = MLDSA::sign_raw(&sk, &payload).unwrap_or_else(|_| "SIG_FAIL".into());
                scheduler.set_pqc_signature(sig);

                crypto_cycles = profiler.end();
            }
            #[cfg(not(feature = "bare-metal"))]
            {
                let payload = scheduler
                    .get_signing_payload()
                    .unwrap_or_else(|| "none".into());
                let sig = MLDSA::sign_raw(&sk, &payload).unwrap_or_else(|_| "SIG_FAIL".into());
                scheduler.set_pqc_signature(sig);
            }
        }

        // Log to Serial (CSV format for easy parsing)
        // Format: CYCLES,CONTROL_TICKS,BFT_TICKS,CRYPTO_TICKS
        let log = format!(
            "CYCLES,{},{},{}\r\n",
            control_cycles, bft_cycles, crypto_cycles
        );
        serial.write_string(&log);

        if trigger_pqc {
            serial.write_string(&format!(
                "[INFO] PQC Epoch Completed at Tick {}\r\n",
                tick_count
            ));
        }

        if quorum_reached && tick_count % 10 == 0 {
            serial.write_string(&format!(
                "[INFO] BFT Quorum Reached for Round {}!\r\n",
                tick_count / 10
            ));
        }

        // Sleep to avoid flooding serial
        for _ in 0..10_000 {
            core::hint::spin_loop();
        }
    }
}

/// This function is called on panic in the kernel.
#[cfg(not(feature = "std"))]
#[panic_handler]
fn panic(info: &PanicInfo) -> ! {
    #[cfg(target_arch = "riscv64")]
    let port = 0x1000_0000;
    #[cfg(not(target_arch = "riscv64"))]
    let port = SERIAL_COM1 as usize;

    let serial = SerialWriter::new(port);
    serial.write_string("\r\n!!! KERNEL PANIC !!!\r\n");
    if let Some(location) = info.location() {
        serial.write_string(&format!(
            "At {}:{}:{}\r\n",
            location.file(),
            location.line(),
            location.column()
        ));
    }
    loop {}
}
