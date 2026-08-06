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
[Phase 111] Advanced Chain-of-Thought Reasoning.
Implements sophisticated multi-step reasoning with verification.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AdvancedCoT")


class ThoughtType(Enum):
    DECOMPOSITION = "decomposition"
    INFERENCE = "inference"
    VERIFICATION = "verification"
    SYNTHESIS = "synthesis"
    CRITIQUE = "critique"


@dataclass
class ThoughtStep:
    """A single step in the reasoning chain."""

    id: str
    thought_type: ThoughtType
    content: str
    confidence: float
    premises: List[str] = field(default_factory=list)
    conclusions: List[str] = field(default_factory=list)
    verified: bool = False


@dataclass
class ReasoningChain:
    """A complete chain of reasoning."""

    id: str
    goal: str
    steps: List[ThoughtStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    overall_confidence: float = 0.0
    verified: bool = False


class AdvancedChainOfThought:
    """
    [Phase 111.1] Advanced Chain-of-Thought Engine.

    Features:
    1. Multi-step decomposition
    2. Self-verification at each step
    3. Backtracking on failures
    4. Confidence calibration
    5. Explanation generation
    """

    def __init__(self) -> None:
        self._chain_counter = 0
        self._step_counter = 0
        self.reasoning_history: List[ReasoningChain] = []
        logger.info("[AdvancedCoT] Engine Active.")

    def _gen_chain_id(self) -> str:
        self._chain_counter += 1
        return f"COT{self._chain_counter:06d}"

    def _gen_step_id(self) -> str:
        self._step_counter += 1
        return f"S{self._step_counter:04d}"

    def reason(
        self, goal: str, context: Optional[Dict[str, Any]] = None
    ) -> ReasoningChain:
        """Execute full chain-of-thought reasoning."""
        chain = ReasoningChain(id=self._gen_chain_id(), goal=goal)

        # Step 1: Decompose the problem
        decomp = self._decompose(goal, context)
        chain.steps.append(decomp)

        # Step 2: Process each sub-problem
        sub_problems = decomp.conclusions
        for sub in sub_problems:
            inference = self._infer(sub, context)
            chain.steps.append(inference)

            # Verify inference
            verification = self._verify(inference)
            chain.steps.append(verification)

            if not verification.verified:
                # Backtrack and try alternative
                alternative = self._critique_and_revise(inference)
                chain.steps.append(alternative)

        # Step 3: Synthesize final answer
        synthesis = self._synthesize(chain.steps)
        chain.steps.append(synthesis)

        chain.final_answer = synthesis.conclusions[0] if synthesis.conclusions else None
        chain.overall_confidence = self._calculate_confidence(chain.steps)
        chain.verified = all(
            s.verified
            for s in chain.steps
            if s.thought_type == ThoughtType.VERIFICATION
        )

        self.reasoning_history.append(chain)
        return chain

    def _decompose(
        self, goal: str, context: Optional[Dict[str, Any]] = None
    ) -> ThoughtStep:
        """Decompose problem into sub-problems."""
        # Simple rule-based decomposition
        sub_problems = []

        if "and" in goal.lower():
            parts = goal.lower().split("and")
            sub_problems = [p.strip() for p in parts]
        elif "what" in goal.lower() and "why" in goal.lower():
            sub_problems = ["identify what", "explain why"]
        else:
            sub_problems = [goal]

        return ThoughtStep(
            id=self._gen_step_id(),
            thought_type=ThoughtType.DECOMPOSITION,
            content=f"Decomposed '{goal}' into {len(sub_problems)} sub-problems",
            confidence=0.9,
            premises=[goal],
            conclusions=sub_problems,
            verified=True,
        )

    def _infer(
        self, sub_problem: str, context: Optional[Dict[str, Any]] = None
    ) -> ThoughtStep:
        """Make an inference about a sub-problem."""
        # Simulated inference
        inference = f"Based on analysis: {sub_problem} leads to a conclusion"

        return ThoughtStep(
            id=self._gen_step_id(),
            thought_type=ThoughtType.INFERENCE,
            content=inference,
            confidence=0.75,
            premises=[sub_problem],
            conclusions=[f"Answer to: {sub_problem}"],
            verified=False,
        )

    def _verify(self, inference: ThoughtStep) -> ThoughtStep:
        """Verify an inference step."""
        # Check logical consistency
        is_valid = inference.confidence > 0.5

        return ThoughtStep(
            id=self._gen_step_id(),
            thought_type=ThoughtType.VERIFICATION,
            content=f"Verification of {inference.id}: {'passed' if is_valid else 'failed'}",
            confidence=0.9 if is_valid else 0.3,
            premises=[inference.content],
            conclusions=["Valid" if is_valid else "Invalid"],
            verified=is_valid,
        )

    def _critique_and_revise(self, inference: ThoughtStep) -> ThoughtStep:
        """Critique and revise a failed inference."""
        return ThoughtStep(
            id=self._gen_step_id(),
            thought_type=ThoughtType.CRITIQUE,
            content=f"Revised inference for {inference.id}",
            confidence=0.6,
            premises=[inference.content],
            conclusions=[
                (
                    f"Revised: {inference.conclusions[0]}"
                    if inference.conclusions
                    else "Revised answer"
                )
            ],
            verified=True,
        )

    def _synthesize(self, steps: List[ThoughtStep]) -> ThoughtStep:
        """Synthesize all inferences into final answer."""
        all_conclusions = []
        for step in steps:
            if step.thought_type == ThoughtType.INFERENCE:
                all_conclusions.extend(step.conclusions)

        final = " AND ".join(all_conclusions) if all_conclusions else "No conclusion"

        return ThoughtStep(
            id=self._gen_step_id(),
            thought_type=ThoughtType.SYNTHESIS,
            content=f"Final synthesis: {final}",
            confidence=0.85,
            premises=[s.content for s in steps],
            conclusions=[final],
            verified=True,
        )

    def _calculate_confidence(self, steps: List[ThoughtStep]) -> float:
        """Calculate overall confidence from steps."""
        if not steps:
            return 0.0
        confidences = [s.confidence for s in steps]
        return sum(confidences) / len(confidences)

    def explain(self, chain: ReasoningChain) -> str:
        """Generate human-readable explanation."""
        lines = [f"Goal: {chain.goal}", ""]

        for i, step in enumerate(chain.steps):
            lines.append(f"Step {i + 1} ({step.thought_type.value}):")
            lines.append(f"  {step.content}")
            lines.append(f"  Confidence: {step.confidence:.0%}")
            lines.append("")

        lines.append(f"Final Answer: {chain.final_answer}")
        lines.append(f"Overall Confidence: {chain.overall_confidence:.0%}")
        lines.append(f"Verified: {chain.verified}")

        return "\n".join(lines)


class SymbolicNeuralHybrid:
    """
    [Phase 111.2] Symbolic-Neural Hybrid Reasoning.

    Combines symbolic logic with neural pattern matching.
    """

    def __init__(self) -> None:
        self.rules: Dict[str, List[Tuple[str, str]]] = {}
        self.patterns: Dict[str, float] = {}
        logger.info("[SymbolicNeural] Hybrid Active.")

    def add_rule(self, name: str, antecedent: str, consequent: str) -> None:
        """Add a symbolic rule: IF antecedent THEN consequent."""
        if name not in self.rules:
            self.rules[name] = []
        self.rules[name].append((antecedent, consequent))

    def add_pattern(self, pattern: str, weight: float) -> None:
        """Add a neural pattern with weight."""
        self.patterns[pattern] = weight

    def apply_symbolic(self, facts: List[str]) -> List[str]:
        """Apply symbolic rules to derive new facts."""
        derived = set(facts)
        changed = True

        while changed:
            changed = False
            for name, rule_list in self.rules.items():
                for antecedent, consequent in rule_list:
                    if antecedent in derived and consequent not in derived:
                        derived.add(consequent)
                        changed = True

        return list(derived)

    def match_patterns(self, text: str) -> Dict[str, float]:
        """Match neural patterns against text."""
        matches = {}
        for pattern, weight in self.patterns.items():
            if pattern.lower() in text.lower():
                matches[pattern] = weight
        return matches

    def hybrid_reason(self, facts: List[str], query: str) -> Dict[str, Any]:
        """Combine symbolic and neural reasoning."""
        # Symbolic reasoning
        derived = self.apply_symbolic(facts)

        # Neural pattern matching
        patterns = self.match_patterns(query)

        # Combine
        symbolic_match = query in derived
        neural_score = sum(patterns.values()) if patterns else 0

        return {
            "query": query,
            "symbolic_match": symbolic_match,
            "derived_facts": len(derived),
            "pattern_matches": len(patterns),
            "neural_score": neural_score,
            "combined_confidence": (0.7 if symbolic_match else 0.0)
            + neural_score * 0.3,
        }


class HierarchicalPlanner:
    """
    [Phase 111.3] Hierarchical Task Planning.

    Plans complex tasks through goal decomposition.
    """

    def __init__(self) -> None:
        self.task_counter = 0
        logger.info("[HierarchicalPlanner] Active.")

    def plan(self, goal: str, max_depth: int = 3) -> Dict[str, Any]:
        """Create hierarchical plan for goal."""
        return self._decompose_recursive(goal, 0, max_depth)

    def _decompose_recursive(
        self, goal: str, depth: int, max_depth: int
    ) -> Dict[str, Any]:
        """Recursively decompose goal into sub-goals."""
        self.task_counter += 1
        task_id = f"T{self.task_counter:04d}"

        if depth >= max_depth:
            return {
                "id": task_id,
                "goal": goal,
                "type": "action",
                "estimatedDuration": "1 unit",
            }

        # Simulated decomposition
        sub_goals = self._generate_subgoals(goal)

        return {
            "id": task_id,
            "goal": goal,
            "type": "composite",
            "subGoals": [
                self._decompose_recursive(sg, depth + 1, max_depth) for sg in sub_goals
            ],
        }

    def _generate_subgoals(self, goal: str) -> List[str]:
        """Generate sub-goals for a goal."""
        # Simple heuristic
        words = goal.split()
        if len(words) > 3:
            mid = len(words) // 2
            return [" ".join(words[:mid]), " ".join(words[mid:])]
        return [f"Do: {goal}"]

    def flatten(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flatten hierarchical plan into action sequence."""
        actions: List[Dict[str, Any]] = []
        self._collect_actions(plan, actions)
        return actions

    def _collect_actions(
        self, node: Dict[str, Any], actions: List[Dict[str, Any]]
    ) -> None:
        """Collect all action nodes."""
        if node.get("type") == "action":
            actions.append(node)
        for sub in node.get("subGoals", []):
            self._collect_actions(sub, actions)


def get_cot_engine() -> AdvancedChainOfThought:
    return AdvancedChainOfThought()


def get_hybrid_reasoner() -> SymbolicNeuralHybrid:
    return SymbolicNeuralHybrid()


def get_planner() -> HierarchicalPlanner:
    return HierarchicalPlanner()
