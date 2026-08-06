"""Tests for Kernel Stability."""

from __future__ import annotations

import pytest

from warm_logic_core.kernel.stability import (
    StabilityStatus,
    StabilityConfig,
    StabilityMetrics,
    StabilityAnalyzer,
    estimate_lipschitz,
    constrained_gain_function,
    stability_index,
    compute_lyapunov_exponent,
)


class TestStabilityStatus:
    """Tests for StabilityStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert StabilityStatus.STABLE.value == "stable"
        assert StabilityStatus.CAUTION.value == "caution"
        assert StabilityStatus.CRITICAL.value == "critical"
        assert StabilityStatus.UNKNOWN.value == "unknown"


class TestStabilityConfig:
    """Tests for StabilityConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = StabilityConfig()

        assert config.stable_threshold == 0.35
        assert config.caution_threshold == 0.75
        assert config.min_samples == 5
        assert config.lipschitz_warning == 1.5
        assert config.lipschitz_critical == 3.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = StabilityConfig(
            stable_threshold=0.5,
            lipschitz_critical=5.0,
        )

        assert config.stable_threshold == 0.5
        assert config.lipschitz_critical == 5.0


class TestStabilityMetrics:
    """Tests for StabilityMetrics."""

    def test_metrics_creation(self):
        """Test metrics creation."""
        metrics = StabilityMetrics.create()

        assert metrics.metrics_id.startswith("STAB-")
        assert metrics.status == StabilityStatus.UNKNOWN
        assert metrics.lipschitz == 0.0
        assert metrics.cgf == 0.0

    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        metrics = StabilityMetrics.create()
        metrics.lipschitz = 1.5
        metrics.cgf = 0.8

        data = metrics.to_dict()

        assert data["schema_version"] == "stability_metrics_v1"
        assert data["lipschitz"] == 1.5
        assert data["cgf"] == 0.8

    def test_metrics_with_lyapunov(self):
        """Test metrics with Lyapunov exponent."""
        metrics = StabilityMetrics.create()
        metrics.lyapunov = -0.1

        data = metrics.to_dict()

        assert data["lyapunov"] == -0.1


class TestEstimateLipschitz:
    """Tests for estimate_lipschitz function."""

    def test_lipschitz_1d_vector(self):
        """Test Lipschitz with 1D vector."""
        vec = [1.0, 2.0, 2.0]
        result = estimate_lipschitz(vec)

        # L2 norm: sqrt(1 + 4 + 4) = 3
        assert abs(result - 3.0) < 0.01

    def test_lipschitz_2x2_identity(self):
        """Test Lipschitz with 2x2 identity matrix."""
        matrix = [[1.0, 0.0], [0.0, 1.0]]
        result = estimate_lipschitz(matrix)

        # Identity has spectral norm 1
        assert abs(result - 1.0) < 0.01

    def test_lipschitz_2x2_scaling(self):
        """Test Lipschitz with scaling matrix."""
        matrix = [[2.0, 0.0], [0.0, 3.0]]
        result = estimate_lipschitz(matrix)

        # Spectral norm is max singular value = 3
        assert abs(result - 3.0) < 0.01

    def test_lipschitz_larger_matrix(self):
        """Test Lipschitz with larger matrix uses Frobenius."""
        matrix = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        result = estimate_lipschitz(matrix)

        # Frobenius norm: sqrt(3)
        assert abs(result - 1.732) < 0.01

    def test_lipschitz_empty_input(self):
        """Test Lipschitz with empty input."""
        result = estimate_lipschitz([])

        assert result == 0.0

    def test_lipschitz_tuple_input(self):
        """Test Lipschitz with tuple input."""
        vec = (3.0, 4.0)
        result = estimate_lipschitz(vec)

        # L2 norm: sqrt(9 + 16) = 5
        assert abs(result - 5.0) < 0.01


class TestConstrainedGainFunction:
    """Tests for constrained_gain_function."""

    def test_cgf_contractive(self):
        """Test CGF with contractive mapping."""
        delta_in = [1.0, 0.0]
        delta_out = [0.5, 0.0]
        result = constrained_gain_function(delta_out, delta_in)

        # CGF = 0.5 / 1.0 = 0.5 (contractive)
        assert abs(result - 0.5) < 0.01

    def test_cgf_expansive(self):
        """Test CGF with expansive mapping."""
        delta_in = [1.0, 0.0]
        delta_out = [2.0, 0.0]
        result = constrained_gain_function(delta_out, delta_in)

        # CGF = 2.0 / 1.0 = 2.0 (expansive)
        assert abs(result - 2.0) < 0.01

    def test_cgf_isometry(self):
        """Test CGF with isometry."""
        delta_in = [3.0, 4.0]  # norm = 5
        delta_out = [4.0, 3.0]  # norm = 5
        result = constrained_gain_function(delta_out, delta_in)

        # CGF = 5 / 5 = 1.0
        assert abs(result - 1.0) < 0.01

    def test_cgf_zero_input(self):
        """Test CGF with zero input."""
        result = constrained_gain_function([1.0, 0.0], [0.0, 0.0])

        assert result == 0.0

    def test_cgf_near_zero_input(self):
        """Test CGF with near-zero input."""
        result = constrained_gain_function([1.0], [1e-12])

        assert result == 0.0


class TestStabilityIndex:
    """Tests for stability_index function."""

    def test_stability_index_lipschitz_dominant(self):
        """Test stability index with higher Lipschitz."""
        result = stability_index({"lipschitz": 2.0, "cgf": 0.5})

        assert result["stability_index"] == 2.0
        assert result["lipschitz"] == 2.0
        assert result["cgf"] == 0.5

    def test_stability_index_cgf_dominant(self):
        """Test stability index with higher CGF."""
        result = stability_index({"lipschitz": 0.5, "cgf": 1.5})

        assert result["stability_index"] == 1.5

    def test_stability_index_equal(self):
        """Test stability index when equal."""
        result = stability_index({"lipschitz": 1.0, "cgf": 1.0})

        assert result["stability_index"] == 1.0

    def test_stability_index_missing_values(self):
        """Test stability index with missing values."""
        result = stability_index({})

        assert result["lipschitz"] == 0.0
        assert result["cgf"] == 0.0
        assert result["stability_index"] == 0.0

    def test_stability_index_none_values(self):
        """Test stability index with None values."""
        result = stability_index({"lipschitz": None, "cgf": None})

        assert result["stability_index"] == 0.0


class TestComputeLyapunovExponent:
    """Tests for compute_lyapunov_exponent function."""

    def test_lyapunov_stable_trajectory(self):
        """Test Lyapunov with stable (converging) trajectory."""
        # Converging trajectory
        trajectory = [
            [1.0, 1.0],
            [0.5, 0.5],
            [0.25, 0.25],
            [0.125, 0.125],
        ]
        result = compute_lyapunov_exponent(trajectory)

        assert result is not None
        # Negative Lyapunov indicates stable
        assert result < 0

    def test_lyapunov_diverging_trajectory(self):
        """Test Lyapunov with diverging trajectory."""
        # Diverging trajectory
        trajectory = [
            [0.125, 0.125],
            [0.25, 0.25],
            [0.5, 0.5],
            [1.0, 1.0],
        ]
        result = compute_lyapunov_exponent(trajectory)

        assert result is not None
        # Positive Lyapunov indicates unstable
        assert result > 0

    def test_lyapunov_insufficient_data(self):
        """Test Lyapunov with insufficient data."""
        trajectory = [[1.0], [2.0]]
        result = compute_lyapunov_exponent(trajectory)

        assert result is None

    def test_lyapunov_empty_trajectory(self):
        """Test Lyapunov with empty trajectory."""
        result = compute_lyapunov_exponent([])

        assert result is None

    def test_lyapunov_custom_dt(self):
        """Test Lyapunov with custom time step."""
        trajectory = [
            [1.0],
            [0.5],
            [0.25],
            [0.125],
        ]
        result_dt1 = compute_lyapunov_exponent(trajectory, dt=1.0)
        result_dt2 = compute_lyapunov_exponent(trajectory, dt=2.0)

        assert result_dt1 is not None
        assert result_dt2 is not None
        # Different dt should affect result
        assert abs(result_dt1) != abs(result_dt2)


class TestStabilityAnalyzer:
    """Tests for StabilityAnalyzer class."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = StabilityAnalyzer()

        assert analyzer.analyzer_id.startswith("ANALYZER-")
        assert len(analyzer.history) == 0

    def test_analyzer_custom_id(self):
        """Test analyzer with custom ID."""
        analyzer = StabilityAnalyzer(analyzer_id="TEST-ANALYZER")

        assert analyzer.analyzer_id == "TEST-ANALYZER"

    def test_analyzer_custom_config(self):
        """Test analyzer with custom config."""
        config = StabilityConfig(lipschitz_critical=10.0)
        analyzer = StabilityAnalyzer(config=config)

        assert analyzer.config.lipschitz_critical == 10.0

    def test_analyze_with_jacobian(self):
        """Test analyze with Jacobian input."""
        analyzer = StabilityAnalyzer()
        jacobian = [[1.0, 0.0], [0.0, 1.0]]

        metrics = analyzer.analyze(jacobian=jacobian)

        assert metrics.lipschitz > 0
        assert "lipschitz=" in metrics.trace[1]

    def test_analyze_with_cgf(self):
        """Test analyze with CGF inputs."""
        analyzer = StabilityAnalyzer()

        metrics = analyzer.analyze(
            delta_in=[1.0, 0.0],
            delta_out=[0.5, 0.0],
        )

        assert metrics.cgf == 0.5
        assert "cgf=" in metrics.trace[1]

    def test_analyze_with_trajectory(self):
        """Test analyze with trajectory."""
        analyzer = StabilityAnalyzer()
        trajectory = [[1.0], [0.5], [0.25], [0.125]]

        metrics = analyzer.analyze(trajectory=trajectory)

        assert metrics.lyapunov is not None

    def test_analyze_combined(self):
        """Test analyze with all inputs."""
        analyzer = StabilityAnalyzer()

        metrics = analyzer.analyze(
            jacobian=[[2.0, 0.0], [0.0, 2.0]],
            delta_in=[1.0, 0.0],
            delta_out=[1.5, 0.0],
            trajectory=[[1.0], [0.5], [0.25], [0.125]],
        )

        assert metrics.lipschitz > 0
        assert metrics.cgf > 0
        assert metrics.lyapunov is not None
        assert metrics.stability_index > 0

    def test_analyze_updates_history(self):
        """Test analyze updates history."""
        analyzer = StabilityAnalyzer()

        analyzer.analyze(jacobian=[[1.0, 0.0], [0.0, 1.0]])
        analyzer.analyze(jacobian=[[2.0, 0.0], [0.0, 2.0]])

        assert len(analyzer.history) == 2

    def test_status_unknown_insufficient_samples(self):
        """Test status unknown with insufficient samples."""
        analyzer = StabilityAnalyzer()

        metrics = analyzer.analyze(jacobian=[[1.0, 0.0], [0.0, 1.0]])

        # Only 1 sample, min is 5
        assert metrics.status == StabilityStatus.UNKNOWN

    def test_status_critical_high_lipschitz(self):
        """Test status critical with high Lipschitz."""
        config = StabilityConfig(min_samples=1, lipschitz_critical=2.0)
        analyzer = StabilityAnalyzer(config=config)

        metrics = analyzer.analyze(jacobian=[[5.0, 0.0], [0.0, 5.0]])

        assert metrics.status == StabilityStatus.CRITICAL

    def test_status_caution_warning_lipschitz(self):
        """Test status caution at warning threshold."""
        config = StabilityConfig(
            min_samples=1,
            lipschitz_warning=1.0,
            lipschitz_critical=3.0,
        )
        analyzer = StabilityAnalyzer(config=config)

        metrics = analyzer.analyze(jacobian=[[2.0, 0.0], [0.0, 2.0]])

        assert metrics.status == StabilityStatus.CAUTION

    def test_status_stable_low_index(self):
        """Test status stable with low index."""
        config = StabilityConfig(
            min_samples=1,
            stable_threshold=1.0,
        )
        analyzer = StabilityAnalyzer(config=config)

        metrics = analyzer.analyze(jacobian=[[0.1, 0.0], [0.0, 0.1]])

        assert metrics.status == StabilityStatus.STABLE

    def test_analyze_batch(self):
        """Test batch analysis."""
        analyzer = StabilityAnalyzer()
        samples = [
            {"jacobian": [[1.0, 0.0], [0.0, 1.0]]},
            {"jacobian": [[2.0, 0.0], [0.0, 2.0]]},
            {"delta_in": [1.0], "delta_out": [0.5]},
        ]

        results = analyzer.analyze_batch(samples)

        assert len(results) == 3

    def test_get_trend_insufficient_data(self):
        """Test trend with insufficient data."""
        analyzer = StabilityAnalyzer()

        trend = analyzer.get_trend()

        assert trend["direction"] == "unknown"

    def test_get_trend_stable(self):
        """Test stable trend."""
        analyzer = StabilityAnalyzer()

        # Add samples with similar stability index
        for _ in range(5):
            analyzer.analyze(jacobian=[[1.0, 0.0], [0.0, 1.0]])

        trend = analyzer.get_trend()

        assert trend["direction"] == "stable"

    def test_get_trend_improving(self):
        """Test improving trend."""
        analyzer = StabilityAnalyzer()

        # Decreasing stability index (lower is better)
        for i in range(5, 0, -1):
            val = float(i) * 0.1
            analyzer.history.append(
                StabilityMetrics(
                    metrics_id=f"TEST-{i}",
                    stability_index=val,
                )
            )

        trend = analyzer.get_trend()

        assert trend["direction"] == "improving"

    def test_get_trend_degrading(self):
        """Test degrading trend."""
        analyzer = StabilityAnalyzer()

        # Increasing stability index (higher is worse)
        for i in range(1, 6):
            val = float(i) * 0.1
            analyzer.history.append(
                StabilityMetrics(
                    metrics_id=f"TEST-{i}",
                    stability_index=val,
                )
            )

        trend = analyzer.get_trend()

        assert trend["direction"] == "degrading"

    def test_get_summary_empty(self):
        """Test summary with no data."""
        analyzer = StabilityAnalyzer()

        summary = analyzer.get_summary()

        assert summary["count"] == 0
        assert summary["avg_lipschitz"] == 0.0

    def test_get_summary_with_data(self):
        """Test summary with data."""
        analyzer = StabilityAnalyzer()

        analyzer.analyze(jacobian=[[1.0, 0.0], [0.0, 1.0]])
        analyzer.analyze(jacobian=[[2.0, 0.0], [0.0, 2.0]])

        summary = analyzer.get_summary()

        assert summary["count"] == 2
        assert summary["avg_lipschitz"] > 0

    def test_clear(self):
        """Test clearing history."""
        analyzer = StabilityAnalyzer()

        analyzer.analyze(jacobian=[[1.0, 0.0], [0.0, 1.0]])
        analyzer.clear()

        assert len(analyzer.history) == 0


class TestEdgeCases:
    """Edge case tests."""

    def test_lipschitz_malformed_matrix(self):
        """Test Lipschitz with malformed matrix."""
        matrix = [[1.0, 2.0], [3.0]]  # Uneven rows
        result = estimate_lipschitz(matrix)

        # Should handle gracefully
        assert result >= 0.0

    def test_cgf_different_dimensions(self):
        """Test CGF with different input/output dimensions."""
        result = constrained_gain_function([1.0, 2.0, 3.0], [1.0, 2.0])

        assert result >= 0.0

    def test_lyapunov_constant_trajectory(self):
        """Test Lyapunov with constant trajectory."""
        trajectory = [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]
        result = compute_lyapunov_exponent(trajectory)

        # Zero differences, should handle gracefully
        assert result is None or abs(result) < 1e-6 or result < 0
