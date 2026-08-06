import ctypes
import os
import random

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
C_LIB_PATH = os.path.join(BASE_DIR, "warm_logic/kernel/formal/libkernel_logic.so")
RUST_LIB_PATH = os.path.join(
    BASE_DIR,
    "warm_logic/kernel/portable/rust/kernel_portable_rs/target/release/libkernel_portable_rs.dylib",
)

# Load Libraries
c_lib = ctypes.CDLL(C_LIB_PATH)
rust_lib = ctypes.CDLL(RUST_LIB_PATH)

# Define Function Signatures
# bool check_phase_transition(kernel_phase_t current, kernel_phase_t next)
c_lib.check_phase_transition.argtypes = [ctypes.c_int, ctypes.c_int]
c_lib.check_phase_transition.restype = ctypes.c_bool

# bool rs_check_phase_transition(KernelPhase current, KernelPhase next)
rust_lib.rs_check_phase_transition.argtypes = [ctypes.c_int, ctypes.c_int]
rust_lib.rs_check_phase_transition.restype = ctypes.c_bool


def fuzz_consistency(iterations=100000):
    print(
        f"🔬 Starting Cross-Language Consistency Fuzzing ({iterations} iterations)..."
    )

    mismatches = 0

    # Range of phases: 0-6 (Standard), plus some extra for out-of-bounds testing
    for i in range(iterations):
        current = random.randint(0, 10)
        next_phase = random.randint(0, 10)

        c_res = c_lib.check_phase_transition(current, next_phase)
        rust_res = rust_lib.rs_check_phase_transition(current, next_phase)

        if c_res != rust_res:
            print(
                f"❌ MISMATCH at {current} -> {next_phase}: C={c_res}, Rust={rust_res}"
            )
            mismatches += 1
            if mismatches > 10:
                print("Too many mismatches. Aborting.")
                break

    if mismatches == 0:
        print("STATUS: PASS (C and Rust implementations are 100% consistent)")
    else:
        print(f"STATUS: FAIL ({mismatches} mismatches found)")
        exit(1)


if __name__ == "__main__":
    fuzz_consistency()
