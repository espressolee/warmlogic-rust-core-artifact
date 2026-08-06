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
Tests for SLA Architecture module.
"""

import time
import unittest

from warm_logic.infrastructure.sla import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    DatabaseHealthCheck,
    DependencyHealthCheck,
    GracefulDegradation,
    HealthCheckRegistry,
    HealthCheckResult,
    HealthStatus,
    SLAConfig,
    SLAMetrics,
    SLAMonitor,
    get_sla_monitor,
    initialize_sla,
    track_sla,
    with_circuit_breaker,
)


class TestHealthStatus(unittest.TestCase):
    """Test HealthStatus enum."""

    def test_status_values(self):
        """Test health status values."""
        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")
        self.assertEqual(HealthStatus.DEGRADED.value, "degraded")
        self.assertEqual(HealthStatus.UNHEALTHY.value, "unhealthy")
        self.assertEqual(HealthStatus.UNKNOWN.value, "unknown")


class TestHealthCheckResult(unittest.TestCase):
    """Test HealthCheckResult dataclass."""

    def test_healthy_result(self):
        """Test healthy check result."""
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=5.0,
        )
        self.assertTrue(result.is_healthy())
        self.assertEqual(result.name, "test")

    def test_unhealthy_result(self):
        """Test unhealthy check result."""
        result = HealthCheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message="Connection failed",
        )
        self.assertFalse(result.is_healthy())


class TestSLAConfig(unittest.TestCase):
    """Test SLAConfig dataclass."""

    def test_default_config(self):
        """Test default SLA configuration."""
        config = SLAConfig()
        self.assertEqual(config.target_uptime, 99.9)
        self.assertEqual(config.target_latency_p99_ms, 200.0)
        self.assertEqual(config.target_error_rate, 0.1)

    def test_custom_config(self):
        """Test custom SLA configuration."""
        config = SLAConfig(
            target_uptime=99.99,
            target_latency_p99_ms=100.0,
            circuit_failure_threshold=3,
        )
        self.assertEqual(config.target_uptime, 99.99)
        self.assertEqual(config.circuit_failure_threshold, 3)


class TestSLAMetrics(unittest.TestCase):
    """Test SLAMetrics dataclass."""

    def test_initial_metrics(self):
        """Test initial metric values."""
        metrics = SLAMetrics()
        self.assertEqual(metrics.total_requests, 0)
        self.assertEqual(metrics.error_rate, 0.0)

    def test_record_success(self):
        """Test recording successful requests."""
        metrics = SLAMetrics()
        metrics.record_request(success=True, latency_ms=50.0)
        metrics.record_request(success=True, latency_ms=100.0)

        self.assertEqual(metrics.total_requests, 2)
        self.assertEqual(metrics.successful_requests, 2)
        self.assertEqual(metrics.failed_requests, 0)
        self.assertEqual(metrics.error_rate, 0.0)
        self.assertEqual(metrics.average_latency_ms, 75.0)

    def test_record_failure(self):
        """Test recording failed requests."""
        metrics = SLAMetrics()
        metrics.record_request(success=True, latency_ms=50.0)
        metrics.record_request(success=False, latency_ms=0.0)

        self.assertEqual(metrics.total_requests, 2)
        self.assertEqual(metrics.failed_requests, 1)
        self.assertEqual(metrics.error_rate, 50.0)

    def test_to_dict(self):
        """Test dictionary conversion."""
        metrics = SLAMetrics()
        metrics.record_request(success=True, latency_ms=100.0)
        result = metrics.to_dict()

        self.assertIn("total_requests", result)
        self.assertIn("error_rate", result)
        self.assertIn("uptime_percentage", result)


class TestCircuitBreaker(unittest.TestCase):
    """Test CircuitBreaker class."""

    def test_initial_state(self):
        """Test circuit starts closed."""
        circuit = CircuitBreaker("test", failure_threshold=3)
        self.assertEqual(circuit.state, CircuitState.CLOSED)
        self.assertTrue(circuit.is_closed)

    def test_success_keeps_closed(self):
        """Test successes keep circuit closed."""
        circuit = CircuitBreaker("test", failure_threshold=3)
        circuit.record_success()
        circuit.record_success()
        self.assertEqual(circuit.state, CircuitState.CLOSED)

    def test_failures_open_circuit(self):
        """Test failures open the circuit."""
        circuit = CircuitBreaker("test", failure_threshold=3)
        circuit.record_failure()
        circuit.record_failure()
        self.assertEqual(circuit.state, CircuitState.CLOSED)

        circuit.record_failure()  # Third failure
        self.assertEqual(circuit.state, CircuitState.OPEN)
        self.assertFalse(circuit.is_closed)

    def test_open_blocks_requests(self):
        """Test open circuit blocks requests."""
        circuit = CircuitBreaker("test", failure_threshold=2)
        circuit.record_failure()
        circuit.record_failure()

        self.assertFalse(circuit.allow_request())

    def test_recovery_timeout(self):
        """Test circuit transitions to half-open after timeout."""
        circuit = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        circuit.record_failure()
        circuit.record_failure()
        self.assertEqual(circuit.state, CircuitState.OPEN)

        # Wait for recovery timeout
        time.sleep(0.15)
        self.assertEqual(circuit.state, CircuitState.HALF_OPEN)

    def test_half_open_success_closes(self):
        """Test successful calls in half-open close circuit."""
        circuit = CircuitBreaker(
            "test", failure_threshold=2, recovery_timeout=0.1, half_open_max_calls=2
        )
        circuit.record_failure()
        circuit.record_failure()
        time.sleep(0.15)

        # Access state to trigger recovery check
        self.assertEqual(circuit.state, CircuitState.HALF_OPEN)

        # Simulate successful requests (need to check state to update)
        circuit.record_success()
        circuit.record_success()
        self.assertEqual(circuit.state, CircuitState.CLOSED)

    def test_execute_with_fallback(self):
        """Test execute with fallback on open circuit."""
        circuit = CircuitBreaker("test", failure_threshold=1)
        circuit.record_failure()

        fallback_value = "fallback"
        result = circuit.execute(
            func=lambda: "primary",
            fallback=lambda: fallback_value,
        )
        self.assertEqual(result, fallback_value)

    def test_execute_raises_without_fallback(self):
        """Test execute raises CircuitOpenError without fallback."""
        circuit = CircuitBreaker("test", failure_threshold=1)
        circuit.record_failure()

        with self.assertRaises(CircuitOpenError):
            circuit.execute(func=lambda: "primary")

    def test_to_dict(self):
        """Test dictionary representation."""
        circuit = CircuitBreaker("test")
        result = circuit.to_dict()

        self.assertEqual(result["name"], "test")
        self.assertIn("state", result)
        self.assertIn("failure_threshold", result)


class TestDatabaseHealthCheck(unittest.TestCase):
    """Test DatabaseHealthCheck class."""

    def test_healthy_check(self):
        """Test healthy database check."""
        check = DatabaseHealthCheck(check_func=lambda: True)
        result = check.check()

        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertGreaterEqual(result.latency_ms, 0)  # May be 0 for fast checks

    def test_unhealthy_check(self):
        """Test unhealthy database check."""
        check = DatabaseHealthCheck(check_func=lambda: False)
        result = check.check()

        self.assertEqual(result.status, HealthStatus.UNHEALTHY)

    def test_exception_handling(self):
        """Test exception handling in check."""

        def failing_check():
            raise ConnectionError("Connection refused")

        check = DatabaseHealthCheck(check_func=failing_check)
        result = check.check()

        self.assertEqual(result.status, HealthStatus.UNHEALTHY)
        self.assertIn("Connection refused", result.message)


class TestDependencyHealthCheck(unittest.TestCase):
    """Test DependencyHealthCheck class."""

    def test_healthy_dependency(self):
        """Test healthy dependency check."""
        check = DependencyHealthCheck(name="redis", check_func=lambda: True)
        result = check.check()

        self.assertEqual(result.status, HealthStatus.HEALTHY)

    def test_degraded_dependency(self):
        """Test degraded dependency check."""
        check = DependencyHealthCheck(name="cache", check_func=lambda: False)
        result = check.check()

        self.assertEqual(result.status, HealthStatus.DEGRADED)


class TestHealthCheckRegistry(unittest.TestCase):
    """Test HealthCheckRegistry class."""

    def test_empty_registry(self):
        """Test empty registry returns healthy."""
        registry = HealthCheckRegistry()
        result = registry.check_liveness()

        self.assertEqual(result.status, HealthStatus.HEALTHY)

    def test_register_and_check_liveness(self):
        """Test registering and running liveness checks."""
        registry = HealthCheckRegistry()
        registry.register_liveness(DatabaseHealthCheck(check_func=lambda: True))

        result = registry.check_liveness()
        self.assertEqual(result.status, HealthStatus.HEALTHY)

    def test_critical_failure(self):
        """Test critical check failure makes system unhealthy."""
        registry = HealthCheckRegistry()
        registry.register_liveness(
            DatabaseHealthCheck(check_func=lambda: False, critical=True)
        )

        result = registry.check_liveness()
        self.assertEqual(result.status, HealthStatus.UNHEALTHY)

    def test_non_critical_failure(self):
        """Test non-critical failure makes system degraded."""
        registry = HealthCheckRegistry()
        registry.register_readiness(
            DependencyHealthCheck(
                name="cache", check_func=lambda: False, critical=False
            )
        )

        result = registry.check_readiness()
        self.assertEqual(result.status, HealthStatus.DEGRADED)


class TestSLAMonitor(unittest.TestCase):
    """Test SLAMonitor class."""

    def test_initialization(self):
        """Test SLA monitor initialization."""
        config = SLAConfig(target_uptime=99.9)
        monitor = SLAMonitor(config)

        self.assertEqual(monitor.config.target_uptime, 99.9)
        self.assertEqual(monitor.metrics.total_requests, 0)

    def test_record_request(self):
        """Test recording requests updates metrics."""
        monitor = SLAMonitor(SLAConfig())
        monitor.record_request(success=True, latency_ms=50.0)

        self.assertEqual(monitor.metrics.total_requests, 1)
        self.assertEqual(monitor.metrics.successful_requests, 1)

    def test_error_budget_tracking(self):
        """Test error budget consumption tracking."""
        monitor = SLAMonitor(SLAConfig(target_uptime=99.0))  # 1% allowed errors

        # 10 requests, 1 failure = 10% error rate
        for _ in range(9):
            monitor.record_request(success=True, latency_ms=10.0)
        monitor.record_request(success=False, latency_ms=0.0)

        # Error rate is 10%, allowed is 1%, so budget consumed = 1000%
        self.assertGreater(monitor.metrics.error_budget_consumed, 100)

    def test_circuit_breaker_management(self):
        """Test circuit breaker registration and retrieval."""
        monitor = SLAMonitor(SLAConfig())
        circuit = monitor.create_circuit_breaker("api")

        self.assertIsNotNone(circuit)
        self.assertEqual(monitor.get_circuit_breaker("api"), circuit)

    def test_get_status(self):
        """Test comprehensive status retrieval."""
        monitor = SLAMonitor(SLAConfig())
        monitor.record_request(success=True, latency_ms=50.0)

        status = monitor.get_status()

        self.assertIn("health", status)
        self.assertIn("metrics", status)
        self.assertIn("sla_targets", status)
        self.assertIn("error_budget", status)

    def test_alert_callback(self):
        """Test alert callback invocation."""
        monitor = SLAMonitor(
            SLAConfig(target_error_rate=0.01, error_budget_alert_threshold=10)
        )

        alerts_received = []

        def alert_handler(alert_type, alert_data):
            alerts_received.append((alert_type, alert_data))

        monitor.register_alert_callback(alert_handler)

        # Trigger high error rate
        for _ in range(10):
            monitor.record_request(success=False, latency_ms=0.0)

        self.assertGreater(len(alerts_received), 0)


class TestGracefulDegradation(unittest.TestCase):
    """Test GracefulDegradation class."""

    def test_initial_level(self):
        """Test initial degradation level is 0."""
        degradation = GracefulDegradation()
        self.assertEqual(degradation.level, 0)

    def test_increase_degradation(self):
        """Test increasing degradation level."""
        degradation = GracefulDegradation()
        level = degradation.increase_degradation()

        self.assertEqual(level, 1)
        self.assertEqual(degradation.level, 1)

    def test_decrease_degradation(self):
        """Test decreasing degradation level."""
        degradation = GracefulDegradation()
        degradation.increase_degradation()
        degradation.increase_degradation()
        level = degradation.decrease_degradation()

        self.assertEqual(level, 1)

    def test_max_level(self):
        """Test degradation doesn't exceed max level."""
        degradation = GracefulDegradation()
        for _ in range(10):
            degradation.increase_degradation()

        self.assertEqual(degradation.level, 5)

    def test_feature_flags_at_level_zero(self):
        """Test all features enabled at level 0."""
        degradation = GracefulDegradation()
        self.assertTrue(degradation.is_feature_enabled("analytics"))
        self.assertTrue(degradation.is_feature_enabled("recommendations"))

    def test_feature_flags_at_high_level(self):
        """Test non-critical features disabled at high levels."""
        degradation = GracefulDegradation()
        for _ in range(3):
            degradation.increase_degradation()

        # Critical features should still be enabled
        self.assertTrue(degradation.is_feature_enabled("auth"))
        self.assertTrue(degradation.is_feature_enabled("core_api"))

        # Non-critical features should be disabled
        self.assertFalse(degradation.is_feature_enabled("analytics"))

    def test_explicit_feature_flag(self):
        """Test explicit feature flag override."""
        degradation = GracefulDegradation()
        degradation.set_feature_flag("custom_feature", False)

        self.assertFalse(degradation.is_feature_enabled("custom_feature"))

    def test_reset(self):
        """Test resetting to normal operation."""
        degradation = GracefulDegradation()
        degradation.increase_degradation()
        degradation.increase_degradation()
        degradation.reset()

        self.assertEqual(degradation.level, 0)


class TestGlobalFunctions(unittest.TestCase):
    """Test global SLA functions."""

    def test_get_sla_monitor(self):
        """Test getting global SLA monitor."""
        monitor = get_sla_monitor()
        self.assertIsNotNone(monitor)
        self.assertIsInstance(monitor, SLAMonitor)

    def test_initialize_sla(self):
        """Test initializing SLA with config."""
        config = SLAConfig(target_uptime=99.99)
        monitor = initialize_sla(config)

        self.assertEqual(monitor.config.target_uptime, 99.99)


class TestDecorators(unittest.TestCase):
    """Test SLA decorators."""

    def test_track_sla_success(self):
        """Test track_sla decorator with success."""

        @track_sla
        def successful_function():
            return "success"

        result = successful_function()
        self.assertEqual(result, "success")

    def test_track_sla_failure(self):
        """Test track_sla decorator with failure."""

        @track_sla
        def failing_function():
            raise ValueError("error")

        with self.assertRaises(ValueError):
            failing_function()

    def test_with_circuit_breaker(self):
        """Test with_circuit_breaker decorator."""
        call_count = 0

        @with_circuit_breaker("test_circuit", fallback=lambda: "fallback")
        def protected_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = protected_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
