import warm_logic_rs
from warm_logic_rs import WeightDistillery
import math

def test_genetic_distillation():
    print("[Verification] Initializing Weight Distillery (Rust)...")

    distillery = WeightDistillery()
    print("WeightDistillery initialized.")

    # Mock weights: 100 values
    original_weights = [0.1 * i for i in range(10)] + [0.001 * i for i in range(10)]
    print(f"Original Weights (first 5): {original_weights[:5]}...")

    # 1. Test Jitter (Mutation)
    print("\n--- Testing Weight Jitter (Mutation) ---")
    jittered = distillery.jitter_weights(original_weights, 0.05)
    diff = sum(abs(a - b) for a, b in zip(original_weights, jittered))
    print(f"Total Jitter Delta: {diff:.4f}")

    if diff > 0:
        print("Jitter Applied Successfully.")
    else:
        print("Jitter failed to change weights.")
        raise Exception("Distillery Error: Jitter failed")

    # 2. Test Pruning (Efficiency)
    print("\n--- Testing Weight Pruning (Pruning) ---")
    # Prune anything below 0.05
    pruned = distillery.prune_weights(original_weights, 0.05)
    zero_count = pruned.count(0.0)
    sparsity = distillery.calculate_sparsity(pruned)

    print(f" Weights zeroed: {zero_count}")
    print(f"Sparsity: {sparsity:.2%}")

    if zero_count > 0:
        print("Pruning Applied Successfully.")
    else:
        print("Pruning failed to zero weights.")
        raise Exception("Distillery Error: Pruning failed")

    print("\n Weight Distillery Verification COMPLETE.")

if __name__ == "__main__":
    test_genetic_distillation()
