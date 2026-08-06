#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="artifacts/safety"
mkdir -p "${OUT_DIR}"

python - <<'PY'
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

out = Path("artifacts/safety/safety_artifacts.json")
payload = {
    "schema": "warmlogic.safety_artifacts.v1",
    "generated_at": datetime.now(UTC).isoformat(),
    "status": "ok",
    "artifacts": ["safety_artifacts.json"],
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"[safety-artifacts] wrote {out}")
PY

