// Copyright 2026 espressolee
// Profiler for measuring Reality Gap on bare-metal RISC-V.

#[cfg(feature = "bare-metal")]
use core::arch::asm;

pub struct CycleProfiler {
    start: u64,
}

impl Default for CycleProfiler {
    fn default() -> Self {
        Self::new()
    }
}

impl CycleProfiler {
    /// Zero-latency cycle counter start
    #[must_use]
    pub const fn new() -> Self {
        Self { start: 0 }
    }

    #[inline(always)]
    pub fn start(&mut self) {
        #[cfg(feature = "bare-metal")]
        unsafe {
            // Read 64-bit cycle counter (available on RV64)
            let cycles: u64;
            asm!("csrr {}, time", out(reg) cycles);
            self.start = cycles;
        }
        #[cfg(not(feature = "bare-metal"))]
        {
            self.start = 0;
        }
    }

    #[inline(always)]
    #[must_use]
    pub fn end(&self) -> u64 {
        #[cfg(feature = "bare-metal")]
        unsafe {
            let end_cycles: u64;
            asm!("csrr {}, time", out(reg) end_cycles);
            if end_cycles >= self.start {
                end_cycles - self.start
            } else {
                0 // Minimal overflow protection
            }
        }
        #[cfg(not(feature = "bare-metal"))]
        0
    }
}
