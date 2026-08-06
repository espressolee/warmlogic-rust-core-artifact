"""
Tests for MCP Tool Limits Enforcer.

Comprehensive test suite covering:
- ToolLimitConfig
- Violation
- CheckResult
- RateLimiter
- ConcurrencyLimiter
- CostTracker
- ToolLimitsEnforcer
"""

import json
import tempfile
import threading
import time
from pathlib import Path

import pytest

try:
    from warm_logic_core.mcp import (
        CheckResult,
        ConcurrencyLimiter,
        CostTracker,
        RateLimiter,
        ToolLimitConfig,
        ToolLimitsEnforcer,
        Violation,
        create_enforcer_from_defaults,
    )
except (ImportError, ModuleNotFoundError):
    pytest.skip("warm_logic_core.mcp not available", allow_module_level=True)

# ============================================================================
# ToolLimitConfig Tests
# ============================================================================


class TestToolLimitConfig:
    """Tests for ToolLimitConfig dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = ToolLimitConfig(tool_name="test_tool")
        assert config.tool_name == "test_tool"
        assert config.timeout_ms == 30000
        assert config.max_retries == 3
        assert config.burst_limit == 5
        assert config.max_concurrent == 5
        assert config.queue_size == 10
        assert config.autonomy_level_min == "none"
        assert config.on_timeout == "fail"
        assert config.on_rate_limit == "queue"

    def test_custom_values(self):
        """Test custom values are set correctly."""
        config = ToolLimitConfig(
            tool_name="custom_tool",
            timeout_ms=60000,
            rate_limit_rpm=100,
            max_concurrent=10,
            required_roles=["admin", "operator"],
            blocked_targets=["/etc/*"],
        )
        assert config.timeout_ms == 60000
        assert config.rate_limit_rpm == 100
        assert config.max_concurrent == 10
        assert config.required_roles == ["admin", "operator"]
        assert config.blocked_targets == ["/etc/*"]

    def test_from_dict_basic(self):
        """Test creating config from dictionary."""
        data = {
            "tool_name": "from_dict_tool",
            "limits": {
                "timeout_ms": 5000,
                "rate_limit": {"requests_per_minute": 30, "burst_limit": 10},
            },
        }
        config = ToolLimitConfig.from_dict(data)
        assert config.tool_name == "from_dict_tool"
        assert config.timeout_ms == 5000
        assert config.rate_limit_rpm == 30
        assert config.burst_limit == 10

    def test_from_dict_full(self):
        """Test creating config from full dictionary."""
        data = {
            "tool_name": "full_tool",
            "limits": {
                "timeout_ms": 10000,
                "max_retries": 5,
                "rate_limit": {
                    "requests_per_minute": 60,
                    "requests_per_hour": 1000,
                    "burst_limit": 15,
                },
                "concurrency": {"max_concurrent": 8, "queue_size": 20},
                "payload": {
                    "max_input_size_bytes": 1000000,
                    "max_output_size_bytes": 500000,
                },
                "cost": {"max_cost_per_call_usd": 0.05, "max_daily_cost_usd": 50.0},
            },
            "permissions": {
                "required_roles": ["developer"],
                "required_scopes": ["read", "write"],
                "autonomy_level_min": "suggest",
                "requires_human_approval": True,
            },
            "security": {
                "allowed_targets": ["*.safe.com"],
                "blocked_targets": ["*.dangerous.com"],
                "data_classification_max": "internal",
                "audit_level": "full",
                "sandbox_required": True,
            },
            "fallback": {
                "on_timeout": "retry",
                "on_rate_limit": "fallback_tool",
                "fallback_tool": "backup_tool",
            },
        }
        config = ToolLimitConfig.from_dict(data)
        assert config.rate_limit_rpm == 60
        assert config.rate_limit_rph == 1000
        assert config.max_concurrent == 8
        assert config.max_input_size_bytes == 1000000
        assert config.max_daily_cost_usd == 50.0
        assert config.required_roles == ["developer"]
        assert config.autonomy_level_min == "suggest"
        assert config.requires_human_approval is True
        assert config.blocked_targets == ["*.dangerous.com"]
        assert config.sandbox_required is True
        assert config.fallback_tool == "backup_tool"


# ============================================================================
# Violation Tests
# ============================================================================


class TestViolation:
    """Tests for Violation dataclass."""

    def test_violation_creation(self):
        """Test creating a violation."""
        v = Violation(
            violation_id="VIO-TEST123",
            violation_type="RATE_LIMIT_EXCEEDED",
            tool_name="test_tool",
            call_id="call-001",
            limit_name="rate_limit",
            limit_value=60,
            actual_value=65,
            unit="rpm",
            timestamp="2024-01-01T00:00:00Z",
        )
        assert v.violation_id == "VIO-TEST123"
        assert v.violation_type == "RATE_LIMIT_EXCEEDED"
        assert v.severity == "warning"

    def test_violation_to_dict(self):
        """Test converting violation to dictionary."""
        v = Violation(
            violation_id="VIO-TEST456",
            violation_type="TIMEOUT_EXCEEDED",
            tool_name="slow_tool",
            call_id="call-002",
            limit_name="timeout_ms",
            limit_value=5000,
            actual_value=7500,
            unit="ms",
            timestamp="2024-01-01T00:00:00Z",
            session_id="session-123",
            decision_id="decision-456",
            severity="error",
            message="Call exceeded timeout",
        )
        d = v.to_dict()
        assert d["schema_version"] == "tool_limit_violation_v1"
        assert d["violation_id"] == "VIO-TEST456"
        assert d["limit_details"]["limit_name"] == "timeout_ms"
        assert d["limit_details"]["overage_percent"] == 50.0

    def test_violation_overage_calculation(self):
        """Test overage percentage calculation."""
        v = Violation(
            violation_id="VIO-OVERAGE",
            violation_type="SIZE_EXCEEDED",
            tool_name="tool",
            call_id="call",
            limit_name="size",
            limit_value=100,
            actual_value=150,
            unit="bytes",
            timestamp="2024-01-01T00:00:00Z",
        )
        d = v.to_dict()
        assert d["limit_details"]["overage_percent"] == 50.0


# ============================================================================
# CheckResult Tests
# ============================================================================


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_allowed_result(self):
        """Test allowed check result."""
        result = CheckResult(allowed=True)
        assert result.allowed is True
        assert result.violation is None
        assert result.wait_time_ms == 0
        assert result.queue_position == 0

    def test_denied_result(self):
        """Test denied check result with violation."""
        v = Violation(
            violation_id="VIO-DENY",
            violation_type="PERMISSION_DENIED",
            tool_name="tool",
            call_id="call",
            limit_name="roles",
            limit_value=["admin"],
            actual_value=["guest"],
            unit="roles",
            timestamp="2024-01-01T00:00:00Z",
        )
        result = CheckResult(allowed=False, violation=v)
        assert result.allowed is False
        assert result.violation is not None
        assert result.violation.violation_type == "PERMISSION_DENIED"

    def test_queued_result(self):
        """Test queued result with position."""
        result = CheckResult(allowed=True, queue_position=3)
        assert result.queue_position == 3

    def test_fallback_result(self):
        """Test result with fallback tool."""
        result = CheckResult(
            allowed=False, fallback_tool="backup_tool", wait_time_ms=1000
        )
        assert result.fallback_tool == "backup_tool"
        assert result.wait_time_ms == 1000


# ============================================================================
# RateLimiter Tests
# ============================================================================


class TestRateLimiter:
    """Tests for RateLimiter (token bucket)."""

    def test_acquire_within_burst(self):
        """Test acquiring tokens within burst limit."""
        limiter = RateLimiter(rate_per_second=10, burst=5)
        for _ in range(5):
            success, wait = limiter.acquire()
            assert success is True
            assert wait == 0.0

    def test_acquire_exceeds_burst(self):
        """Test acquiring more than burst limit."""
        limiter = RateLimiter(rate_per_second=10, burst=3)
        for _ in range(3):
            success, _ = limiter.acquire()
            assert success is True

        success, wait = limiter.acquire()
        assert success is False
        assert wait > 0

    def test_rate_refill(self):
        """Test token refill over time."""
        limiter = RateLimiter(rate_per_second=100, burst=1)
        success, _ = limiter.acquire()
        assert success is True

        success, _ = limiter.acquire()
        assert success is False

        time.sleep(0.02)
        success, _ = limiter.acquire()
        assert success is True

    def test_thread_safety(self):
        """Test rate limiter is thread safe."""
        limiter = RateLimiter(rate_per_second=100, burst=10)
        success_count = [0]
        lock = threading.Lock()

        def acquire_token():
            success, _ = limiter.acquire()
            if success:
                with lock:
                    success_count[0] += 1

        threads = [threading.Thread(target=acquire_token) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Due to token refill during thread execution, may get more than burst
        # Just verify we got at least burst limit and not more than total threads
        assert 10 <= success_count[0] <= 20


# ============================================================================
# ConcurrencyLimiter Tests
# ============================================================================


class TestConcurrencyLimiter:
    """Tests for ConcurrencyLimiter."""

    def test_acquire_within_limit(self):
        """Test acquiring within concurrency limit."""
        limiter = ConcurrencyLimiter(max_concurrent=3, queue_size=5)
        for _ in range(3):
            acquired, pos = limiter.try_acquire()
            assert acquired is True
            assert pos == 0

    def test_queue_when_full(self):
        """Test queueing when slots are full."""
        limiter = ConcurrencyLimiter(max_concurrent=2, queue_size=3)
        limiter.try_acquire()
        limiter.try_acquire()

        acquired, pos = limiter.try_acquire()
        assert acquired is False
        assert pos == 1

    def test_queue_overflow(self):
        """Test queue overflow returns -1."""
        limiter = ConcurrencyLimiter(max_concurrent=1, queue_size=2)
        limiter.try_acquire()
        limiter.try_acquire()
        limiter.try_acquire()

        acquired, pos = limiter.try_acquire()
        assert acquired is False
        assert pos == -1

    def test_release(self):
        """Test releasing a slot."""
        limiter = ConcurrencyLimiter(max_concurrent=1, queue_size=1)
        limiter.try_acquire()
        assert limiter.active_count == 1

        limiter.release()
        assert limiter.active_count == 0

        acquired, _ = limiter.try_acquire()
        assert acquired is True

    def test_thread_safety(self):
        """Test concurrency limiter is thread safe."""
        limiter = ConcurrencyLimiter(max_concurrent=5, queue_size=10)
        acquired_count = [0]
        lock = threading.Lock()

        def try_acquire():
            acquired, _ = limiter.try_acquire()
            if acquired:
                with lock:
                    acquired_count[0] += 1

        threads = [threading.Thread(target=try_acquire) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert acquired_count[0] == 5


# ============================================================================
# CostTracker Tests
# ============================================================================


class TestCostTracker:
    """Tests for CostTracker."""

    def test_add_cost(self):
        """Test adding cost."""
        tracker = CostTracker()
        total = tracker.add_cost("tool1", 1.50)
        assert total == 1.50

        total = tracker.add_cost("tool1", 2.50)
        assert total == 4.00

    def test_get_daily_cost(self):
        """Test getting daily cost."""
        tracker = CostTracker()
        tracker.add_cost("tool1", 5.00)
        tracker.add_cost("tool2", 3.00)

        assert tracker.get_daily_cost("tool1") == 5.00
        assert tracker.get_daily_cost("tool2") == 3.00
        assert tracker.get_daily_cost("tool3") == 0.00

    def test_multiple_tools(self):
        """Test tracking costs for multiple tools."""
        tracker = CostTracker()
        tracker.add_cost("tool1", 1.00)
        tracker.add_cost("tool2", 2.00)
        tracker.add_cost("tool1", 1.00)

        assert tracker.get_daily_cost("tool1") == 2.00
        assert tracker.get_daily_cost("tool2") == 2.00


# ============================================================================
# ToolLimitsEnforcer Tests
# ============================================================================


class TestToolLimitsEnforcer:
    """Tests for ToolLimitsEnforcer."""

    def test_register_config(self):
        """Test registering a configuration."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="test_tool", rate_limit_rpm=60)
        enforcer.register_config(config)

        retrieved = enforcer.get_config("test_tool")
        assert retrieved is not None
        assert retrieved.rate_limit_rpm == 60

    def test_check_unregistered_tool(self):
        """Test checking unregistered tool allows by default."""
        enforcer = ToolLimitsEnforcer()
        result = enforcer.check_before_call("unknown_tool", "call-001")
        assert result.allowed is True

    def test_check_permission_denied(self):
        """Test permission denied violation."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(
            tool_name="admin_tool", required_roles=["admin", "superuser"]
        )
        enforcer.register_config(config)

        result = enforcer.check_before_call(
            "admin_tool", "call-001", actor_roles=["guest"]
        )
        assert result.allowed is False
        assert result.violation.violation_type == "PERMISSION_DENIED"

    def test_check_permission_allowed(self):
        """Test permission allowed."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="admin_tool", required_roles=["admin"])
        enforcer.register_config(config)

        result = enforcer.check_before_call(
            "admin_tool", "call-001", actor_roles=["admin", "user"]
        )
        assert result.allowed is True

    def test_check_autonomy_level_insufficient(self):
        """Test autonomy level insufficient."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(
            tool_name="auto_tool", autonomy_level_min="act_with_approval"
        )
        enforcer.register_config(config)

        result = enforcer.check_before_call(
            "auto_tool", "call-001", autonomy_level="suggest"
        )
        assert result.allowed is False
        assert result.violation.violation_type == "AUTONOMY_LEVEL_INSUFFICIENT"

    def test_check_autonomy_level_sufficient(self):
        """Test autonomy level sufficient."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="auto_tool", autonomy_level_min="suggest")
        enforcer.register_config(config)

        result = enforcer.check_before_call(
            "auto_tool", "call-001", autonomy_level="act_with_approval"
        )
        assert result.allowed is True

    def test_check_blocked_target(self):
        """Test blocked target violation."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(
            tool_name="file_tool", blocked_targets=["/etc/", "/root/"]
        )
        enforcer.register_config(config)

        result = enforcer.check_before_call(
            "file_tool", "call-001", target="/etc/passwd"
        )
        assert result.allowed is False
        assert result.violation.violation_type == "SECURITY_BLOCKED"

    def test_check_input_size_exceeded(self):
        """Test input size exceeded."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="size_tool", max_input_size_bytes=1000)
        enforcer.register_config(config)

        result = enforcer.check_before_call(
            "size_tool", "call-001", input_size_bytes=2000
        )
        assert result.allowed is False
        assert result.violation.violation_type == "PAYLOAD_SIZE_EXCEEDED"

    def test_check_daily_cost_exceeded(self):
        """Test daily cost limit exceeded."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="cost_tool", max_daily_cost_usd=10.0)
        enforcer.register_config(config)

        enforcer._cost_tracker.add_cost("cost_tool", 10.0)

        result = enforcer.check_before_call("cost_tool", "call-001")
        assert result.allowed is False
        assert result.violation.violation_type == "COST_LIMIT_EXCEEDED"

    def test_check_rate_limit_fail_mode(self):
        """Test rate limit in fail mode."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(
            tool_name="rate_tool",
            rate_limit_rpm=60,
            burst_limit=1,
            on_rate_limit="fail",
        )
        enforcer.register_config(config)

        enforcer.check_before_call("rate_tool", "call-001")
        result = enforcer.check_before_call("rate_tool", "call-002")

        assert result.allowed is False
        assert result.violation.violation_type == "RATE_LIMIT_EXCEEDED"

    def test_check_concurrency_queue_full(self):
        """Test concurrency queue full."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="conc_tool", max_concurrent=1, queue_size=1)
        enforcer.register_config(config)

        enforcer.check_before_call("conc_tool", "call-001")
        enforcer.check_before_call("conc_tool", "call-002")
        result = enforcer.check_before_call("conc_tool", "call-003")

        assert result.allowed is False
        assert result.violation.violation_type == "CONCURRENCY_LIMIT_EXCEEDED"

    def test_record_timeout_violation(self):
        """Test recording timeout violation on completion."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="timeout_tool", timeout_ms=1000)
        enforcer.register_config(config)

        violations = enforcer.record_call_completion(
            "timeout_tool", "call-001", duration_ms=2000
        )
        assert len(violations) == 1
        assert violations[0].violation_type == "TIMEOUT_EXCEEDED"

    def test_violation_callback(self):
        """Test violation callback is called."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="callback_tool", timeout_ms=1000)
        enforcer.register_config(config)

        callback_violations = []
        enforcer.set_violation_callback(lambda v: callback_violations.append(v))

        enforcer.record_call_completion("callback_tool", "call-001", duration_ms=2000)
        assert len(callback_violations) == 1

    def test_get_violations(self):
        """Test getting violations."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="vio_tool", timeout_ms=100)
        enforcer.register_config(config)

        enforcer.record_call_completion("vio_tool", "call-001", duration_ms=200)
        enforcer.record_call_completion("vio_tool", "call-002", duration_ms=300)

        violations = enforcer.get_violations()
        assert len(violations) == 2

        violations = enforcer.get_violations(tool_name="vio_tool")
        assert len(violations) == 2

    def test_export_violations_jsonl(self):
        """Test exporting violations to JSONL."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="export_tool", timeout_ms=100)
        enforcer.register_config(config)

        enforcer.record_call_completion("export_tool", "call-001", duration_ms=200)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "violations.jsonl"
            count = enforcer.export_violations_jsonl(path)

            assert count == 1
            assert path.exists()

            with open(path) as f:
                data = json.loads(f.readline())
                assert data["schema_version"] == "tool_limit_violation_v1"

    def test_get_stats(self):
        """Test getting enforcer stats."""
        enforcer = ToolLimitsEnforcer()
        config1 = ToolLimitConfig(tool_name="tool1", timeout_ms=100)
        config2 = ToolLimitConfig(tool_name="tool2", timeout_ms=100)
        enforcer.register_config(config1)
        enforcer.register_config(config2)

        enforcer.record_call_completion("tool1", "call-001", duration_ms=200)

        stats = enforcer.get_stats()
        assert stats["tools_configured"] == 2
        assert stats["total_violations"] == 1
        assert "TIMEOUT_EXCEEDED" in stats["violations_by_type"]


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestCreateEnforcerFromDefaults:
    """Tests for create_enforcer_from_defaults factory."""

    def test_creates_enforcer_with_defaults(self):
        """Test factory creates enforcer with default tools."""
        enforcer = create_enforcer_from_defaults()

        assert enforcer.get_config("web_search") is not None
        assert enforcer.get_config("llm_query") is not None
        assert enforcer.get_config("file_read") is not None
        assert enforcer.get_config("file_write") is not None
        assert enforcer.get_config("shell_exec") is not None

    def test_default_configs_have_expected_values(self):
        """Test default configs have expected values."""
        enforcer = create_enforcer_from_defaults()

        web_search = enforcer.get_config("web_search")
        assert web_search.rate_limit_rpm == 60
        assert web_search.max_concurrent == 3

        shell_exec = enforcer.get_config("shell_exec")
        assert shell_exec.required_roles == ["admin"]
        assert shell_exec.autonomy_level_min == "act_with_approval"
        assert shell_exec.sandbox_required is True


# ============================================================================
# Integration Tests
# ============================================================================


class TestEnforcerIntegration:
    """Integration tests for enforcer workflow."""

    def test_full_workflow(self):
        """Test full workflow: check, execute, complete."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(
            tool_name="workflow_tool",
            rate_limit_rpm=60,
            max_concurrent=5,
            timeout_ms=5000,
            required_roles=["user"],
        )
        enforcer.register_config(config)

        result = enforcer.check_before_call(
            "workflow_tool",
            "call-001",
            session_id="session-001",
            actor_roles=["user"],
        )
        assert result.allowed is True

        violations = enforcer.record_call_completion(
            "workflow_tool", "call-001", duration_ms=1000
        )
        assert len(violations) == 0

    def test_fallback_on_rate_limit(self):
        """Test fallback tool suggestion on rate limit."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(
            tool_name="main_tool",
            rate_limit_rpm=60,
            burst_limit=1,
            on_rate_limit="fallback_tool",
            fallback_tool="backup_tool",
        )
        enforcer.register_config(config)

        enforcer.check_before_call("main_tool", "call-001")
        result = enforcer.check_before_call("main_tool", "call-002")

        assert result.allowed is False
        assert result.fallback_tool == "backup_tool"

    def test_concurrency_release_allows_new(self):
        """Test releasing concurrency slot allows new call."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="conc_tool", max_concurrent=1, queue_size=0)
        enforcer.register_config(config)

        result1 = enforcer.check_before_call("conc_tool", "call-001")
        assert result1.allowed is True

        result2 = enforcer.check_before_call("conc_tool", "call-002")
        assert result2.allowed is False

        enforcer.record_call_completion("conc_tool", "call-001", duration_ms=100)

        result3 = enforcer.check_before_call("conc_tool", "call-003")
        assert result3.allowed is True


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_roles_list(self):
        """Test with empty roles list."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="tool", required_roles=["admin"])
        enforcer.register_config(config)

        result = enforcer.check_before_call("tool", "call", actor_roles=[])
        assert result.allowed is False

    def test_none_roles(self):
        """Test with None roles."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="tool", required_roles=["admin"])
        enforcer.register_config(config)

        result = enforcer.check_before_call("tool", "call", actor_roles=None)
        assert result.allowed is False

    def test_wildcard_blocked_target(self):
        """Test wildcard pattern in blocked targets."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="tool", blocked_targets=["*.bad.com"])
        enforcer.register_config(config)

        result = enforcer.check_before_call("tool", "call", target="evil.bad.com")
        assert result.allowed is False

    def test_zero_rate_limit(self):
        """Test with no rate limit configured but high concurrency."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(
            tool_name="tool",
            max_concurrent=100,  # High limit to avoid concurrency issues
            queue_size=100,
        )
        enforcer.register_config(config)

        for i in range(50):
            result = enforcer.check_before_call("tool", f"call-{i}")
            assert result.allowed is True
            # Release slot to allow next call
            enforcer.record_call_completion("tool", f"call-{i}", duration_ms=1)

    def test_invalid_autonomy_level(self):
        """Test with invalid autonomy level defaults to lowest."""
        enforcer = ToolLimitsEnforcer()
        config = ToolLimitConfig(tool_name="tool", autonomy_level_min="suggest")
        enforcer.register_config(config)

        result = enforcer.check_before_call("tool", "call", autonomy_level="invalid")
        assert result.allowed is False
