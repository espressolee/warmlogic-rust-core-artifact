"""Tests for Circuit Breaker."""

from __future__ import annotations

import time

import pytest

from warm_logic_core.os.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitConfig,
    CircuitOpenError,
    CircuitBreakerRegistry,
    circuit_breaker,
    get_circuit_registry,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_breaker_initialization(self):
        """Test breaker initialization."""
        breaker = CircuitBreaker()

        assert breaker.circuit_id.startswith("CB-")
        assert breaker.state == CircuitState.CLOSED

    def test_breaker_custom_id(self):
        """Test breaker with custom ID."""
        breaker = CircuitBreaker(circuit_id="TEST-CB")

        assert breaker.circuit_id == "TEST-CB"

    def test_initial_state_closed(self):
        """Test initial state is closed."""
        breaker = CircuitBreaker()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.allow_request() is True

    def test_record_success(self):
        """Test recording success."""
        breaker = CircuitBreaker()

        breaker.record_success()

        stats = breaker.get_stats()
        assert stats["success_count"] == 1
        assert stats["consecutive_failures"] == 0

    def test_record_failure(self):
        """Test recording failure."""
        breaker = CircuitBreaker()

        breaker.record_failure()

        stats = breaker.get_stats()
        assert stats["failure_count"] == 1
        assert stats["consecutive_failures"] == 1

    def test_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        config = CircuitConfig(failure_threshold=3)
        breaker = CircuitBreaker(config=config)

        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.allow_request() is False

    def test_blocks_requests_when_open(self):
        """Test requests blocked when open."""
        config = CircuitConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config)

        breaker.record_failure()

        assert breaker.allow_request() is False

    def test_transitions_to_half_open(self):
        """Test transition to half-open after timeout."""
        config = CircuitConfig(failure_threshold=1, timeout_seconds=0.1)
        breaker = CircuitBreaker(config=config)

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        time.sleep(0.15)

        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.allow_request() is True

    def test_half_open_limited_requests(self):
        """Test half-open allows limited requests."""
        config = CircuitConfig(
            failure_threshold=1,
            timeout_seconds=0.1,
            half_open_max_calls=2,
        )
        breaker = CircuitBreaker(config=config)

        breaker.record_failure()
        time.sleep(0.15)

        assert breaker.allow_request() is True
        assert breaker.allow_request() is True
        assert breaker.allow_request() is False

    def test_closes_after_success_in_half_open(self):
        """Test circuit closes after success in half-open."""
        config = CircuitConfig(
            failure_threshold=1,
            timeout_seconds=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker(config=config)

        breaker.record_failure()
        time.sleep(0.15)

        breaker.allow_request()
        breaker.record_success()
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        """Test circuit reopens on failure in half-open."""
        config = CircuitConfig(failure_threshold=1, timeout_seconds=0.1)
        breaker = CircuitBreaker(config=config)

        breaker.record_failure()
        time.sleep(0.15)

        breaker.allow_request()
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

    def test_force_open(self):
        """Test forcing circuit open."""
        breaker = CircuitBreaker()

        breaker.force_open()

        assert breaker.state == CircuitState.OPEN

    def test_force_close(self):
        """Test forcing circuit closed."""
        config = CircuitConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config)

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.force_close()

        assert breaker.state == CircuitState.CLOSED

    def test_reset(self):
        """Test resetting breaker."""
        config = CircuitConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config)

        breaker.record_failure()
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats["failure_count"] == 0

    def test_protect_decorator(self):
        """Test protect decorator."""
        config = CircuitConfig(failure_threshold=2)
        breaker = CircuitBreaker(config=config)

        call_count = 0

        @breaker.protect
        def my_func():
            nonlocal call_count
            call_count += 1
            return "result"

        result = my_func()

        assert result == "result"
        assert call_count == 1

    def test_protect_decorator_failure(self):
        """Test protect decorator with failures."""
        config = CircuitConfig(failure_threshold=2)
        breaker = CircuitBreaker(config=config)

        @breaker.protect
        def failing_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            failing_func()

        with pytest.raises(ValueError):
            failing_func()

        with pytest.raises(CircuitOpenError):
            failing_func()

    def test_call_with_fallback(self):
        """Test call with fallback."""
        config = CircuitConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config)

        def failing_func():
            raise ValueError("error")

        def fallback():
            return "fallback"

        # First call fails and opens circuit
        with pytest.raises(ValueError):
            breaker.call(failing_func)

        # Second call uses fallback
        result = breaker.call(failing_func, fallback=fallback)

        assert result == "fallback"

    def test_get_remaining_timeout(self):
        """Test getting remaining timeout."""
        config = CircuitConfig(failure_threshold=1, timeout_seconds=10.0)
        breaker = CircuitBreaker(config=config)

        breaker.record_failure()

        remaining = breaker.get_remaining_timeout()

        assert 9.0 < remaining <= 10.0

    def test_get_stats(self):
        """Test getting statistics."""
        breaker = CircuitBreaker()

        breaker.record_success()
        breaker.record_failure()

        stats = breaker.get_stats()

        assert stats["total_calls"] == 2
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""

    def test_get_or_create(self):
        """Test get or create."""
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("test-service")
        breaker2 = registry.get_or_create("test-service")

        assert breaker1 is breaker2

    def test_get_nonexistent(self):
        """Test get nonexistent breaker."""
        registry = CircuitBreakerRegistry()

        breaker = registry.get("nonexistent")

        assert breaker is None

    def test_remove(self):
        """Test removing breaker."""
        registry = CircuitBreakerRegistry()

        registry.get_or_create("test-service")
        removed = registry.remove("test-service")

        assert removed is True
        assert registry.get("test-service") is None

    def test_get_all_stats(self):
        """Test getting all stats."""
        registry = CircuitBreakerRegistry()

        registry.get_or_create("service-1")
        registry.get_or_create("service-2")

        stats = registry.get_all_stats()

        assert "service-1" in stats
        assert "service-2" in stats

    def test_reset_all(self):
        """Test resetting all breakers."""
        registry = CircuitBreakerRegistry()

        config = CircuitConfig(failure_threshold=1)
        b1 = registry.get_or_create("service-1", config)
        b2 = registry.get_or_create("service-2", config)

        b1.record_failure()
        b2.record_failure()

        registry.reset_all()

        assert b1.state == CircuitState.CLOSED
        assert b2.state == CircuitState.CLOSED


class TestCircuitBreakerDecorator:
    """Tests for circuit_breaker decorator."""

    def test_decorator_creates_breaker(self):
        """Test decorator creates breaker."""

        @circuit_breaker("decorator-test")
        def my_func():
            return "result"

        result = my_func()

        assert result == "result"

        registry = get_circuit_registry()
        breaker = registry.get("decorator-test")

        assert breaker is not None

    def test_decorator_tracks_failures(self):
        """Test decorator tracks failures."""
        registry = get_circuit_registry()

        @circuit_breaker("failing-test", CircuitConfig(failure_threshold=3))
        def failing_func():
            raise ValueError("error")

        for _ in range(2):
            with pytest.raises(ValueError):
                failing_func()

        breaker = registry.get("failing-test")

        assert breaker.get_stats()["consecutive_failures"] == 2
