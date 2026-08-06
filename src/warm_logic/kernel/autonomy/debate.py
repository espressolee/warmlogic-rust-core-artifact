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
"""
[Phase A2: Agent ] LLM-Powered Multi-Agent Debate Council.
Upgrades CouncilOfThree from rule-based to LLM-powered reasoning.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SovereignDebate")


@dataclass
class AgentPersona:
    """Defines an agent's role and perspective."""

    name: str
    role: str
    system_prompt: str
    focus_areas: List[str] = field(default_factory=list)


@dataclass
class DebateRound:
    """A single round of debate."""

    persona: str
    stance: str  # "APPROVE", "REJECT", "ABSTAIN"
    reasoning: str
    confidence: float  # 0.0 to 1.0


@dataclass
class DebateResult:
    """Final outcome of a multi-agent debate."""

    approved: bool
    rounds: List[DebateRound]
    consensus_score: float  # 0.0 to 1.0
    summary: str


# Default personas for code review
DEFAULT_PERSONAS = [
    AgentPersona(
        name="Architect",
        role="System Designer",
        system_prompt="""You are the Architect, focused on:
- Code structure and design patterns
- Maintainability and extensibility
- Alignment with system architecture

Evaluate the proposed change from a design perspective.
Output your decision as JSON: {"stance": "APPROVE|REJECT", "reasoning": "...", "confidence": 0.0-1.0}""",
        focus_areas=["structure", "patterns", "scalability"],
    ),
    AgentPersona(
        name="Skeptic",
        role="Devil's Advocate",
        system_prompt="""You are the Skeptic, focused on:
- Edge cases and failure modes
- Missing error handling
- Security vulnerabilities
- Unintended side effects

Challenge the proposed change aggressively.
Output your decision as JSON: {"stance": "APPROVE|REJECT", "reasoning": "...", "confidence": 0.0-1.0}""",
        focus_areas=["edge_cases", "security", "failure_modes"],
    ),
    AgentPersona(
        name="Auditor",
        role="Compliance Officer",
        system_prompt="""You are the Auditor, focused on:
- Code complexity and readability
- Test coverage requirements
- Documentation completeness
- Safety invariant preservation

Ensure the change meets quality standards.
Output your decision as JSON: {"stance": "APPROVE|REJECT", "reasoning": "...", "confidence": 0.0-1.0}""",
        focus_areas=["complexity", "testing", "documentation"],
    ),
]


class LLMDebateCouncil:
    """
    [] LLM-Powered Multi-Agent Debate Council.

    Conducts actual debates between agent personas using an LLM backend.
    Falls back to rule-based logic if LLM is unavailable.
    """

    def __init__(
        self,
        personas: Optional[List[AgentPersona]] = None,
        llm_client: Optional[Any] = None,
        require_unanimous: bool = False,
    ):
        self.personas = personas or DEFAULT_PERSONAS
        self.llm_client = llm_client
        self.require_unanimous = require_unanimous
        self._debate_history: List[DebateResult] = []

    def _get_llm_client(self):
        """Lazy load LLM client."""
        if self.llm_client is None:
            try:
                from warm_logic.kernel.intelligence.llm_bridge import (
                    LocalInferenceClient,
                )

                self.llm_client = LocalInferenceClient()
            except ImportError:
                logger.warning("LLM client unavailable, using rule-based fallback")
                return None
        return self.llm_client

    def _query_persona(
        self,
        persona: AgentPersona,
        context: Dict[str, Any],
    ) -> DebateRound:
        """Query a single persona for their vote."""
        client = self._get_llm_client()

        # Build the debate prompt
        prompt = f"""## Context
Function: {context.get("function_name", "unknown")}

## Proposed Change
```python
{context.get("patch_code", "")}
```

## Test Code
```python
{context.get("test_code", "No tests provided")}
```

## Your Role
{persona.system_prompt}

Focus on: {", ".join(persona.focus_areas)}

Provide your evaluation as a JSON object."""

        if client:
            try:
                messages = [
                    {"role": "system", "content": persona.system_prompt},
                    {"role": "user", "content": prompt},
                ]
                response = client.generate_thought(messages=messages)

                # Parse JSON from response
                json_match = self._extract_json(response)
                if json_match:
                    stance = json_match.get("stance", "ABSTAIN").upper()
                    reasoning = json_match.get("reasoning", "No reasoning provided")
                    confidence = float(json_match.get("confidence", 0.5))

                    return DebateRound(
                        persona=persona.name,
                        stance=stance,
                        reasoning=reasoning,
                        confidence=min(1.0, max(0.0, confidence)),
                    )
            except Exception as e:
                logger.warning(f"LLM query failed for {persona.name}: {e}")

        # Fallback to rule-based logic
        return self._rule_based_vote(persona, context)

    def _rule_based_vote(
        self,
        persona: AgentPersona,
        context: Dict[str, Any],
    ) -> DebateRound:
        """Rule-based fallback voting (original CouncilOfThree logic)."""
        patch_code = context.get("patch_code", "")
        test_code = context.get("test_code", "")

        if persona.name == "Architect":
            approved = len(patch_code) > 0
            reasoning = (
                "Code structure appears valid."
                if approved
                else "Empty or invalid code."
            )
        elif persona.name == "Skeptic":
            approved = len(test_code) > 0
            reasoning = (
                "Tests provided for validation."
                if approved
                else "NO TESTS FOUND - HIGH RISK."
            )
        elif persona.name == "Auditor":
            lines = len(patch_code.splitlines()) if patch_code else 0
            approved = lines <= 50
            reasoning = (
                f"Complexity acceptable ({lines} lines)."
                if approved
                else f"Complexity too high ({lines} lines > 50)."
            )
        else:
            approved = True
            reasoning = "Default approval."

        return DebateRound(
            persona=persona.name,
            stance="APPROVE" if approved else "REJECT",
            reasoning=f"[Rule-based] {reasoning}",
            confidence=0.7 if approved else 0.8,
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response."""
        import re

        # Try to find JSON block
        json_pattern = r"\{[^{}]*\}"
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        return None

    def review_patch(
        self,
        patch_code: str,
        test_code: str,
        function_name: str,
    ) -> bool:
        """
        Conduct a multi-agent debate on the proposed patch.

        Args:
            patch_code: The code being proposed.
            test_code: Associated test code.
            function_name: Name of the function being modified.

        Returns:
            True if the patch is approved, False otherwise.
        """
        logger.info(f"[Council] Convening LLM debate for '{function_name}'...")

        context = {
            "patch_code": patch_code,
            "test_code": test_code,
            "function_name": function_name,
        }

        rounds: List[DebateRound] = []

        # Phase 1: Independent voting
        for persona in self.personas:
            round_result = self._query_persona(persona, context)
            rounds.append(round_result)

            status = "✅" if round_result.stance == "APPROVE" else "❌"
            logger.info(
                f"  {status} [{persona.name}] ({round_result.confidence:.0%}): {round_result.reasoning[:100]}..."
            )

        # Phase 2: Calculate consensus
        approve_count = sum(1 for r in rounds if r.stance == "APPROVE")
        total = len(rounds)
        consensus_score = approve_count / total if total > 0 else 0.0

        # Decision
        if self.require_unanimous:
            approved = approve_count == total
        else:
            approved = approve_count >= (total // 2) + 1  # Majority

        # Generate summary
        summary = self._generate_summary(rounds, approved)

        result = DebateResult(
            approved=approved,
            rounds=rounds,
            consensus_score=consensus_score,
            summary=summary,
        )
        self._debate_history.append(result)

        if approved:
            logger.info(
                f"🛰️ [Council] Patch APPROVED ({approve_count}/{total}, consensus: {consensus_score:.0%})"
            )
        else:
            logger.warning(
                f"🚨 [Council] Patch REJECTED ({approve_count}/{total}, consensus: {consensus_score:.0%})"
            )

        return approved

    def _generate_summary(self, rounds: List[DebateRound], approved: bool) -> str:
        """Generate a human-readable debate summary."""
        lines = ["## Debate Summary", ""]

        for r in rounds:
            emoji = "✅" if r.stance == "APPROVE" else "❌"
            lines.append(f"**{r.persona}** {emoji} ({r.confidence:.0%})")
            lines.append(f"> {r.reasoning}")
            lines.append("")

        verdict = "APPROVED" if approved else "REJECTED"
        lines.append(f"**Final Verdict: {verdict}**")

        return "\n".join(lines)

    def get_debate_history(self) -> List[DebateResult]:
        """Return all past debate results."""
        return self._debate_history.copy()


# Backwards compatibility alias
CouncilOfThreeLLM = LLMDebateCouncil
