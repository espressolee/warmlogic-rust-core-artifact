"""
SBS-1 Metric 4: Recovery Integrity.
Simulates bit-rot in a sharded ledger and verifies reconstruction.
"""

import copy
import logging
import time

from warm_logic.mesh.scribe.sharded_ledger import ShardLedger
from warm_logic.resilience.reconstruct import StateReconstructor

# Configure logging for clinical precision
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("SBS-Metric-4")


def run_recovery_benchmark():
    print("\n--- Metric 4: Recovery Integrity (Era 54) ---")

    # 1. Setup Ledger and Peer
    shard_id = "0a"
    main_ledger = ShardLedger(shard_id)
    peer_ledger = ShardLedger(shard_id)

    # Populate chain
    print(f"Initializing ledger with 10 blocks...")
    for i in range(10):
        events = [{"action": "STRESS_LOAD", "val": i}]
        block = main_ledger.add_block(events, f"SIG_{i}")
        # Clone to peer for redundancy (DEEP COPY to ensure independence)
        peer_ledger.chain.append(copy.deepcopy(block))

    # 2. Simulate Bit-Rot (Tamper)
    tamper_index = 5
    print(f" TAMPERING: Mutating Block {tamper_index} events...")
    # Directly mutate data to bypass ShardLedger.add_block validation
    main_ledger.chain[tamper_index].events[0]["action"] = "CORRUPTED_DATA"

    # 3. Detection
    t0 = time.perf_counter()
    corrupted = StateReconstructor.detect_bit_rot(main_ledger)
    t_detect = (time.perf_counter() - t0) * 1000

    if corrupted == [tamper_index]:
        print(f"Detection: SUCCESS (Found index {corrupted} in {t_detect:.4f} ms)")
    else:
        print(f"Detection: FAILED (Found {corrupted})")
        return

    # 4. Reconstruction
    t1 = time.perf_counter()
    repair_package = StateReconstructor.request_repair_package(
        tamper_index, [peer_ledger]
    )

    if repair_package:
        success = StateReconstructor.apply_repair(main_ledger, repair_package)
        t_repair = (time.perf_counter() - t1) * 1000

        if success:
            print(f"Reconstruction: SUCCESS (Completed in {t_repair:.4f} ms)")
        else:
            print("Reconstruction: FAILED to apply repair.")
            return
    else:
        print("Reconstruction: FAILED to find repair package.")
        return

    # 5. Final Verification
    final_check = StateReconstructor.detect_bit_rot(main_ledger)
    if not final_check:
        print(" Final Integrity: SCENARIO OK (not verification) (Zero corrupted blocks)")
        print(f"Result: PASS (Total Recovery Time: {t_detect + t_repair:.4f} ms)")
    else:
        print(f"Final Verification: FAILED (Residual corruption at {final_check})")


if __name__ == "__main__":
    run_recovery_benchmark()
