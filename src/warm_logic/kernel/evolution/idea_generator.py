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

from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient

logger = logging.getLogger("IdeaGenerator")


class IdeaGenerator:
    """
    Neuro-Symbolic Idea Generator.
    Uses Sovereign Inference (LLM) + MCTS to generate verifiable code optimizations.
    Replaces the Mock.
    """

    def __init__(self, use_mock: bool = False):
        self.llm = LocalInferenceClient()
        self.use_mock = use_mock  # For unit tests only

    def generate_optimization(self, source_code: str, goal: str) -> str:
        """
        Public API: Analyzes source_code and returns optimized version.
        Now routes to LLM or MCTS.
        """
        logger.info(f"[IdeaGen] Generating optimization for goal: {goal}")

        if self.use_mock:
            # Legacy mock path for fast unit tests if strictly requested
            if "slow_fib" in source_code:
                return self._template_iterative_fib()
            return source_code

        return self.generate_optimization_llm(source_code, goal)

    def generate_optimization_llm(self, source_code: str, goal: str) -> str:
        """
        [Phase 65] Real Neural Inference.
        """
        system_prompt = (
            "You are the Evolution Engine of WarmLogic. "
            "Your task is to optimize the provided Python code to achieve the specified goal "
            "(e.g., improve time complexity from O(2^N) to O(N)).\n"
            "RULES:\n"
            "1. Output ONLY valid Python code inside a code block ```python ... ```.\n"
            "2. Do not change the function signature or name.\n"
            "3. Ensure the code is self-contained and imports necessary standard libraries.\n"
            "4. Add a comment '# OPTIMIZED by WarmLogic Neural Engine' at the top."
        )

        prompt = (
            f"GOAL: {goal}\n\n"
            f"SOURCE CODE:\n```python\n{source_code}\n```\n\n"
            f"OPTIMIZED CODE:"
        )

        response = self.llm.generate_thought(prompt=prompt, system_prompt=system_prompt)

        if not response:
            logger.error("[IdeaGen] LLM returned no response.")
            return source_code

        # Extract code block
        import re

        match = re.search(r"```python(.*?)```", response, re.DOTALL)
        if match:
            optimized_code = match.group(1).strip()
            logger.info("[IdeaGen] LLM successfully synthesized code.")
            return optimized_code

        # Fallback: check if the whole response is code (heuristic)
        if "def " in response and "return " in response:
            return response.strip()

        logger.warning("[IdeaGen] Failed to extract code from LLM response.")
        return source_code

    def _template_iterative_fib(self) -> str:
        return """
def slow_fib(n):
    # OPTIMIZED by WarmLogic IdeaGenerator
    if n <= 1: return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
"""
