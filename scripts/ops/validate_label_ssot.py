#!/usr/bin/env python3
"""Validate a coding label SSOT CSV with lightweight structural checks."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def _err(message: str) -> int:
    print(f"ERROR: {message}")
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_label_ssot.py <coding_labels_wide.csv>")
        return 2

    csv_path = Path(sys.argv[1])
    if not csv_path.is_file():
        return _err(f"CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return _err("CSV header is missing")
        headers = [h.strip() for h in reader.fieldnames if h and h.strip()]
        if len(headers) < 3:
            return _err(f"Expected >=3 columns, found {len(headers)}")
        rows = list(reader)

    if not rows:
        return _err("CSV has no data rows")

    first_col = headers[0]
    seen = set()
    for idx, row in enumerate(rows, start=2):
        key = (row.get(first_col) or "").strip()
        if not key:
            return _err(f"Row {idx} has empty primary key column '{first_col}'")
        if key in seen:
            return _err(f"Duplicate primary key '{key}' in column '{first_col}'")
        seen.add(key)

    print(
        f"label SSOT valid: rows={len(rows)}, columns={len(headers)}, path={csv_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
