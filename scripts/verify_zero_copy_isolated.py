import os
import sys
import time
from pathlib import Path

# Fix Path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError:
    print("Failed to import warm_logic_rs")
    sys.exit(1)


def run_isolated_benchmark():
    print("Starting Isolated Zero-Copy O(1) Verification")
    print("ℹ Skipping Sled DB initialization to avoid OOM")

    # We test [1MB, 5MB, 10MB] - strictly measuring bridge overhead
    # In O(1), latency should be identical regardless of size (approx 0.002ms)
    # The only diff is allocation time (which we exclude)

    zc_sizes = [1024 * 1024, 5 * 1024 * 1024, 10 * 1024 * 1024]  # 1MB, 5MB, 10MB

    try:
        for size in zc_sizes:
            # Allocate only - excluded from timing
            data = bytearray(size)

            # Warm up
            warm_logic_rs.benchmark_zero_copy(data)

            start = time.perf_counter()
            # Call the zero-copy function
            res = warm_logic_rs.benchmark_zero_copy(data)
            end = time.perf_counter()

            duration_ms = (end - start) * 1000

            if res != size:
                print(f"Size mismatch: expected {size}, got {res}")

            print(
                f"⚡ Payload: {size / 1024 / 1024:.0f} MB | Latency: {duration_ms:.4f} ms"
            )

            if duration_ms > 0.05:
                print(f"    Latency > 0.05ms.")
            else:
                print(f"   O(1) Access verified")

            # Explicit cleanup
            del data

    except AttributeError:
        print("benchmark_zero_copy not found in module.")
    except Exception as e:
        print(f"Test Failed: {e}")


if __name__ == "__main__":
    run_isolated_benchmark()
