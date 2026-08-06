"""Tests for emit_ce_from_experiment module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from scripts.meta_obs.emit_ce_from_experiment import (
    CEEntry,
    CEType,
    ViolationRecord,
    check_threshold_violations,
    compute_sha256,
    create_ce_entry,
    determine_ce_type,
    emit_ce_from_experiment,
    extract_metrics_from_experiment,
    find_experiment_files,
    format_ce_for_ledger,
    generate_ce_id,
    generate_remediation_hint,
    load_existing_ce_ids,
    load_experiment_result,
    load_thresholds,
    process_experiment,
    write_ce_to_ledger,
    DEFAULT_THRESHOLDS,
)


class TestComputeSha256:
    """Tests for compute_sha256."""

    def test_hash_string(self):
        """Test hashing a string."""
        result = compute_sha256("hello world")
        assert len(result) == 64
        assert (
            result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        )

    def test_hash_bytes(self):
        """Test hashing bytes."""
        result = compute_sha256(b"hello world")
        assert len(result) == 64

    def test_different_inputs_different_hashes(self):
        """Test different inputs produce different hashes."""
        hash1 = compute_sha256("input1")
        hash2 = compute_sha256("input2")
        assert hash1 != hash2


class TestGenerateCeId:
    """Tests for generate_ce_id."""

    def test_id_format(self):
        """Test ID format."""
        ce_id = generate_ce_id()
        assert ce_id.startswith("CE-")
        assert len(ce_id) == 19  # CE- + 16 chars

    def test_ids_unique(self):
        """Test IDs are unique."""
        ids = {generate_ce_id() for _ in range(100)}
        assert len(ids) == 100


class TestViolationRecord:
    """Tests for ViolationRecord."""

    def test_violation_creation(self):
        """Test violation creation."""
        violation = ViolationRecord(
            metric="p_value",
            actual_value=0.10,
            threshold_value=0.05,
            violation_type="exceeded",
            severity="warning",
        )

        assert violation.metric == "p_value"
        assert violation.actual_value == 0.10
        assert violation.severity == "warning"

    def test_violation_to_dict(self):
        """Test violation serialization."""
        violation = ViolationRecord(
            metric="error_rate",
            actual_value=0.05,
            threshold_value=0.01,
            violation_type="exceeded",
            severity="critical",
        )

        data = violation.to_dict()

        assert data["metric"] == "error_rate"
        assert data["actual_value"] == 0.05
        assert data["severity"] == "critical"


class TestCEEntry:
    """Tests for CEEntry."""

    def test_entry_creation(self):
        """Test CE entry creation."""
        entry = CEEntry(
            ce_id="CE-TEST001",
            cause="Test cause",
            effect="Test effect",
            ce_type="experiment_unknown",
            severity="warning",
            experiment_id="EXP-001",
        )

        assert entry.ce_id == "CE-TEST001"
        assert entry.cause == "Test cause"
        assert len(entry.content_hash) == 64

    def test_entry_to_dict(self):
        """Test CE entry serialization."""
        entry = CEEntry(
            ce_id="CE-TEST002",
            cause="Cause",
            effect="Effect",
            ce_type="experiment_statistical_failure",
            severity="critical",
            experiment_id="EXP-002",
            violations=[{"metric": "p_value", "actual_value": 0.1}],
        )

        data = entry.to_dict()

        assert data["schema_version"] == "ce_ledger_entry_v1"
        assert data["ce_id"] == "CE-TEST002"
        assert data["source"]["type"] == "experiment"
        assert data["source"]["experiment_id"] == "EXP-002"


class TestLoadThresholds:
    """Tests for load_thresholds."""

    def test_default_thresholds(self):
        """Test loading default thresholds."""
        thresholds = load_thresholds()

        assert thresholds["p_value"] == 0.05
        assert thresholds["effect_size"] == 0.1
        assert thresholds["error_rate"] == 0.01

    def test_custom_thresholds_file(self):
        """Test loading custom thresholds from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "thresholds.json"
            with open(path, "w") as f:
                json.dump({"p_value": 0.01, "custom_metric": 100}, f)

            thresholds = load_thresholds(path)

            assert thresholds["p_value"] == 0.01
            assert thresholds["custom_metric"] == 100
            assert thresholds["effect_size"] == 0.1  # Default preserved

    def test_missing_file_returns_defaults(self):
        """Test missing file returns defaults."""
        thresholds = load_thresholds("/nonexistent/path.json")

        assert thresholds == DEFAULT_THRESHOLDS


class TestLoadExperimentResult:
    """Tests for load_experiment_result."""

    def test_load_valid_experiment(self):
        """Test loading valid experiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "experiment.json"
            experiment = {
                "schema_version": "meta_obs_experiment_v1",
                "experiment_id": "EXP-001",
                "experiment_type": "ab_test",
                "status": "completed",
            }
            with open(path, "w") as f:
                json.dump(experiment, f)

            result = load_experiment_result(path)

            assert result is not None
            assert result["experiment_id"] == "EXP-001"

    def test_load_missing_file(self):
        """Test loading missing file."""
        result = load_experiment_result("/nonexistent/experiment.json")

        assert result is None

    def test_load_invalid_json(self):
        """Test loading invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.json"
            with open(path, "w") as f:
                f.write("not valid json")

            result = load_experiment_result(path)

            assert result is None


class TestFindExperimentFiles:
    """Tests for find_experiment_files."""

    def test_find_experiments(self):
        """Test finding experiment files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid experiment file
            exp1 = Path(tmpdir) / "exp1.json"
            with open(exp1, "w") as f:
                json.dump(
                    {
                        "schema_version": "meta_obs_experiment_v1",
                        "experiment_id": "EXP-001",
                    },
                    f,
                )

            # Create non-experiment file
            other = Path(tmpdir) / "other.json"
            with open(other, "w") as f:
                json.dump({"type": "other"}, f)

            files = find_experiment_files(tmpdir)

            assert len(files) == 1
            assert files[0].name == "exp1.json"


class TestExtractMetrics:
    """Tests for extract_metrics_from_experiment."""

    def test_extract_statistical_metrics(self):
        """Test extracting statistical metrics."""
        experiment = {
            "results": {
                "statistical_significance": {
                    "p_value": 0.03,
                    "effect_size": 0.15,
                    "confidence_level": 0.95,
                }
            }
        }

        metrics = extract_metrics_from_experiment(experiment)

        assert metrics["p_value"] == 0.03
        assert metrics["effect_size"] == 0.15
        assert metrics["confidence_level"] == 0.95

    def test_extract_control_treatment_metrics(self):
        """Test extracting control/treatment metrics."""
        experiment = {
            "results": {
                "control_metrics": {"latency": 100, "error_rate": 0.01},
                "treatment_metrics": {"latency": 90, "error_rate": 0.008},
            }
        }

        metrics = extract_metrics_from_experiment(experiment)

        assert metrics["control_latency"] == 100
        assert metrics["treatment_latency"] == 90
        assert "delta_latency_percent" in metrics

    def test_empty_experiment(self):
        """Test extracting from empty experiment."""
        metrics = extract_metrics_from_experiment({})

        assert metrics == {}


class TestCheckThresholdViolations:
    """Tests for check_threshold_violations."""

    def test_no_violations(self):
        """Test when no violations."""
        metrics = {"p_value": 0.03, "effect_size": 0.2}

        violations = check_threshold_violations(metrics)

        assert len(violations) == 0

    def test_p_value_violation(self):
        """Test p_value violation detection."""
        metrics = {"p_value": 0.10}

        violations = check_threshold_violations(metrics)

        assert len(violations) == 1
        assert violations[0].metric == "p_value"
        assert violations[0].violation_type == "exceeded"

    def test_effect_size_violation(self):
        """Test effect_size violation detection."""
        metrics = {"effect_size": 0.05}  # Below threshold

        violations = check_threshold_violations(metrics)

        assert len(violations) == 1
        assert violations[0].metric == "effect_size"
        assert violations[0].violation_type == "below"

    def test_multiple_violations(self):
        """Test multiple violations."""
        metrics = {"p_value": 0.15, "effect_size": 0.05, "error_rate": 0.05}

        violations = check_threshold_violations(metrics)

        assert len(violations) >= 2


class TestDetermineCEType:
    """Tests for determine_ce_type."""

    def test_statistical_failure(self):
        """Test statistical failure type."""
        violations = [
            ViolationRecord(
                metric="p_value",
                actual_value=0.1,
                threshold_value=0.05,
                violation_type="exceeded",
                severity="warning",
            )
        ]

        ce_type = determine_ce_type(violations)

        assert ce_type == CEType.STATISTICAL_FAILURE

    def test_error_threshold(self):
        """Test error threshold type."""
        violations = [
            ViolationRecord(
                metric="error_rate",
                actual_value=0.05,
                threshold_value=0.01,
                violation_type="exceeded",
                severity="critical",
            )
        ]

        ce_type = determine_ce_type(violations)

        assert ce_type == CEType.ERROR_THRESHOLD

    def test_performance_regression(self):
        """Test performance regression type."""
        violations = [
            ViolationRecord(
                metric="latency_p99_ms",
                actual_value=800,
                threshold_value=500,
                violation_type="exceeded",
                severity="warning",
            )
        ]

        ce_type = determine_ce_type(violations)

        assert ce_type == CEType.PERFORMANCE_REGRESSION

    def test_empty_violations(self):
        """Test empty violations returns unknown."""
        ce_type = determine_ce_type([])

        assert ce_type == CEType.UNKNOWN


class TestGenerateRemediationHint:
    """Tests for generate_remediation_hint."""

    def test_statistical_hint(self):
        """Test statistical failure hint."""
        violations = [
            ViolationRecord(
                metric="p_value",
                actual_value=0.1,
                threshold_value=0.05,
                violation_type="exceeded",
                severity="warning",
            )
        ]
        experiment = {"experiment_type": "ab_test"}

        hint = generate_remediation_hint(
            CEType.STATISTICAL_FAILURE, violations, experiment
        )

        assert "Statistical significance" in hint
        assert "sample size" in hint

    def test_performance_hint(self):
        """Test performance regression hint."""
        violations = []
        experiment = {"experiment_type": "canary"}

        hint = generate_remediation_hint(
            CEType.PERFORMANCE_REGRESSION, violations, experiment
        )

        assert "Performance regression" in hint


class TestWriteCEToLedger:
    """Tests for write_ce_to_ledger."""

    def test_write_jsonl(self):
        """Test writing to JSONL ledger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ce_ledger.jsonl"

            entry = CEEntry(
                ce_id="CE-TEST001",
                cause="Test cause",
                effect="Test effect",
                ce_type="experiment_unknown",
                severity="warning",
                experiment_id="EXP-001",
            )

            result = write_ce_to_ledger(entry, path)

            assert result is True
            assert path.exists()
            with open(path) as f:
                data = json.loads(f.readline())
            assert data["ce_id"] == "CE-TEST001"

    def test_write_dry_run(self):
        """Test dry run doesn't write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ce_ledger.jsonl"

            entry = CEEntry(
                ce_id="CE-TEST002",
                cause="Test",
                effect="Test",
                ce_type="experiment_unknown",
                severity="warning",
                experiment_id="EXP-002",
            )

            result = write_ce_to_ledger(entry, path, dry_run=True)

            assert result is True
            assert not path.exists()


class TestLoadExistingCEIds:
    """Tests for load_existing_ce_ids."""

    def test_load_from_jsonl(self):
        """Test loading from JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.jsonl"
            with open(path, "w") as f:
                f.write(json.dumps({"ce_id": "CE-001"}) + "\n")
                f.write(json.dumps({"ce_id": "CE-002"}) + "\n")

            ids = load_existing_ce_ids(path)

            assert "CE-001" in ids
            assert "CE-002" in ids

    def test_missing_file(self):
        """Test missing file returns empty set."""
        ids = load_existing_ce_ids("/nonexistent/ledger.jsonl")

        assert ids == set()


class TestProcessExperiment:
    """Tests for process_experiment."""

    def test_process_with_violations(self):
        """Test processing experiment with violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create experiment file
            exp_path = Path(tmpdir) / "experiment.json"
            experiment = {
                "schema_version": "meta_obs_experiment_v1",
                "experiment_id": "EXP-001",
                "experiment_type": "ab_test",
                "status": "completed",
                "results": {
                    "statistical_significance": {
                        "p_value": 0.15,  # Violates threshold
                        "effect_size": 0.05,  # Violates threshold
                    }
                },
            }
            with open(exp_path, "w") as f:
                json.dump(experiment, f)

            ledger_path = Path(tmpdir) / "ledger.jsonl"

            ce = process_experiment(exp_path, ledger_path)

            assert ce is not None
            assert ce.experiment_id == "EXP-001"
            assert len(ce.violations) >= 1

    def test_process_no_violations(self):
        """Test processing experiment without violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir) / "experiment.json"
            experiment = {
                "schema_version": "meta_obs_experiment_v1",
                "experiment_id": "EXP-002",
                "experiment_type": "ab_test",
                "status": "completed",
                "results": {
                    "statistical_significance": {
                        "p_value": 0.01,  # Good
                        "effect_size": 0.5,  # Good
                    }
                },
            }
            with open(exp_path, "w") as f:
                json.dump(experiment, f)

            ledger_path = Path(tmpdir) / "ledger.jsonl"

            ce = process_experiment(exp_path, ledger_path)

            assert ce is None  # No violations, no CE

    def test_process_pending_experiment_skipped(self):
        """Test pending experiment is skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir) / "experiment.json"
            experiment = {
                "schema_version": "meta_obs_experiment_v1",
                "experiment_id": "EXP-003",
                "experiment_type": "ab_test",
                "status": "pending",  # Not completed
            }
            with open(exp_path, "w") as f:
                json.dump(experiment, f)

            ledger_path = Path(tmpdir) / "ledger.jsonl"

            ce = process_experiment(exp_path, ledger_path)

            assert ce is None
