"""Tests for CostTracker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from warm_logic_core.meta_obs.cost_tracker import (
    CostAllocation,
    CostBudget,
    CostComponent,
    CostEntry,
    CostTracker,
    ImplementationEffort,
    OptimizationRecommendation,
)


class TestCostEntry:
    """Tests for CostEntry."""

    def test_entry_creation(self):
        """Test entry creation."""
        entry = CostEntry(
            entry_id="COST-001",
            component=CostComponent.LLM_INFERENCE,
            amount_usd=0.05,
            description="LLM call",
        )

        assert entry.entry_id == "COST-001"
        assert entry.component == CostComponent.LLM_INFERENCE
        assert entry.amount_usd == 0.05

    def test_entry_to_dict(self):
        """Test entry serialization."""
        entry = CostEntry(
            entry_id="COST-002",
            component=CostComponent.TOOL_EXECUTION,
            amount_usd=0.01,
            quantity=5,
            unit_cost_usd=0.002,
        )

        data = entry.to_dict()

        assert data["entry_id"] == "COST-002"
        assert data["component"] == "tool_execution"
        assert data["amount_usd"] == 0.01
        assert data["quantity"] == 5


class TestCostBudget:
    """Tests for CostBudget."""

    def test_budget_creation(self):
        """Test budget creation."""
        budget = CostBudget(
            daily_budget_usd=100.0,
            monthly_budget_usd=3000.0,
        )

        assert budget.daily_budget_usd == 100.0
        assert budget.monthly_budget_usd == 3000.0

    def test_budget_utilization(self):
        """Test budget utilization calculation."""
        budget = CostBudget(
            monthly_budget_usd=1000.0,
            current_monthly_spend_usd=250.0,
        )

        assert budget.budget_utilization_percent == 25.0

    def test_budget_to_dict(self):
        """Test budget serialization."""
        budget = CostBudget(
            daily_budget_usd=50.0,
            monthly_budget_usd=1500.0,
            current_daily_spend_usd=10.0,
            current_monthly_spend_usd=200.0,
        )

        data = budget.to_dict()

        assert data["daily_budget_usd"] == 50.0
        assert data["budget_utilization_percent"] == pytest.approx(13.33, rel=0.01)


class TestCostTracker:
    """Tests for CostTracker."""

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        tracker = CostTracker()

        assert tracker.model_id.startswith("COSTMODEL-")
        assert tracker.model_version == "1.0.0"

    def test_tracker_with_custom_id(self):
        """Test tracker with custom model ID."""
        tracker = CostTracker(model_id="COSTMODEL-CUSTOM001")

        assert tracker.model_id == "COSTMODEL-CUSTOM001"

    def test_track_llm_call(self):
        """Test tracking LLM calls."""
        tracker = CostTracker()

        entry = tracker.track_llm_call(
            input_tokens=1000,
            output_tokens=500,
            model="default",
        )

        assert entry.component == CostComponent.LLM_INFERENCE
        assert entry.amount_usd > 0
        assert entry.context["input_tokens"] == 1000
        assert entry.context["output_tokens"] == 500

    def test_track_llm_call_with_model_rates(self):
        """Test tracking LLM calls with model-specific rates."""
        tracker = CostTracker()

        entry1 = tracker.track_llm_call(
            input_tokens=1000,
            output_tokens=500,
            model="claude-3-opus",
        )

        entry2 = tracker.track_llm_call(
            input_tokens=1000,
            output_tokens=500,
            model="claude-3-haiku",
        )

        # Opus should be more expensive than Haiku
        assert entry1.amount_usd > entry2.amount_usd

    def test_track_tool_call(self):
        """Test tracking tool calls."""
        tracker = CostTracker()

        entry = tracker.track_tool_call(
            tool_name="read_file",
            call_count=5,
        )

        assert entry.component == CostComponent.TOOL_EXECUTION
        assert entry.amount_usd > 0
        assert entry.context["tool_name"] == "read_file"

    def test_track_storage(self):
        """Test tracking storage costs."""
        tracker = CostTracker()

        # Regular storage
        entry1 = tracker.track_storage(
            size_bytes=1024 * 1024 * 1024,  # 1 GB
            duration_hours=720,  # 30 days
        )

        # Egress
        entry2 = tracker.track_storage(
            size_bytes=1024 * 1024 * 1024,  # 1 GB
            is_egress=True,
        )

        assert entry1.component == CostComponent.STORAGE
        assert entry2.component == CostComponent.STORAGE
        assert entry2.amount_usd > entry1.amount_usd  # Egress is more expensive

    def test_track_compute(self):
        """Test tracking compute costs."""
        tracker = CostTracker()

        entry = tracker.track_compute(
            cpu_hours=2.0,
            gpu_hours=1.0,
            memory_gb_hours=8.0,
        )

        assert entry.component == CostComponent.COMPUTE
        assert entry.amount_usd > 0
        assert entry.context["cpu_hours"] == 2.0
        assert entry.context["gpu_hours"] == 1.0

    def test_track_network(self):
        """Test tracking network costs."""
        tracker = CostTracker()

        entry = tracker.track_network(
            transfer_bytes=1024 * 1024 * 100,  # 100 MB
            request_count=1000,
        )

        assert entry.component == CostComponent.NETWORK
        assert entry.amount_usd > 0

    def test_track_observability(self):
        """Test tracking observability overhead."""
        tracker = CostTracker()

        entry = tracker.track_observability(
            span_count=10000,
            metric_count=50000,
            log_bytes=1024 * 1024 * 10,  # 10 MB
        )

        assert entry.component == CostComponent.OBSERVABILITY_OVERHEAD
        assert entry.amount_usd > 0

    def test_get_total_cost(self):
        """Test getting total cost."""
        tracker = CostTracker()

        tracker.track_llm_call(input_tokens=1000, output_tokens=500)
        tracker.track_tool_call(tool_name="test", call_count=10)

        total = tracker.get_total_cost()

        assert total > 0

    def test_get_cost_by_component(self):
        """Test getting costs by component."""
        tracker = CostTracker()

        tracker.track_llm_call(input_tokens=1000, output_tokens=500)
        tracker.track_tool_call(tool_name="test", call_count=10)

        by_component = tracker.get_cost_by_component()

        assert CostComponent.LLM_INFERENCE.value in by_component
        assert CostComponent.TOOL_EXECUTION.value in by_component

    def test_get_cost_allocation(self):
        """Test getting cost allocation."""
        tracker = CostTracker()

        tracker.track_llm_call(input_tokens=10000, output_tokens=5000)
        tracker.track_tool_call(tool_name="test", call_count=10)

        allocations = tracker.get_cost_allocation()

        assert len(allocations) > 0
        total_percentage = sum(a.percentage for a in allocations)
        assert total_percentage == pytest.approx(100.0, abs=0.1)

    def test_get_daily_spend(self):
        """Test getting daily spend."""
        tracker = CostTracker()

        tracker.track_llm_call(input_tokens=1000, output_tokens=500)
        tracker.track_tool_call(tool_name="test", call_count=5)

        daily_spend = tracker.get_daily_spend()

        assert daily_spend > 0

    def test_check_budget_within(self):
        """Test budget check when within budget."""
        budget = CostBudget(
            daily_budget_usd=100.0,
            monthly_budget_usd=3000.0,
        )
        tracker = CostTracker(budget=budget)

        tracker.track_llm_call(input_tokens=1000, output_tokens=500)

        is_within, message = tracker.check_budget()

        assert is_within is True
        assert "Within budget" in message

    def test_check_budget_exceeded(self):
        """Test budget check when exceeded."""
        budget = CostBudget(
            daily_budget_usd=0.0001,  # Very low budget
            monthly_budget_usd=0.0001,
        )
        tracker = CostTracker(budget=budget)

        # Make some expensive calls
        for _ in range(10):
            tracker.track_llm_call(input_tokens=10000, output_tokens=5000)

        is_within, message = tracker.check_budget()

        assert is_within is False
        assert "exceeded" in message.lower()

    def test_get_optimization_recommendations(self):
        """Test getting optimization recommendations."""
        tracker = CostTracker()

        # Generate significant LLM costs
        for _ in range(100):
            tracker.track_llm_call(input_tokens=10000, output_tokens=5000)

        recommendations = tracker.get_optimization_recommendations()

        assert len(recommendations) > 0

    def test_to_dict(self):
        """Test serialization."""
        tracker = CostTracker()

        tracker.track_llm_call(input_tokens=1000, output_tokens=500)

        data = tracker.to_dict()

        assert data["schema_version"] == "obs_cost_model_v1"
        assert data["model_id"].startswith("COSTMODEL-")
        assert "cost_components" in data
        assert "cost_tracking" in data
        assert "cost_allocation" in data

    def test_export_json(self):
        """Test JSON export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = CostTracker()

            tracker.track_llm_call(input_tokens=1000, output_tokens=500)

            path = Path(tmpdir) / "cost_model.json"
            tracker.export_json(path)

            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert data["schema_version"] == "obs_cost_model_v1"

    def test_export_entries(self):
        """Test entries export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = CostTracker()

            tracker.track_llm_call(input_tokens=1000, output_tokens=500)
            tracker.track_tool_call(tool_name="test", call_count=5)
            tracker.track_network(request_count=100)

            path = Path(tmpdir) / "cost_entries.jsonl"
            tracker.export_entries(path)

            assert path.exists()
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 3

    def test_clear(self):
        """Test clearing tracked costs."""
        tracker = CostTracker()

        tracker.track_llm_call(input_tokens=1000, output_tokens=500)
        tracker.track_tool_call(tool_name="test", call_count=5)

        assert tracker.get_total_cost() > 0

        tracker.clear()

        assert tracker.get_total_cost() == 0

    def test_custom_cost_rates(self):
        """Test custom cost rates."""
        custom_rates = {
            "llm_inference": {
                "input_token_cost_usd": 0.001,  # Much higher
                "output_token_cost_usd": 0.003,
            }
        }
        tracker = CostTracker(cost_rates=custom_rates)

        entry = tracker.track_llm_call(input_tokens=1000, output_tokens=500)

        # Cost should be much higher with custom rates
        assert entry.amount_usd > 1.0  # > $1 for 1.5K tokens

    def test_context_in_entries(self):
        """Test context is properly stored in entries."""
        tracker = CostTracker()

        entry = tracker.track_llm_call(
            input_tokens=1000,
            output_tokens=500,
            model="claude-3-opus",
            context={"session_id": "sess-001", "user": "test"},
        )

        assert entry.context["session_id"] == "sess-001"
        assert entry.context["user"] == "test"
        assert entry.context["model"] == "claude-3-opus"
