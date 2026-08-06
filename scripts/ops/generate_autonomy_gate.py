"""Generates the autonomy_gate.json for Mode 2 gated automatic patches."""

import argparse
import json
import os
import time


def generate_gate(
    run_id: str, drift_score: float, risk_score: float, tests_passed: bool
):
    """
    Evaluates safety metrics and emits an autonomy gate decision.
    """
    # Era 2 Safety Invariants:
    # 1. Drift must be < 0.1
    # 2. Risk must be < 0.5
    # 3. All tests must pass

    is_open = tests_passed and drift_score < 0.1 and risk_score < 0.5

    gate_data = {
        "run_id": run_id,
        "timestamp": time.time(),
        "autonomy_gate": is_open,
        "metrics": {
            "drift_score": drift_score,
            "risk_score": risk_score,
            "tests_passed": tests_passed,
        },
        "reason": "safe_thresholds_met" if is_open else "safety_threshold_violation",
    }

    output_path = "out/ct/autonomy_gate.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(gate_data, f, indent=2)

    print(f"Autonomy Gate Decision: {'OPEN' if is_open else 'CLOSED'} for {run_id}")
    print(f"   Saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--drift", type=float, default=0.0)
    parser.add_argument("--risk", type=float, default=0.0)
    parser.add_argument("--passed", action="store_true")

    args = parser.parse_args()
    generate_gate(args.run_id, args.drift, args.risk, args.passed)
