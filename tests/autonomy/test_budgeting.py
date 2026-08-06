import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from warm_logic.kernel.autonomy.budget import PatchBudgeter


def _fresh_store():
    """Create a fresh mock store for testing."""
    store = MagicMock()
    store.get_meta = MagicMock(return_value=None)  # Simulate fresh start
    store.set_meta = MagicMock()
    return store


def test_budget_calculation():
    budgeter = PatchBudgeter(store=_fresh_store())
    patch = "def foo(): pass"
    # base 10 + 1 * 1.5 = 11.5
    cost = budgeter.calculate_cost(patch, "stub")
    assert cost == 11.5

    # base 50 + 1 * 1.5 = 51.5
    cost_semantic = budgeter.calculate_cost(patch, "semantic")
    assert cost_semantic == 51.5


def test_budget_exhaustion():
    # Low budget with fresh store
    budgeter = PatchBudgeter(daily_limit=20.0, store=_fresh_store())

    # 11.5 is ok
    cost = budgeter.calculate_cost("def foo(): pass", "stub")
    assert budgeter.pre_approve(cost) is True
    budgeter.finalize_expenditure(cost)
    assert budgeter.remaining_energy == 8.5

    # Another 11.5 is NOT ok
    assert budgeter.pre_approve(cost) is False


def test_budget_replenish():
    budgeter = PatchBudgeter(daily_limit=100.0, store=_fresh_store())
    budgeter.finalize_expenditure(50.0)
    assert budgeter.remaining_energy == 50.0

    budgeter.replenish()
    assert budgeter.remaining_energy == 100.0
