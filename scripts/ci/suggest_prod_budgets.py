#!/usr/bin/env python3
"""Generate conservative production budget suggestions from perf snapshots."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERF_JSON = ROOT / "model" / "out" / "perf" / "card_perf.json"
OUT_JSON = ROOT / "model" / "out" / "perf" / "budget_suggestions.json"


def main() -> int:
    if not PERF_JSON.exists():
        raise SystemExit(f"missing perf json: {PERF_JSON}")

    payload = json.loads(PERF_JSON.read_text(encoding="utf-8"))
    cards = payload.get("cards", [])
    if not isinstance(cards, list):
        raise SystemExit("invalid perf json: cards must be a list")

    suggestions = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        p95_ms = float(card.get("p95_ms", 0.0))
        suggestions.append(
            {
                "card_id": card.get("card_id", "unknown"),
                "observed_p95_ms": round(p95_ms, 6),
                "suggested_prod_budget_ms": round(p95_ms * 1.2, 6),
            }
        )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"cards": suggestions}, indent=2), encoding="utf-8")
    print(f"[card-perf] wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
