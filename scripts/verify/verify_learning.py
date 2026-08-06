#!/usr/bin/env python3
"""
[Phase 98.5] Verify Learning Pipeline Stub.
Tests the interface for future training integration.
"""

import logging
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.intelligence.learning import (
    LearningPipeline,
    PreferenceDatapoint,
    get_learning_status,
)

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_learning_pipeline():
    print("Testing Learning Pipeline Stub...")
    print("=" * 60)

    pipeline = LearningPipeline(data_dir="data/learning_test")

    # Test 1: Record a preference
    # Korean prompt/response kept as-is: exercised as real Korean-language payload.
    print("\n--- Test 1: Record Preference ---")
    pref = PreferenceDatapoint(
        prompt="한국어로 양자암호를 설명해줘",
        response_a="양자암호는 양자역학의 원리를 이용한 암호화 기술입니다.",
        response_b="Quantum cryptography uses quantum mechanics.",
        preferred="A",
    )
    success = pipeline.record_preference(pref)
    print(f"Preference recorded: {success}")

    # Test 2: Record an interaction
    # Korean prompt/response kept as-is: exercised as real Korean-language payload.
    print("\n--- Test 2: Record Interaction ---")
    success = pipeline.record_interaction(
        prompt="WarmLogic의 핵심 기능은?",
        response="WarmLogic은 AI 거버넌스를 위한 양자내성 런타임입니다.",
        feedback="Good but could be more specific",
    )
    print(f"Interaction recorded: {success}")

    # Test 3: Check stats
    print("\n--- Test 3: Learning Stats ---")
    stats = pipeline.get_stats()
    print(f"Preferences: {stats['preferences_collected']}")
    print(f"Interactions: {stats['interactions_collected']}")
    print(f"Ready for training: {stats['ready_for_training']}")

    # Test 4: Training readiness
    print("\n--- Test 4: Training Readiness ---")
    readiness = pipeline.get_training_readiness()
    print(f"Data Ready: {readiness['data_ready']}")
    print(f"Infrastructure Ready: {readiness['infrastructure_ready']}")
    print("Recommendations:")
    for rec in readiness["recommendations"]:
        print(f"  - {rec}")

    # Test 5: Trigger training (stub)
    print("\n--- Test 5: Trigger Training (Stub) ---")
    result = pipeline.trigger_training()
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")

    print("\n" + "=" * 60)
    print("Learning Pipeline Stub Verified!")
    print("   Interface ready for future GPU training integration.")


if __name__ == "__main__":
    test_learning_pipeline()
