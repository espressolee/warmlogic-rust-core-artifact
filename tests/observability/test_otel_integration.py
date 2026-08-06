from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.observability.telemetry import TelemetryProvider


@pytest.fixture
def mock_otel():
    with patch("warm_logic.kernel.observability.telemetry.trace") as mock_trace:
        yield mock_trace


def test_telemetry_provider_singleton():
    """Verify that TelemetryProvider returns the same instance."""
    p1 = TelemetryProvider()
    p2 = TelemetryProvider()
    assert p1 is p2


def test_tracer_factory():
    """Verify that get_tracer returns a tracer (NoOp or Real)."""
    provider = TelemetryProvider()
    tracer = provider.get_tracer("test.tracer")
    assert tracer is not None
    assert hasattr(tracer, "start_as_current_span")


def test_sovereign_loop_instrumentation():
    """Verify that SovereignIntelligence loop uses tracing."""
    from warm_logic.kernel.sys.sovereign_intelligence import SovereignIntelligence

    # Mock deps
    otel_mock = MagicMock()
    # Ensure start_as_current_span returns a context manager
    otel_mock.start_as_current_span.return_value.__enter__.return_value = MagicMock()

    with patch("warm_logic.kernel.sys.sovereign_intelligence.tracer", otel_mock):
        si = SovereignIntelligence(
            "node_test", MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        si.heartbeat.is_alive.return_value = True

        # Run one tick (Synchronous because I removed async in previous edits or it was sync)
        # Based on file content verification: def _tick(self): ...
        si._tick()

        # Verify start_as_current_span was called
        otel_mock.start_as_current_span.assert_called_with("loop_cycle")


def test_policy_instrumentation():
    """Verify that PolicyEngine uses tracing."""
    from warm_logic.kernel.policy import enforce_critical_directive

    # Mock deps
    otel_mock = MagicMock()
    span_mock = MagicMock()
    otel_mock.start_as_current_span.return_value.__enter__.return_value = span_mock

    # This test targets tracing behavior only; bypass hardware guard side effects.
    raw_enforcer = getattr(enforce_critical_directive, "__wrapped__", None)
    assert raw_enforcer is not None

    with patch("warm_logic.kernel.policy.tracer", otel_mock):
        raw_enforcer("DIRECTIVE_001", lambda: None)

        otel_mock.start_as_current_span.assert_called_with("enforce_critical_directive")
        span_mock.set_attribute.assert_called_with("directive_id", "DIRECTIVE_001")
