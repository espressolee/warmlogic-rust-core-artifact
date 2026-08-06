import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

try:
    from warm_logic_rs import BFTEngine, Vote, generate_keypair, sign
except ImportError as e:
    print(f"CRITICAL: warm_logic_rs not available: {e}")
    sys.exit(1)


def bench_bft(rounds: int = 200):
    print(f"🚀 Benchmarking 5-Node BFT Consensus ({rounds} rounds, Parallel Sign)...")

    # 1. Setup 5 Nodes (Key Generation)
    print("   Generating 5 PQC Identity Keypairs...")
    nodes = []
    for i in range(5):
        pk, sk = generate_keypair()
        nodes.append((pk, sk))

    # 2. Engine Setup
    engine = BFTEngine(5)
    engine.set_min_regions(2)
    regions = ["US-EAST", "US-WEST", "EU-NORTH", "EU-SOUTH", "AP-SOUTH"]

    start_time = time.time()
    committed_count = 0

    def sign_single_vote(args):
        i, sk, block_hash, decision = args
        intent = f"VOTE:{block_hash}:{decision}"
        # This now releases GIL in Rust!
        sig = sign(sk, intent)
        return i, sig

    with ThreadPoolExecutor(max_workers=5) as executor:
        for r in range(rounds):
            block_hash = f"block_{r}_{os.urandom(4).hex()}"
            decision = "APPROVE"

            # Map signing to threads
            sign_tasks = [(i, nodes[i][1], block_hash, decision) for i in range(5)]
            results = list(executor.map(sign_single_vote, sign_tasks))

            # Submit to engine (Sequential verification)
            for i, sig in results:
                pk = nodes[i][0]
                v = Vote(
                    block_hash=block_hash,
                    voter_id=pk,
                    region=regions[i],
                    decision=decision,
                    signature=sig,
                    timestamp=time.time(),
                )
                if engine.submit_vote(v):
                    committed_count += 1
                    break

    end_time = time.time()
    duration = end_time - start_time
    tps = rounds / duration

    print(f"   [Consensus] w/ Parallel ML-DSA-65 Signatures")
    print(f"   Total Time: {duration:.4f}s")
    print(f"   Throughput: {tps:.2f} blocks/sec")
    print(f"   Latency:    {1000 / tps:.2f} ms/block")

    if committed_count != rounds:
        print(f"WARNING: Only committed {committed_count}/{rounds} blocks!")


if __name__ == "__main__":
    bench_bft(200)
