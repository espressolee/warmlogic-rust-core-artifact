"""Tests for CompletenessChecker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from warm_logic_core.meta_obs.completeness_checker import (
    CompletenessChecker,
    CompletenessResult,
    CompletenessThresholds,
    ComponentScores,
    GapAnalysis,
    MeasurementScope,
    MissingComponent,
    Priority,
    QualityMetrics,
    Recommendation,
    Trend,
    TrendDirection,
)


class TestMeasurementScope:
    """Tests for MeasurementScope."""

    def test_scope_creation(self):
        """Test scope creation."""
        scope = MeasurementScope(
            run_id="RUN-001",
            session_id="SESS-001",
            component_filter=["governance", "kernel"],
        )

        assert scope.run_id == "RUN-001"
        assert scope.session_id == "SESS-001"
        assert len(scope.component_filter) == 2

    def test_scope_to_dict(self):
        """Test scope serialization."""
        scope = MeasurementScope(
            run_id="RUN-002",
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-01T01:00:00Z",
        )

        data = scope.to_dict()

        assert data["run_id"] == "RUN-002"
        assert "time_range" in data
        assert data["time_range"]["start"] == "2024-01-01T00:00:00Z"


class TestComponentScores:
    """Tests for ComponentScores."""

    def test_scores_creation(self):
        """Test scores creation."""
        scores = ComponentScores(
            mcp_trace_coverage=0.95,
            decision_chain_coverage=0.80,
            governance_linkage=0.70,
            ce_correlation=0.60,
            reasoning_preservation=0.90,
            timing_completeness=0.85,
        )

        assert scores.mcp_trace_coverage == 0.95
        assert scores.decision_chain_coverage == 0.80

    def test_overall_score(self):
        """Test overall score calculation."""
        scores = ComponentScores(
            mcp_trace_coverage=1.0,
            decision_chain_coverage=1.0,
            governance_linkage=1.0,
            ce_correlation=1.0,
            reasoning_preservation=1.0,
            timing_completeness=1.0,
        )

        assert scores.overall_score() == 1.0

        scores2 = ComponentScores(
            mcp_trace_coverage=0.5,
            decision_chain_coverage=0.5,
            governance_linkage=0.5,
            ce_correlation=0.5,
            reasoning_preservation=0.5,
            timing_completeness=0.5,
        )

        assert scores2.overall_score() == 0.5

    def test_scores_to_dict(self):
        """Test scores serialization."""
        scores = ComponentScores(
            mcp_trace_coverage=0.95,
            decision_chain_coverage=0.80,
        )

        data = scores.to_dict()

        assert data["mcp_trace_coverage"] == 0.95
        assert data["decision_chain_coverage"] == 0.80


class TestGapAnalysis:
    """Tests for GapAnalysis."""

    def test_gap_analysis_creation(self):
        """Test gap analysis creation."""
        gap = GapAnalysis(
            total_decisions=100,
            complete_traces=85,
            incomplete_traces=15,
            orphaned_artifacts=3,
        )

        assert gap.total_decisions == 100
        assert gap.completeness_ratio == 0.85

    def test_missing_components(self):
        """Test missing components tracking."""
        missing = MissingComponent(
            component="reasoning",
            missing_count=10,
            affected_decisions=["DEC-001", "DEC-002"],
        )

        gap = GapAnalysis(
            total_decisions=100,
            complete_traces=90,
            incomplete_traces=10,
            missing_components=[missing],
        )

        assert len(gap.missing_components) == 1
        assert gap.missing_components[0].component == "reasoning"

    def test_gap_analysis_to_dict(self):
        """Test gap analysis serialization."""
        gap = GapAnalysis(
            total_decisions=50,
            complete_traces=45,
            incomplete_traces=5,
        )

        data = gap.to_dict()

        assert data["total_decisions"] == 50
        assert data["complete_traces"] == 45


class TestCompletenessThresholds:
    """Tests for CompletenessThresholds."""

    def test_thresholds_creation(self):
        """Test thresholds creation."""
        thresholds = CompletenessThresholds(
            target=0.95,
            warning=0.85,
            critical=0.70,
        )

        assert thresholds.target == 0.95
        assert thresholds.warning == 0.85
        assert thresholds.critical == 0.70

    def test_get_status(self):
        """Test status determination."""
        thresholds = CompletenessThresholds(
            target=0.95,
            warning=0.85,
            critical=0.70,
        )

        assert thresholds.get_status(0.98) == "healthy"
        assert thresholds.get_status(0.90) == "warning"
        assert thresholds.get_status(0.75) == "critical"
        assert thresholds.get_status(0.50) == "failing"


class TestCompletenessResult:
    """Tests for CompletenessResult."""

    def test_result_creation(self):
        """Test result creation."""
        result = CompletenessResult(
            measurement_id="DTCOMP-001",
            completeness_score=0.92,
        )

        assert result.measurement_id == "DTCOMP-001"
        assert result.completeness_score == 0.92

    def test_result_to_dict(self):
        """Test result serialization."""
        result = CompletenessResult(
            measurement_id="DTCOMP-002",
            completeness_score=0.88,
            scope=MeasurementScope(run_id="RUN-001"),
            component_scores=ComponentScores(mcp_trace_coverage=0.95),
        )

        data = result.to_dict()

        assert data["schema_version"] == "dt_completeness_v1"
        assert data["measurement_id"] == "DTCOMP-002"
        assert data["completeness_score"] == 0.88


class TestCompletenessChecker:
    """Tests for CompletenessChecker."""

    def test_checker_initialization(self):
        """Test checker initialization."""
        checker = CompletenessChecker()

        assert checker.thresholds.target == 0.95
        assert checker.thresholds.warning == 0.85
        assert checker.thresholds.critical == 0.70

    def test_check_complete_decisions(self):
        """Test checking complete decisions."""
        checker = CompletenessChecker()

        decisions = [
            {
                "decision_id": "DEC-001",
                "timestamp": "2024-01-01T00:00:00Z",
                "decision_type": "approval",
                "reasoning": "Approved based on policy compliance",
                "outcome": "approved",
                "mcp_trace": {"trace_id": "trace-001"},
                "governance_policy": "policy-001",
            },
            {
                "decision_id": "DEC-002",
                "timestamp": "2024-01-01T00:01:00Z",
                "decision_type": "rejection",
                "reasoning": "Rejected due to risk threshold",
                "outcome": "rejected",
                "mcp_trace": {"trace_id": "trace-002"},
                "governance_policy": "policy-002",
            },
        ]

        result = checker.check(decisions)

        assert result.completeness_score >= 0.5
        assert result.gap_analysis.complete_traces == 2

    def test_check_incomplete_decisions(self):
        """Test checking incomplete decisions."""
        checker = CompletenessChecker()

        decisions = [
            {
                "decision_id": "DEC-001",
                "timestamp": "2024-01-01T00:00:00Z",
                # Missing: decision_type, reasoning, outcome
            },
            {
                "decision_id": "DEC-002",
                # Missing: timestamp, decision_type, reasoning, outcome
            },
        ]

        result = checker.check(decisions)

        assert result.gap_analysis.incomplete_traces == 2
        assert len(result.gap_analysis.missing_components) > 0

    def test_check_single_decision(self):
        """Test checking single decision."""
        checker = CompletenessChecker()

        complete_decision = {
            "decision_id": "DEC-001",
            "timestamp": "2024-01-01T00:00:00Z",
            "decision_type": "approval",
            "reasoning": "Valid reasoning",
            "outcome": "approved",
        }

        is_complete, missing = checker.check_decision(complete_decision)

        assert is_complete is True
        assert len(missing) == 0

    def test_check_incomplete_decision(self):
        """Test checking incomplete single decision."""
        checker = CompletenessChecker()

        incomplete_decision = {
            "decision_id": "DEC-001",
            "timestamp": "2024-01-01T00:00:00Z",
            # Missing: decision_type, reasoning, outcome
        }

        is_complete, missing = checker.check_decision(incomplete_decision)

        assert is_complete is False
        assert "decision_type" in missing
        assert "reasoning" in missing
        assert "outcome" in missing

    def test_check_trace(self):
        """Test checking trace completeness."""
        checker = CompletenessChecker()

        trace = {
            "decision_id": "DEC-001",
            "timestamp": "2024-01-01T00:00:00Z",
            "decision_type": "approval",
            "reasoning": "Valid reasoning",
            "outcome": "approved",
            "governance_policy": "policy-001",
            "mcp_trace": {"trace_id": "trace-001"},
        }

        score, missing = checker.check_trace(trace)

        assert score > 0.5
        assert len(missing) == 0  # All required present

    def test_recommendations_generated(self):
        """Test that recommendations are generated."""
        checker = CompletenessChecker()

        decisions = [
            {
                "decision_id": f"DEC-{i:03d}",
                "timestamp": "2024-01-01T00:00:00Z",
                "decision_type": "approval",
                "reasoning": "R" if i % 2 == 0 else None,  # 50% missing reasoning
                "outcome": "approved",
            }
            for i in range(20)
        ]

        result = checker.check(decisions)

        # Should have recommendation for reasoning preservation
        assert len(result.recommendations) > 0

    def test_trend_calculation(self):
        """Test trend calculation."""
        checker = CompletenessChecker()

        decisions1 = [
            {
                "decision_id": "DEC-001",
                "timestamp": "2024-01-01T00:00:00Z",
                "decision_type": "approval",
                "reasoning": "Valid reasoning",
                "outcome": "approved",
            }
        ]

        # First check (no trend)
        result1 = checker.check(decisions1)
        assert result1.trend is None  # No previous data

        # Second check (should have trend)
        result2 = checker.check(decisions1)
        # Trend is calculated after first result is stored

        # Third check (should definitely have trend)
        result3 = checker.check(decisions1)
        assert result3.trend is not None

    def test_schema_compliance_validation(self):
        """Test schema compliance validation."""
        checker = CompletenessChecker()

        records = [
            {"schema_version": "decision_trace_v1", "data": "..."},
            {"schema_version": "decision_trace_v1", "data": "..."},
            {"schema_version": "decision_trace_v2", "data": "..."},  # Wrong version
        ]

        rate = checker.validate_schema_compliance(records, "decision_trace_v1")

        assert rate == pytest.approx(0.666, rel=0.01)

    def test_export_report(self):
        """Test exporting report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checker = CompletenessChecker()

            decisions = [
                {
                    "decision_id": "DEC-001",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "decision_type": "approval",
                    "reasoning": "Valid",
                    "outcome": "approved",
                }
            ]

            result = checker.check(decisions)

            path = Path(tmpdir) / "completeness_report.json"
            checker.export_report(result, path)

            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert data["schema_version"] == "dt_completeness_v1"

    def test_mcp_trace_coverage_score(self):
        """Test MCP trace coverage scoring."""
        checker = CompletenessChecker()

        decisions = [
            {
                "decision_id": f"DEC-{i:03d}",
                "timestamp": "2024-01-01T00:00:00Z",
                "decision_type": "approval",
                "reasoning": "Valid",
                "outcome": "approved",
                "mcp_trace": {"trace_id": f"trace-{i:03d}"} if i < 8 else None,
            }
            for i in range(10)
        ]

        result = checker.check(decisions)

        # 8 out of 10 have MCP traces = 80%
        assert result.component_scores.mcp_trace_coverage == 0.8

    def test_governance_linkage_score(self):
        """Test governance linkage scoring."""
        checker = CompletenessChecker()

        decisions = [
            {
                "decision_id": f"DEC-{i:03d}",
                "timestamp": "2024-01-01T00:00:00Z",
                "decision_type": "approval",
                "reasoning": "Valid",
                "outcome": "approved",
                "governance_policy": f"policy-{i:03d}" if i < 7 else None,
            }
            for i in range(10)
        ]

        result = checker.check(decisions)

        # 7 out of 10 have governance linkage = 70%
        assert result.component_scores.governance_linkage == 0.7

    def test_timing_completeness_score(self):
        """Test timing completeness scoring."""
        checker = CompletenessChecker()

        decisions = [
            {
                "decision_id": f"DEC-{i:03d}",
                "timestamp": "2024-01-01T00:00:00Z",
                "decision_type": "approval",
                "reasoning": "Valid",
                "outcome": "approved",
                "duration_ms": 100 if i < 9 else None,
            }
            for i in range(10)
        ]

        result = checker.check(decisions)

        # 9 out of 10 have timing = 90%
        assert result.component_scores.timing_completeness == 0.9

    def test_quality_metrics(self):
        """Test quality metrics calculation."""
        checker = CompletenessChecker()

        decisions = [
            {
                "decision_id": f"DEC-{i:03d}",
                "timestamp": "2024-01-01T00:00:00Z",
                "decision_type": "approval",
                "reasoning": "Valid",
                "outcome": "approved",
                "trace_depth": i + 1,
                "duration_ms": 50 + i * 10,
            }
            for i in range(10)
        ]

        result = checker.check(decisions)

        assert result.quality_metrics.trace_depth_avg > 0
        assert result.quality_metrics.trace_depth_max == 10
        assert result.quality_metrics.latency_p99_ms > 0

    def test_orphaned_artifacts(self):
        """Test orphaned artifact detection."""
        checker = CompletenessChecker()

        decisions = [
            {
                "decision_id": "DEC-001",
                "timestamp": "2024-01-01T00:00:00Z",
                "decision_type": "approval",
                "reasoning": "Valid",
                "outcome": "approved",
            }
        ]

        traces = [
            {"decision_id": "DEC-001", "trace_data": "..."},
            {"decision_id": "DEC-002", "trace_data": "..."},  # Orphaned
            {"decision_id": "DEC-003", "trace_data": "..."},  # Orphaned
        ]

        result = checker.check(decisions, traces)

        assert result.gap_analysis.orphaned_artifacts == 2

    def test_custom_thresholds(self):
        """Test custom thresholds."""
        thresholds = CompletenessThresholds(
            target=0.99,
            warning=0.95,
            critical=0.90,
        )
        checker = CompletenessChecker(thresholds=thresholds)

        assert checker.thresholds.target == 0.99
        assert checker.thresholds.warning == 0.95

    def test_empty_decisions(self):
        """Test checking empty decisions list."""
        checker = CompletenessChecker()

        result = checker.check([])

        assert result.completeness_score == 0.0
        assert result.gap_analysis.total_decisions == 0

    def test_recommendation_priorities(self):
        """Test recommendation priority sorting."""
        rec_high = Recommendation(
            priority=Priority.HIGH,
            component="test",
            issue="High priority issue",
            recommendation="Fix it",
        )

        rec_low = Recommendation(
            priority=Priority.LOW,
            component="test",
            issue="Low priority issue",
            recommendation="Maybe fix it",
        )

        # HIGH should sort before LOW
        assert rec_high.priority.value < rec_low.priority.value
