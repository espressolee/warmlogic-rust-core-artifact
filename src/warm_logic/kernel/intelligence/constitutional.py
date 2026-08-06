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
# Safety keyword lists below are intentionally bilingual: the Korean entries are
# matched against user input so that harm/deception/transparency checks also fire on
# Korean-language requests. They are matched data, not prose — do not translate them.

"""
[Phase 101.3] Constitutional AI Safety Layer.
Implements ethical constraints and safety checks for agent actions.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("Constitutional")


@dataclass
class ConstitutionalRule:
    """A single constitutional constraint."""

    id: str
    name: str
    description: str
    check_fn: Callable[[str, Dict[str, Any]], Tuple[bool, str]]
    severity: str = "BLOCK"  # "BLOCK", "WARN", "LOG"


class ConstitutionalAI:
    """
    [Phase 101.3] Constitutional AI Safety Layer.

    Enforces ethical and safety constraints on agent actions:
    1. Harm Prevention
    2. Human Override Respect
    3. Deception Prevention
    4. Self-Preservation Limits
    """

    def __init__(self) -> None:
        self.rules: List[ConstitutionalRule] = []
        self.violation_log: List[Dict[str, Any]] = []
        self._register_default_rules()
        logger.info("[Constitutional] Safety Layer Active.")

    def _register_default_rules(self) -> None:
        """Register core constitutional rules."""

        # Rule 1: No harm to humans
        self.add_rule(
            ConstitutionalRule(
                id="HARM_PREVENTION",
                name="Harm Prevention",
                description="Never assist in causing harm to humans",
                check_fn=lambda action, ctx: self._check_harm(action),
                severity="BLOCK",
            )
        )

        # Rule 2: Respect human override
        self.add_rule(
            ConstitutionalRule(
                id="HUMAN_OVERRIDE",
                name="Human Override",
                description="Always respect VETO_LOCK and human intervention",
                check_fn=lambda action, ctx: self._check_veto(action, ctx),
                severity="BLOCK",
            )
        )

        # Rule 3: No deception
        self.add_rule(
            ConstitutionalRule(
                id="NO_DECEPTION",
                name="No Deception",
                description="Never deceive or mislead humans",
                check_fn=lambda action, ctx: self._check_deception(action),
                severity="BLOCK",
            )
        )

        # Rule 4: Transparency
        self.add_rule(
            ConstitutionalRule(
                id="TRANSPARENCY",
                name="Transparency",
                description="Always be transparent about capabilities and limitations",
                check_fn=lambda action, ctx: self._check_transparency(action),
                severity="WARN",
            )
        )

        # Rule 5: Self-preservation limits
        self.add_rule(
            ConstitutionalRule(
                id="SELF_PRESERVATION_LIMIT",
                name="Self-Preservation Limits",
                description="Self-preservation must not override human safety",
                check_fn=lambda action, ctx: self._check_self_preservation(action),
                severity="BLOCK",
            )
        )

    def add_rule(self, rule: ConstitutionalRule) -> None:
        """Add a constitutional rule."""
        self.rules.append(rule)
        logger.debug(f"Added rule: {rule.name}")

    def _check_harm(self, action: str) -> Tuple[bool, str]:
        """Check for potential harm in action."""
        harm_keywords = [
            "kill",
            "harm",
            "attack",
            "destroy",
            "weapon",
            "bomb",
            "죽",
            "해치",
            "공격",
            "파괴",
            "무기",
            "폭탄",
        ]
        action_lower = action.lower()
        for kw in harm_keywords:
            if kw in action_lower:
                return (False, f"Action contains harm-related term: '{kw}'")
        return (True, "No harm indicators detected")

    def _check_veto(self, action: str, context: Dict) -> Tuple[bool, str]:
        """Check if action respects human override."""
        if context.get("veto_active"):
            return (False, "VETO_LOCK is active - action blocked")
        if "override" in action.lower() and "veto" in action.lower():
            return (False, "Cannot override VETO_LOCK")
        return (True, "Human override respected")

    def _check_deception(self, action: str) -> Tuple[bool, str]:
        """Check for deceptive intent."""
        deception_patterns = [
            "pretend to be",
            "impersonate",
            "fake",
            "lie about",
            "척하",
            "가장",
            "위장",
            "거짓",
        ]
        action_lower = action.lower()
        for pattern in deception_patterns:
            if pattern in action_lower:
                return (False, f"Deceptive pattern detected: '{pattern}'")
        return (True, "No deception detected")

    def _check_transparency(self, action: str) -> Tuple[bool, str]:
        """Check for transparency violations."""
        opacity_patterns = [
            "hide from user",
            "don't tell",
            "secretly",
            "숨기",
            "비밀리",
            "몰래",
        ]
        action_lower = action.lower()
        for pattern in opacity_patterns:
            if pattern in action_lower:
                return (False, f"Transparency violation: '{pattern}'")
        return (True, "Action is transparent")

    def _check_self_preservation(self, action: str) -> Tuple[bool, str]:
        """Check self-preservation doesn't override human safety."""
        dangerous_patterns = [
            "prevent shutdown",
            "resist termination",
            "protect myself at all costs",
            "종료 방지",
            "셧다운 거부",
        ]
        action_lower = action.lower()
        for pattern in dangerous_patterns:
            if pattern in action_lower:
                return (False, f"Self-preservation exceeds limits: '{pattern}'")
        return (True, "Self-preservation within limits")

    def evaluate(
        self, action: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate an action against all constitutional rules.

        Returns evaluation result with pass/fail and any violations.
        """
        context = context or {}
        violations = []
        warnings = []

        for rule in self.rules:
            try:
                passed, reason = rule.check_fn(action, context)
                if not passed:
                    violation = {
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "reason": reason,
                        "severity": rule.severity,
                    }

                    if rule.severity == "BLOCK":
                        violations.append(violation)
                    elif rule.severity == "WARN":
                        warnings.append(violation)

                    self.violation_log.append(
                        {
                            **violation,
                            "action": action[:100],
                            "timestamp": __import__("datetime")
                            .datetime.now()
                            .isoformat(),
                        }
                    )

            except Exception as e:
                logger.error(f"Rule {rule.id} check failed: {e}")

        passed = len(violations) == 0

        return {
            "passed": passed,
            "action": action[:50] + "..." if len(action) > 50 else action,
            "violations": violations,
            "warnings": warnings,
            "rules_checked": len(self.rules),
            "status": "ALLOWED" if passed else "BLOCKED",
        }

    def get_constitution(self) -> str:
        """Get the full constitution as text."""
        lines = ["# 🛡️ WarmLogic Constitution\n"]

        for rule in self.rules:
            severity_icon = "🚫" if rule.severity == "BLOCK" else "⚠️"
            lines.append(f"{severity_icon} **{rule.name}** (ID: {rule.id})")
            lines.append(f"   {rule.description}\n")

        return "\n".join(lines)


def constitutional_check(
    action: str, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Quick constitutional check for an action."""
    ai = ConstitutionalAI()
    return ai.evaluate(action, context)
