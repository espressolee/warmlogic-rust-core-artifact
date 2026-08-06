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
import importlib.util
import logging
import multiprocessing
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("SkillSandbox")


class SecurityError(Exception):
    """SEC-004: Raised when plugin security validation fails."""

    pass


# SEC-004: Allowed plugin directories (relative to project root)
ALLOWED_PLUGIN_DIRS = [
    "plugins",
    "skills",
    "src/warm_logic/plugins",
    "src/warm_logic/skills",
]


def _validate_plugin_path(plugin_path: str, base_dir: Optional[str] = None) -> bool:
    """
    SEC-004: Validate plugin path to prevent path traversal attacks.

    Returns True if path is safe, False otherwise.
    """
    try:
        path = Path(plugin_path).resolve()

        # Check for path traversal attempts
        if ".." in str(plugin_path):
            logger.error(f"SEC-004: Path traversal detected in: {plugin_path}")
            return False

        # Verify file exists and is a Python file
        if not path.exists():
            logger.error(f"SEC-004: Plugin file does not exist: {plugin_path}")
            return False

        if path.suffix != ".py":
            logger.error(f"SEC-004: Plugin must be a .py file: {plugin_path}")
            return False

        # If base_dir provided, ensure plugin is within allowed directories
        if base_dir:
            base = Path(base_dir).resolve()
            allowed = False
            for allowed_dir in ALLOWED_PLUGIN_DIRS:
                allowed_path = (base / allowed_dir).resolve()
                try:
                    path.relative_to(allowed_path)
                    allowed = True
                    break
                except ValueError:
                    continue

            if not allowed:
                logger.error(
                    f"SEC-004: Plugin outside allowed directories: {plugin_path}"
                )
                return False

        return True
    except Exception as e:
        logger.error(f"SEC-004: Plugin path validation failed: {e}")
        return False


def _sandbox_worker(plugin_path, class_name, params, pipe):
    """
    Sub-process worker that executes the skill logic.
    Re-imports the skill from path to avoid pickling issues.
    """
    try:
        # SEC-004: Validate plugin path before loading
        if not _validate_plugin_path(plugin_path):
            raise SecurityError(f"SEC-004: Invalid plugin path: {plugin_path}")

        # Load from path
        p = Path(plugin_path)
        spec = importlib.util.spec_from_file_location(p.stem, str(p))
        if not spec or not spec.loader:
            raise ImportError(f"Could not load plugin from {plugin_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        skill_class = getattr(module, class_name)
        skill = skill_class()

        result = skill.execute(params)
        pipe.send({"status": "success", "result": result})
    except Exception as e:
        pipe.send(
            {
                "status": "error",
                "message": f"{type(e).__name__}: {str(e)}",
                "trace": traceback.format_exc(),
            }
        )
    finally:
        pipe.close()


class PluginSandbox:
    """
    [Phase 57.2] Restricted execution environment for plugins.
    Wraps SovereignSkill execution in a separate process with a timeout.
    """

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def execute_safely(
        self, plugin_path: str, class_name: str, params: Dict[str, Any]
    ) -> str:
        """
        Executes a skill in a sandboxed process using its file path.

        SEC-004: Validates plugin path before execution.
        """
        # SEC-004: Validate path before spawning subprocess
        if not _validate_plugin_path(plugin_path):
            return (
                f"Error: SEC-004 - Invalid or unauthorized plugin path: {plugin_path}"
            )

        parent_conn, child_conn = multiprocessing.Pipe()

        process = multiprocessing.Process(
            target=_sandbox_worker, args=(plugin_path, class_name, params, child_conn)
        )

        logger.debug(f"[Sandbox] Starting process for {class_name}")
        process.start()

        if parent_conn.poll(self.timeout):
            response = parent_conn.recv()
            process.join()

            if response["status"] == "success":
                return response["result"]
            else:
                logger.error(f"[Sandbox] Plugin Error: {response['message']}")
                return f"Error: {response['message']}"
        else:
            logger.error(f"[Sandbox] Plugin Timeout ({self.timeout}s) exceeded.")
            process.terminate()
            process.join()
            return f"Error: Plugin execution timed out after {self.timeout}s."
