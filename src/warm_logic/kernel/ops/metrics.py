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
# ==========================================================
# Module: metrics.py
# Project: Warm Logic — Patch Engine
# Description: Helpers to derive patch-efficiency telemetry from history logs.
# Author: Warm Logic Dev Team
# ==========================================================

from __future__ import annotations

import json
import logging
import os
import platform
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
)

logger = logging.getLogger("MetricsLoader")

SUCCESS_STATUSES = {"applied", "manual_applied", "ok", "llm_applied"}
ROLLBACK_STATUSES = {"rollback", "rolled_back"}
FAIL_STATUSES = {
    "llm_eval_error",
    "llm_apply_error",
    "llm_timeout",
    "llm_skipped",
    "llm_deferred",
    "llm_eval",
    "llm_rejected",
}

CI_MARKERS = ("ci", "test", "lint", "build", "flake")
REVIEW_REASON_MARKERS = ("review", "human", "protected")


def _parse_ts(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        candidate = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass
    return None


def _load_lines(path: Path, limit: int) -> List[Dict[str, Any]]:
    if not path.exists():
        logger.warning(f"Metrics file missing: {path}")
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        logger.error(f"Failed to read metrics file {path}: {e}")
        return []
    records: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            obj = json.loads(line)
        except Exception as e:
            logger.debug(f"Skipping malformed metric line: {e}")
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


def _status_bucket(status: str | None) -> str:
    s = (status or "").lower()
    if s in SUCCESS_STATUSES:
        return "success"
    if s in ROLLBACK_STATUSES:
        return "rollback"
    return "failed"


def _origin_from_entry(entry: Mapping[str, Any]) -> str:
    origin = None
    meta = entry.get("meta") if isinstance(entry.get("meta"), Mapping) else None
    if isinstance(meta, Mapping):
        origin = meta.get("origin") or meta.get("source")
    origin = origin or entry.get("origin")
    if isinstance(origin, str) and origin:
        return origin
    return "unknown"


def _is_ci_related(entry: Mapping[str, Any]) -> bool:
    reason = str(entry.get("reason", "")).lower()
    status = str(entry.get("status", "")).lower()
    error_texts: List[str] = [reason, status]
    detail = entry.get("detail") if isinstance(entry.get("detail"), Mapping) else {}
    if isinstance(detail, Mapping):
        for key in ("error", "stderr", "ci_logs", "summary", "message"):
            val = detail.get(key)
            if isinstance(val, str):
                error_texts.append(val.lower())
            elif isinstance(val, Iterable) and not isinstance(val, (str, bytes)):
                for item in val:
                    if isinstance(item, str):
                        error_texts.append(item.lower())
        if detail.get("tests_failing") or detail.get("ci_failure"):
            return True
    if entry.get("tests_failing"):
        return True
    combined = "\n".join(error_texts)
    return any(marker in combined for marker in CI_MARKERS)


def _estimate_human_minutes(entry: Mapping[str, Any]) -> float:
    review_minutes = float(os.environ.get("PATCH_REVIEW_MINUTES", 5))
    manual_minutes = float(os.environ.get("PATCH_MANUAL_MINUTES", 6))
    minutes = 0.0
    origin = _origin_from_entry(entry)
    reason = str(entry.get("reason", "")).lower()
    if origin == "manual":
        minutes += manual_minutes
    if entry.get("human_in_loop") or entry.get("requires_human"):
        minutes += review_minutes
    meta = entry.get("meta") if isinstance(entry.get("meta"), Mapping) else {}
    if isinstance(meta, Mapping) and (
        meta.get("human_in_loop") or meta.get("requires_human")
    ):
        minutes += review_minutes
    if any(token in reason for token in REVIEW_REASON_MARKERS):
        minutes += review_minutes
    detail = entry.get("detail") if isinstance(entry.get("detail"), Mapping) else {}
    if isinstance(detail, Mapping):
        if detail.get("manual_review") or detail.get("human_minutes"):
            minutes += float(detail.get("human_minutes", review_minutes))
        elif any(
            token in str(detail.get("reason", "")).lower()
            for token in REVIEW_REASON_MARKERS
        ):
            minutes += review_minutes
    return minutes


@dataclass
class PatchEfficiencyReport:
    success_rate_by_source: Dict[str, float]
    human_minutes_per_success: float
    rollback_rate: float
    ci_fix_stats: Dict[str, Any]
    sample_size: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success_rate_by_source": self.success_rate_by_source,
            "human_minutes_per_success": round(self.human_minutes_per_success, 3),
            "rollback_rate": round(self.rollback_rate, 3),
            "time_to_fix_ci_error": self.ci_fix_stats,
            "sample_size": self.sample_size,
        }


def _compute_success_rate_by_source(
    records: Sequence[Mapping[str, Any]],
) -> Dict[str, float]:
    buckets: Dict[str, Dict[str, int]] = {}
    for entry in records:
        origin = _origin_from_entry(entry)
        bucket = _status_bucket(entry.get("status"))
        origin_counts = buckets.setdefault(origin, {"success": 0, "total": 0})
        origin_counts["total"] += 1
        if bucket == "success":
            origin_counts["success"] += 1
    rates: Dict[str, float] = {}
    for origin, stats in buckets.items():
        total = stats.get("total", 0)
        success = stats.get("success", 0)
        rates[origin] = round(success / total, 3) if total else 0.0
    return dict(sorted(rates.items()))


def _compute_ci_fix_stats(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    records_sorted = sorted(
        records,
        key=lambda e: (
            _parse_ts(e.get("ts")) or datetime.min.replace(tzinfo=timezone.utc)
        ),
    )
    first_failure: Dict[str, datetime] = {}
    durations: Dict[str, List[float]] = {}
    for entry in records_sorted:
        pattern = entry.get("pattern") or entry.get("id")
        ts = _parse_ts(entry.get("ts"))
        if not pattern or ts is None:
            continue
        bucket = _status_bucket(entry.get("status"))
        if bucket != "success" and not _is_ci_related(entry):
            continue
        if bucket != "success" and pattern not in first_failure:
            first_failure[pattern] = ts
            continue
        if bucket == "success" and pattern in first_failure:
            delta = (ts - first_failure.pop(pattern)).total_seconds() / 60.0
            durations.setdefault(pattern, []).append(max(0.0, delta))
    flat = [value for values in durations.values() for value in values]
    avg = sum(flat) / len(flat) if flat else None
    per_pattern = {k: sum(v) / len(v) for k, v in durations.items() if v}
    return {
        "average_minutes": round(avg, 3) if avg is not None else None,
        "per_pattern_minutes": {k: round(v, 3) for k, v in per_pattern.items()},
        "sample_size": len(flat),
    }


def _compute_rollback_rate(records: Sequence[Mapping[str, Any]]) -> float:
    success = 0
    rollback = 0
    for entry in records:
        bucket = _status_bucket(entry.get("status"))
        if bucket == "success":
            success += 1
        elif bucket == "rollback":
            rollback += 1
    denom = success + rollback
    return round(rollback / denom, 3) if denom else 0.0


def build_patch_efficiency_report(
    records: Sequence[Mapping[str, Any]],
) -> PatchEfficiencyReport:
    records_seq = list(records)
    success_rates = _compute_success_rate_by_source(records_seq)
    human_minutes_total = sum(_estimate_human_minutes(entry) for entry in records_seq)
    success_count = sum(
        1 for entry in records_seq if _status_bucket(entry.get("status")) == "success"
    )
    human_per_success = human_minutes_total / success_count if success_count else 0.0
    rollback_rate = _compute_rollback_rate(records_seq)
    ci_stats = _compute_ci_fix_stats(records_seq)
    return PatchEfficiencyReport(
        success_rate_by_source=success_rates,
        human_minutes_per_success=human_per_success,
        rollback_rate=rollback_rate,
        ci_fix_stats=ci_stats,
        sample_size=len(records_seq),
    )


try:
    from warm_logic_rs import analyze_history

    _HAS_RUST_METRICS = True
except ImportError:
    _HAS_RUST_METRICS = False


def load_patch_efficiency(
    history_path: Path,
    *,
    limit: int = 500,
) -> Dict[str, Any]:
    if _HAS_RUST_METRICS and history_path.exists():
        try:
            # High-speed analysis via Rust Core
            lines = history_path.read_text(encoding="utf-8").splitlines()
            if limit > 0:
                lines = lines[-limit:]
            report = analyze_history(lines)
            return report.to_dict()
        except Exception as e:
            logger.warning(
                f"⏩ [Metrics] Rust analysis failed, falling back to Python: {e}"
            )

    records = _load_lines(history_path, limit)
    report = build_patch_efficiency_report(records)
    return report.to_dict()


class SystemMetrics:
    """
    /701 System Observability.
    Aggregates entropy, metrics, and patch efficiency.
    """

    def __init__(self) -> None:
        self.start_time: float = time.time()
        self.drift_score: float = 1.0  # Critical by default.
        self.governance_health: float = 0.0  # Requires verification.
        self.network_stability: float = 0.0  # Requires verification.

        self.local_root: str = "0" * 64
        self.absolute_root: str = "0" * 64

        # Trend Prediction
        self._trend_buffer: List[Dict[str, float]] = []
        self._max_buffer_size = 10

    def record_snapshot(self):
        """Records current state to trend buffer."""
        snapshot = {
            "drift_score": self.drift_score,
            "governance_health": self.governance_health,
            "network_stability": self.network_stability,
            "timestamp": time.time(),
        }
        self._trend_buffer.append(snapshot)
        if len(self._trend_buffer) > self._max_buffer_size:
            self._trend_buffer.pop(0)

    def get_derivative(self, metric: str) -> float:
        """
        Calculates the rate of change (slope) of a metric over the buffered duration.
        Returns units per second. Positive = increasing, Negative = decreasing.
        """
        if len(self._trend_buffer) < 2:
            return 0.0

        start_point = self._trend_buffer[0]
        end_point = self._trend_buffer[-1]

        delta_val = end_point.get(metric, 0.0) - start_point.get(metric, 0.0)
        delta_time = end_point.get("timestamp", 0.0) - start_point.get("timestamp", 0.0)

        if delta_time <= 0:
            return 0.0

        return delta_val / delta_time

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time

    @property
    def hardware_id(self) -> str:
        """
        Identity Enforcement.
        Injects a safe fallback for platform-specific hardware lookups.
        """
        try:
            # Try to use Kinetic Identity if available
            # Note: Circular import avoided by local import
            from warm_logic.kernel.identity.kinetic_id import KineticIdentity

            return str(KineticIdentity.get_node_id() or uuid.getnode())
        except Exception:
            # Fallback to platform-specific derived ID
            node = uuid.getnode()
            return f"{platform.system().upper()}-{node}"

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "uptime": self.uptime,
            "drift_score": self.drift_score,
            "governance_health": self.governance_health,
            "network_stability": self.network_stability,
            "hardware_id": self.hardware_id,
        }

    def is_critical(self) -> bool:
        return (
            self.drift_score > 0.8
            or self.governance_health < 0.5
            or self.network_stability < 0.5
        )

    def ingest_batch(
        self, records: Sequence[Mapping[str, Any]]
    ) -> PatchEfficiencyReport:
        """Processes a batch of patch records and updates internal metrics."""
        report = build_patch_efficiency_report(records)
        # Update internal score based on report
        if report.success_rate_by_source:
            total_rate = sum(report.success_rate_by_source.values())
            self.governance_health = total_rate / len(report.success_rate_by_source)
        return report


__all__ = [
    "SystemMetrics",
    "PatchEfficiencyReport",
    "load_patch_efficiency",
    "build_patch_efficiency_report",
]
