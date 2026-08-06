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
[Phase 102.3] Infrastructure Monitoring.
Implements system health monitoring and metrics collection.
"""

import logging
import os
import platform
import sys
from dataclasses import dataclass, field
import psutil
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("InfraMonitor")


@dataclass
class HealthMetric:
    """A single health metric."""

    name: str
    value: float
    unit: str
    status: str  # "healthy", "warning", "critical"
    threshold_warning: float
    threshold_critical: float
    timestamp: datetime = field(default_factory=datetime.now)


class InfrastructureMonitor:
    """
    [Phase 102.3] Infrastructure Health Monitor.

    Monitors:
    1. System resources (CPU, Memory, Disk)
    2. Process health
    3. API latency
    4. Error rates
    """

    def __init__(self):
        self.metrics: List[HealthMetric] = []
        self.alerts: List[Dict[str, Any]] = []
        self._start_time = datetime.now()
        self.threshold_disk_warn = float(os.getenv("WARM_DISK_WARN", "80.0"))
        self.threshold_disk_critical = float(os.getenv("WARM_DISK_CRIT", "90.0"))
        logger.info("[InfraMonitor] Monitoring Active.")

    def collect_metrics(self) -> Dict[str, HealthMetric]:
        """Collect all system metrics."""
        metrics = {}

        # Memory (basic Python)
        try:
            import resource

            mem_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # Convert to MB (macOS reports in bytes, Linux in KB)
            if platform.system() == "Darwin":
                mem_mb = mem_usage / 1024 / 1024
            else:
                mem_mb = mem_usage / 1024

            metrics["memory"] = HealthMetric(
                name="Memory Usage",
                value=mem_mb,
                unit="MB",
                status=self._get_status(mem_mb, 500, 1000),
                threshold_warning=500,
                threshold_critical=1000,
            )
        except Exception:
            pass

        # Uptime
        uptime_seconds = (datetime.now() - self._start_time).total_seconds()
        metrics["uptime"] = HealthMetric(
            name="Uptime",
            value=uptime_seconds,
            unit="seconds",
            status="healthy",
            threshold_warning=0,
            threshold_critical=0,
        )

        # Python version
        py_version = float(f"{sys.version_info.major}.{sys.version_info.minor}")
        # 2. Disk Usage
        try:
            disk = psutil.disk_usage("/")
            disk_warn = 80.0
            disk_critical = 95.0
            metrics["disk_usage"] = HealthMetric(
                name="disk_usage",
                value=float(disk.percent),
                unit="%",
                status=self._get_status(disk.percent, disk_warn, disk_critical),
                threshold_warning=disk_warn,
                threshold_critical=disk_critical,
            )
        except Exception:
            pass

        # Disk space (current directory)
        try:
            stat = os.statvfs(".")
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            metrics["disk_free"] = HealthMetric(
                name="Disk Free",
                value=free_gb,
                unit="GB",
                status=self._get_status_reverse(free_gb, 10, 5),
                threshold_warning=10,
                threshold_critical=5,
            )
        except Exception:
            pass

        # Store metrics
        self.metrics.extend(metrics.values())

        return metrics

    def _get_status(self, value: float, warning: float, critical: float) -> str:
        """Get status based on thresholds (higher is worse)."""
        if value >= critical:
            return "critical"
        elif value >= warning:
            return "warning"
        return "healthy"

    def _get_status_reverse(self, value: float, warning: float, critical: float) -> str:
        """Get status based on thresholds (lower is worse)."""
        if value <= critical:
            return "critical"
        elif value <= warning:
            return "warning"
        return "healthy"

    def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        metrics = self.collect_metrics()

        health: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {},
        }

        critical_count = 0
        warning_count = 0

        for name, metric in metrics.items():
            health["checks"][name] = {
                "value": metric.value,
                "unit": metric.unit,
                "status": metric.status,
            }

            if metric.status == "critical":
                critical_count += 1
            elif metric.status == "warning":
                warning_count += 1

        # Set overall status
        if critical_count > 0:
            health["status"] = "critical"
        elif warning_count > 0:
            health["status"] = "warning"

        health["summary"] = {
            "healthy": len(metrics) - critical_count - warning_count,
            "warning": warning_count,
            "critical": critical_count,
        }

        return health

    def add_custom_metric(
        self,
        name: str,
        value: float,
        unit: str,
        warning_threshold: float,
        critical_threshold: float,
    ):
        """Add a custom metric."""
        metric = HealthMetric(
            name=name,
            value=value,
            unit=unit,
            status=self._get_status(value, warning_threshold, critical_threshold),
            threshold_warning=warning_threshold,
            threshold_critical=critical_threshold,
        )
        self.metrics.append(metric)
        logger.debug(f"Added custom metric: {name}")

    def get_alerts(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        if since:
            return [a for a in self.alerts if a["timestamp"] > since.isoformat()]
        return self.alerts

    def generate_report(self) -> str:
        """Generate a health report."""
        health = self.check_health()

        status_icon = {"healthy": "✅", "warning": "⚠️", "critical": "🚨"}.get(
            health["status"], "❓"
        )

        lines = [
            f"# {status_icon} Infrastructure Health Report\n",
            f"**Status**: {health['status'].upper()}",
            f"**Timestamp**: {health['timestamp']}\n",
            "## Metrics\n",
            "| Metric | Value | Status |",
            "|--------|-------|--------|",
        ]

        for name, check in health["checks"].items():
            icon = {"healthy": "✅", "warning": "⚠️", "critical": "🚨"}.get(
                check["status"], ""
            )
            lines.append(f"| {name} | {check['value']:.2f} {check['unit']} | {icon} |")

        lines.extend(
            [
                "",
                "## Summary",
                f"- Healthy: {health['summary']['healthy']}",
                f"- Warning: {health['summary']['warning']}",
                f"- Critical: {health['summary']['critical']}",
            ]
        )

        return "\n".join(lines)


def get_monitor() -> InfrastructureMonitor:
    """Get a new infrastructure monitor."""
    return InfrastructureMonitor()
