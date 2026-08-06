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
[Phase 109.4] Forensic Audit Logger.
Provides tamper-evident audit logging for compliance and legal evidence.
"""

import hashlib
import hmac
import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ForensicAudit")


class AuditEventType(Enum):
    """Types of audit events."""

    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    DATA_ACCESS = "data_access"
    DATA_MODIFY = "data_modify"
    DATA_DELETE = "data_delete"
    ADMIN_ACTION = "admin_action"
    SECURITY_ALERT = "security_alert"
    API_CALL = "api_call"
    VETO_TRIGGERED = "veto_triggered"
    CONFIG_CHANGE = "config_change"


@dataclass
class AuditEvent:
    """A single audit event."""

    id: str
    timestamp: str
    event_type: str
    actor: str
    action: str
    target: str
    details: Dict[str, Any]
    result: str  # success, failure, blocked
    previous_hash: str
    event_hash: str


class ForensicAuditLogger:
    """
    [Phase 109.4] Forensic Audit Logger.

    Provides tamper-evident audit logging with:
    1. Hash chain for integrity verification
    2. HMAC authentication
    3. Structured JSON logging
    4. Compliance-ready format
    """

    def __init__(
        self, log_path: Optional[str] = None, hmac_key: Optional[str] = None
    ) -> None:
        self.log_path = Path(log_path or "/app/logs/audit")
        self.log_path.mkdir(parents=True, exist_ok=True)

        # HMAC key for log authentication
        self.hmac_key = (
            hmac_key or os.environ.get("WARMLOGIC_AUDIT_KEY", "default-key")
        ).encode()

        self._counter = 0
        self._previous_hash = "GENESIS"
        self._lock = threading.Lock()

        # Load last hash from existing log
        self._load_chain_state()

        logger.info(f"[ForensicAudit] Active. Log path: {self.log_path}")

    def _load_chain_state(self) -> None:
        """Load the last hash from the existing audit log."""
        log_file = self.log_path / "audit.jsonl"
        if log_file.exists():
            try:
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    if lines:
                        last_event = json.loads(lines[-1])
                        self._previous_hash = last_event.get("event_hash", "GENESIS")
                        self._counter = int(
                            last_event.get("id", "AUD0").replace("AUD", "")
                        )
            except Exception as e:
                logger.warning(f"Could not load chain state: {e}")

    def _generate_id(self) -> str:
        self._counter += 1
        return f"AUD{self._counter:010d}"

    def _compute_hash(self, event_data: Dict) -> str:
        """Compute hash for event integrity."""
        # Include previous hash for chain
        data_str = json.dumps(event_data, sort_keys=True)
        combined = f"{self._previous_hash}:{data_str}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _compute_hmac(self, data: str) -> str:
        """Compute HMAC for authentication."""
        return hmac.new(self.hmac_key, data.encode(), hashlib.sha256).hexdigest()[:16]

    def log(
        self,
        event_type: AuditEventType,
        actor: str,
        action: str,
        target: str = "",
        details: Optional[Dict[str, Any]] = None,
        result: str = "success",
    ) -> AuditEvent:
        """Log an audit event."""
        with self._lock:
            event_id = self._generate_id()
            timestamp = datetime.utcnow().isoformat() + "Z"

            event_data: Dict[str, Any] = {
                "id": event_id,
                "timestamp": timestamp,
                "event_type": event_type.value,
                "actor": actor,
                "action": action,
                "target": target,
                "details": details or {},
                "result": result,
                "previous_hash": self._previous_hash,
            }

            event_hash = self._compute_hash(event_data)
            event_data["event_hash"] = event_hash

            # Create event object
            event = AuditEvent(**event_data)

            # Write to log file
            self._write_event(event_data)

            # Update chain state
            self._previous_hash = event_hash

            logger.debug(f"Audit: {event_type.value} by {actor} -> {result}")
            return event

    def _write_event(self, event_data: Dict[str, Any]) -> None:
        """Write event to log file."""
        log_file = self.log_path / "audit.jsonl"

        # Add HMAC for authentication
        event_json = json.dumps(event_data, ensure_ascii=False)
        event_data["_hmac"] = self._compute_hmac(event_json)

        with open(log_file, "a") as f:
            f.write(json.dumps(event_data, ensure_ascii=False) + "\n")

    def verify_chain(self) -> Dict[str, Any]:
        """Verify integrity of the entire audit chain."""
        log_file = self.log_path / "audit.jsonl"
        if not log_file.exists():
            return {"valid": True, "events": 0, "message": "No events to verify"}

        with open(log_file, "r") as f:
            lines = f.readlines()

        if not lines:
            return {"valid": True, "events": 0}

        valid_count = 0
        invalid_events = []
        expected_prev = "GENESIS"

        for i, line in enumerate(lines):
            try:
                event = json.loads(line)

                # Check previous hash chain
                if event.get("previous_hash") != expected_prev:
                    invalid_events.append(
                        {"line": i + 1, "id": event.get("id"), "error": "broken_chain"}
                    )

                # Verify event hash
                stored_hash = event.get("event_hash")
                event_copy = {
                    k: v for k, v in event.items() if k not in ("event_hash", "_hmac")
                }
                event_copy["previous_hash"] = event.get("previous_hash")

                computed_hash = hashlib.sha256(
                    f"{event.get('previous_hash')}:{json.dumps(event_copy, sort_keys=True)}".encode()
                ).hexdigest()[:32]

                if stored_hash != computed_hash:
                    invalid_events.append(
                        {"line": i + 1, "id": event.get("id"), "error": "hash_mismatch"}
                    )
                else:
                    valid_count += 1

                expected_prev = stored_hash

            except Exception as e:
                invalid_events.append({"line": i + 1, "error": str(e)})

        return {
            "valid": len(invalid_events) == 0,
            "total_events": len(lines),
            "valid_events": valid_count,
            "invalid_events": invalid_events,
        }

    def search(
        self,
        event_type: Optional[AuditEventType] = None,
        actor: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search audit events."""
        log_file = self.log_path / "audit.jsonl"
        if not log_file.exists():
            return []

        results = []
        with open(log_file, "r") as f:
            for line in f:
                try:
                    event = json.loads(line)

                    # Apply filters
                    if event_type and event.get("event_type") != event_type.value:
                        continue
                    if actor and event.get("actor") != actor:
                        continue
                    if start_time and event.get("timestamp", "") < start_time:
                        continue
                    if end_time and event.get("timestamp", "") > end_time:
                        continue

                    results.append(event)

                    if len(results) >= limit:
                        break

                except json.JSONDecodeError:
                    continue

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        log_file = self.log_path / "audit.jsonl"
        if not log_file.exists():
            return {"total_events": 0}

        event_counts: Dict[str, int] = {}
        result_counts: Dict[str, int] = {"success": 0, "failure": 0, "blocked": 0}

        with open(log_file, "r") as f:
            for line in f:
                try:
                    event = json.loads(line)
                    event_type = event.get("event_type", "unknown")
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1

                    result = event.get("result", "unknown")
                    if result in result_counts:
                        result_counts[result] += 1
                except Exception:
                    continue

        return {
            "total_events": sum(event_counts.values()),
            "by_type": event_counts,
            "by_result": result_counts,
            "chain_valid": self.verify_chain()["valid"],
        }


# Global audit logger
_audit_logger: Optional[ForensicAuditLogger] = None
_audit_logger_lock = threading.Lock()


def get_audit_logger() -> ForensicAuditLogger:
    """Get or create the global audit logger (thread-safe)."""
    global _audit_logger
    if _audit_logger is None:
        with _audit_logger_lock:
            if _audit_logger is None:  # Double-checked locking
                _audit_logger = ForensicAuditLogger()
    return _audit_logger


def audit(
    event_type: AuditEventType, actor: str, action: str, **kwargs: Any
) -> AuditEvent:
    """Quick audit logging function."""
    return get_audit_logger().log(event_type, actor, action, **kwargs)
