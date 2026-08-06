from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

from scripts import dev_loop_steps_v1 as steps

# Default paths - these can be monkeypatched in tests
STATUS_PATH = Path("warm_logic/meta/WarmLogic_P_Status_v4.json")
SCHEMA_PATH = Path("spec/schema/meta/p_status_v3.schema.json")
RUN_LOG_PATH = Path("warm_logic/model/data/p_series_runs.jsonl")


def run_checks(prefix: Optional[int] = None) -> Tuple[bool, List[str]]:
    """Runs protocol checks for the repository status and logs."""
    errors = []

    # 1. Check P-Status schema compliance
    if STATUS_PATH.exists() and SCHEMA_PATH.exists():
        try:
            import jsonschema

            status_data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
            schema_data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(instance=status_data, schema=schema_data)
        except Exception as exc:
            errors.append(f"P-Status schema validation failed: {exc}")

    # 2. Check run log patch metadata
    if RUN_LOG_PATH.exists():
        try:
            steps.enforce_run_log_patch_metadata(RUN_LOG_PATH)
        except RuntimeError as exc:
            errors.append(f"Run log protocol check failed: {exc}")
        except Exception as exc:
            errors.append(f"Run log read error: {exc}")

    return len(errors) == 0, errors


if __name__ == "__main__":
    import sys

    ok, errs = run_checks()
    if not ok:
        for e in errs:
            print(f"ERROR: {e}")
        sys.exit(1)
    print("Protocol checks passed.")
    sys.exit(0)
