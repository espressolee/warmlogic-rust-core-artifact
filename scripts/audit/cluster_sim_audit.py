#!/usr/bin/env python3
import json
import random
import statistics
import time
from pathlib import Path


class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.clock = 0
        self.state_hash = 0

    def process_event(self, external_clock=None):
        # Lamport Clock Update
        if external_clock is not None:
            # Sync to received clock
            self.clock = max(self.clock, external_clock)
        else:
            # Local event increment
            self.clock += 1
        # State Hash simulation
        self.state_hash = hash((self.state_hash, self.clock))
        return self.clock


def simulate_cluster(node_count=3, cycles=100):
    nodes = [Node(i) for i in range(node_count)]
    latencies = []

    print(
        f"🌐 Starting Cluster Scalability Audit: {node_count} Nodes, {cycles} Cycles..."
    )

    for c in range(cycles):
        start = time.perf_counter()

        # 1. Randomized Leader Election (Mock)
        leader_idx = random.randint(0, node_count - 1)
        leader = nodes[leader_idx]

        # 2. Leader tick
        msg_clock = leader.process_event()

        # 3. Broadcast and Sync (O(N))
        for i, node in enumerate(nodes):
            if i != leader_idx:
                node.process_event(msg_clock)

        # 4. Verify Convergence (All clocks should be identical at end of round)
        clocks = [n.clock for n in nodes]
        if len(set(clocks)) != 1:
            raise RuntimeError(f"Convergence Failure at cycle {c}: {clocks}")

        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # ms

    return latencies


def run_scalability_audit():
    # Test Scaling O(N)
    results_3 = simulate_cluster(3, 1000)
    results_10 = simulate_cluster(10, 1000)

    avg_3 = statistics.mean(results_3)
    avg_10 = statistics.mean(results_10)

    print(f"\nCluster Scalability Results:")
    print(f"   - 3 Nodes Avg Latency: {avg_3:.4f}ms")
    print(f"   - 10 Nodes Avg Latency: {avg_10:.4f}ms")

    # Check linear scaling bound (should not explode exponentially)
    scaling_ratio = avg_10 / avg_3
    print(f"   - Scaling Ratio (10/3): {scaling_ratio:.2f}x")

    EXPECTED_MAX_RATIO = 5.0  # Loose bound for simulated overhead
    if scaling_ratio < EXPECTED_MAX_RATIO:
        print(f"PASS: Scaling behavior is within O(N) bounds.")
        verdict = "PASS"
    else:
        print(f"FAIL: Scaling behavior exceeded O(N) expectations!")
        verdict = "FAIL"

    # Save artifact
    artifact_path = Path("out/audit/scalability_report.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with open(artifact_path, "w") as f:
        json.dump(
            {
                "avg_3_nodes_ms": avg_3,
                "avg_10_nodes_ms": avg_10,
                "scaling_ratio": scaling_ratio,
                "verdict": verdict,
            },
            f,
            indent=2,
        )
    print(f"\nArtifact saved to {artifact_path}")


if __name__ == "__main__":
    run_scalability_audit()
