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


def bench_bft_parallel(rounds: int = 100, max_workers: int = 8):
    print(
        f"🚀 Benchmarking 5-Node BFT Consensus ({rounds} rounds, {max_workers} workers)..."
    )

    # 1. Setup 5 Nodes
    nodes = [generate_keypair() for _ in range(5)]
    engine = BFTEngine(5)
    regions = ["US-EAST", "US-WEST", "EU-NORTH", "EU-SOUTH", "AP-SOUTH"]

    start_time = time.time()
    committed_count = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for r in range(rounds):
            block_hash = f"block_{r}_{os.urandom(4).hex()}"
            intent = f"VOTE:{block_hash}:APPROVE"

            # Parallelize signing for the 5 nodes
            futures = [
                executor.submit(sign_worker, nodes[i][1], intent) for i in range(5)
            ]
            signatures = [f.result() for f in futures]

            for i in range(5):
                pk, _ = nodes[i]
                # Vote signature: (block_hash, voter_id, region, decision, signature, timestamp)
                v = Vote(
                    block_hash, pk, regions[i], "APPROVE", signatures[i], time.time()
                )

                if engine.submit_vote(v):
                    if engine.is_committed(block_hash):
                        committed_count += 1
                        break

    end_time = time.time()
    duration = end_time - start_time
    tps = rounds / duration

    print(f"   [Consensus] Parallel Producer w/ ML-DSA-65")
    print(f"   Total Time: {duration:.4f}s")
    print(f"   Throughput: {tps:.2f} blocks/sec")
    print(f"   Latency:    {1000 / tps:.2f} ms/block")

    if committed_count != rounds:
        print(f"WARNING: Only committed {committed_count}/{rounds} blocks!")


if __name__ == "__main__":
    bench_bft_parallel(100, max_workers=10)
