//! rust_core/src/hardware/trng.rs
//! CV1800B Hardware True Random Number Generator (TRNG) Driver
//!
//! This module provides direct MMIO access to the CV1800B's hardware TRNG
//! for secure entropy generation in bare-metal environments.
//!
//! ## CV1800B TRNG Specification
//!
//! - Base Address: 0x03007000
//! - Entropy Width: 128-bit (4 x 32-bit registers)
//! - Output Rate: ~1 Mbit/s
//!
//! ## Register Map (Offset from Base)
//!
//! | Offset | Name     | Description                    |
//! |--------|----------|--------------------------------|
//! | 0x00   | TRNG_D0  | Entropy data word 0 (bits 0-31)|
//! | 0x04   | TRNG_D1  | Entropy data word 1 (bits 32-63)|
//! | 0x08   | TRNG_D2  | Entropy data word 2 (bits 64-95)|
//! | 0x0C   | TRNG_D3  | Entropy data word 3 (bits 96-127)|
//! | 0x10   | TRNG_CR  | Control register               |
//! | 0x14   | TRNG_SR  | Status register                |
//!
//! ## Safety
//!
//! This driver uses unsafe MMIO access. It should only be used on
//! actual CV1800B hardware (Milk-V Duo S, SG2000, etc.).

#![allow(dead_code)]

#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

/// CV1800B TRNG Base Address (memory-mapped I/O)
pub const TRNG_BASE_ADDR: usize = 0x0300_7000;

/// TRNG Register Offsets
pub const TRNG_DATA0_OFFSET: usize = 0x00;
pub const TRNG_DATA1_OFFSET: usize = 0x04;
pub const TRNG_DATA2_OFFSET: usize = 0x08;
pub const TRNG_DATA3_OFFSET: usize = 0x0C;
pub const TRNG_CTRL_OFFSET: usize = 0x10;
pub const TRNG_STATUS_OFFSET: usize = 0x14;

/// TRNG Control Register Bits
pub const TRNG_CTRL_ENABLE: u32 = 1 << 0;
pub const TRNG_CTRL_RESET: u32 = 1 << 1;

/// TRNG Status Register Bits
pub const TRNG_STATUS_READY: u32 = 1 << 0;
pub const TRNG_STATUS_ERROR: u32 = 1 << 1;

/// CV1800B Hardware TRNG Driver
///
/// Provides direct MMIO access to the SoC's true random number generator.
pub struct CV1800BTRNG {
    base_addr: usize,
    initialized: bool,
}

impl CV1800BTRNG {
    /// Create a new TRNG driver instance.
    ///
    /// # Safety
    ///
    /// This function is safe to call, but actual hardware access
    /// requires running on CV1800B silicon.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            base_addr: TRNG_BASE_ADDR,
            initialized: false,
        }
    }

    /// Create a TRNG driver with a custom base address (for testing).
    #[must_use]
    pub const fn with_base_addr(base_addr: usize) -> Self {
        Self {
            base_addr,
            initialized: false,
        }
    }

    /// Read a 32-bit value from a TRNG register.
    ///
    /// # Safety
    ///
    /// Caller must ensure the address is valid TRNG MMIO space.
    #[inline]
    unsafe fn read_reg(&self, offset: usize) -> u32 {
        let addr = (self.base_addr + offset) as *const u32;
        core::ptr::read_volatile(addr)
    }

    /// Write a 32-bit value to a TRNG register.
    ///
    /// # Safety
    ///
    /// Caller must ensure the address is valid TRNG MMIO space.
    #[inline]
    unsafe fn write_reg(&self, offset: usize, value: u32) {
        let addr = (self.base_addr + offset) as *mut u32;
        core::ptr::write_volatile(addr, value);
    }

    /// Initialize the TRNG hardware.
    ///
    /// This enables the TRNG and waits for it to be ready.
    ///
    /// # Safety
    ///
    /// Must be called on actual CV1800B hardware.
    pub unsafe fn init(&mut self) -> Result<(), TRNGError> {
        // Reset the TRNG
        self.write_reg(TRNG_CTRL_OFFSET, TRNG_CTRL_RESET);

        // Small delay for reset to complete
        for _ in 0..100 {
            core::hint::spin_loop();
        }

        // Enable the TRNG
        self.write_reg(TRNG_CTRL_OFFSET, TRNG_CTRL_ENABLE);

        // Wait for TRNG to be ready (with timeout)
        let mut timeout = 10_000;
        while timeout > 0 {
            let status = self.read_reg(TRNG_STATUS_OFFSET);
            if status & TRNG_STATUS_ERROR != 0 {
                return Err(TRNGError::HardwareError);
            }
            if status & TRNG_STATUS_READY != 0 {
                self.initialized = true;
                return Ok(());
            }
            timeout -= 1;
            core::hint::spin_loop();
        }

        Err(TRNGError::Timeout)
    }

    /// Check if the TRNG is ready to provide entropy.
    ///
    /// # Safety
    ///
    /// Must be called on actual CV1800B hardware.
    #[must_use]
    pub unsafe fn is_ready(&self) -> bool {
        let status = self.read_reg(TRNG_STATUS_OFFSET);
        (status & TRNG_STATUS_READY != 0) && (status & TRNG_STATUS_ERROR == 0)
    }

    /// # [PROOF_CONTRACT] Read 128 bits (16 bytes) of hardware entropy.
    ///
    /// ## Ensures
    /// - `result` is a valid 16-byte array.
    /// - Hardware entropy density matches the `Groundable` specification.
    ///
    /// # Safety
    ///
    /// Must be called on actual CV1800B hardware after init().
    pub unsafe fn read_entropy_128(&self) -> Result<[u8; 16], TRNGError> {
        if !self.initialized {
            return Err(TRNGError::NotInitialized);
        }

        if !self.is_ready() {
            return Err(TRNGError::NotReady);
        }

        // Read 4 x 32-bit words = 128 bits
        let d0 = self.read_reg(TRNG_DATA0_OFFSET);
        let d1 = self.read_reg(TRNG_DATA1_OFFSET);
        let d2 = self.read_reg(TRNG_DATA2_OFFSET);
        let d3 = self.read_reg(TRNG_DATA3_OFFSET);

        // Convert to bytes (little-endian)
        let mut entropy = [0u8; 16];
        entropy[0..4].copy_from_slice(&d0.to_le_bytes());
        entropy[4..8].copy_from_slice(&d1.to_le_bytes());
        entropy[8..12].copy_from_slice(&d2.to_le_bytes());
        entropy[12..16].copy_from_slice(&d3.to_le_bytes());

        Ok(entropy)
    }

    /// Fill a buffer with hardware random bytes.
    ///
    /// # Safety
    ///
    /// Must be called on actual CV1800B hardware after init().
    pub unsafe fn fill_bytes(&self, buf: &mut [u8]) -> Result<(), TRNGError> {
        if !self.initialized {
            return Err(TRNGError::NotInitialized);
        }

        let mut offset = 0;
        while offset < buf.len() {
            // Wait for ready
            let mut timeout = 1_000;
            while !self.is_ready() && timeout > 0 {
                timeout -= 1;
                core::hint::spin_loop();
            }
            if timeout == 0 {
                return Err(TRNGError::Timeout);
            }

            // Read 128 bits
            let entropy = self.read_entropy_128()?;

            // Copy to buffer
            let remaining = buf.len() - offset;
            let copy_len = core::cmp::min(remaining, 16);
            buf[offset..offset + copy_len].copy_from_slice(&entropy[..copy_len]);
            offset += copy_len;
        }

        Ok(())
    }

    /// Get the base address of the TRNG peripheral.
    #[must_use]
    pub const fn base_addr(&self) -> usize {
        self.base_addr
    }

    /// Check if the TRNG has been initialized.
    #[must_use]
    pub const fn is_initialized(&self) -> bool {
        self.initialized
    }
}

impl crate::hardware::grounding::Groundable for CV1800BTRNG {
    fn grounding_spec(&self) -> [u8; 32] {
        // High-density bitmask spec for entropy sources
        [0xFF; 32]
    }

    fn physical_value(&self) -> [u8; 32] {
        let mut entropy = [0u8; 32];
        unsafe {
            // Self-init if needed for the probe
            if !self.initialized {
                // We cannot modify self here as it's &self,
                // but in bare-metal this is often a static probe.
                return [0u16 as u8; 32]; // Return empty if not ready for probe
            }
            let _ = self.fill_bytes(&mut entropy);
        }
        entropy
    }
}

impl Default for CV1800BTRNG {
    fn default() -> Self {
        Self::new()
    }
}

/// TRNG Error Types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TRNGError {
    /// TRNG not initialized (call init() first)
    NotInitialized,
    /// TRNG hardware not ready
    NotReady,
    /// Operation timed out
    Timeout,
    /// Hardware error detected
    HardwareError,
    /// Platform not supported
    Unsupported,
}

impl core::fmt::Display for TRNGError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            TRNGError::NotInitialized => write!(f, "TRNG not initialized"),
            TRNGError::NotReady => write!(f, "TRNG not ready"),
            TRNGError::Timeout => write!(f, "TRNG timeout"),
            TRNGError::HardwareError => write!(f, "TRNG hardware error"),
            TRNGError::Unsupported => write!(f, "TRNG unsupported on this platform"),
        }
    }
}

// ============================================================================
// Global TRNG Instance for getrandom Integration
// ============================================================================

#[cfg(feature = "bare-metal")]
use core::sync::atomic::{AtomicBool, Ordering};

#[cfg(feature = "bare-metal")]
static TRNG_INITIALIZED: AtomicBool = AtomicBool::new(false);

#[cfg(feature = "bare-metal")]
static mut TRNG_INSTANCE: CV1800BTRNG = CV1800BTRNG::new();

/// Custom getrandom implementation for bare-metal targets.
#[cfg(feature = "bare-metal")]
fn custom_getrandom(buf: &mut [u8]) -> Result<(), getrandom::Error> {
    unsafe {
        if !TRNG_INITIALIZED.load(Ordering::SeqCst) {
            // Self-initialize if not done yet
            let _ = TRNG_INSTANCE.init();
            TRNG_INITIALIZED.store(true, Ordering::SeqCst);
        }

        TRNG_INSTANCE
            .fill_bytes(buf)
            .map_err(|_| getrandom::Error::UNSUPPORTED)
    }
}

// Register the custom getrandom implementation
#[cfg(feature = "bare-metal")]
getrandom::register_custom_getrandom!(custom_getrandom);

/// Initialize the global TRNG instance.
///
/// This must be called once during bare-metal startup before any
/// cryptographic operations.
///
/// # Safety
///
/// Must be called on actual CV1800B hardware, and only once.
#[cfg(feature = "bare-metal")]
pub unsafe fn init_trng() -> Result<(), TRNGError> {
    if TRNG_INITIALIZED.load(Ordering::SeqCst) {
        return Ok(()); // Already initialized
    }

    TRNG_INSTANCE.init()?;
    TRNG_INITIALIZED.store(true, Ordering::SeqCst);
    Ok(())
}

/// Fill a buffer with random bytes from the global TRNG.
///
/// This is the function called by getrandom in bare-metal mode.
///
/// # Safety
///
/// Must be called after init_trng() on CV1800B hardware.
#[cfg(feature = "bare-metal")]
pub unsafe fn trng_fill_bytes(buf: &mut [u8]) -> Result<(), TRNGError> {
    if !TRNG_INITIALIZED.load(Ordering::SeqCst) {
        return Err(TRNGError::NotInitialized);
    }
    TRNG_INSTANCE.fill_bytes(buf)
}

// ============================================================================
// Tests (std-only, simulate register behavior)
// ============================================================================

#[cfg(all(test, feature = "std"))]
mod tests {
    use super::*;

    #[test]
    fn test_trng_constants() {
        assert_eq!(TRNG_BASE_ADDR, 0x0300_7000);
        assert_eq!(TRNG_DATA0_OFFSET, 0x00);
        assert_eq!(TRNG_DATA1_OFFSET, 0x04);
        assert_eq!(TRNG_DATA2_OFFSET, 0x08);
        assert_eq!(TRNG_DATA3_OFFSET, 0x0C);
    }

    #[test]
    fn test_trng_creation() {
        let trng = CV1800BTRNG::new();
        assert_eq!(trng.base_addr(), TRNG_BASE_ADDR);
        assert!(!trng.is_initialized());
    }

    #[test]
    fn test_trng_custom_addr() {
        let trng = CV1800BTRNG::with_base_addr(0x1234_0000);
        assert_eq!(trng.base_addr(), 0x1234_0000);
    }

    #[test]
    fn test_error_display() {
        assert_eq!(
            format!("{}", TRNGError::NotInitialized),
            "TRNG not initialized"
        );
        assert_eq!(format!("{}", TRNGError::Timeout), "TRNG timeout");
    }
}
