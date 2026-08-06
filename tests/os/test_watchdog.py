"""Tests for OS Watchdog."""

from __future__ import annotations

import time
import threading

import pytest

from warm_logic_core.os.watchdog import (
    Watchdog,
    WatchdogState,
    TimeoutAction,
    WatchdogEvent,
    MultiWatchdog,
    get_watchdog_manager,
    watchdog_monitor,
)


class TestWatchdog:
    """Tests for Watchdog."""

    def test_watchdog_initialization(self):
        """Test watchdog initialization."""
        watchdog = Watchdog()

        assert watchdog.watchdog_id.startswith("WD-")
        assert watchdog.state == WatchdogState.IDLE

    def test_watchdog_custom_id(self):
        """Test watchdog with custom ID."""
        watchdog = Watchdog(watchdog_id="TEST-WD")

        assert watchdog.watchdog_id == "TEST-WD"

    def test_start_monitoring(self):
        """Test starting monitoring."""
        watchdog = Watchdog(timeout_seconds=10.0)

        watchdog.start("test_op")

        assert watchdog.state == WatchdogState.MONITORING

        watchdog.stop()

    def test_stop_returns_elapsed(self):
        """Test stop returns elapsed time."""
        watchdog = Watchdog(timeout_seconds=10.0)

        watchdog.start("test_op")
        time.sleep(0.05)
        elapsed = watchdog.stop()

        assert elapsed >= 0.05
        assert watchdog.state == WatchdogState.IDLE

    def test_context_manager(self):
        """Test context manager usage."""
        watchdog = Watchdog(timeout_seconds=10.0)

        with watchdog.monitor("test_op"):
            assert watchdog.state == WatchdogState.MONITORING

        assert watchdog.state == WatchdogState.IDLE

    def test_get_elapsed(self):
        """Test getting elapsed time."""
        watchdog = Watchdog(timeout_seconds=10.0)

        watchdog.start("test_op")
        time.sleep(0.05)

        elapsed = watchdog.get_elapsed()

        assert elapsed >= 0.05

        watchdog.stop()

    def test_get_remaining(self):
        """Test getting remaining time."""
        watchdog = Watchdog(timeout_seconds=1.0)

        watchdog.start("test_op")

        remaining = watchdog.get_remaining()

        assert remaining is not None
        assert remaining <= 1.0

        watchdog.stop()

    def test_pet_resets_timer(self):
        """Test pet resets timer."""
        watchdog = Watchdog(timeout_seconds=0.1)

        watchdog.start("test_op")
        time.sleep(0.05)
        watchdog.pet()

        remaining = watchdog.get_remaining()

        # Should be close to full timeout after pet
        assert remaining is not None
        assert remaining > 0.05

        watchdog.stop()

    def test_timeout_detection(self):
        """Test timeout is detected."""
        watchdog = Watchdog(timeout_seconds=0.05)

        watchdog.start("test_op")
        time.sleep(0.1)

        assert watchdog.state == WatchdogState.TIMEOUT

    def test_timeout_callback(self):
        """Test timeout callback is called."""
        callback_called = []
        callback_event = threading.Event()

        def callback(op, timeout, elapsed):
            callback_called.append((op, timeout, elapsed))
            callback_event.set()

        watchdog = Watchdog(
            timeout_seconds=0.05,
            action=TimeoutAction.CALLBACK,
            callback=callback,
        )

        watchdog.start("test_op")
        assert callback_event.wait(timeout=0.5)

        assert len(callback_called) == 1
        assert callback_called[0][0] == "test_op"

    def test_get_history(self):
        """Test event history."""
        watchdog = Watchdog(timeout_seconds=10.0)

        with watchdog.monitor("op1"):
            pass

        with watchdog.monitor("op2"):
            pass

        history = watchdog.get_history()

        assert len(history) == 2

    def test_get_stats(self):
        """Test getting statistics."""
        watchdog = Watchdog(timeout_seconds=10.0)

        with watchdog.monitor("test"):
            pass

        stats = watchdog.get_stats()

        assert stats["success_count"] == 1
        assert stats["timeout_count"] == 0

    def test_reset(self):
        """Test resetting watchdog."""
        watchdog = Watchdog(timeout_seconds=10.0)

        with watchdog.monitor("test"):
            pass

        watchdog.reset()

        stats = watchdog.get_stats()

        assert stats["success_count"] == 0
        assert len(watchdog.get_history()) == 0

    def test_stops_previous_on_restart(self):
        """Test starting stops previous monitoring."""
        watchdog = Watchdog(timeout_seconds=10.0)

        watchdog.start("op1")
        watchdog.start("op2")

        assert watchdog._current_operation == "op2"

        watchdog.stop()


class TestMultiWatchdog:
    """Tests for MultiWatchdog."""

    def test_get_or_create(self):
        """Test get or create."""
        multi = MultiWatchdog()

        wd1 = multi.get_or_create("service-1")
        wd2 = multi.get_or_create("service-1")

        assert wd1 is wd2

    def test_different_names(self):
        """Test different names create different watchdogs."""
        multi = MultiWatchdog()

        wd1 = multi.get_or_create("service-1")
        wd2 = multi.get_or_create("service-2")

        assert wd1 is not wd2

    def test_get(self):
        """Test getting watchdog by name."""
        multi = MultiWatchdog()

        multi.get_or_create("test")
        wd = multi.get("test")

        assert wd is not None
        assert wd.watchdog_id == "test"

    def test_get_nonexistent(self):
        """Test getting nonexistent watchdog."""
        multi = MultiWatchdog()

        wd = multi.get("nonexistent")

        assert wd is None

    def test_context_manager(self):
        """Test context manager."""
        multi = MultiWatchdog()

        with multi.monitor("test_op") as wd:
            assert wd.state == WatchdogState.MONITORING

    def test_get_all_stats(self):
        """Test getting all stats."""
        multi = MultiWatchdog()

        with multi.monitor("op1"):
            pass

        with multi.monitor("op2"):
            pass

        stats = multi.get_all_stats()

        assert "op1" in stats
        assert "op2" in stats

    def test_reset_all(self):
        """Test resetting all watchdogs."""
        multi = MultiWatchdog()

        with multi.monitor("op1"):
            pass

        with multi.monitor("op2"):
            pass

        multi.reset_all()

        stats = multi.get_all_stats()
        for s in stats.values():
            assert s["success_count"] == 0


class TestGlobalWatchdog:
    """Tests for global watchdog functions."""

    def test_get_manager(self):
        """Test getting global manager."""
        m1 = get_watchdog_manager()
        m2 = get_watchdog_manager()

        assert m1 is m2

    def test_watchdog_monitor_function(self):
        """Test watchdog_monitor function."""
        with watchdog_monitor("global_test", timeout_seconds=10.0) as wd:
            assert wd.state == WatchdogState.MONITORING


class TestWatchdogEvent:
    """Tests for WatchdogEvent."""

    def test_event_to_dict(self):
        """Test event serialization."""
        event = WatchdogEvent(
            event_id="WDE-1",
            timestamp="2024-01-01T00:00:00Z",
            operation="test",
            timeout_seconds=10.0,
            elapsed_seconds=5.0,
            state=WatchdogState.RECOVERED,
        )

        data = event.to_dict()

        assert data["event_id"] == "WDE-1"
        assert data["state"] == "recovered"
        assert data["elapsed_seconds"] == 5.0
