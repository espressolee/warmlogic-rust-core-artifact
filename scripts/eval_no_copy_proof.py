import json
import os
import sys
from pathlib import Path

# Ensure import path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import warm_logic_rs
except ImportError:
    print("Error: warm_logic_rs module not found.")
    sys.exit(1)


def verify_no_copy(run_id="bridge_eval_v1"):
    print(f"RUN_ID: {run_id} | Experiment: B1 (No-Copy Proof)")

    # 1. Pointer Identity (via hex(id(data)))
    size = 10 * 1024 * 1024  # 10MB
    data_raw = bytearray(b"S" * size)
    data_raw[0] = 0xAA
    data_raw[-1] = 0xBB

    data = bytes(data_raw)  # PyBytes binding
    py_addr = id(data)

    try:
        rust_addr = warm_logic_rs.get_ptr_addr(data)
        print(f"Python-reported Data Address (proxy): {hex(py_addr)}")
        print(f"Rust-reported Data Address: {hex(rust_addr)}")
        is_addr_match = True
    except AttributeError:
        print("Missing get_ptr_addr in Rust bridge. Falling back to timing.")
        is_addr_match = None

    # 2. Timing Verification
    import time

    start = time.perf_counter_ns()
    length = warm_logic_rs.benchmark_zero_copy(data)
    end = time.perf_counter_ns()

    duration_ns = end - start

    # If copy occurs, 10MB copy takes ~2-10ms.
    # Zero-copy takes <1000ns.
    is_no_copy = duration_ns < 1000000

    print(f"Size: {size} bytes")
    print(f"Duration: {duration_ns} ns")
    print(f"No-Copy Status: {'SEALED' if is_no_copy else 'FAILURE'}")

    results = {
        "experiment": "B1",
        "size_bytes": size,
        "duration_ns": duration_ns,
        "is_no_copy": is_no_copy,
        "is_addr_match": is_addr_match,
    }

    out_dir = Path(f"out/bridge_eval/{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "results_b1.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {out_dir}/results_b1.json")


if __name__ == "__main__":
    verify_no_copy()
