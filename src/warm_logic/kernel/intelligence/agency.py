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
import json
import logging
import re
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from warm_logic.kernel.intelligence import skill_engine
from warm_logic.kernel.ops import tracing

logger = logging.getLogger("SovereignAgency")


class AgencyExecutor:
    """
    [Phase 33] The Hands of Sovereignty.
    Parses LLM output for JSON actions and executes them.
    Refactored to allow scoped deletion in ./tmp/sovereign/
    """

    def __init__(
        self,
        sandbox_dir: str = ".",
        registry: Optional[skill_engine.SkillRegistry] = None,
    ):
        self.sandbox_dir = sandbox_dir
        self.registry = registry or skill_engine.SkillRegistry()

        # Action dispatch table (reduces cyclomatic complexity)
        self._action_handlers: Dict[str, callable] = {
            "shell": self._handle_shell,
            "write_file": self._handle_write_file,
            "read_file": self._handle_read_file,
            "search": self._handle_search,
            "diff": self._handle_diff,
            "analyze_image": self._handle_analyze_image,
        }

    def observe_visual(
        self, image_path: str, prompt: str = "Describe what you see."
    ) -> str:
        """
        [Phase B] Hooks into VisionClient to allow the agent to 'see'.
        """
        logger.info(f"[Agency] Observing: {image_path}")
        try:
            from warm_logic.kernel.intelligence.vision import VisionClient

            client = VisionClient()
            full_path = Path(self.sandbox_dir) / image_path
            if not full_path.exists():
                return f"Error: Image not found: {image_path}"

            result = client.analyze_image(prompt, str(full_path))
            return result if result else "Error: Vision analysis failed."
        except ImportError:
            return "Error: Vision module not available."
        except Exception as e:
            return f"Vision Error: {e}"

    def extract_action(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts JSON action(s) from the model's text response.
        Supports single object {} or list of objects [{}, {}].
        Returns a list of actions.
        """
        actions = []
        try:
            # 1. Try to find a JSON list first (Tool Chaining)
            list_match = re.search(r'\[\s*\{.*"action":.*\}\s*\]', text, re.DOTALL)
            if list_match:
                data = json.loads(list_match.group())
                if isinstance(data, list):
                    return data

            # 2. Fallback to single JSON object
            match = re.search(r'\{.*"action":\s*".*".*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return [data]

        except Exception as e:
            logger.error(f"Failed to parse action block: {e}")

        return actions

    def execute(
        self, action: Dict[str, Any], trace_ctx: Optional[tracing.TraceContext] = None
    ) -> str:
        """
        Executes the identified action.
        Supports: shell, write_file, read_file, search, diff
        """
        action_type = action.get("action")
        if trace_ctx:
            tracing.log_trace(trace_ctx, "ACTION_START", action=action)

        result_str = ""

        # [Phase 57.1] Attempt to delegate to Dynamic Skill Engine
        skill = self.registry.get_skill(action_type)
        if skill:
            try:
                logger.info(f"[Agency] Invoking Skill: {action_type}")
                return skill.execute(action)
            except Exception as e:
                return f"Skill Execution Error ({action_type}): {e}"

        try:
            # Dispatch to appropriate handler (reduces cyclomatic complexity)
            handler = self._action_handlers.get(action_type)
            if handler:
                result_str = handler(action)
            else:
                result_str = f"Unknown action type: {action_type}"

        except Exception as e:
            result_str = f"Execution Error: {e}"

        if trace_ctx:
            tracing.log_trace(
                trace_ctx,
                "ACTION_RESULT",
                action_type=action_type,
                result_preview=result_str[:200],
            )

        return result_str

    # --- Action Handlers (extracted for reduced cyclomatic complexity) ---

    def _handle_shell(self, action: Dict[str, Any]) -> str:
        """Handle shell command execution with security guards."""
        command = action.get("command")
        if not command:
            return "Error: No command provided in shell action."

        logger.info(f"[Agency] Executing: {command}")

        # Security Policy: Block root/recursive deletion by default
        dangerous_patterns = [
            r"rm\s+-rf\s+/",
            r"rm\s+-[^ ]*r\s+/",
            r"rm\s+/",
        ]
        is_dangerous = any(re.search(p, command) for p in dangerous_patterns)

        # Exception: Allow deletion in ./tmp/sovereign/
        is_safe_scope = "./tmp/sovereign/" in command and ".." not in command

        if is_dangerous and not is_safe_scope:
            return "Error: Dangerous root-level deletion blocked by Sovereign Policy."

        # SECURITY: Use shlex.split() instead of shell=True (CWE-78)
        result = subprocess.run(
            shlex.split(command),
            shell=False,
            capture_output=True,
            text=True,
            cwd=self.sandbox_dir,
            timeout=30,
        )
        result_str = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            result_str += f"\nReturn Code: {result.returncode}"
        return result_str

    def _handle_write_file(self, action: Dict[str, Any]) -> str:
        """Handle file write operations."""
        path = action.get("path")
        content = action.get("content")
        if not path or content is None:
            return "Error: Missing path or content for write_file action."

        logger.info(f"[Agency] Writing to: {path}")
        full_path = Path(self.sandbox_dir) / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return f"Successfully wrote to {path}"

    def _handle_read_file(self, action: Dict[str, Any]) -> str:
        """Handle file read operations."""
        path = action.get("path")
        if not path:
            return "Error: Missing path for read_file action."

        logger.info(f"[Agency] Reading: {path}")
        full_path = Path(self.sandbox_dir) / path
        if not full_path.exists():
            return f"Error: File not found: {path}"

        content = full_path.read_text()
        if len(content) > 8000:
            content = content[:8000] + "\n\n... [TRUNCATED] ..."
        return f"File Content ({path}):\n{content}"

    def _handle_search(self, action: Dict[str, Any]) -> str:
        """Handle grep-based search operations."""
        query = action.get("query")
        if not query:
            return "Error: Missing query for search action."

        logger.info(f"[Agency] Searching: {query}")
        cmd = [
            "grep",
            "-rnI",
            "--exclude-dir=.git",
            "--exclude-dir=__pycache__",
            query,
            self.sandbox_dir,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        result_str = result.stdout if result.stdout else "No matches found."
        if len(result_str) > 5000:
            result_str = result_str[:5000] + "\n... [TRUNCATED via grep limit] ..."
        return result_str

    def _handle_diff(self, action: Dict[str, Any]) -> str:
        """Handle git diff operations."""
        logger.info("[Agency] Checking Diff")
        result = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            cwd=self.sandbox_dir,
            timeout=5,
        )
        return (
            f"Unstaged Changes:\n{result.stdout}"
            if result.stdout
            else "No unstaged changes."
        )

    def _handle_analyze_image(self, action: Dict[str, Any]) -> str:
        """Handle image analysis via VisionClient."""
        image_path = action.get("path")
        prompt = action.get("prompt", "Describe this image in detail.")
        if not image_path:
            return "Error: Missing 'path' for analyze_image action."

        logger.info(f"[Agency] Analyzing image: {image_path}")
        from warm_logic.kernel.intelligence.vision import VisionClient

        client = VisionClient()
        full_path = Path(self.sandbox_dir) / image_path
        if not full_path.exists():
            return f"Error: Image not found: {image_path}"

        res = client.analyze_image(prompt, str(full_path))
        return res if res else "Error: Vision analysis failed."

    def execute_batch(
        self,
        actions: List[Dict[str, Any]],
        max_workers: int = 5,
        trace_ctx: Optional[tracing.TraceContext] = None,
    ) -> List[str]:
        """
        [Phase 55.4.2] Parallel Execution.
        """
        logger.info(
            f"⚡ [Agency] Batch executing {len(actions)} actions in parallel..."
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Pass trace_ctx to each execution
            from functools import partial

            exec_func = partial(self.execute, trace_ctx=trace_ctx)
            results = list(executor.map(exec_func, actions))
        return results
