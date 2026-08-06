""" Federation Benchmark
Simulates 1,000 nodes reaching consensus on a new Block Root.
Target: Convergence in < 2.0s
"""

import sys
import time
from pathlib import Path

# Path setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from warm_logic.kernel.mesh.p2p_federation import FederationNetwork


def run_federation_benchmark():
    print("\n--- P2P Federation Scale Test ---")

    NODE_COUNT = 1000
    print(f"Initializing {NODE_COUNT} Sovereign Nodes...")
    t_init = time.perf_counter()
    network = FederationNetwork(size=NODE_COUNT)
    print(f"Mesh Topology Built in {time.perf_counter() - t_init:.4f}s")

    # TEST 1: CONSENSUS PROPAGATION
    target_root = "ROOT_BLOCK_8A7F"
    print(f"\nBroadcasting New Block Root: {target_root}")

    t_start = time.perf_counter()
    network.broadcast_event(0, f"NEW_ROOT:{target_root}")

    ticks = 0
    converged = False

    while ticks < 50:  # Max ticks
        msgs = network.tick()
        coverage = network.consensus_reached(target_root)
        ticks += 1
        print(f"   Tick {ticks}: {msgs} msgs sent | Coverage: {coverage * 100:.1f}%")

        if coverage >= 0.99:  # 99% Consensus
            converged = True
            break

    t_end = time.perf_counter()
    duration = t_end - t_start

    if converged:
        print(f"Consensus Reached in {duration:.4f}s ({ticks} ticks)")
        if duration < 2.0:
            print("PERF: < 2.0s Goal MET")
        else:
            print("PERF: > 2.0s (Optimization Required)")
    else:
        print("FAIL: Did not reach 99% consensus.")
        sys.exit(1)

    # TEST 2: SOVEREIGN ALARM (LOCKDOWN)
    print(f"\nBroadcasting SOVEREIGN_ALARM (Mesh Lockdown)")
    t_start = time.perf_counter()
    network.broadcast_event(500, "SOVEREIGN_ALARM")  # Start from middle

    ticks = 0
    locked = False
    while ticks < 20:
        network.tick()
        coverage = network.lockdown_reached()
        ticks += 1

        if coverage >= 0.99:
            locked = True
            break

    duration = time.perf_counter() - t_start
    if locked:
        print(f"Mesh Lockdown in {duration:.4f}s")
    else:
        print("FAIL: Lockdown propagation too slow.")
        sys.exit(1)


if __name__ == "__main__":
    run_federation_benchmark()
