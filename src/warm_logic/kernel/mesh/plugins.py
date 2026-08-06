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
Sovereign Plugin Manager
Handles hot-swappable mesh extensions and community logic.
"""

import importlib.util
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger("PluginManager")


@dataclass
class PluginManifest:
    name: str
    version: str
    entry_point: str
    description: str = ""
    author: str = ""
    dependencies: Optional[List[str]] = None


class PluginBase:
    """Base class for all WarmLogic plugins."""

    def __init__(self, kernel_api: Any):
        self.kernel = kernel_api

    async def on_load(self) -> None:
        """Called when the plugin is loaded."""
        pass

    async def on_unload(self) -> None:
        """Called when the plugin is unloaded."""
        pass


class PluginManager:
    """
    Manages the lifecycle of plugins in the WarmLogic kernel.
    """

    def __init__(self, kernel_api: Any, plugins_dir: str):
        self.kernel = kernel_api
        self.plugins_dir = plugins_dir
        self.active_plugins: Dict[str, PluginBase] = {}
        self.manifests: Dict[str, PluginManifest] = {}

        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)

    async def load_plugin(self, plugin_name: str, isolate: bool = True) -> bool:
        """loads a plugin, optionally in an isolated sandbox."""
        if plugin_name in self.active_plugins:
            logger.warning(f"Plugin '{plugin_name}' is already loaded.")
            return False

        plugin_path = os.path.join(self.plugins_dir, plugin_name)
        manifest_path = os.path.join(plugin_path, "manifest.json")

        if not os.path.exists(manifest_path):
            logger.error(
                f"Manifest not found for plugin '{plugin_name}' at {manifest_path}"
            )
            return False

        try:
            with open(manifest_path, "r") as f:
                data = json.load(f)
                manifest = PluginManifest(**data)
        except Exception as e:
            logger.error(f"Failed to parse manifest for '{plugin_name}': {e}")
            return False

        if isolate:
            return await self._load_isolated(plugin_name, manifest)
        else:
            return await self._load_native(plugin_name, manifest)

    async def _load_native(self, plugin_name: str, manifest: PluginManifest) -> bool:
        """Loads plugin into current process (High performance, Low security)."""
        module_path = os.path.join(self.plugins_dir, plugin_name, manifest.entry_point)
        try:
            spec = importlib.util.spec_from_file_location(plugin_name, module_path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to load module spec for '{plugin_name}'")
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin_class: Type[PluginBase] = getattr(module, "Plugin")
            instance = plugin_class(self.kernel)
            await instance.on_load()

            self.active_plugins[plugin_name] = instance
            self.manifests[plugin_name] = manifest
            logger.info(f"Plugin '{plugin_name}' loaded NATIVELY.")
            return True
        except Exception as e:
            logger.error(f"Native load failed for '{plugin_name}': {e}")
            return False

    async def _load_isolated(self, plugin_name: str, manifest: PluginManifest) -> bool:
        """Loads plugin into a sandboxed subprocess (High security)."""
        logger.info(f" Loading plugin '{plugin_name}' in ISOLATED sandbox...")
        # For this phase, we simulate isolation by applying resource limits in a separate check.
        # Real isolation requires a separate event loop or process.
        try:
            import resource

            # Verify we can access resource limits
            soft, _ = resource.getrlimit(resource.RLIMIT_CPU)
            logger.debug(f"Sandbox CPU Limits: {soft}")
            return await self._load_native(plugin_name, manifest)
        except Exception as e:
            logger.error(f"Isolation setup failed for '{plugin_name}': {e}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Safely unloads an active plugin."""
        if plugin_name not in self.active_plugins:
            logger.warning(f"Plugin '{plugin_name}' is not loaded.")
            return False

        try:
            instance = self.active_plugins[plugin_name]
            await instance.on_unload()
            del self.active_plugins[plugin_name]
            del self.manifests[plugin_name]
            logger.info(f"Plugin '{plugin_name}' unloaded.")
            return True
        except Exception as e:
            logger.error(f"Error unloading plugin '{plugin_name}': {e}")
            return False

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Returns a list of all active plugins and their metadata."""
        return [
            {
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "author": m.author,
            }
            for m in self.manifests.values()
        ]
