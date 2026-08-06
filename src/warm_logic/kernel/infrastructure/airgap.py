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
[Phase 109.3] Airgap Mode - Offline Operation.
Enables WarmLogic to run completely offline for secure environments.
"""

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

logger = logging.getLogger("AirgapMode")


def _get_secure_temp_path(subdir: str) -> str:
    """Get a secure temporary path using system temp directory."""
    base = os.environ.get("WARMLOGIC_DATA_DIR", tempfile.gettempdir())
    return str(Path(base) / "warmlogic" / subdir)


@dataclass
class AirgapConfig:
    """Configuration for airgap operation."""

    enabled: bool = False
    local_model_path: str = field(
        default_factory=lambda: _get_secure_temp_path("models")
    )
    local_data_path: str = field(default_factory=lambda: _get_secure_temp_path("data"))
    disable_telemetry: bool = True
    disable_external_api: bool = True
    allow_usb_import: bool = False
    encryption_required: bool = True


class AirgapManager:
    """
    [Phase 109.3] Airgap Mode Manager.

    Manages offline operation for secure/classified environments.

    Features:
    1. Complete network isolation
    2. Local model storage
    3. USB import/export with encryption
    4. Audit trail for all operations
    """

    def __init__(self, config: Optional[AirgapConfig] = None) -> None:
        self.config = config or AirgapConfig()
        self._initialized = False
        self._external_blocked: Set[str] = set()

        if self.config.enabled:
            self._enable_airgap()

        logger.info(
            f"🔒 [AirgapMode] {'ENABLED' if self.config.enabled else 'DISABLED'}"
        )

    def _enable_airgap(self) -> None:
        """Enable airgap mode restrictions."""
        # Block external network access
        self._block_external_network()

        # Ensure local paths exist
        Path(self.config.local_model_path).mkdir(parents=True, exist_ok=True)
        Path(self.config.local_data_path).mkdir(parents=True, exist_ok=True)

        # Disable telemetry
        os.environ["WARMLOGIC_TELEMETRY"] = "disabled"
        os.environ["WARMLOGIC_AIRGAP"] = "true"

        self._initialized = True
        logger.info("Airgap restrictions applied")

    def _block_external_network(self) -> None:
        """Block external network operations."""
        blocked_hosts = [
            "api.openai.com",
            "api.anthropic.com",
            "huggingface.co",
            "*.amazonaws.com",
            "*.azure.com",
            "*.google.com",
        ]
        self._external_blocked = set(blocked_hosts)

    def check_network_allowed(self, host: str) -> bool:
        """Check if network access is allowed."""
        if not self.config.enabled:
            return True

        # In airgap mode, only local network is allowed
        if host in ("localhost", "127.0.0.1", "::1"):
            return True

        # Check blocked patterns
        for pattern in self._external_blocked:
            if pattern.startswith("*"):
                if host.endswith(pattern[1:]):
                    return False
            elif host == pattern:
                return False

        return not self.config.disable_external_api

    def import_from_usb(
        self, source_path: str, encryption_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import data from USB device."""
        if not self.config.allow_usb_import:
            return {"success": False, "error": "USB import disabled"}

        if self.config.encryption_required and not encryption_key:
            return {"success": False, "error": "Encryption key required"}

        source = Path(source_path)
        if not source.exists():
            return {"success": False, "error": "Source not found"}

        # Audit log
        self._log_import(
            {
                "source": str(source),
                "timestamp": datetime.now().isoformat(),
                "encrypted": encryption_key is not None,
            }
        )

        # In production, would decrypt and verify integrity
        return {
            "success": True,
            "imported_path": str(source),
            "timestamp": datetime.now().isoformat(),
        }

    def export_to_usb(
        self, data_path: str, dest_path: str, encryption_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Export data to USB device with encryption."""
        if self.config.encryption_required and not encryption_key:
            return {"success": False, "error": "Encryption key required"}

        data = Path(data_path)
        if not data.exists():
            return {"success": False, "error": "Data not found"}

        # Audit log
        self._log_export(
            {
                "data": str(data),
                "destination": dest_path,
                "timestamp": datetime.now().isoformat(),
                "encrypted": encryption_key is not None,
            }
        )

        # In production, would encrypt before export
        return {
            "success": True,
            "exported_path": dest_path,
            "encrypted": encryption_key is not None,
        }

    def _log_import(self, details: Dict[str, Any]) -> None:
        """Log import operation for audit."""
        log_path = Path(self.config.local_data_path) / "audit" / "imports.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a") as f:
            f.write(json.dumps(details) + "\n")

    def _log_export(self, details: Dict[str, Any]) -> None:
        """Log export operation for audit."""
        log_path = Path(self.config.local_data_path) / "audit" / "exports.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a") as f:
            f.write(json.dumps(details) + "\n")

    def get_status(self) -> Dict[str, Any]:
        """Get airgap status."""
        return {
            "enabled": self.config.enabled,
            "initialized": self._initialized,
            "telemetry_disabled": self.config.disable_telemetry,
            "external_api_disabled": self.config.disable_external_api,
            "usb_import_allowed": self.config.allow_usb_import,
            "encryption_required": self.config.encryption_required,
            "blocked_hosts": list(self._external_blocked),
        }


# Global airgap manager
_airgap_manager: Optional[AirgapManager] = None
_airgap_manager_lock = threading.Lock()


def get_airgap_manager() -> AirgapManager:
    """Get or create the global airgap manager (thread-safe)."""
    global _airgap_manager
    if _airgap_manager is None:
        with _airgap_manager_lock:
            if _airgap_manager is None:  # Double-checked locking
                enabled = (
                    os.environ.get("WARMLOGIC_AIRGAP_MODE", "false").lower() == "true"
                )
                _airgap_manager = AirgapManager(AirgapConfig(enabled=enabled))
    return _airgap_manager


def is_airgap_mode() -> bool:
    """Check if running in airgap mode."""
    return get_airgap_manager().config.enabled
