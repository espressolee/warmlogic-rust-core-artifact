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
# Critique templates and their trigger tokens are intentionally bilingual: the
# Korean entries are matched against model output so self-correction also fires on
# Korean-language responses. Matched data, not prose - do not translate.

"""
[Phase 103.1] Self-Correction Reasoning Loop.
Implements iterative self-critique and correction for enhanced reasoning.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger("SelfCorrection")


@dataclass
class CorrectionStep:
    """A single step in the self-correction loop."""

    iteration: int
    thought: str
    critique: str
    correction: str
    confidence: float
    improved: bool


class SelfCorrectionEngine:
    """
    [Phase 103.1] Self-Correction Reasoning.

    Implements:
    1. Initial reasoning
    2. Self-critique (identify flaws)
    3. Correction (improve based on critique)
    4. Verification (check if improved)
    5. Iteration until confidence threshold
    """

    def __init__(
        self, llm=None, max_iterations: int = 3, confidence_threshold: float = 0.85
    ):
        self.llm = llm
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        self.history: List[CorrectionStep] = []
        logger.info("[SelfCorrection] Engine Active.")

    def _critique(self, thought: str, goal: str) -> Dict[str, Any]:
        """Generate critique of a thought."""
        critiques = []
        confidence = 0.5

        # Check for common reasoning flaws
        flaws = {
            "lacks_evidence": (
                "주장에 근거가 부족합니다.",
                lambda t: (
                    len(t) < 50 or "because" not in t.lower() and "따라서" not in t
                ),
            ),
            "too_vague": (
                "답변이 너무 모호합니다.",
                lambda t: any(
                    w in t.lower()
                    for w in ["maybe", "possibly", "might", "아마", "아닐까"]
                ),
            ),
            "ignores_constraints": (
                "제약 조건을 고려하지 않았습니다.",
                lambda t: (
                    "constraint" not in t.lower()
                    and "조건" not in t
                    and "제한" not in t
                ),
            ),
            "no_alternatives": (
                "대안을 고려하지 않았습니다.",
                lambda t: (
                    "alternative" not in t.lower()
                    and "대안" not in t
                    and "다른" not in t
                ),
            ),
            "overconfident": (
                "과도한 확신입니다.",
                lambda t: any(
                    w in t.lower()
                    for w in ["definitely", "certainly", "always", "무조건", "반드시"]
                ),
            ),
        }

        for flaw_id, (description, check_fn) in flaws.items():
            if check_fn(thought):
                critiques.append({"type": flaw_id, "description": description})

        # Calculate confidence (fewer flaws = higher confidence)
        confidence = max(0.3, 1.0 - len(critiques) * 0.15)

        return {
            "critiques": critiques,
            "flaw_count": len(critiques),
            "confidence": confidence,
            "needs_correction": confidence < self.confidence_threshold,
        }

    def _correct(self, thought: str, critique: Dict, goal: str) -> str:
        """Generate corrected thought based on critique."""
        if not critique["needs_correction"]:
            return thought

        corrections = []

        # Apply corrections based on critique
        for c in critique["critiques"]:
            if c["type"] == "lacks_evidence":
                corrections.append(
                    f"근거 추가: {goal}의 경우 구체적 데이터가 필요합니다."
                )
            elif c["type"] == "too_vague":
                corrections.append(
                    "모호한 표현 수정: 구체적인 수치와 사례를 제시합니다."
                )
            elif c["type"] == "ignores_constraints":
                corrections.append(
                    "제약 조건 고려: 시간, 비용, 리소스 한계를 명시합니다."
                )
            elif c["type"] == "no_alternatives":
                corrections.append("대안 제시: 2-3가지 다른 접근법을 검토합니다.")
            elif c["type"] == "overconfident":
                corrections.append("확신 수준 조정: 불확실성을 인정합니다.")

        corrected = thought
        if corrections:
            corrected = (
                thought + "\n\n[보완사항]\n" + "\n".join(f"- {c}" for c in corrections)
            )

        return corrected

    def reason(self, goal: str, initial_thought: str = None) -> Dict[str, Any]:
        """
        Execute self-correcting reasoning loop.
        """
        logger.info(f"[SelfCorrection] Starting for: {goal[:50]}...")

        self.history = []
        current_thought = (
            initial_thought
            or f"Goal: {goal}\n초기 분석: 목표를 달성하기 위한 접근법을 검토합니다."
        )
        best_confidence = 0.0
        best_thought = current_thought

        for iteration in range(self.max_iterations):
            # Critique
            critique = self._critique(current_thought, goal)

            # Correct
            corrected = self._correct(current_thought, critique, goal)

            # Check improvement
            new_critique = self._critique(corrected, goal)
            improved = new_critique["confidence"] > critique["confidence"]

            step = CorrectionStep(
                iteration=iteration + 1,
                thought=current_thought,
                critique="; ".join(c["description"] for c in critique["critiques"]),
                correction=corrected if improved else current_thought,
                confidence=new_critique["confidence"],
                improved=improved,
            )
            self.history.append(step)

            # Track best
            if new_critique["confidence"] > best_confidence:
                best_confidence = new_critique["confidence"]
                best_thought = corrected

            # Check threshold
            if new_critique["confidence"] >= self.confidence_threshold:
                logger.info(
                    f"🔄 [SelfCorrection] Threshold reached at iteration {iteration + 1}"
                )
                break

            current_thought = corrected

        return {
            "goal": goal,
            "final_thought": best_thought,
            "final_confidence": best_confidence,
            "iterations": len(self.history),
            "improvement_path": [
                {
                    "iteration": s.iteration,
                    "confidence": s.confidence,
                    "improved": s.improved,
                }
                for s in self.history
            ],
            "reached_threshold": best_confidence >= self.confidence_threshold,
        }

    def get_trace(self) -> str:
        """Get human-readable trace of the correction process."""
        lines = ["# 🔄 Self-Correction Trace\n"]

        for step in self.history:
            icon = "✅" if step.improved else "➡️"
            lines.append(f"## Iteration {step.iteration} {icon}")
            lines.append(f"**Confidence**: {step.confidence:.2f}")
            lines.append(f"**Critique**: {step.critique or 'None'}")
            lines.append("")

        return "\n".join(lines)


def self_correct(goal: str, initial_thought: str = None) -> Dict[str, Any]:
    """Convenience function for self-correcting reasoning."""
    engine = SelfCorrectionEngine()
    return engine.reason(goal, initial_thought)
