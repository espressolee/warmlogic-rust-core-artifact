import json
import random
import time
from datetime import datetime

from warm_logic.kernel.ops.metrics import SystemMetrics


def generate_mock_logs(count: int):
    logs = []
    statuses = ["applied", "rollback", "failed", "ok"]
    origins = ["agent", "human", "system"]
    reasons = ["ci failed", "logic error", "review", "test failed"]

    for i in range(count):
        log = {
            "status": random.choice(statuses),
            "origin": random.choice(origins),
            "ts": datetime.utcnow().isoformat(),
            "id": f"patch_{i}",
            "meta": {"requires_human": random.random() < 0.1},
        }
        if log["status"] == "failed":
            log["detail"] = {"reason": random.choice(reasons)}
        logs.append(log)
    return logs


def verify_velocity():
    print("Starting High-Velocity Telemetry Verification")
    TARGET_OPS = 100000
    TARGET_TIME = 1.0

    print(f"Generating {TARGET_OPS} mock records...")
    gen_start = time.perf_counter()
    records = generate_mock_logs(TARGET_OPS)
    gen_time = time.perf_counter() - gen_start
    print(f"   Generation took: {gen_time:.4f}s")

    metrics = SystemMetrics()

    print("Ingesting Batch...")
    start_time = time.perf_counter()
    report = metrics.ingest_batch(records)
    end_time = time.perf_counter()

    duration = end_time - start_time
    ops_sec = TARGET_OPS / duration

    print(f"   Report Statistics: {report.sample_size} records processed")
    print(f"   Success Rate (Agent): {report.success_rate_by_source.get('agent', 0.0)}")
    print(f"⏱ Duration: {duration:.4f}s")
    print(f"Throughput: {ops_sec:.2f} ops/sec")

    if duration > TARGET_TIME:
        print(f"FAIL: Velocity too low (> {TARGET_TIME}s)")
        print(
            "   Optimization required in metrics.py or build_patch_efficiency_report."
        )
        exit(1)
    else:
        print("PASS: High-Velocity Telemetry Confirmed.")


if __name__ == "__main__":
    verify_velocity()
