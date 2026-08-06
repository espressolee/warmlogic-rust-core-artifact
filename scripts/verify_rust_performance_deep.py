import os
import shutil
import sys
import threading
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


def run_benchmark():
    print("Starting Deep Performance Verification for +")

    db_path = "/tmp/bench_deep_sled"
    if os.path.exists(db_path):
        try:
            shutil.rmtree(db_path)
            print(f"Cleaned up {db_path}")
        except Exception as e:
            print(f"Failed to cleanup {db_path}: {e}")

    # 1. Throughput & Copy Overhead Test
    print("\n--- Phase 1: Throughput & Copy Overhead (String Copy) ---")
    sizes = [1024, 1024 * 1024, 5 * 1024 * 1024]  # 1KB, 1MB, 5MB

    ledger = warm_logic_rs.RustReplicatedLedger(db_path)

    for size in sizes:
        payload = "A" * size  # Python String

        start = time.perf_counter()
        # We start a transaction with a generic payload (simulated by signature field for now)
        ledger.submit_transaction("id", "src", "dst", 100, payload, 0.0)
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"Payload: {size / 1024:.2f} KB | Latency: {duration_ms:.4f} ms")

    # 2. GIL Blocking Test
    print("\n--- Phase 2: GIL Blocking Analysis ---")

    # Flood with transactions to make mining slow
    for i in range(10000):
        ledger.submit_transaction(f"tx_{i}", "A", "B", 1, "sig", 0.0)

    timestamps = []
    stop_event = threading.Event()

    def ticker():
        while not stop_event.is_set():
            timestamps.append(time.perf_counter())
            time.sleep(0.005)  # 5ms sleep

    t_ticker = threading.Thread(target=ticker)
    t_ticker.start()

    # Trigger heavy Rust operation
    print(" Rust Mining (Heavy Op)...")
    start_mine = time.perf_counter()
    try:
        ledger.mine_block("MINER")
    except Exception as e:
        print(f"Mining failed: {e}")
    end_mine = time.perf_counter()

    stop_event.set()
    t_ticker.join()

    # Analyze gaps
    max_gap = 0
    if len(timestamps) > 1:
        gaps = [t2 - t1 for t1, t2 in zip(timestamps, timestamps[1:])]
        max_gap = max(gaps) * 1000

    print(f"⏱ Max Python Thread Gap: {max_gap:.2f} ms")

    if max_gap > 35:
        print("GIL BLOCKED: Python thread was starved during Rust execution.")
    else:
        print("GIL RELEASED: Python thread ran concurrently.")

    # 3. O(1) Zero-Copy Test
    print("\n--- Phase 3: Zero-Copy O(1) Verification ---")

    # We test with minimal allocation to avoid OOM
    zc_sizes = [1024 * 1024, 2 * 1024 * 1024, 5 * 1024 * 1024]

    try:
        for size in zc_sizes:
            data = bytearray(size)
            start = time.perf_counter()
            res = warm_logic_rs.benchmark_zero_copy(data)
            end = time.perf_counter()

            if res != size:
                print(f"Size mismatch: expected {size}, got {res}")

            duration_ms = (end - start) * 1000
            print(
                f"⚡ Payload: {size / 1024 / 1024:.0f} MB | Latency: {duration_ms:.4f} ms"
            )

            if duration_ms > 0.05:
                print(f"    Latency > 0.05ms. Is it truly zero-copy?")
            else:
                print(f"   O(1) Access Confirmed")

    except AttributeError:
        print("benchmark_zero_copy not found in module. Did you rebuild?")
    except Exception as e:
        print(f"Zero-Copy Test Failed: {e}")


if __name__ == "__main__":
    run_benchmark()
