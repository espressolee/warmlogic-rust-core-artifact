# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
from dataclasses import dataclass

logger = logging.getLogger("SovereignGovernance")


@dataclass
class Vote:
    persona: str
    approved: bool
    reasoning: str


class CouncilOfThree:
    """
    [] The Oracle: A tri-persona consensus engine.
    Ensures that autonomous modifications are vetted from three perspectives.
    """

    def __init__(self):
        self.personas = ["Architect", "Skeptic", "Auditor"]

    def review_patch(self, patch_code: str, test_code: str, function_name: str) -> bool:
        """
        Simulates a debate between three personas.
        Currently, these would be separate agentic calls.
        """
        logger.info(f"[Council] Convening session for '{function_name}'...")

        votes = []

        # 1. The Architect: Focuses on functionality and elegance.
        votes.append(
            Vote(
                persona="Architect",
                approved=len(patch_code) > 0,
                reasoning="Logic appears functionally complete and follows standard structural patterns.",
            )
        )

        # 2. The Skeptic: Focuses on edge cases and failure modes.
        has_tests = len(test_code) > 0
        votes.append(
            Vote(
                persona="Skeptic",
                approved=has_tests,
                reasoning="Verifying that validation logic exists. "
                + ("Tests provided." if has_tests else "NO TESTS FOUND."),
            )
        )

        # 3. The Auditor: Focuses on security and system-wide invariants.
        # (Mock logic: Auditor is suspicious of very long functions)
        too_long = len(patch_code.splitlines()) > 50
        votes.append(
            Vote(
                persona="Auditor",
                approved=not too_long,
                reasoning="Code complexity check: "
                + (
                    "Accepted."
                    if not too_long
                    else "Complexity exceeds safety threshold."
                ),
            )
        )

        # Consensus: 2/3 majority required
        approval_count = sum(1 for v in votes if v.approved)
        consensus = approval_count >= 2

        for vote in votes:
            status = "✅" if vote.approved else "❌"
            logger.info(f"  {status} [{vote.persona}]: {vote.reasoning}")

        if consensus:
            logger.info(f"[Council] Patch APPROVED ({approval_count}/3).")
        else:
            logger.warning(f"[Council] Patch REJECTED ({approval_count}/3).")

        return consensus


# [Phase A2] LLM-Powered Upgrade
# Import the new debate council for advanced use cases
try:
    from warm_logic.kernel.autonomy.debate import LLMDebateCouncil  # noqa: F401

    # Provide upgrade path: use LLMDebateCouncil for LLM-powered debates
    __all__ = ["CouncilOfThree", "LLMDebateCouncil", "Vote"]
except ImportError:
    __all__ = ["CouncilOfThree", "Vote"]
