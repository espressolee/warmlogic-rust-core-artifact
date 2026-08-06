import shutil
import time
from pathlib import Path

from warm_logic.kernel import rust_loader


def bench_atomic_storage():
    if not rust_loader.HAS_RUST_CORE:
        print("Rust Core not available. Skipping Benchmark.")
        return

    rs = rust_loader.load_rust_core()
    test_dir = Path("/tmp/bench_atomic_store")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)

    db_path = str(test_dir / "bench.sled")
    store = rs.SovereignStore(db_path)

    print(f"🔥 Starting Atomic Batch Benchmark on Sled @ {db_path}")

    start_time = time.time()
    BATCH_SIZE = 1000
    NUM_BATCHES = 100

    for b in range(NUM_BATCHES):
        batch = rs.SovereignBatch()
        for i in range(BATCH_SIZE):
            key = f"key_{b}_{i}".encode()
            val = b"x" * 100  # 100 bytes
            batch.insert(key, val)
        store.apply_batch(batch)

    duration = time.time() - start_time
    total_ops = BATCH_SIZE * NUM_BATCHES
    ops_sec = total_ops / duration

    print(f"✅ Completed {total_ops} ops in {duration:.4f}s")
    print(f"🚀 Throughput: {ops_sec:.2f} IOPS (Atomic Batched)")

    shutil.rmtree(test_dir)


if __name__ == "__main__":
    bench_atomic_storage()
