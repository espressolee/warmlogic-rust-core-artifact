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


def bench_bft_kernel_limit(rounds: int = 5000, batch_size: int = 500):
    print(f"🚀 Measuring KERNEL LIMIT (BFT 5-Node, {rounds} blocks)...")

    # 1. Setup 5 Nodes
    nodes = [generate_keypair() for _ in range(5)]
    engine = BFTEngine(5)
    regions = ["US-EAST", "US-WEST", "EU-NORTH", "EU-SOUTH", "AP-SOUTH"]

    # 2. Pre-sign all votes (Offline)
    print(f"   - Pre-signing {rounds * 5} votes (this may take a moment)...")
    all_votes = []

    # We'll use 10 workers for pre-signing to speed it up
    with ProcessPoolExecutor(max_workers=10) as executor:
        for b in range(0, rounds, batch_size):
            current_batch_size = min(batch_size, rounds - b)
            batch_tasks = []
            for r in range(current_batch_size):
                block_hash = f"block_{b + r}"
                intent = f"VOTE:{block_hash}:APPROVE"
                for i in range(5):
                    batch_tasks.append((nodes[i], block_hash, regions[i], intent))

            futures = [executor.submit(sign_worker, t[0][1], t[3]) for t in batch_tasks]
            sigs = [f.result() for f in futures]

            for idx, sig in enumerate(sigs):
                t = batch_tasks[idx]
                all_votes.append(Vote(t[1], t[0][0], t[2], "APPROVE", sig, 0.0))

    print(f"   - Starting Kernel Internal Benchmark...")
    start_time = time.time()

    # Submit in batches to Rust
    committed_total = 0
    for i in range(0, len(all_votes), batch_size * 5):
        batch = all_votes[i : i + batch_size * 5]
        committed_total += engine.submit_votes_batch(batch)

    end_time = time.time()
    duration = end_time - start_time
    tps = rounds / duration

    print(f"   [Kernel Limit] Pre-signed ML-DSA-65 + Rayon Verify")
    print(f"   Total Time: {duration:.4f}s")
    print(f"   Throughput: {tps:.2f} blocks/sec")
    print(f"   Latency:    {1000 / tps:.2f} ms/block")

    if committed_total != rounds:
        print(f"WARNING: Only committed {committed_total}/{rounds} blocks!")


if __name__ == "__main__":
    bench_bft_kernel_limit(rounds=1000, batch_size=200)
