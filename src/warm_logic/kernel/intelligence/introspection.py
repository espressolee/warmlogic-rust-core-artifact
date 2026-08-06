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
[Phase 98.4] Introspection API (Self-Awareness Module).
Enables the agent to inspect and report its own internal state.
"""

import json
import logging
import os
import platform
import sys
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger("Introspection")


class SelfInspector:
    """
    The Mirror of WarmLogic.
    Allows the agent to examine its own components, state, and capabilities.
    """

    def __init__(self, memory=None, tools=None, reasoning=None):
        self.memory = memory
        self.tools = tools
        self.reasoning = reasoning
        self._birth_time = datetime.now()
        logger.info("[Introspection] Self-Awareness Module Active.")

    def get_identity(self) -> Dict[str, Any]:
        """Who am I?"""
        return {
            "name": "WarmLogic",
            "version": "1.0.0-omega",
            "type": "Sovereign Autonomous Agent",
            "philosophy": "Sovereignty is not a feature. It is a physical state.",
            "core_values": [
                "Cryptographic Accountability",
                "Post-Quantum Security",
                "Human Override (VETO_LOCK)",
                "Formal Verification",
            ],
            "uptime_seconds": (datetime.now() - self._birth_time).total_seconds(),
        }

    def get_capabilities(self) -> Dict[str, Any]:
        """What can I do?"""
        tools_available = []
        if self.tools:
            try:
                manifest = json.loads(self.tools.get_tool_list())
                tools_available = [t["name"] for t in manifest]
            except Exception:
                pass

        return {
            "memory": {
                "available": self.memory is not None,
                "type": type(self.memory).__name__ if self.memory else None,
            },
            "reasoning": {
                "available": self.reasoning is not None,
                "type": type(self.reasoning).__name__ if self.reasoning else None,
            },
            "tools": {"count": len(tools_available), "available": tools_available},
        }

    def get_environment(self) -> Dict[str, Any]:
        """Where am I running?"""
        return {
            "python_version": sys.version.split()[0],
            "platform": platform.system(),
            "platform_release": platform.release(),
            "architecture": platform.machine(),
            "cwd": os.getcwd(),
            "env_keys": list(os.environ.keys())[:10],  # Limited for privacy
        }

    def get_memory_state(self) -> Dict[str, Any]:
        """What do I remember?"""
        if not self.memory:
            return {"status": "No memory module attached"}

        try:
            # Try to get memory stats if available
            state = {
                "semantic_available": hasattr(self.memory, "semantic"),
                "vault_available": hasattr(self.memory, "vault"),
            }
            if hasattr(self.memory, "semantic") and self.memory.semantic:
                if hasattr(self.memory.semantic, "_collection"):
                    state["semantic_count"] = self.memory.semantic._collection.count()
            return state
        except Exception as e:
            return {"status": f"Error reading memory: {e}"}

    def introspect(self) -> Dict[str, Any]:
        """Full self-inspection report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "identity": self.get_identity(),
            "capabilities": self.get_capabilities(),
            "environment": self.get_environment(),
            "memory_state": self.get_memory_state(),
        }
        return report

    def summarize(self) -> str:
        """Human-readable self-summary."""
        identity = self.get_identity()
        caps = self.get_capabilities()
        env = self.get_environment()

        lines = [
            "# 🪞 WarmLogic Self-Inspection",
            f"**Name**: {identity['name']} v{identity['version']}",
            f"**Type**: {identity['type']}",
            f"**Uptime**: {identity['uptime_seconds']:.1f}s",
            "",
            "## Capabilities",
            f"- Memory: {'✅' if caps['memory']['available'] else '❌'} ({caps['memory']['type']})",
            f"- Reasoning: {'✅' if caps['reasoning']['available'] else '❌'} ({caps['reasoning']['type']})",
            f"- Tools: {caps['tools']['count']} available ({', '.join(caps['tools']['available'][:3])}...)",
            "",
            "## Environment",
            f"- Python: {env['python_version']}",
            f"- Platform: {env['platform']} {env['platform_release']}",
            f"- Architecture: {env['architecture']}",
            "",
            f'> *"{identity["philosophy"]}"*',
        ]
        return "\n".join(lines)


def introspect() -> Dict[str, Any]:
    """Quick introspection without dependencies."""
    inspector = SelfInspector()
    return inspector.introspect()
