# ADR-002: Kinetic Identity (Hardware Binding)
 
 **Date**: 2026-01-31
 **Status**: Accepted
 **Era**: 520
 
 ## Context
 "Identity" in digital systems is usually a private key file (`.pem`) stored on disk. This is "Cold Identity"—it can be copied, stolen, or moved without the software knowing. We wanted "Kinetic Identity"—identity that is inseparable from the physical machine running it.
 
 ## Decision
 We implemented `HardwareEntropy` in `warm_logic_rs/src/hardware.rs`.
 
 - **Mechanism**: The system reads immutable hardware serial numbers (CPU UUID, Disk UUID) at runtime.
 - **Binding**: These values are hashed into the *seed* of the session keys (`ML-DSA` pairs).
 - **Constraint**: If the software is moved to a new machine, the Identity *changes*.
 
 ## Consequences
 ### Positive
 - **Sovereignty**: The code "knows" where it is. It cannot be forked without losing its Identity.
 - **Theft Resistance**: Stealing the hard drive does not steal the running session state if the CPU signature changes (requires TPM binding in Phase 2).
 
 ### Negative
 - **Migration Difficulty**: Legitimate migration requires a "Death/Rebirth" ceremony (creating a new Identity).
 
 ## Evidence
 - `tests/kernel/test_hardware_binding.py` confirms that the seed is deterministic on the same "mocked" hardware.
