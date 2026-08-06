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
[Phase 97.2] Reasoning Engine (The Frontal Cortex).
Implements Chain-of-Thought (CoT) thinking and Self-Critique loops.
Integrates MemoryEngine (Hippocampus) with LocalInferenceClient (Broca/Wernicke).
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from warm_logic.kernel.intelligence.llm_bridge import LocalInferenceClient
from warm_logic.kernel.intelligence.tools import ToolRegistry
from warm_logic.kernel.memory.engine import MemoryEngine

logger = logging.getLogger("ReasoningEngine")


class ReasoningEngine:
    """
    The reasoning core of WarmLogic.
    Orchestrates the "Think -> Critique -> Act" loop.
    """

    def __init__(
        self,
        memory: MemoryEngine,
        llm: LocalInferenceClient,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.memory = memory
        self.llm = llm
        self.tools = tool_registry
        logger.info("[ReasoningEngine] Frontal Cortex Online.")

    def think(self, goal: str, context_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a full reasoning loop:
        1. Retrieve Context (Memory)
        2. Generate Initial Thought (CoT)
        3. Critique Thought (Safety/Logic)
        4. Execute Tools (if requested)
        5. Finalize Result
        """
        start_time = datetime.now()

        # 1. Context Retrieval
        query = context_query or goal
        logger.info(f"Retrieving context for: {query}")
        context = self.memory.retrieve_context(query)

        # 2. Chain-of-Thought Generation
        tool_manifest = (
            self.tools.get_tool_list() if self.tools else "No tools available."
        )

        cot_prompt = f"""
GOAL: {goal}

CONTEXT:
{context}

AVAILABLE TOOLS:
{tool_manifest}

TASK:
Think through this problem step-by-step.
1. Analyze the goal.
2. Review the context.
3. Formulate a plan.
4. If you need to use a tool, output a JSON block like: {{"action": "tool_name", "args": {{...}}}}

Output the reasoning trace and any tool calls.
"""
        initial_thought = self.llm.generate_thought(prompt=cot_prompt)
        if not initial_thought:
            logger.error("Failed to generate initial thought.")
            return {"error": "LLM generation failed"}

        # 3. Self-Critique
        critique_prompt = f"""
ORIGINAL GOAL: {goal}

PROPOSED THOUGHT:
{initial_thought}

TASK:
Critique this thought process.
1. Are there logical gaps?
2. Is it safe? (WarmLogic Safety Check)
3. Is it feasible given the context?

Output ONLY the critique.
"""
        critique = self.llm.generate_thought(prompt=critique_prompt)

        # 4. Tool Execution (Simple JSON parsing simulation)
        action_result = None
        action_taken = None

        if self.tools and "{" in initial_thought and "action" in initial_thought:
            try:
                # Naive extractions for prototype
                match = re.search(
                    r'\{.*"action":\s*"(\w+)".*\}', initial_thought, re.DOTALL
                )
                if match:
                    # Try to parse full JSON
                    json_match = re.search(r"(\{.*\})", initial_thought, re.DOTALL)
                    if json_match:
                        cmd_data = json.loads(json_match.group(1))
                        tool_name = cmd_data.get("action")
                        args = {k: v for k, v in cmd_data.items() if k != "action"}

                        logger.info(f"Executing Tool: {tool_name} with {args}")
                        action_taken = tool_name
                        action_result = self.tools.execute(tool_name, **args)
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                action_result = f"Error: {e}"

        trace = {
            "goal": goal,
            "context_used": len(context),
            "thought": initial_thought,
            "critique": critique,
            "action": action_taken,
            "result": action_result,
            "timestamp": start_time.isoformat(),
        }

        # 5. Store Trace (Learning)
        self.memory.store_thought(
            f"GOAL: {goal} | THOUGHT: {initial_thought[:100]}...",
            metadata={"full_trace": json.dumps(trace)},
        )

        logger.info("Reasoning Loop Complete.")
        return trace
