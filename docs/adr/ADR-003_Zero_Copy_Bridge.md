# ADR-003: Zero-Copy Python-Rust Bridge
 
 **Date**: 2026-01-31
 **Status**: Accepted
 **Era**: 460
 
 ## Context
 The boundary between Python (Logic) and Rust (Safety) was the performance bottleneck. Serializing objects to JSON/Pickle to pass them across the FFI incurred an $O(N)$ penalty, capping throughput at ~100MB/s.
 
 ## Decision
 We adopted a **Zero-Copy Architecture** using `PyBytes` references.
 
 - **Mechanism**: Python allocates memory. Rust receives a *pointer* to that memory (`&Bound<PyBytes>`) effectively treated as an immutable byte slice (`&[u8]`).
 - **Safety**: The GIL protects the memory from being deallocated while Rust reads it.
 
 ## Consequences
 ### Positive
 - **Throughput**: $O(1)$ complexity. Transferring 10MB takes the same time as 10bytes (~250ns).
 - **Efficiency**: No CPU cycles wasted on `memcpy`.
 
 ### Negative
 - **Safety Risk**: Rust cannot *modify* the data in-place easily without `unsafe`. We treat inputs as Read-Only.
 
 ## Evidence
 - `scripts/eval/bridge_eval_v1/` proves that latency is flat across payload sizes.
