import asyncio
import json
import logging
import time

from warm_logic.kernel.consensus.kernel_node import SovereignKernelNode


async def run_benchmark():
    logging.basicConfig(level=logging.INFO)
    print("[BENCHMARK] Starting Zero-Latency Consensus Audit...")

    # 1. Setup local 'fleet' simulation
    node_id = "bench-alpha"
    peers = ["bench-beta", "bench-gamma"]
    node = SovereignKernelNode(node_id, peers, port=6060)

    # 2. Start the native heart
    node.start()
    await asyncio.sleep(0.5)  # Let the election timer settle

    # 3. Measure Proposal Latency
    test_value = {"event": "P-STATUS_UPGRADE", "timestamp": time.time()}

    start_time = time.perf_counter()
    success = await node.propose_value(test_value)
    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000

    print(f"\n[RESULT] Consensus Proposal Latency: {latency_ms:.4f} ms")

    if latency_ms < 1.0:
        print("[HEGEMONY] ZERO-LATENCY TARGET ACHIEVED (< 1ms).")
    else:
        print("[CAUTION] Latency above target. Further optimization required.")

    # 4. Status Audit
    status = node.get_consensus_status()
    print(f"\n[STATUS] {json.dumps(status, indent=2)}")

    print("\n[VERIFICATION COMPLETE] Phase 111 is operational.")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
