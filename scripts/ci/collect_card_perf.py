#!/usr/bin/env python3
"""Collect lightweight dashboard card rendering perf snapshots."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import quantiles
from time import perf_counter


ROOT = Path(__file__).resolve().parents[2]
CARDS_PATH = ROOT / "src" / "warm_logic" / "docs" / "ops" / "dashboard" / "card_contracts_v1.json"
OUT_DIR = ROOT / "model" / "out" / "perf"
OUT_CSV = OUT_DIR / "card_perf.csv"
OUT_JSON = OUT_DIR / "card_perf.json"


def _render_card(card: dict[str, object]) -> dict[str, object]:
    # Simulate deterministic card materialization from contract payload.
    return {
        "id": card.get("id"),
        "title": card.get("title"),
        "category": card.get("category"),
        "tier": card.get("tier"),
        "width": card.get("width"),
    }


def _p95(samples_ms: list[float]) -> float:
    if len(samples_ms) == 1:
        return samples_ms[0]
    return quantiles(samples_ms, n=100, method="inclusive")[94]


def main() -> int:
    if not CARDS_PATH.exists():
        raise SystemExit(f"missing dashboard contract: {CARDS_PATH}")

    payload = json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    cards = payload.get("cards", [])
    if not isinstance(cards, list):
        raise SystemExit("invalid contract: cards must be an array")

    rows: list[dict[str, object]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        samples: list[float] = []
        for _ in range(15):
            start = perf_counter()
            _render_card(card)
            samples.append((perf_counter() - start) * 1000.0)
        samples.sort()
        row = {
            "card_id": card.get("id", "unknown"),
            "p50_ms": round(samples[len(samples) // 2], 6),
            "p95_ms": round(_p95(samples), 6),
            "samples": len(samples),
        }
        rows.append(row)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["card_id", "p50_ms", "p95_ms", "samples"])
        writer.writeheader()
        writer.writerows(rows)

    OUT_JSON.write_text(json.dumps({"cards": rows}, indent=2), encoding="utf-8")
    print(f"[card-perf] wrote {OUT_CSV}")
    print(f"[card-perf] wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
