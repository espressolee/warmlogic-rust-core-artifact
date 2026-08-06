from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter


CARD_CONTRACT = Path("src/warm_logic/docs/ops/dashboard/card_contracts_v1.json")
MAX_RENDER_MS = 500.0


def _render_card(card: dict[str, object]) -> dict[str, object]:
    return {
        "id": card.get("id"),
        "title": card.get("title"),
        "category": card.get("category"),
        "tier": card.get("tier"),
        "width": card.get("width"),
    }


def test_dashboard_render_budget() -> None:
    payload = json.loads(CARD_CONTRACT.read_text(encoding="utf-8"))
    cards = payload.get("cards", [])
    assert isinstance(cards, list)
    assert cards, "card contracts must not be empty"

    start = perf_counter()
    rendered = [_render_card(card) for card in cards if isinstance(card, dict)]
    elapsed_ms = (perf_counter() - start) * 1000.0

    assert rendered
    assert elapsed_ms <= MAX_RENDER_MS, (
        f"dashboard card rendering exceeded budget: {elapsed_ms:.3f}ms > {MAX_RENDER_MS:.3f}ms"
    )
