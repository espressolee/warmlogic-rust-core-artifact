# ADR-001: Vector Abstraction Layer (Soft-Vector)
 
 **Date**: 2026-01-31
 **Status**: Accepted
 **Era**: 510
 
 ## Context
 We needed a way to support high-performance cryptography (SHA3, ML-DSA) on future RISC-V hardware (with V-Extensions) while maintaining compatibility with current Scalar hardware (x86_64, ARM64) and avoiding the "dependency hell" of platform-specific intrinsics in the core kernel.
 
 ## Decision
 We implemented a `VectorOp` trait in `warm_logic_rs/src/vector_std.rs` that abstracts SIMD operations.
 
 - **Scalar Implementation**: Uses standard Rust loops (for current hardware).
 - **Vector Implementation**: Will use `core::arch::riscv64::v` intrinsics (when the hardware arrives).
 
 ## Consequences
 ### Positive
 - **Portability**: The kernel compiles on any architecture supported by Rust.
 - **Testability**: We can verify the logic (math) on Scalar hardware before the Vector hardware exists.
 
 ### Negative
 - **Indirection Overhead**: The trait dispatch entails a small runtime cost compared to raw intrinsics (though `#[inline(always)]` mitigates this).
 
 ## Evidence
 - `tests/kernel/test_vector_vec.py` confirms that the Scalar fallback behaves identically to the mathematical specification.
