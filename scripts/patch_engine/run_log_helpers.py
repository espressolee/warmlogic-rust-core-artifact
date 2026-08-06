import json
import os
from pathlib import Path
from typing import Any, Dict


def append_run_log_with_patch_context(
    entry: Dict[str, Any], run_log_path: Path
) -> None:
    """Appends patch-specific context to a run log entry and writes it."""
    from warm_logic.app.devloop import patch_metrics

    # Enrich the entry with patch engine telemetry
    mode = os.environ.get("PATCH_ENGINE_MODE", "unknown")
    wl_llm_mode = os.environ.get("WL_LLM_MODE", "unknown")

    patch_ctx = {
        "mode": mode,
        "wl_llm_mode": patch_metrics.LOG_LLM_MODE.get(wl_llm_mode, wl_llm_mode),
    }

    # Merge into entry
    if "tools" not in entry:
        entry["tools"] = {}
    entry["tools"]["patch_engine"] = patch_ctx

    # Write to log
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with run_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
