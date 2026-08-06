#!/usr/bin/env python3
import json
import statistics
import time
from pathlib import Path

from warm_logic.kernel.load_shedder import LoadShedder


def run_degradation_audit():
    print("Starting WarmLogic Degradation Audit...")
    ls = LoadShedder(80.0)
    history = []

    # Test cases: normal, spike, recovery
    test_latencies = [40.0, 50.0, 95.0, 110.0, 70.0, 40.0]

    for i, lat in enumerate(test_latencies):
        print(f"   Cycle {i}: Latency = {lat:.2f}μs")
        result = ls.execute_logic(lat)
        print(f"   Result: {result} [Mode: {ls.mode}]")
        history.append(
            {"cycle": i, "latency_us": lat, "mode": ls.mode, "result": result}
        )

    # Verify transition logic
    modes = [h["mode"] for h in history]
    if modes == ["HARD", "HARD", "LITE", "LITE", "HARD", "HARD"]:
        print("\nPASS: Load shedding and recovery logic verified.")
        verdict = "PASS"
    else:
        print("\nFAIL: Transition logic failure!")
        print(f"Modes: {modes}")
        verdict = "FAIL"

    # Save artifact
    artifact_path = Path("out/audit/degradation_report.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with open(artifact_path, "w") as f:
        json.dump({"history": history, "verdict": verdict}, f, indent=2)
    print(f"\nArtifact saved to {artifact_path}")


if __name__ == "__main__":
    run_degradation_audit()
