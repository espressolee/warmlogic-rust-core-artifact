use crate::hardware::grounding::Groundable;
use crate::hardware::HardwareRealityBinder;

pub struct SiliconGrounding;

impl Groundable for SiliconGrounding {
    fn grounding_spec(&self) -> [u8; 32] {
        // Reality Spec: Silicon fingerprint must match axiomatic expectation
        // In simulation/dev, we might use a fixed spec, but in production this is bound to hardware.
        HardwareRealityBinder::get_hardware_fingerprint_raw()
    }

    fn physical_value(&self) -> [u8; 32] {
        // [PHASE 13.5] Real CV1800B Hardware Extraction
        HardwareRealityBinder::get_hardware_fingerprint_raw()
    }

    /// [Phase 100] Physical PUF Invariant: Max 2 bits difference.
    fn is_grounded(&self) -> bool {
        self.is_puf_aligned(2)
    }
}
