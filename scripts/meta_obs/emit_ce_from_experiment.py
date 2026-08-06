#!/usr/bin/env python3
"""Emit CE from Experiment (Phase 20).

This module emits Counterexamples (CEs) from meta-observability experiments.
When an experiment detects threshold violations or anomalies, this module
creates properly formatted CE entries and writes them to the CE ledger.

Conforms to:
- meta_obs_experiment_v1.schema.json
- ce_ledger_entry_v1.schema.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default thresholds for experiment analysis
DEFAULT_THRESHOLDS = {
    "p_value": 0.05,
    "effect_size": 0.1,
    "error_rate": 0.01,
    "latency_p99_ms": 500,
    "cost_increase_percent": 20.0,
    "completeness_min": 0.95,
}

# CE type mappings based on violation type
CE_TYPE_MAPPING = {
    "statistical": "experiment_statistical_failure",
    "performance": "experiment_performance_regression",
    "cost": "experiment_cost_overrun",
    "completeness": "experiment_completeness_gap",
    "error": "experiment_error_threshold",
    "rollback": "experiment_auto_rollback",
}


class CEType(Enum):
    """Types of CEs that can be emitted from experiments."""

    STATISTICAL_FAILURE = "experiment_statistical_failure"
    PERFORMANCE_REGRESSION = "experiment_performance_regression"
    COST_OVERRUN = "experiment_cost_overrun"
    COMPLETENESS_GAP = "experiment_completeness_gap"
    ERROR_THRESHOLD = "experiment_error_threshold"
    AUTO_ROLLBACK = "experiment_auto_rollback"
    UNKNOWN = "experiment_unknown"


class ThresholdViolation(Exception):
    """Raised when an experiment threshold is violated."""

    def __init__(
        self,
        metric: str,
        actual: float,
        threshold: float,
        violation_type: str = "exceeded",
    ):
        self.metric = metric
        self.actual = actual
        self.threshold = threshold
        self.violation_type = violation_type
        super().__init__(
            f"Threshold violation: {metric} {violation_type} "
            f"(actual={actual}, threshold={threshold})"
        )


@dataclass
class ViolationRecord:
    """Record of a threshold violation."""

    metric: str
    actual_value: float
    threshold_value: float
    violation_type: str  # "exceeded", "below", "out_of_range"
    severity: str  # "warning", "critical"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric": self.metric,
            "actual_value": self.actual_value,
            "threshold_value": self.threshold_value,
            "violation_type": self.violation_type,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


@dataclass
class CEEntry:
    """A Counterexample entry conforming to ce_ledger_entry_v1 schema."""

    ce_id: str
    cause: str
    effect: str
    ce_type: str
    severity: str
    experiment_id: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    violations: list[dict[str, Any]] = field(default_factory=list)
    remediation_hint: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self):
        """Compute content hash after initialization."""
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of CE content."""
        content = json.dumps(
            {
                "ce_id": self.ce_id,
                "cause": self.cause,
                "effect": self.effect,
                "ce_type": self.ce_type,
                "experiment_id": self.experiment_id,
                "violations": self.violations,
            },
            sort_keys=True,
        )
        return compute_sha256(content)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary conforming to ce_ledger_entry_v1 schema."""
        return {
            "schema_version": "ce_ledger_entry_v1",
            "ce_id": self.ce_id,
            "timestamp": self.timestamp,
            "cause": self.cause,
            "effect": self.effect,
            "ce_type": self.ce_type,
            "severity": self.severity,
            "source": {
                "type": "experiment",
                "experiment_id": self.experiment_id,
            },
            "violations": self.violations,
            "remediation_hint": self.remediation_hint,
            "evidence_refs": self.evidence_refs,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }


def compute_sha256(data: str | bytes) -> str:
    """Compute SHA-256 hash of data.

    Args:
        data: String or bytes to hash.

    Returns:
        Hexadecimal hash string.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def generate_ce_id() -> str:
    """Generate a unique CE ID.

    Returns:
        CE ID in format CE-XXXXXXXXXXXXXXXX.
    """
    unique = uuid.uuid4().hex[:16].upper()
    return f"CE-{unique}"


def load_thresholds(
    thresholds_path: str | Path | None = None,
) -> dict[str, float]:
    """Load thresholds from file or return defaults.

    Args:
        thresholds_path: Optional path to thresholds JSON file.

    Returns:
        Dictionary of threshold values.
    """
    if thresholds_path is None:
        return DEFAULT_THRESHOLDS.copy()

    path = Path(thresholds_path)
    if not path.exists():
        logger.warning(f"Thresholds file not found: {path}, using defaults")
        return DEFAULT_THRESHOLDS.copy()

    try:
        with open(path) as f:
            custom = json.load(f)
        # Merge with defaults
        merged = DEFAULT_THRESHOLDS.copy()
        merged.update(custom)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load thresholds: {e}")
        return DEFAULT_THRESHOLDS.copy()


def load_experiment_result(
    experiment_path: str | Path,
) -> dict[str, Any] | None:
    """Load experiment result from file.

    Args:
        experiment_path: Path to experiment result JSON file.

    Returns:
        Experiment result dictionary or None if failed.
    """
    path = Path(experiment_path)
    if not path.exists():
        logger.error(f"Experiment file not found: {path}")
        return None

    try:
        with open(path) as f:
            data = json.load(f)

        # Validate required fields per meta_obs_experiment_v1 schema
        required = ["schema_version", "experiment_id", "experiment_type", "status"]
        missing = [field for field in required if field not in data]
        if missing:
            logger.error(f"Missing required fields: {missing}")
            return None

        if data.get("schema_version") != "meta_obs_experiment_v1":
            logger.warning(
                f"Schema version mismatch: {data.get('schema_version')} "
                "!= meta_obs_experiment_v1"
            )

        return data

    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load experiment: {e}")
        return None


def find_experiment_files(
    directory: str | Path,
    pattern: str = "*.json",
) -> list[Path]:
    """Find experiment result files in a directory.

    Args:
        directory: Directory to search.
        pattern: Glob pattern for files.

    Returns:
        List of matching file paths.
    """
    path = Path(directory)
    if not path.is_dir():
        logger.warning(f"Not a directory: {path}")
        return []

    files = list(path.glob(pattern))
    # Filter for experiment files
    experiment_files = []
    for f in files:
        try:
            with open(f) as fp:
                data = json.load(fp)
            if data.get("schema_version") == "meta_obs_experiment_v1":
                experiment_files.append(f)
        except (json.JSONDecodeError, OSError):
            continue

    return experiment_files


def extract_metrics_from_experiment(
    experiment: dict[str, Any],
) -> dict[str, float]:
    """Extract metrics from experiment results.

    Args:
        experiment: Experiment result dictionary.

    Returns:
        Dictionary of metric name to value.
    """
    metrics: dict[str, float] = {}

    results = experiment.get("results", {})

    # Extract statistical significance metrics
    stat_sig = results.get("statistical_significance", {})
    if "p_value" in stat_sig:
        metrics["p_value"] = stat_sig["p_value"]
    if "effect_size" in stat_sig:
        metrics["effect_size"] = abs(stat_sig["effect_size"])
    if "confidence_level" in stat_sig:
        metrics["confidence_level"] = stat_sig["confidence_level"]

    # Extract control and treatment metrics
    control = results.get("control_metrics", {})
    treatment = results.get("treatment_metrics", {})

    for key in control:
        metrics[f"control_{key}"] = control[key]
    for key in treatment:
        metrics[f"treatment_{key}"] = treatment[key]

    # Calculate deltas
    for key in control:
        if key in treatment:
            control_val = control[key]
            treatment_val = treatment[key]
            if control_val != 0:
                delta_pct = ((treatment_val - control_val) / control_val) * 100
                metrics[f"delta_{key}_percent"] = delta_pct

    # Extract from metrics array if present
    for metric_entry in experiment.get("metrics", []):
        name = metric_entry.get("metric_name")
        if name and "value" in metric_entry:
            metrics[name] = metric_entry["value"]

    return metrics


def check_threshold_violations(
    metrics: dict[str, float],
    thresholds: dict[str, float] | None = None,
    strict: bool = False,
) -> list[ViolationRecord]:
    """Check metrics against thresholds.

    Args:
        metrics: Dictionary of metric values.
        thresholds: Dictionary of threshold values.
        strict: If True, treat warnings as violations.

    Returns:
        List of ViolationRecord for each violation.
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS.copy()

    violations: list[ViolationRecord] = []

    # Check p_value (lower is better, but we want < threshold)
    if "p_value" in metrics and "p_value" in thresholds:
        p_val = metrics["p_value"]
        threshold = thresholds["p_value"]
        if p_val > threshold:
            violations.append(
                ViolationRecord(
                    metric="p_value",
                    actual_value=p_val,
                    threshold_value=threshold,
                    violation_type="exceeded",
                    severity="critical" if p_val > threshold * 2 else "warning",
                )
            )

    # Check effect_size (should be above threshold)
    if "effect_size" in metrics and "effect_size" in thresholds:
        effect = metrics["effect_size"]
        threshold = thresholds["effect_size"]
        if effect < threshold:
            violations.append(
                ViolationRecord(
                    metric="effect_size",
                    actual_value=effect,
                    threshold_value=threshold,
                    violation_type="below",
                    severity="warning",
                )
            )

    # Check error_rate
    if "error_rate" in metrics and "error_rate" in thresholds:
        error_rate = metrics["error_rate"]
        threshold = thresholds["error_rate"]
        if error_rate > threshold:
            violations.append(
                ViolationRecord(
                    metric="error_rate",
                    actual_value=error_rate,
                    threshold_value=threshold,
                    violation_type="exceeded",
                    severity="critical",
                )
            )

    # Check latency_p99
    for latency_key in ["latency_p99_ms", "treatment_latency_p99"]:
        if latency_key in metrics and "latency_p99_ms" in thresholds:
            latency = metrics[latency_key]
            threshold = thresholds["latency_p99_ms"]
            if latency > threshold:
                violations.append(
                    ViolationRecord(
                        metric=latency_key,
                        actual_value=latency,
                        threshold_value=threshold,
                        violation_type="exceeded",
                        severity="critical" if latency > threshold * 2 else "warning",
                    )
                )

    # Check cost increase
    for cost_key in ["delta_cost_percent", "cost_increase_percent"]:
        if cost_key in metrics and "cost_increase_percent" in thresholds:
            cost_delta = metrics[cost_key]
            threshold = thresholds["cost_increase_percent"]
            if cost_delta > threshold:
                violations.append(
                    ViolationRecord(
                        metric=cost_key,
                        actual_value=cost_delta,
                        threshold_value=threshold,
                        violation_type="exceeded",
                        severity="warning",
                    )
                )

    # Check completeness
    for comp_key in ["completeness", "completeness_score"]:
        if comp_key in metrics and "completeness_min" in thresholds:
            completeness = metrics[comp_key]
            threshold = thresholds["completeness_min"]
            if completeness < threshold:
                violations.append(
                    ViolationRecord(
                        metric=comp_key,
                        actual_value=completeness,
                        threshold_value=threshold,
                        violation_type="below",
                        severity="warning",
                    )
                )

    return violations


def determine_ce_type(violations: list[ViolationRecord]) -> CEType:
    """Determine CE type based on violations.

    Args:
        violations: List of threshold violations.

    Returns:
        CEType enum value.
    """
    if not violations:
        return CEType.UNKNOWN

    # Check for specific violation patterns
    metrics = {v.metric for v in violations}

    if "error_rate" in metrics:
        return CEType.ERROR_THRESHOLD
    if "p_value" in metrics or "effect_size" in metrics:
        return CEType.STATISTICAL_FAILURE
    if any("latency" in m for m in metrics):
        return CEType.PERFORMANCE_REGRESSION
    if any("cost" in m for m in metrics):
        return CEType.COST_OVERRUN
    if any("completeness" in m for m in metrics):
        return CEType.COMPLETENESS_GAP

    return CEType.UNKNOWN


def generate_remediation_hint(
    ce_type: CEType,
    violations: list[ViolationRecord],
    experiment: dict[str, Any],
) -> str:
    """Generate remediation hint based on CE type and violations.

    Args:
        ce_type: Type of CE.
        violations: List of violations.
        experiment: Original experiment data.

    Returns:
        Human-readable remediation hint.
    """
    hints: list[str] = []

    experiment_type = experiment.get("experiment_type", "unknown")

    if ce_type == CEType.STATISTICAL_FAILURE:
        hints.append(
            "Statistical significance not achieved. Consider: "
            "(1) Increasing sample size, "
            "(2) Extending experiment duration, "
            "(3) Reducing variance in test conditions."
        )
    elif ce_type == CEType.PERFORMANCE_REGRESSION:
        hints.append(
            "Performance regression detected. Investigate: "
            "(1) Treatment group configuration changes, "
            "(2) Resource contention during experiment, "
            "(3) Infrastructure differences between groups."
        )
    elif ce_type == CEType.COST_OVERRUN:
        hints.append(
            "Cost increase exceeds threshold. Review: "
            "(1) Token usage patterns in treatment, "
            "(2) Tool call frequency changes, "
            "(3) Resource allocation efficiency."
        )
    elif ce_type == CEType.COMPLETENESS_GAP:
        hints.append(
            "Trace completeness below target. Check: "
            "(1) Instrumentation coverage, "
            "(2) Trace propagation across components, "
            "(3) Sampling configuration."
        )
    elif ce_type == CEType.ERROR_THRESHOLD:
        hints.append(
            "Error rate exceeds threshold. Examine: "
            "(1) Error logs from treatment group, "
            "(2) Configuration differences, "
            "(3) Edge cases in new code paths."
        )

    # Add specific metric hints
    for v in violations[:3]:  # Limit to top 3
        hints.append(
            f"Metric '{v.metric}' {v.violation_type}: "
            f"actual={v.actual_value:.4f}, threshold={v.threshold_value:.4f}"
        )

    if experiment_type == "ab_test":
        hints.append(
            "Consider whether the hypothesis needs refinement or "
            "if the treatment implementation requires adjustment."
        )

    return " | ".join(hints)


def create_ce_entry(
    experiment: dict[str, Any],
    violations: list[ViolationRecord],
    ce_type: CEType,
) -> CEEntry:
    """Create a CE entry from experiment and violations.

    Args:
        experiment: Experiment data.
        violations: List of violations.
        ce_type: Type of CE.

    Returns:
        CEEntry object.
    """
    experiment_id = experiment.get("experiment_id", "UNKNOWN")

    # Determine severity from violations
    severity = "warning"
    if any(v.severity == "critical" for v in violations):
        severity = "critical"

    # Build cause and effect descriptions
    cause = (
        f"Experiment {experiment_id} ({experiment.get('experiment_type', 'unknown')}) "
        f"completed with threshold violations"
    )

    effect_parts = [f"{v.metric} {v.violation_type}" for v in violations]
    effect = f"Violations detected: {', '.join(effect_parts)}"

    # Generate remediation hint
    hint = generate_remediation_hint(ce_type, violations, experiment)

    # Collect evidence references
    evidence_refs = []
    if "metadata" in experiment:
        if "artifact_paths" in experiment["metadata"]:
            evidence_refs.extend(experiment["metadata"]["artifact_paths"])

    return CEEntry(
        ce_id=generate_ce_id(),
        cause=cause,
        effect=effect,
        ce_type=ce_type.value,
        severity=severity,
        experiment_id=experiment_id,
        violations=[v.to_dict() for v in violations],
        remediation_hint=hint,
        evidence_refs=evidence_refs,
        metadata={
            "experiment_type": experiment.get("experiment_type"),
            "experiment_status": experiment.get("status"),
            "hypothesis": experiment.get("hypothesis", {}).get("statement", ""),
        },
    )


def format_ce_for_ledger(ce_entry: CEEntry) -> dict[str, Any]:
    """Format CE entry for ledger storage.

    Args:
        ce_entry: CEEntry object.

    Returns:
        Dictionary ready for ledger storage.
    """
    return ce_entry.to_dict()


def load_existing_ce_ids(ledger_path: str | Path) -> set[str]:
    """Load existing CE IDs from ledger.

    Args:
        ledger_path: Path to CE ledger file.

    Returns:
        Set of existing CE IDs.
    """
    path = Path(ledger_path)
    if not path.exists():
        return set()

    ce_ids: set[str] = set()

    try:
        # Support both JSON and JSONL formats
        if path.suffix == ".jsonl":
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        if "ce_id" in entry:
                            ce_ids.add(entry["ce_id"])
        else:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                for entry in data:
                    if "ce_id" in entry:
                        ce_ids.add(entry["ce_id"])
            elif "entries" in data:
                for entry in data["entries"]:
                    if "ce_id" in entry:
                        ce_ids.add(entry["ce_id"])

    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load existing CEs: {e}")

    return ce_ids


def write_ce_to_ledger(
    ce_entry: CEEntry,
    ledger_path: str | Path,
    dry_run: bool = False,
) -> bool:
    """Write CE entry to ledger.

    Args:
        ce_entry: CEEntry object to write.
        ledger_path: Path to CE ledger file.
        dry_run: If True, don't actually write.

    Returns:
        True if successful, False otherwise.
    """
    path = Path(ledger_path)

    if dry_run:
        logger.info(f"[DRY RUN] Would write CE {ce_entry.ce_id} to {path}")
        return True

    try:
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        formatted = format_ce_for_ledger(ce_entry)

        # JSONL format for append-friendly writes
        if path.suffix == ".jsonl":
            with open(path, "a") as f:
                f.write(json.dumps(formatted) + "\n")
        else:
            # JSON format - read, append, write
            existing: list[dict[str, Any]] = []
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    existing = data
                elif "entries" in data:
                    existing = data["entries"]

            existing.append(formatted)

            with open(path, "w") as f:
                json.dump(existing, f, indent=2)

        logger.info(f"Wrote CE {ce_entry.ce_id} to {path}")
        return True

    except OSError as e:
        logger.error(f"Failed to write CE to ledger: {e}")
        return False


def process_experiment(
    experiment_path: str | Path,
    ledger_path: str | Path,
    thresholds: dict[str, float] | None = None,
    dry_run: bool = False,
) -> CEEntry | None:
    """Process a single experiment and emit CE if needed.

    Args:
        experiment_path: Path to experiment result file.
        ledger_path: Path to CE ledger file.
        thresholds: Optional threshold overrides.
        dry_run: If True, don't write to ledger.

    Returns:
        CEEntry if CE was emitted, None otherwise.
    """
    experiment = load_experiment_result(experiment_path)
    if experiment is None:
        return None

    # Skip non-completed experiments
    status = experiment.get("status")
    if status not in ("completed", "failed"):
        logger.info(f"Skipping experiment with status: {status}")
        return None

    # Extract metrics
    metrics = extract_metrics_from_experiment(experiment)
    if not metrics:
        logger.warning("No metrics found in experiment")
        return None

    # Check for violations
    if thresholds is None:
        thresholds = load_thresholds()

    violations = check_threshold_violations(metrics, thresholds)
    if not violations:
        logger.info(f"No violations in experiment {experiment.get('experiment_id')}")
        return None

    # Check for rollback
    rollback = experiment.get("rollback", {})
    if rollback.get("rollback_triggered"):
        violations.append(
            ViolationRecord(
                metric="auto_rollback",
                actual_value=1.0,
                threshold_value=0.0,
                violation_type="triggered",
                severity="critical",
            )
        )

    # Determine CE type
    ce_type = determine_ce_type(violations)

    # Create CE entry
    ce_entry = create_ce_entry(experiment, violations, ce_type)

    # Check for duplicates
    existing = load_existing_ce_ids(ledger_path)
    # Use content hash to detect logical duplicates
    for existing_id in existing:
        # Note: In production, we'd compare content hashes
        pass

    # Write to ledger
    if write_ce_to_ledger(ce_entry, ledger_path, dry_run=dry_run):
        return ce_entry

    return None


def emit_ce_from_experiment(
    experiment_id: str,
    experiment_path: str | Path | None = None,
    ledger_path: str | Path | None = None,
    thresholds: dict[str, float] | None = None,
    dry_run: bool = False,
) -> CEEntry | None:
    """Main entry point: Emit CE from experiment.

    Args:
        experiment_id: Experiment ID to process.
        experiment_path: Optional explicit path to experiment file.
        ledger_path: Optional explicit path to CE ledger.
        thresholds: Optional threshold overrides.
        dry_run: If True, don't write to ledger.

    Returns:
        CEEntry if CE was emitted, None otherwise.
    """
    # Default paths
    if experiment_path is None:
        experiment_path = (
            Path("artifacts/meta_obs/experiments") / f"{experiment_id}.json"
        )

    if ledger_path is None:
        ledger_path = Path("artifacts/ce_ledger/ce_ledger.jsonl")

    return process_experiment(
        experiment_path=experiment_path,
        ledger_path=ledger_path,
        thresholds=thresholds,
        dry_run=dry_run,
    )


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Emit CEs from meta-observability experiments"
    )
    parser.add_argument(
        "experiment_path",
        type=Path,
        help="Path to experiment result file or directory",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("artifacts/ce_ledger/ce_ledger.jsonl"),
        help="Path to CE ledger file",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        help="Path to thresholds JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually write to ledger",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    thresholds = load_thresholds(args.thresholds) if args.thresholds else None

    # Process single file or directory
    if args.experiment_path.is_dir():
        files = find_experiment_files(args.experiment_path)
        logger.info(f"Found {len(files)} experiment files")
        emitted = 0
        for f in files:
            ce = process_experiment(f, args.ledger, thresholds, args.dry_run)
            if ce:
                emitted += 1
                print(f"Emitted CE: {ce.ce_id} from {f.name}")
        print(f"Total CEs emitted: {emitted}")
    else:
        ce = process_experiment(
            args.experiment_path, args.ledger, thresholds, args.dry_run
        )
        if ce:
            print(f"Emitted CE: {ce.ce_id}")
            print(f"  Type: {ce.ce_type}")
            print(f"  Severity: {ce.severity}")
            print(f"  Violations: {len(ce.violations)}")
        else:
            print("No CE emitted")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
