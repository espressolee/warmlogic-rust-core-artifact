//! rust_core/src/hardware/hwrng.rs
//! Hardware Random Number Generator (HWRNG) driver for Linux.
//!
//! This module provides a safe interface to the system's hardware TRNG
//! via the `/dev/hwrng` character device, common on SoCs like JH7110 (VisionFive 2).

use std::fs::File;
use std::io::{Read, Result as IoResult};
use std::path::Path;

/// Linux Hardware RNG Interface
pub struct HWRNG {
    device_path: String,
}

impl HWRNG {
    /// Create a new HWRNG instance using the default device path.
    #[must_use]
    pub fn new() -> Self {
        Self {
            device_path: "/dev/hwrng".into(),
        }
    }

    /// Create a new HWRNG instance with a custom device path.
    #[must_use]
    pub fn with_path(path: &str) -> Self {
        Self {
            device_path: path.into(),
        }
    }

    /// Check if the hardware RNG device is accessible.
    ///
    /// The node existing is not enough: on hosts without a backing TRNG (or
    /// without read permission) `/dev/hwrng` is present but unreadable, so
    /// availability is probed with an actual 1-byte read.
    #[must_use]
    pub fn is_available(&self) -> bool {
        if !Path::new(&self.device_path).exists() {
            return false;
        }
        let mut probe = [0u8; 1];
        File::open(&self.device_path)
            .and_then(|mut f| f.read_exact(&mut probe))
            .is_ok()
    }

    /// Read raw entropy bytes from the hardware RNG.
    ///
    /// # Errors
    ///
    /// Returns an IO error if the device cannot be opened or read.
    pub fn fill_bytes(&self, buf: &mut [u8]) -> IoResult<()> {
        let mut file = File::open(&self.device_path)?;
        file.read_exact(buf)?;
        Ok(())
    }

    /// Read a single 64-bit entropy value.
    pub fn next_u64(&self) -> IoResult<u64> {
        let mut bytes = [0u8; 8];
        self.fill_bytes(&mut bytes)?;
        Ok(u64::from_le_bytes(bytes))
    }
}

impl Default for HWRNG {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hwrng_availability() {
        let hwrng = HWRNG::new();
        // This may be false on dev machines, but should not panic
        let available = hwrng.is_available();
        println!("HWRNG available: {}", available);
    }

    #[test]
    fn test_hwrng_read_if_available() {
        let hwrng = HWRNG::new();
        if hwrng.is_available() {
            let mut buf = [0u8; 32];
            let result = hwrng.fill_bytes(&mut buf);
            assert!(result.is_ok());
            // Most HWRNGs won't return all zeros, but we can't strictly guarantee it
            // as a test case unless we know the hardware.
        }
    }
}
