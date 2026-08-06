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
SLA Architecture - 99.9% Uptime Infrastructure

Provides production-grade reliability patterns:
- Health check system (liveness, readiness, startup)
- Circuit breaker pattern
- Error budget tracking
- SLA metrics and alerting
- Graceful degradation
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger("SLA")

T = TypeVar("T")


class HealthStatus(Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        """Check if status is healthy."""
        return self.status == HealthStatus.HEALTHY


@dataclass
class SLAConfig:
    """SLA configuration."""

    # SLA targets
    target_uptime: float = 99.9  # Percentage
    target_latency_p99_ms: float = 200.0
    target_error_rate: float = 0.1  # Percentage

    # Error budget
    error_budget_window_hours: int = 720  # 30 days
    error_budget_alert_threshold: float = 50.0  # Alert when 50% consumed

    # Health check settings
    health_check_interval_seconds: float = 10.0
    health_check_timeout_seconds: float = 5.0

    # Circuit breaker settings
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout_seconds: float = 30.0
    circuit_half_open_max_calls: int = 3


@dataclass
class SLAMetrics:
    """SLA metrics tracking."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    window_start: float = field(default_factory=time.time)

    # Error budget tracking
    error_budget_consumed: float = 0.0
    uptime_percentage: float = 100.0

    @property
    def error_rate(self) -> float:
        """Calculate current error rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100

    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def record_request(self, success: bool, latency_ms: float) -> None:
        """Record a request result."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
            self.total_latency_ms += latency_ms
            self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        else:
            self.failed_requests += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate": self.error_rate,
            "average_latency_ms": self.average_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "uptime_percentage": self.uptime_percentage,
            "error_budget_consumed": self.error_budget_consumed,
        }


class HealthCheck(ABC):
    """Abstract base class for health checks."""

    def __init__(self, name: str, critical: bool = True):
        self.name = name
        self.critical = critical  # If critical, failure = system unhealthy

    @abstractmethod
    def check(self) -> HealthCheckResult:
        """Perform health check and return result."""
        pass


class DatabaseHealthCheck(HealthCheck):
    """Health check for database connectivity."""

    def __init__(
        self,
        name: str = "database",
        check_func: Optional[Callable[[], bool]] = None,
        critical: bool = True,
    ):
        super().__init__(name, critical)
        self._check_func = check_func

    def check(self) -> HealthCheckResult:
        """Check database connectivity."""
        start = time.time()
        try:
            if self._check_func:
                is_healthy = self._check_func()
            else:
                # Default: assume healthy if no check function
                is_healthy = True

            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                message=(
                    "Database connection OK" if is_healthy else "Database check failed"
                ),
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {e}",
                latency_ms=(time.time() - start) * 1000,
            )


class DependencyHealthCheck(HealthCheck):
    """Health check for external dependencies."""

    def __init__(
        self,
        name: str,
        check_func: Callable[[], bool],
        timeout_seconds: float = 5.0,
        critical: bool = False,
    ):
        super().__init__(name, critical)
        self._check_func = check_func
        self._timeout = timeout_seconds

    def check(self) -> HealthCheckResult:
        """Check dependency health with timeout."""
        start = time.time()
        try:
            is_healthy = self._check_func()
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY if is_healthy else HealthStatus.DEGRADED,
                message=f"{self.name} OK" if is_healthy else f"{self.name} degraded",
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message=f"{self.name} error: {e}",
                latency_ms=(time.time() - start) * 1000,
            )


class CircuitBreaker:
    """
    Circuit Breaker Pattern

    Prevents cascading failures by stopping requests to failing services.
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests rejected immediately
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            self._check_recovery()
            return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    def _check_recovery(self) -> None:
        """Check if circuit should transition from OPEN to HALF_OPEN."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if time.time() - self._last_failure_time >= self._recovery_timeout:
                logger.info(
                    f"Circuit {self.name}: OPEN -> HALF_OPEN (recovery timeout)"
                )
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls += 1
                if self._success_count >= self._half_open_max_calls:
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED (recovery)")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (failure)")
                self._state = CircuitState.OPEN
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self._failure_threshold:
                    logger.warning(f"Circuit {self.name}: CLOSED -> OPEN (threshold)")
                    self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check if request should be allowed."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self._half_open_max_calls:
                    return True
            return False
        return False  # OPEN state

    def execute(
        self, func: Callable[[], T], fallback: Optional[Callable[[], T]] = None
    ) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            fallback: Optional fallback function if circuit is open

        Returns:
            Result of func or fallback

        Raises:
            CircuitOpenError: If circuit is open and no fallback provided
        """
        if not self.allow_request():
            if fallback:
                logger.debug(f"Circuit {self.name} open, using fallback")
                return fallback()
            raise CircuitOpenError(f"Circuit {self.name} is open")

        try:
            result = func()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            if fallback:
                return fallback()
            raise

    def to_dict(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout": self._recovery_timeout,
        }


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class HealthCheckRegistry:
    """
    Health Check Registry

    Manages multiple health checks for liveness, readiness, and startup probes.
    """

    def __init__(self) -> None:
        self._liveness_checks: List[HealthCheck] = []
        self._readiness_checks: List[HealthCheck] = []
        self._startup_checks: List[HealthCheck] = []
        self._lock = threading.Lock()

    def register_liveness(self, check: HealthCheck) -> None:
        """Register a liveness check."""
        with self._lock:
            self._liveness_checks.append(check)

    def register_readiness(self, check: HealthCheck) -> None:
        """Register a readiness check."""
        with self._lock:
            self._readiness_checks.append(check)

    def register_startup(self, check: HealthCheck) -> None:
        """Register a startup check."""
        with self._lock:
            self._startup_checks.append(check)

    def check_liveness(self) -> HealthCheckResult:
        """
        Run liveness checks.

        Liveness: Is the application alive? If not, restart it.
        """
        return self._run_checks("liveness", self._liveness_checks)

    def check_readiness(self) -> HealthCheckResult:
        """
        Run readiness checks.

        Readiness: Is the application ready to serve traffic?
        """
        return self._run_checks("readiness", self._readiness_checks)

    def check_startup(self) -> HealthCheckResult:
        """
        Run startup checks.

        Startup: Has the application started successfully?
        """
        return self._run_checks("startup", self._startup_checks)

    def _run_checks(
        self, probe_type: str, checks: List[HealthCheck]
    ) -> HealthCheckResult:
        """Run a list of health checks and aggregate results."""
        if not checks:
            return HealthCheckResult(
                name=probe_type,
                status=HealthStatus.HEALTHY,
                message=f"No {probe_type} checks registered",
            )

        results: List[HealthCheckResult] = []
        messages: List[str] = []
        start = time.time()
        overall_status = HealthStatus.HEALTHY

        for check in checks:
            result, message, new_status = self._execute_single_check(
                check, overall_status
            )
            if result:
                results.append(result)
            if message:
                messages.append(message)
            overall_status = new_status

        return HealthCheckResult(
            name=probe_type,
            status=overall_status,
            message="; ".join(messages) if messages else "All checks passed",
            latency_ms=(time.time() - start) * 1000,
            details={"checks": [r.name for r in results]},
        )

    def _execute_single_check(
        self,
        check: HealthCheck,
        current_status: HealthStatus,
    ) -> tuple[HealthCheckResult | None, str | None, HealthStatus]:
        """Execute a single health check and return result, message, and new status."""
        try:
            result = check.check()
            message, new_status = self._determine_status(check, result, current_status)
            return result, message, new_status
        except Exception as e:
            new_status = HealthStatus.UNHEALTHY if check.critical else current_status
            return None, f"{check.name}: error - {e}", new_status

    def _determine_status(
        self,
        check: HealthCheck,
        result: HealthCheckResult,
        current_status: HealthStatus,
    ) -> tuple[str | None, HealthStatus]:
        """Determine status and message based on check result."""
        if result.status == HealthStatus.UNHEALTHY:
            if check.critical:
                return f"{check.name}: {result.message}", HealthStatus.UNHEALTHY
            elif current_status != HealthStatus.UNHEALTHY:
                return f"{check.name}: {result.message}", HealthStatus.DEGRADED
            return f"{check.name}: {result.message}", current_status

        if result.status == HealthStatus.DEGRADED:
            if current_status == HealthStatus.HEALTHY:
                return f"{check.name}: degraded", HealthStatus.DEGRADED
            return f"{check.name}: degraded", current_status

        return None, current_status


class SLAMonitor:
    """
    SLA Monitor

    Tracks SLA metrics and error budget consumption.
    Provides alerting when SLA targets are at risk.
    """

    def __init__(self, config: SLAConfig):
        self.config = config
        self._metrics = SLAMetrics()
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._health_registry = HealthCheckRegistry()
        self._lock = threading.Lock()
        self._alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    @property
    def metrics(self) -> SLAMetrics:
        """Get current SLA metrics."""
        return self._metrics

    @property
    def health_registry(self) -> HealthCheckRegistry:
        """Get health check registry."""
        return self._health_registry

    def register_circuit_breaker(self, circuit: CircuitBreaker) -> None:
        """Register a circuit breaker for monitoring."""
        with self._lock:
            self._circuit_breakers[circuit.name] = circuit

    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        return self._circuit_breakers.get(name)

    def create_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Create and register a new circuit breaker."""
        circuit = CircuitBreaker(
            name=name,
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_timeout=self.config.circuit_recovery_timeout_seconds,
            half_open_max_calls=self.config.circuit_half_open_max_calls,
        )
        self.register_circuit_breaker(circuit)
        return circuit

    def record_request(self, success: bool, latency_ms: float) -> None:
        """Record a request for SLA tracking."""
        with self._lock:
            self._metrics.record_request(success, latency_ms)
            self._update_error_budget()
            self._check_alerts()

    def _update_error_budget(self) -> None:
        """Update error budget consumption."""
        # Calculate allowed errors based on SLA target
        # For 99.9% uptime, we allow 0.1% errors
        allowed_error_rate = 100 - self.config.target_uptime
        current_error_rate = self._metrics.error_rate

        if allowed_error_rate > 0:
            self._metrics.error_budget_consumed = (
                current_error_rate / allowed_error_rate
            ) * 100
        else:
            self._metrics.error_budget_consumed = 0.0

        # Calculate uptime
        if self._metrics.total_requests > 0:
            self._metrics.uptime_percentage = (
                self._metrics.successful_requests / self._metrics.total_requests
            ) * 100

    def _check_alerts(self) -> None:
        """Check if any alert conditions are met."""
        alerts = []

        # Check error budget
        if (
            self._metrics.error_budget_consumed
            >= self.config.error_budget_alert_threshold
        ):
            alerts.append(
                {
                    "type": "error_budget",
                    "message": f"Error budget {self._metrics.error_budget_consumed:.1f}% consumed",
                    "severity": "warning",
                }
            )

        # Check error rate
        if self._metrics.error_rate > self.config.target_error_rate:
            alerts.append(
                {
                    "type": "error_rate",
                    "message": f"Error rate {self._metrics.error_rate:.2f}% exceeds target",
                    "severity": "critical",
                }
            )

        # Check latency
        if self._metrics.average_latency_ms > self.config.target_latency_p99_ms:
            alerts.append(
                {
                    "type": "latency",
                    "message": f"Average latency {self._metrics.average_latency_ms:.1f}ms exceeds target",
                    "severity": "warning",
                }
            )

        # Trigger alert callbacks
        for alert in alerts:
            for callback in self._alert_callbacks:
                try:
                    callback(alert["type"], alert)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")

    def register_alert_callback(
        self, callback: Callable[[str, Dict[str, Any]], None]
    ) -> None:
        """Register a callback for SLA alerts."""
        self._alert_callbacks.append(callback)

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive SLA status."""
        liveness = self._health_registry.check_liveness()
        readiness = self._health_registry.check_readiness()

        return {
            "health": {
                "liveness": {
                    "status": liveness.status.value,
                    "message": liveness.message,
                },
                "readiness": {
                    "status": readiness.status.value,
                    "message": readiness.message,
                },
            },
            "metrics": self._metrics.to_dict(),
            "sla_targets": {
                "uptime": self.config.target_uptime,
                "latency_p99_ms": self.config.target_latency_p99_ms,
                "error_rate": self.config.target_error_rate,
            },
            "circuit_breakers": {
                name: cb.to_dict() for name, cb in self._circuit_breakers.items()
            },
            "error_budget": {
                "consumed_percent": self._metrics.error_budget_consumed,
                "remaining_percent": max(0, 100 - self._metrics.error_budget_consumed),
                "alert_threshold": self.config.error_budget_alert_threshold,
            },
        }

    def reset_metrics(self) -> None:
        """Reset metrics for a new measurement window."""
        with self._lock:
            self._metrics = SLAMetrics()


class GracefulDegradation:
    """
    Graceful Degradation Manager

    Manages service degradation levels when system is under stress.
    """

    def __init__(self) -> None:
        self._degradation_level = 0  # 0 = normal, higher = more degraded
        self._max_level = 5
        self._lock = threading.Lock()
        self._feature_flags: Dict[str, bool] = {}

    @property
    def level(self) -> int:
        """Get current degradation level."""
        return self._degradation_level

    def increase_degradation(self) -> int:
        """Increase degradation level."""
        with self._lock:
            if self._degradation_level < self._max_level:
                self._degradation_level += 1
                logger.warning(
                    f"Degradation level increased to {self._degradation_level}"
                )
            return self._degradation_level

    def decrease_degradation(self) -> int:
        """Decrease degradation level."""
        with self._lock:
            if self._degradation_level > 0:
                self._degradation_level -= 1
                logger.info(f"Degradation level decreased to {self._degradation_level}")
            return self._degradation_level

    def reset(self) -> None:
        """Reset to normal operation."""
        with self._lock:
            self._degradation_level = 0
            logger.info("Degradation level reset to normal")

    def is_feature_enabled(self, feature: str, default: bool = True) -> bool:
        """
        Check if a feature should be enabled at current degradation level.

        Higher degradation levels disable more features.
        """
        # Check explicit feature flag first
        if feature in self._feature_flags:
            return self._feature_flags[feature]

        # Default behavior based on degradation level
        # Level 0: All features enabled
        # Level 1-2: Non-critical features may be disabled
        # Level 3+: Only critical features enabled
        if self._degradation_level == 0:
            return default
        elif self._degradation_level <= 2:
            # Disable expensive features
            expensive_features = {"analytics", "recommendations", "batch_jobs"}
            return feature not in expensive_features and default
        else:
            # Only critical features
            critical_features = {"auth", "core_api", "health"}
            return feature in critical_features

    def set_feature_flag(self, feature: str, enabled: bool) -> None:
        """Set explicit feature flag."""
        with self._lock:
            self._feature_flags[feature] = enabled


# Global SLA monitor instance
_sla_monitor: Optional[SLAMonitor] = None


def get_sla_monitor() -> SLAMonitor:
    """Get the global SLA monitor instance."""
    global _sla_monitor
    if _sla_monitor is None:
        _sla_monitor = SLAMonitor(SLAConfig())
    return _sla_monitor


def initialize_sla(config: Optional[SLAConfig] = None) -> SLAMonitor:
    """Initialize the global SLA monitor."""
    global _sla_monitor
    _sla_monitor = SLAMonitor(config or SLAConfig())
    logger.info(
        f"SLA Monitor initialized: target={_sla_monitor.config.target_uptime}%, "
        f"latency_p99={_sla_monitor.config.target_latency_p99_ms}ms"
    )
    return _sla_monitor


# Convenience decorators
def with_circuit_breaker(
    circuit_name: str, fallback: Optional[Callable[[], T]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to wrap function with circuit breaker."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            monitor = get_sla_monitor()
            circuit = monitor.get_circuit_breaker(circuit_name)
            if circuit is None:
                circuit = monitor.create_circuit_breaker(circuit_name)

            return circuit.execute(
                lambda: func(*args, **kwargs),
                fallback=fallback,
            )

        return wrapper

    return decorator


def track_sla(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to track function execution for SLA metrics."""

    def wrapper(*args: Any, **kwargs: Any) -> T:
        monitor = get_sla_monitor()
        start = time.time()
        success = True
        try:
            result = func(*args, **kwargs)
            return result
        except Exception:
            success = False
            raise
        finally:
            latency_ms = (time.time() - start) * 1000
            monitor.record_request(success, latency_ms)

    return wrapper
