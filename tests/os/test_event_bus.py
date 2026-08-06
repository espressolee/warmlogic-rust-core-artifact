"""Tests for OS Event Bus."""

from __future__ import annotations

import threading
import time

import pytest

from warm_logic_core.os.event_bus import (
    EventBus,
    BusEvent,
    EventCategory,
    EventPriority,
    Subscription,
    get_event_bus,
    publish_event,
)


class TestBusEvent:
    """Tests for BusEvent."""

    def test_event_creation(self):
        """Test event creation."""
        event = BusEvent.create(
            category=EventCategory.KERNEL,
            event_type="tick",
            payload={"tick": 1},
        )

        assert event.event_id.startswith("EVT-")
        assert event.category == EventCategory.KERNEL
        assert event.event_type == "tick"
        assert event.payload == {"tick": 1}
        assert event.priority == EventPriority.NORMAL

    def test_event_with_priority(self):
        """Test event with priority."""
        event = BusEvent.create(
            category=EventCategory.GOVERNANCE,
            event_type="decision",
            priority=EventPriority.HIGH,
        )

        assert event.priority == EventPriority.HIGH

    def test_event_to_dict(self):
        """Test event serialization."""
        event = BusEvent.create(
            category=EventCategory.STABILITY,
            event_type="alert",
        )

        data = event.to_dict()

        assert data["category"] == "stability"
        assert data["event_type"] == "alert"


class TestSubscription:
    """Tests for Subscription."""

    def test_subscription_matches_all(self):
        """Test subscription matching all events."""
        sub = Subscription(subscription_id="SUB-1")
        event = BusEvent.create(EventCategory.KERNEL, "tick")

        assert sub.matches(event) is True

    def test_subscription_category_filter(self):
        """Test subscription with category filter."""
        sub = Subscription(
            subscription_id="SUB-1",
            categories={EventCategory.KERNEL},
        )

        kernel_event = BusEvent.create(EventCategory.KERNEL, "tick")
        gov_event = BusEvent.create(EventCategory.GOVERNANCE, "decision")

        assert sub.matches(kernel_event) is True
        assert sub.matches(gov_event) is False

    def test_subscription_event_type_filter(self):
        """Test subscription with event type filter."""
        sub = Subscription(
            subscription_id="SUB-1",
            event_types={"tick", "start"},
        )

        tick_event = BusEvent.create(EventCategory.KERNEL, "tick")
        stop_event = BusEvent.create(EventCategory.KERNEL, "stop")

        assert sub.matches(tick_event) is True
        assert sub.matches(stop_event) is False

    def test_subscription_priority_filter(self):
        """Test subscription with priority filter."""
        sub = Subscription(
            subscription_id="SUB-1",
            priority_filter=EventPriority.HIGH,
        )

        high_event = BusEvent.create(
            EventCategory.KERNEL, "alert", priority=EventPriority.HIGH
        )
        low_event = BusEvent.create(
            EventCategory.KERNEL, "info", priority=EventPriority.LOW
        )

        assert sub.matches(high_event) is True
        assert sub.matches(low_event) is False


class TestEventBus:
    """Tests for EventBus."""

    def test_bus_initialization(self):
        """Test bus initialization."""
        bus = EventBus()

        assert bus.bus_id.startswith("BUS-")

    def test_bus_custom_id(self):
        """Test bus with custom ID."""
        bus = EventBus(bus_id="TEST-BUS")

        assert bus.bus_id == "TEST-BUS"

    def test_subscribe_and_publish(self):
        """Test subscribing and publishing."""
        bus = EventBus()
        received = []

        def handler(event: BusEvent):
            received.append(event)

        bus.subscribe(handler=handler)
        bus.publish_sync(EventCategory.KERNEL, "tick")

        assert len(received) == 1
        assert received[0].event_type == "tick"

    def test_multiple_subscribers(self):
        """Test multiple subscribers."""
        bus = EventBus()
        received_1 = []
        received_2 = []

        bus.subscribe(handler=lambda e: received_1.append(e))
        bus.subscribe(handler=lambda e: received_2.append(e))

        bus.publish_sync(EventCategory.KERNEL, "tick")

        assert len(received_1) == 1
        assert len(received_2) == 1

    def test_unsubscribe(self):
        """Test unsubscribing."""
        bus = EventBus()
        received = []

        sub_id = bus.subscribe(handler=lambda e: received.append(e))
        bus.publish_sync(EventCategory.KERNEL, "tick")

        assert len(received) == 1

        bus.unsubscribe(sub_id)
        bus.publish_sync(EventCategory.KERNEL, "tick")

        assert len(received) == 1  # Still 1

    def test_filtered_subscription(self):
        """Test filtered subscription."""
        bus = EventBus()
        kernel_events = []
        gov_events = []

        bus.subscribe(
            handler=lambda e: kernel_events.append(e),
            categories={EventCategory.KERNEL},
        )
        bus.subscribe(
            handler=lambda e: gov_events.append(e),
            categories={EventCategory.GOVERNANCE},
        )

        bus.publish_sync(EventCategory.KERNEL, "tick")
        bus.publish_sync(EventCategory.GOVERNANCE, "decision")

        assert len(kernel_events) == 1
        assert len(gov_events) == 1

    def test_get_history(self):
        """Test event history."""
        bus = EventBus()

        bus.publish_sync(EventCategory.KERNEL, "tick")
        bus.publish_sync(EventCategory.GOVERNANCE, "decision")

        history = bus.get_history()

        assert len(history) == 2

    def test_history_limit(self):
        """Test history limit."""
        bus = EventBus(max_history=5)

        for i in range(10):
            bus.publish_sync(EventCategory.KERNEL, f"tick_{i}")

        history = bus.get_history()

        assert len(history) == 5

    def test_get_stats(self):
        """Test bus statistics."""
        bus = EventBus()
        bus.subscribe(handler=lambda e: None)

        bus.publish_sync(EventCategory.KERNEL, "tick")

        stats = bus.get_stats()

        assert stats["subscription_count"] == 1
        assert stats["events_published"] == 1
        assert stats["events_delivered"] == 1

    def test_thread_safety(self):
        """Test thread safety."""
        bus = EventBus()
        received = []
        lock = threading.Lock()

        def handler(event: BusEvent):
            with lock:
                received.append(event)

        bus.subscribe(handler=handler)

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=lambda: bus.publish_sync(EventCategory.KERNEL, "tick")
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(received) == 10


class TestGlobalEventBus:
    """Tests for global event bus."""

    def test_get_global_bus(self):
        """Test getting global bus."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()

        assert bus1 is bus2

    def test_publish_event(self):
        """Test global publish function."""
        event = publish_event(EventCategory.KERNEL, "global_test")

        assert event.event_type == "global_test"
