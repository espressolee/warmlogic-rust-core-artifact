import asyncio
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

try:
    from warm_logic_rs import (
        BFTEngine,
        Vote,
        generate_keypair,
        sign,
    )
except ImportError as e:
    print(f"CRITICAL: warm_logic_rs not available: {e}")
    sys.exit(1)


def sign_worker(sk, intent):
    return sign(sk, intent)


def bench_bft_batch(rounds: int = 1000, batch_size: int = 100, max_workers: int = 10):
    print(
        f"🚀 Benchmarking 5-Node BFT Consensus BATCH ({rounds} blocks, {batch_size} batch, {max_workers} workers)..."
    )

    # 1. Setup 5 Nodes
    nodes = [generate_keypair() for _ in range(5)]
    engine = BFTEngine(5)
    regions = ["US-EAST", "US-WEST", "EU-NORTH", "EU-SOUTH", "AP-SOUTH"]

    start_time = time.time()
    committed_total = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for b in range(0, rounds, batch_size):
            current_batch_size = min(batch_size, rounds - b)
            batch_votes = []

            # Prepare all signing tasks for the batch
            signing_tasks = []
            for r in range(current_batch_size):
                block_hash = f"block_{b + r}_{os.urandom(4).hex()}"
                intent = f"VOTE:{block_hash}:APPROVE"
                for i in range(5):
                    signing_tasks.append((nodes[i], block_hash, regions[i], intent))

            # Parallelize signing
            futures = [
                executor.submit(sign_worker, t[0][1], t[3]) for t in signing_tasks
            ]
            signatures = [f.result() for f in futures]

            # Create Vote objects
            votes = []
            for idx, sig in enumerate(signatures):
                node, block_hash, region, intent = signing_tasks[idx]
                votes.append(
                    Vote(block_hash, node[0], region, "APPROVE", sig, time.time())
                )

            # Submit batch to Rust (where it's parallelly verified)
            committed_in_batch = engine.submit_votes_batch(votes)
            committed_total += committed_in_batch

    end_time = time.time()
    duration = end_time - start_time
    tps = rounds / duration

    print(f"   [Consensus] Batch Parallel Producer w/ ML-DSA-65 + Rayon Verify")
    print(f"   Total Time: {duration:.4f}s")
    print(f"   Throughput: {tps:.2f} blocks/sec")
    print(f"   Latency:    {1000 / tps:.2f} ms/block")

    if committed_total < rounds:
        print(f"WARNING: Only committed {committed_total}/{rounds} blocks!")


if __name__ == "__main__":
    # Increased rounds to 1000 to see sustained throughput
    bench_bft_batch(1000, batch_size=100, max_workers=10)
