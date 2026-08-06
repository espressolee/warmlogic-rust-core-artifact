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
[Phase 109.2] Prometheus Metrics Exporter.
Exposes system metrics for monitoring dashboards.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger("Metrics")


@dataclass
class MetricValue:
    """A single metric value."""

    name: str
    value: float
    labels: Dict[str, str]
    timestamp: float
    metric_type: str  # gauge, counter, histogram


class MetricsExporter:
    """
    [Phase 109.2] Prometheus-Compatible Metrics Exporter.

    Exposes metrics for:
    1. System health (CPU, memory, disk)
    2. AI module performance
    3. API request metrics
    4. Security events
    """

    def __init__(self) -> None:
        self.metrics: Dict[str, MetricValue] = {}
        self.counters: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Start background collector
        self._collector_thread = threading.Thread(
            target=self._collect_system_metrics, daemon=True
        )
        self._collector_thread.start()

        logger.info("[Metrics] Exporter Active.")

    def gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric (current value)."""
        with self._lock:
            self.metrics[name] = MetricValue(
                name=name,
                value=value,
                labels=labels or {},
                timestamp=time.time(),
                metric_type="gauge",
            )

    def counter_inc(
        self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        with self._lock:
            key = f"{name}:{labels}" if labels else name
            self.counters[key] = self.counters.get(key, 0) + value
            self.metrics[name] = MetricValue(
                name=name,
                value=self.counters[key],
                labels=labels or {},
                timestamp=time.time(),
                metric_type="counter",
            )

    def histogram_observe(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a value for histogram metric."""
        with self._lock:
            key = f"{name}:{labels}" if labels else name
            if key not in self.histograms:
                self.histograms[key] = []
            self.histograms[key].append(value)

            # Keep last 1000 observations
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]

    def _collect_system_metrics(self) -> None:
        """Background task to collect system metrics."""
        while True:
            try:
                # CPU
                self.gauge("warmlogic_cpu_percent", psutil.cpu_percent(interval=1))

                # Memory
                mem = psutil.virtual_memory()
                self.gauge("warmlogic_memory_used_bytes", mem.used)
                self.gauge("warmlogic_memory_percent", mem.percent)

                # Disk
                disk = psutil.disk_usage("/")
                self.gauge("warmlogic_disk_used_bytes", disk.used)
                self.gauge("warmlogic_disk_percent", disk.percent)

                # Process
                process = psutil.Process(os.getpid())
                self.gauge("warmlogic_process_memory_bytes", process.memory_info().rss)
                self.gauge("warmlogic_process_threads", process.num_threads())

                # Uptime
                self.gauge("warmlogic_uptime_seconds", time.time() - self._start_time)

            except Exception as e:
                logger.warning(f"Metrics collection error: {e}")

            time.sleep(15)  # Collect every 15 seconds

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        with self._lock:
            for metric in self.metrics.values():
                # Add type and help
                lines.append(f"# TYPE {metric.name} {metric.metric_type}")

                # Format labels
                if metric.labels:
                    labels_str = ",".join(
                        f'{k}="{v}"' for k, v in metric.labels.items()
                    )
                    lines.append(f"{metric.name}{{{labels_str}}} {metric.value}")
                else:
                    lines.append(f"{metric.name} {metric.value}")

            # Export histograms
            for key, values in self.histograms.items():
                name = key.split(":")[0]
                if values:
                    lines.append(f"# TYPE {name} histogram")
                    lines.append(f"{name}_count {len(values)}")
                    lines.append(f"{name}_sum {sum(values)}")

                    # Quantiles
                    sorted_vals = sorted(values)
                    for q in [0.5, 0.9, 0.95, 0.99]:
                        idx = int(len(sorted_vals) * q)
                        lines.append(
                            f'{name}{{quantile="{q}"}} {sorted_vals[min(idx, len(sorted_vals) - 1)]}'
                        )

        return "\n".join(lines) + "\n"

    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get metrics as dictionary."""
        with self._lock:
            return {
                name: {"value": m.value, "type": m.metric_type, "labels": m.labels}
                for name, m in self.metrics.items()
            }

    def get_health(self) -> Dict[str, Any]:
        """Get health check status."""
        metrics = self.get_metrics_dict()

        cpu = metrics.get("warmlogic_cpu_percent", {}).get("value", 0)
        mem = metrics.get("warmlogic_memory_percent", {}).get("value", 0)
        disk = metrics.get("warmlogic_disk_percent", {}).get("value", 0)

        status = "healthy"
        issues = []

        if cpu > 90:
            status = "degraded"
            issues.append("high_cpu")
        if mem > 90:
            status = "degraded"
            issues.append("high_memory")
        if disk > 90:
            status = "degraded"
            issues.append("high_disk")

        return {
            "status": status,
            "uptime": metrics.get("warmlogic_uptime_seconds", {}).get("value", 0),
            "cpu_percent": cpu,
            "memory_percent": mem,
            "disk_percent": disk,
            "issues": issues,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


# Global metrics exporter
_metrics_exporter = None
_metrics_exporter_lock = threading.Lock()


def get_metrics() -> MetricsExporter:
    """Get or create the global metrics exporter (thread-safe)."""
    global _metrics_exporter
    if _metrics_exporter is None:
        with _metrics_exporter_lock:
            if _metrics_exporter is None:  # Double-checked locking
                _metrics_exporter = MetricsExporter()
    return _metrics_exporter
