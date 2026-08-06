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
from typing import Any, Dict, List, Optional

from warm_logic.kernel.intelligence.skill_interface import SovereignSkill
from warm_logic.kernel.substrate.plugin_sandbox import PluginSandbox

logger = logging.getLogger("SkillEngine")


class SandboxedSkill(SovereignSkill):
    """
    Wrapper that executes a skill class within the PluginSandbox.
    """

    def __init__(
        self, skill_class: type, plugin_path: str, sandbox: PluginSandbox
    ) -> None:
        self._temp_instance = skill_class()  # To get metadata
        self._class_name = skill_class.__name__
        self._plugin_path = plugin_path
        self._sandbox = sandbox

    @property
    def name(self) -> str:
        return self._temp_instance.name

    @property
    def description(self) -> str:
        return self._temp_instance.description

    def get_specification(self) -> Dict[str, Any]:
        return self._temp_instance.get_specification()

    def execute(self, params: Dict[str, Any]) -> str:
        return self._sandbox.execute_safely(self._plugin_path, self._class_name, params)


class SkillRegistry:
    """
    Central registry for all active Sovereign Skills.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, SovereignSkill] = {}

    def register(self, skill: SovereignSkill) -> None:
        logger.info(f"Registering Skill: {skill.name}")
        self._skills[skill.name] = skill

    def get_skill(self, name: str) -> Optional[SovereignSkill]:
        return self._skills.get(name)

    def list_skills(self) -> List[SovereignSkill]:
        return list(self._skills.values())

    def get_discovery_prompt(self) -> str:
        if not self._skills:
            return ""

        discovery = "\n=== DYNAMIC SKILLS AVAILABLE ===\n"
        for skill in self._skills.values():
            spec = skill.get_specification()
            discovery += f"- {skill.name}: {skill.description}\n"
            discovery += f"  Parameters: {spec.get('parameters', {})}\n"
        return discovery


class SkillManager:
    """
    Handles dynamic loading and management of plugins.
    """

    def __init__(self, registry: Optional[SkillRegistry] = None) -> None:
        self.registry = registry or SkillRegistry()
        self.sandbox = PluginSandbox(timeout=15)

    def load_builtins(self) -> None:
        pass

    def load_plugins(self, plugin_dir: str) -> None:
        import importlib.util
        import os
        from pathlib import Path

        if not os.path.exists(plugin_dir):
            os.makedirs(plugin_dir, exist_ok=True)
            return

        for f in Path(plugin_dir).glob("*.py"):
            try:
                module_name = f.stem
                spec = importlib.util.spec_from_file_location(module_name, str(f))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, SovereignSkill)
                            and attr is not SovereignSkill
                        ):
                            # Wrap in Sandbox for Phase 57.2
                            sandboxed = SandboxedSkill(attr, str(f), self.sandbox)
                            self.registry.register(sandboxed)
            except Exception as e:
                logger.error(f"Failed to load plugin {f.name}: {e}")
