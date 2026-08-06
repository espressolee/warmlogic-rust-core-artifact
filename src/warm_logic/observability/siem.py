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
Security Information and Event Management (SIEM) Integration

Exports audit events to enterprise SIEM platforms:
- Splunk (HTTP Event Collector)
- Datadog (Logs API)
- Elastic Security (future)
- Microsoft Sentinel (future)

Supports Common Event Format (CEF) and JSON structured logging.
"""

import hashlib
import json
import logging
import os
import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("SIEM")


class SIEMProvider(Enum):
    """Supported SIEM providers."""

    SPLUNK = "splunk"
    DATADOG = "datadog"
    ELASTIC = "elastic"
    SENTINEL = "sentinel"


class EventSeverity(Enum):
    """CEF severity levels (0-10 scale)."""

    UNKNOWN = 0
    LOW = 3
    MEDIUM = 5
    HIGH = 7
    CRITICAL = 10


@dataclass
class SIEMConfig:
    """SIEM integration configuration."""

    provider: SIEMProvider
    enabled: bool = False

    # Splunk HEC settings
    splunk_hec_url: Optional[str] = None
    splunk_hec_token: Optional[str] = None
    splunk_index: str = "warmlogic"
    splunk_source: str = "warmlogic:audit"
    splunk_sourcetype: str = "warmlogic:security"

    # Datadog settings
    datadog_api_key: Optional[str] = None
    datadog_site: str = "datadoghq.com"  # US1
    datadog_service: str = "warmlogic"
    datadog_env: str = "production"
    datadog_tags: List[str] = field(default_factory=list)

    # Common settings
    batch_size: int = 100
    flush_interval_seconds: float = 5.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    use_tls: bool = True
    verify_ssl: bool = True

    # CEF format settings
    cef_vendor: str = "WarmLogic"
    cef_product: str = "WarmLogic"
    cef_version: str = "1.1.0"


@dataclass
class AuditEvent:
    """Structured audit event for SIEM export."""

    event_id: str
    timestamp: float
    event_type: str
    severity: EventSeverity
    source: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    # Actor information
    actor_id: Optional[str] = None
    actor_type: Optional[str] = None  # user, system, service

    # Resource information
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None

    # Outcome
    outcome: str = "success"  # success, failure, unknown

    # Network context
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None

    def to_cef(self, config: SIEMConfig) -> str:
        """Convert to Common Event Format (CEF)."""
        # CEF:Version|Device Vendor|Device Product|Device Version|
        # Signature ID|Name|Severity|Extension
        extension = self._build_cef_extension()
        return (
            f"CEF:0|{config.cef_vendor}|{config.cef_product}|{config.cef_version}|"
            f"{self.event_type}|{self.message}|{self.severity.value}|{extension}"
        )

    def _build_cef_extension(self) -> str:
        """Build CEF extension key=value pairs."""
        ext = {
            "rt": int(self.timestamp * 1000),  # Receipt Time in milliseconds
            "src": self.source,
            "outcome": self.outcome,
        }
        if self.actor_id:
            ext["suser"] = self.actor_id
        if self.source_ip:
            ext["src"] = self.source_ip
        if self.destination_ip:
            ext["dst"] = self.destination_ip
        if self.resource_id:
            ext["cs1"] = self.resource_id
            ext["cs1Label"] = "ResourceID"

        return " ".join(f"{k}={v}" for k, v in ext.items())

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "event_id": self.event_id,
            "timestamp": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat(),
            "event_type": self.event_type,
            "severity": self.severity.name,
            "severity_value": self.severity.value,
            "source": self.source,
            "message": self.message,
            "details": self.details,
            "actor": (
                {
                    "id": self.actor_id,
                    "type": self.actor_type,
                }
                if self.actor_id
                else None
            ),
            "resource": (
                {
                    "id": self.resource_id,
                    "type": self.resource_type,
                }
                if self.resource_id
                else None
            ),
            "outcome": self.outcome,
            "network": (
                {
                    "source_ip": self.source_ip,
                    "destination_ip": self.destination_ip,
                }
                if self.source_ip or self.destination_ip
                else None
            ),
        }


class SIEMExporter(ABC):
    """Abstract base class for SIEM exporters."""

    def __init__(self, config: SIEMConfig):
        self.config = config
        self._event_queue: queue.Queue[AuditEvent] = queue.Queue()
        self._shutdown = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._initialized = False
        self._events_sent = 0
        self._events_failed = 0

    @abstractmethod
    def _send_batch(self, events: List[AuditEvent]) -> bool:
        """Send a batch of events to the SIEM. Returns True on success."""
        pass

    def initialize(self) -> bool:
        """Initialize the exporter and start the worker thread."""
        if not self.config.enabled:
            logger.info(f"SIEM {self.__class__.__name__} is disabled")
            return True

        try:
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"SIEM-{self.config.provider.value}",
            )
            self._worker_thread.start()
            self._initialized = True
            logger.info(f"SIEM {self.__class__.__name__} initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SIEM exporter: {e}")
            return False

    def shutdown(self, timeout: float = 10.0) -> None:
        """Gracefully shutdown the exporter, flushing remaining events."""
        self._shutdown.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        logger.info(
            f"SIEM exporter shutdown. Sent: {self._events_sent}, Failed: {self._events_failed}"
        )

    def export(self, event: AuditEvent) -> None:
        """Queue an event for export."""
        if not self.config.enabled:
            return
        self._event_queue.put(event)

    def export_batch(self, events: List[AuditEvent]) -> None:
        """Queue multiple events for export."""
        for event in events:
            self.export(event)

    def _worker_loop(self) -> None:
        """Background worker that batches and sends events."""
        batch: List[AuditEvent] = []
        last_flush = time.time()

        while not self._shutdown.is_set():
            try:
                # Try to get an event with timeout
                event = self._event_queue.get(timeout=0.5)
                batch.append(event)
                self._event_queue.task_done()
            except queue.Empty:
                pass

            # Check if we should flush
            should_flush = len(batch) >= self.config.batch_size or (
                batch and time.time() - last_flush >= self.config.flush_interval_seconds
            )

            if should_flush and batch:
                self._flush_batch(batch)
                batch = []
                last_flush = time.time()

        # Final flush on shutdown
        if batch:
            self._flush_batch(batch)

    def _flush_batch(self, batch: List[AuditEvent]) -> None:
        """Flush a batch with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                if self._send_batch(batch):
                    self._events_sent += len(batch)
                    return
            except Exception as e:
                logger.warning(f"SIEM batch send failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_seconds * (attempt + 1))

        self._events_failed += len(batch)
        logger.error(f"SIEM batch send failed after {self.config.max_retries} retries")

    @property
    def stats(self) -> Dict[str, int]:
        """Get export statistics."""
        return {
            "sent": self._events_sent,
            "failed": self._events_failed,
            "queued": self._event_queue.qsize(),
        }


class SplunkHECExporter(SIEMExporter):
    """Splunk HTTP Event Collector (HEC) exporter."""

    def _send_batch(self, events: List[AuditEvent]) -> bool:
        """Send events to Splunk HEC."""
        if not self.config.splunk_hec_url or not self.config.splunk_hec_token:
            logger.error("Splunk HEC URL or token not configured")
            return False

        # Build HEC payload (batch format)
        payload_lines = []
        for event in events:
            hec_event = {
                "time": event.timestamp,
                "source": self.config.splunk_source,
                "sourcetype": self.config.splunk_sourcetype,
                "index": self.config.splunk_index,
                "event": event.to_json(),
            }
            payload_lines.append(json.dumps(hec_event))

        payload = "\n".join(payload_lines)

        # Send to HEC
        headers = {
            "Authorization": f"Splunk {self.config.splunk_hec_token}",
            "Content-Type": "application/json",
        }

        try:
            req = Request(
                self.config.splunk_hec_url,
                data=payload.encode("utf-8"),
                headers=headers,
                method="POST",
            )

            # Note: In production, use requests library with proper SSL verification
            # This uses urllib for minimal dependencies
            with urlopen(req, timeout=30) as response:
                if response.status == 200:
                    logger.debug(f"Splunk HEC: Sent {len(events)} events")
                    return True
                else:
                    logger.warning(f"Splunk HEC returned status {response.status}")
                    return False
        except HTTPError as e:
            logger.error(f"Splunk HEC HTTP error: {e.code} - {e.reason}")
            return False
        except URLError as e:
            logger.error(f"Splunk HEC URL error: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"Splunk HEC error: {e}")
            return False


class DatadogExporter(SIEMExporter):
    """Datadog Logs API exporter."""

    def _send_batch(self, events: List[AuditEvent]) -> bool:
        """Send events to Datadog Logs API."""
        if not self.config.datadog_api_key:
            logger.error("Datadog API key not configured")
            return False

        # Build Datadog logs payload
        logs = []
        for event in events:
            log_entry = {
                "ddsource": "warmlogic",
                "ddtags": ",".join(
                    self.config.datadog_tags
                    + [
                        f"env:{self.config.datadog_env}",
                        f"service:{self.config.datadog_service}",
                        f"severity:{event.severity.name.lower()}",
                    ]
                ),
                "hostname": os.environ.get("HOSTNAME", "warmlogic-node"),
                "service": self.config.datadog_service,
                "message": event.message,
                "status": self._severity_to_dd_status(event.severity),
                **event.to_json(),
            }
            logs.append(log_entry)

        payload = json.dumps(logs)

        # Datadog Logs API endpoint
        url = f"https://http-intake.logs.{self.config.datadog_site}/api/v2/logs"

        headers = {
            "DD-API-KEY": self.config.datadog_api_key,
            "Content-Type": "application/json",
        }

        try:
            req = Request(
                url,
                data=payload.encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urlopen(req, timeout=30) as response:
                if response.status in (200, 202):
                    logger.debug(f"Datadog: Sent {len(events)} events")
                    return True
                else:
                    logger.warning(f"Datadog returned status {response.status}")
                    return False
        except HTTPError as e:
            logger.error(f"Datadog HTTP error: {e.code} - {e.reason}")
            return False
        except URLError as e:
            logger.error(f"Datadog URL error: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"Datadog error: {e}")
            return False

    @staticmethod
    def _severity_to_dd_status(severity: EventSeverity) -> str:
        """Map severity to Datadog status."""
        mapping = {
            EventSeverity.UNKNOWN: "info",
            EventSeverity.LOW: "info",
            EventSeverity.MEDIUM: "warn",
            EventSeverity.HIGH: "error",
            EventSeverity.CRITICAL: "critical",
        }
        return mapping.get(severity, "info")


class SIEMManager:
    """
    Unified SIEM export manager.

    Manages multiple SIEM exporters and routes events to all configured destinations.
    """

    def __init__(self, configs: Optional[List[SIEMConfig]] = None):
        self._exporters: Dict[SIEMProvider, SIEMExporter] = {}
        self._initialized = False

        if configs:
            for config in configs:
                self.add_exporter(config)

    def add_exporter(self, config: SIEMConfig) -> bool:
        """Add a SIEM exporter based on configuration."""
        if not config.enabled:
            return True

        exporter: Optional[SIEMExporter] = None

        if config.provider == SIEMProvider.SPLUNK:
            exporter = SplunkHECExporter(config)
        elif config.provider == SIEMProvider.DATADOG:
            exporter = DatadogExporter(config)
        else:
            logger.warning(f"Unsupported SIEM provider: {config.provider}")
            return False

        if exporter:
            self._exporters[config.provider] = exporter
            return True
        return False

    def initialize(self) -> bool:
        """Initialize all exporters."""
        success = True
        for provider, exporter in self._exporters.items():
            if not exporter.initialize():
                logger.error(f"Failed to initialize {provider.value} exporter")
                success = False
        self._initialized = success
        return success

    def shutdown(self, timeout: float = 10.0) -> None:
        """Shutdown all exporters."""
        for exporter in self._exporters.values():
            exporter.shutdown(timeout=timeout / len(self._exporters))

    def export(self, event: AuditEvent) -> None:
        """Export event to all configured SIEM systems."""
        for exporter in self._exporters.values():
            exporter.export(event)

    def export_batch(self, events: List[AuditEvent]) -> None:
        """Export batch to all configured SIEM systems."""
        for exporter in self._exporters.values():
            exporter.export_batch(events)

    @property
    def is_enabled(self) -> bool:
        """Check if any SIEM exporter is enabled."""
        return len(self._exporters) > 0

    @property
    def stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics from all exporters."""
        return {
            provider.value: exporter.stats
            for provider, exporter in self._exporters.items()
        }


# Global SIEM manager instance
_siem_manager: Optional[SIEMManager] = None


def get_siem_manager() -> SIEMManager:
    """Get the global SIEM manager instance."""
    global _siem_manager
    if _siem_manager is None:
        _siem_manager = SIEMManager()
    return _siem_manager


def initialize_siem_from_env() -> SIEMManager:
    """
    Initialize SIEM manager from environment variables.

    Environment variables:
    - SIEM_SPLUNK_ENABLED: true/false
    - SIEM_SPLUNK_HEC_URL: Splunk HEC endpoint
    - SIEM_SPLUNK_HEC_TOKEN: Splunk HEC token
    - SIEM_SPLUNK_INDEX: Index name (default: warmlogic)
    - SIEM_DATADOG_ENABLED: true/false
    - SIEM_DATADOG_API_KEY: Datadog API key
    - SIEM_DATADOG_SITE: Datadog site (default: datadoghq.com)
    - SIEM_BATCH_SIZE: Batch size (default: 100)
    - SIEM_FLUSH_INTERVAL: Flush interval in seconds (default: 5)
    """
    global _siem_manager

    configs: List[SIEMConfig] = []

    # Splunk configuration
    if os.environ.get("SIEM_SPLUNK_ENABLED", "").lower() == "true":
        splunk_config = SIEMConfig(
            provider=SIEMProvider.SPLUNK,
            enabled=True,
            splunk_hec_url=os.environ.get("SIEM_SPLUNK_HEC_URL"),
            splunk_hec_token=os.environ.get("SIEM_SPLUNK_HEC_TOKEN"),
            splunk_index=os.environ.get("SIEM_SPLUNK_INDEX", "warmlogic"),
            batch_size=int(os.environ.get("SIEM_BATCH_SIZE", "100")),
            flush_interval_seconds=float(os.environ.get("SIEM_FLUSH_INTERVAL", "5.0")),
        )
        configs.append(splunk_config)
        logger.info("Splunk SIEM configured from environment")

    # Datadog configuration
    if os.environ.get("SIEM_DATADOG_ENABLED", "").lower() == "true":
        datadog_config = SIEMConfig(
            provider=SIEMProvider.DATADOG,
            enabled=True,
            datadog_api_key=os.environ.get("SIEM_DATADOG_API_KEY"),
            datadog_site=os.environ.get("SIEM_DATADOG_SITE", "datadoghq.com"),
            datadog_env=os.environ.get("SIEM_DATADOG_ENV", "production"),
            datadog_service=os.environ.get("SIEM_DATADOG_SERVICE", "warmlogic"),
            batch_size=int(os.environ.get("SIEM_BATCH_SIZE", "100")),
            flush_interval_seconds=float(os.environ.get("SIEM_FLUSH_INTERVAL", "5.0")),
        )
        configs.append(datadog_config)
        logger.info("Datadog SIEM configured from environment")

    _siem_manager = SIEMManager(configs)
    _siem_manager.initialize()
    return _siem_manager


# Convenience functions for audit integration
def export_audit_event(
    event_type: str,
    message: str,
    severity: EventSeverity = EventSeverity.MEDIUM,
    source: str = "warmlogic:kernel",
    actor_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    outcome: str = "success",
) -> None:
    """
    Export an audit event to all configured SIEM systems.

    This is the primary interface for WarmLogic components to emit security events.
    """
    manager = get_siem_manager()
    if not manager.is_enabled:
        return

    # Generate event ID using hash of key fields
    event_id = hashlib.sha256(
        f"{time.time()}{event_type}{message}".encode()
    ).hexdigest()[:16]

    event = AuditEvent(
        event_id=event_id,
        timestamp=time.time(),
        event_type=event_type,
        severity=severity,
        source=source,
        message=message,
        details=details or {},
        actor_id=actor_id,
        resource_id=resource_id,
        outcome=outcome,
    )

    manager.export(event)


def export_governance_event(
    action: str,
    decision: str,
    actor_id: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Export a governance decision event."""
    export_audit_event(
        event_type="governance.decision",
        message=f"Governance {action}: {decision}",
        severity=EventSeverity.HIGH,
        source="warmlogic:governance",
        actor_id=actor_id,
        resource_id=resource_id,
        details=details,
        outcome="success" if decision == "approved" else "failure",
    )


def export_security_event(
    threat_type: str,
    description: str,
    severity: EventSeverity = EventSeverity.HIGH,
    source_ip: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Export a security threat event."""
    manager = get_siem_manager()
    if not manager.is_enabled:
        return

    event_id = hashlib.sha256(
        f"{time.time()}{threat_type}{description}".encode()
    ).hexdigest()[:16]

    event = AuditEvent(
        event_id=event_id,
        timestamp=time.time(),
        event_type=f"security.{threat_type}",
        severity=severity,
        source="warmlogic:security",
        message=description,
        details=details or {},
        source_ip=source_ip,
        outcome="detected",
    )

    manager.export(event)


def export_consensus_event(
    round_id: str,
    outcome: str,
    participants: int,
    quorum_reached: bool,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Export a BFT consensus round event."""
    export_audit_event(
        event_type="consensus.round",
        message=f"BFT Round {round_id}: {outcome}",
        severity=EventSeverity.MEDIUM if quorum_reached else EventSeverity.HIGH,
        source="warmlogic:consensus",
        resource_id=round_id,
        details={
            "participants": participants,
            "quorum_reached": quorum_reached,
            **(details or {}),
        },
        outcome="success" if quorum_reached else "failure",
    )
