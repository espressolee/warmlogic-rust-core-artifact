#!/usr/bin/env python3
"""Verify dashboard card perf budgets from collected perf snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERF_JSON = ROOT / "model" / "out" / "perf" / "card_perf.json"
DEFAULT_BUDGET_MS = 500.0


def main() -> int:
    budget_ms = float(os.getenv("DASHBOARD_CARD_P95_BUDGET_MS", str(DEFAULT_BUDGET_MS)))
    if not PERF_JSON.exists():
        raise SystemExit(f"missing perf json: {PERF_JSON}")

    payload = json.loads(PERF_JSON.read_text(encoding="utf-8"))
    cards = payload.get("cards", [])
    if not isinstance(cards, list):
        raise SystemExit("invalid perf json: cards must be a list")

    offenders: list[str] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        p95 = float(card.get("p95_ms", 0.0))
        if p95 > budget_ms:
            offenders.append(f"{card.get('card_id', 'unknown')}: {p95:.3f}ms > {budget_ms:.3f}ms")

    if offenders:
        raise SystemExit(
            "[card-perf] budget exceeded:\n" + "\n".join(offenders[:20])
        )

    print(f"[card-perf] OK: all card p95 <= {budget_ms:.3f}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
