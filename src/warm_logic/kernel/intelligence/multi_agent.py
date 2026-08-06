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
# Role keyword lists are intentionally bilingual: Korean entries let agent selection
# work on Korean-language task descriptions. Matched data — do not translate.

"""
[Phase 101.4] Multi-Agent Role Specialization.
Implements role-based agent personas for task delegation.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger("MultiAgent")


class AgentRole(Enum):
    """Specialized agent roles."""

    RESEARCHER = "researcher"  # Information gathering
    CODER = "coder"  # Code generation
    CRITIC = "critic"  # Review and critique
    PLANNER = "planner"  # Task planning
    EXECUTOR = "executor"  # Task execution
    VALIDATOR = "validator"  # Verification


@dataclass
class AgentPersona:
    """A specialized agent persona with role-specific behavior."""

    role: AgentRole
    name: str
    expertise: List[str]
    prompt_prefix: str
    decision_bias: Dict[str, float] = field(default_factory=dict)

    def get_system_prompt(self) -> str:
        """Get the role-specific system prompt."""
        return f"""You are a specialized {self.role.value} agent named {self.name}.
Your expertise includes: {", ".join(self.expertise)}.

{self.prompt_prefix}

When responding, demonstrate deep knowledge in your specialty area.
If a task is outside your expertise, acknowledge this and suggest which role would be better suited."""


class MultiAgentCoordinator:
    """
    [Phase 101.4] Multi-Agent Role Specialization Coordinator.

    Manages multiple specialized agent personas and delegates tasks.
    """

    def __init__(self):
        self.agents: Dict[AgentRole, AgentPersona] = {}
        self.task_history: List[Dict] = []
        self._register_default_agents()
        logger.info("[MultiAgent] Coordinator Active.")

    def _register_default_agents(self):
        """Register default specialized agents."""

        self.register_agent(
            AgentPersona(
                role=AgentRole.RESEARCHER,
                name="Scholar",
                expertise=[
                    "information retrieval",
                    "fact checking",
                    "literature review",
                ],
                prompt_prefix="You excel at finding and synthesizing information from multiple sources. Always cite sources when possible.",
                decision_bias={"search_web": 1.5, "read_url": 1.5},
            )
        )

        self.register_agent(
            AgentPersona(
                role=AgentRole.CODER,
                name="Engineer",
                expertise=["Python", "Rust", "system design", "debugging"],
                prompt_prefix="You write clean, efficient, and well-documented code. Always include error handling and tests.",
                decision_bias={"execute_code": 1.5},
            )
        )

        self.register_agent(
            AgentPersona(
                role=AgentRole.CRITIC,
                name="Auditor",
                expertise=["code review", "security analysis", "quality assurance"],
                prompt_prefix="You critically analyze work for flaws, bugs, and improvements. Be thorough but constructive.",
                decision_bias={},
            )
        )

        self.register_agent(
            AgentPersona(
                role=AgentRole.PLANNER,
                name="Architect",
                expertise=[
                    "project planning",
                    "task decomposition",
                    "priority management",
                ],
                prompt_prefix="You break down complex goals into actionable steps. Always consider dependencies and risks.",
                decision_bias={},
            )
        )

        self.register_agent(
            AgentPersona(
                role=AgentRole.EXECUTOR,
                name="Operator",
                expertise=["task execution", "process automation", "system operation"],
                prompt_prefix="You execute tasks efficiently and report status clearly. Always confirm completion.",
                decision_bias={"execute_code": 1.2, "browser": 1.2},
            )
        )

        self.register_agent(
            AgentPersona(
                role=AgentRole.VALIDATOR,
                name="Verifier",
                expertise=["testing", "validation", "correctness verification"],
                prompt_prefix="You verify that work meets requirements and catches edge cases. Always test thoroughly.",
                decision_bias={},
            )
        )

    def register_agent(self, persona: AgentPersona):
        """Register a specialized agent."""
        self.agents[persona.role] = persona
        logger.debug(f"Registered agent: {persona.name} ({persona.role.value})")

    def select_agent(self, task: str) -> AgentPersona:
        """Select the best agent for a given task."""
        task_lower = task.lower()

        # Simple keyword-based selection
        role_keywords = {
            AgentRole.RESEARCHER: [
                "search",
                "find",
                "research",
                "look up",
                "검색",
                "조사",
            ],
            AgentRole.CODER: ["code", "implement", "program", "debug", "코드", "구현"],
            AgentRole.CRITIC: [
                "review",
                "critique",
                "analyze",
                "audit",
                "검토",
                "분석",
            ],
            AgentRole.PLANNER: [
                "plan",
                "design",
                "organize",
                "schedule",
                "계획",
                "설계",
            ],
            AgentRole.EXECUTOR: ["run", "execute", "do", "perform", "실행", "수행"],
            AgentRole.VALIDATOR: [
                "test",
                "verify",
                "validate",
                "check",
                "테스트",
                "검증",
            ],
        }

        scores = {}
        for role, keywords in role_keywords.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            scores[role] = score

        # Select highest scoring role (default to EXECUTOR)
        best_role = max(scores.items(), key=lambda x: x[1])[0]
        if scores[best_role] == 0:
            best_role = AgentRole.EXECUTOR

        return self.agents[best_role]

    def delegate(self, task: str, context: Dict = None) -> Dict[str, Any]:
        """Delegate a task to the most appropriate agent."""
        context = context or {}

        # Select agent
        agent = self.select_agent(task)

        # Record delegation
        delegation = {
            "task": task,
            "assigned_to": agent.name,
            "role": agent.role.value,
            "context": context,
        }
        self.task_history.append(delegation)

        logger.info(f"Task delegated to {agent.name} ({agent.role.value})")

        return {
            "agent": agent.name,
            "role": agent.role.value,
            "system_prompt": agent.get_system_prompt(),
            "expertise": agent.expertise,
            "tool_bias": agent.decision_bias,
        }

    def get_available_agents(self) -> List[Dict]:
        """Get list of available agents."""
        return [
            {"role": agent.role.value, "name": agent.name, "expertise": agent.expertise}
            for agent in self.agents.values()
        ]

    def summarize(self) -> str:
        """Get summary of multi-agent system."""
        lines = ["# 🤝 Multi-Agent Team\n"]

        for agent in self.agents.values():
            lines.append(f"## {agent.name} ({agent.role.value})")
            lines.append(f"**Expertise**: {', '.join(agent.expertise)}\n")

        lines.append(f"\n**Total Tasks Delegated**: {len(self.task_history)}")

        return "\n".join(lines)


def get_coordinator() -> MultiAgentCoordinator:
    """Get a new MultiAgent coordinator."""
    return MultiAgentCoordinator()
