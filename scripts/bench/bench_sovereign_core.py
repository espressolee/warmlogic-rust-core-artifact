import asyncio
import logging
import os
import time
from pathlib import Path

from warm_logic.kernel.core.state_root import KernelPhase
from warm_logic.kernel.formal_runtime import FormalEvent, FormalInstructionPipeline
from warm_logic.kernel.security.ckms import SovereignKMS

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("SBS-Bench")


async def run_throughput_benchmark(iterations=100):
    """Measures transitions per second (TPS)."""
    pipeline = FormalInstructionPipeline("bench_run")
    event = FormalEvent(
        event_id="bench_id", prefix="P100", payload={}, trace_id="trace_id"
    )

    # Measure IPC only (Transition overhead)
    ipc_start = time.time()
    for _ in range(iterations):
        pipeline.enclave_bridge.request_transition(KernelPhase.AUTHORIZED)
    ipc_end = time.time()
    ipc_latency = (ipc_end - ipc_start) / iterations

    # Measure full step (with Sieve)
    full_start = time.time()
    for i in range(iterations):
        await pipeline.step_authorize(event)
    full_end = time.time()

    avg_latency = (full_end - full_start) / iterations
    tps = iterations / (full_end - full_start)
    return avg_latency, tps, ipc_latency


def run_rotation_benchmark(rotations=10):
    """Measures key rotation overhead."""
    kms = SovereignKMS()
    latencies = []

    for i in range(rotations):
        start = time.time()
        kms.rotate_keys()
        latencies.append(time.time() - start)

    return sum(latencies) / len(latencies)


async def main():
    print("INITIALIZING SOVEREIGN BENCHMARKING SUITE (SBS-1)")
    print("=" * 60)

    # 1. Throughput
    print("Metric 1: Formal Enforcement Throughput...")
    latency, tps, ipc_lat = await run_throughput_benchmark(50)
    print(f"   - Average Full Latency: {latency * 1000:.4f} ms")
    print(f"   - IPC Bridge Latency: {ipc_lat * 1000:.4f} ms")
    print(f"   - Full Throughput (TPS): {tps:.2f}")
    print(f"   - Potential IPC Throughput (TPS): {1 / ipc_lat:.2f}")

    # 2. Key Rotation
    print("Metric 2: Key Rotation Elasticity...")
    avg_rot_latency = run_rotation_benchmark(5)
    print(f"   - Average Rotation Latency: {avg_rot_latency * 1000:.4f} ms")

    # 3. Host-Independence Rigor (Simulated Tamper)
    print(" Metric 3: Host-Independence Rigor...")
    # Simulate a tamper event in a dummy file to avoid breaking the core
    dummy_file = Path("warm_logic/kernel/temp_bench_file.py")
    dummy_file.write_text("# Initial State")
    from warm_logic.security.pure_sieve import sieve

    sieve.generate_baseline(["warm_logic/kernel/temp_bench_file.py"])

    # Modify
    start_tamper = time.time()
    dummy_file.write_text("# TAMPERED STATE")
    time.sleep(0.6)  # Wait for background watcher (poll interval 500ms)
    is_valid = sieve.verify_runtime()
    end_tamper = time.time()

    print(f"   - Tamper Detection: {'SUCCESS' if not is_valid else 'FAILED'}")
    print(f"   - Verification Latency: {(end_tamper - start_tamper) * 1000:.4f} ms")

    os.remove(dummy_file)
    print("=" * 60)
    print("SBS-1 BENCHMARK COMPLETE.")


if __name__ == "__main__":
    asyncio.run(main())
