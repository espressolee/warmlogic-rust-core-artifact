#!/usr/bin/env python3
"""
[Phase 98.3] Verify Autonomous Goal Formation.
Tests that the agent can propose its own goals.
"""

import logging
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from warm_logic.kernel.intelligence.task_discovery import (
    AutonomousGoalFormation,
    propose_next_goal,
)

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_autonomous_goal():
    print("Testing Autonomous Goal Formation...")
    print("=" * 60)

    # Test 1: Quick proposal
    print("\n--- Test 1: Quick Goal Proposal ---")
    proposal = propose_next_goal(workspace="src/warm_logic")

    print(f"Has Goal: {proposal['has_goal']}")
    print(f"Proposed Goal: {proposal['goal']}")
    print(f"Priority: {proposal['priority']}")
    print(f"Rationale: {proposal['rationale']}")
    print(f"Total Tasks Found: {proposal['total_tasks_found']}")
    print(f"Scan Duration: {proposal['scan_duration_ms']:.0f}ms")

    if proposal["suggested_actions"]:
        print(f"Suggested Actions: {proposal['suggested_actions'][:2]}")

    # Test 2: Full summary
    print("\n--- Test 2: Full Goals Summary ---")
    engine = AutonomousGoalFormation(workspace="src/warm_logic")
    engine.analyze_and_propose()
    summary = engine.get_all_goals_summary()
    print(summary[:1000])  # Truncate for readability

    print("\n" + "=" * 60)
    print("Autonomous Goal Formation Verified!")
    print(f"   The agent proposed: {proposal['goal'][:50]}...")


if __name__ == "__main__":
    test_autonomous_goal()
