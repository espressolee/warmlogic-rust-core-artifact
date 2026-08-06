# ==========================================================
# Module: local_llm_eval.py
# Project: Warm Logic — Model Layer
# Description: Auto-inserted header (add description).
# Author: espressolee
# ==========================================================

"""Local LLM evaluation harness (manifest generator + metrics)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import statistics
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from jsonschema import Draft202012Validator

try:  # matplotlib is optional; figure generation degrades gracefully
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - optional dependency
    plt = None

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_SET_DIR = REPO_ROOT / "config" / "local_llm_eval" / "task_sets"
TASK_SET_SCHEMA = (
    REPO_ROOT / "spec" / "schema" / "meta" / "local_llm_eval_task_set_v1.schema.json"
)
EXPERIMENT_SCHEMA = (
    REPO_ROOT / "spec" / "schema" / "meta" / "experiment_run_v1.schema.json"
)
DEFAULT_OUT_DIR = REPO_ROOT / "out" / "experiments" / "local_llm_eval"
SUMMARY_DIR = REPO_ROOT / "docs" / "research" / "eval"
# Support env-based override for image/CSV roots
_ENV_IMG_DIR = os.environ.get("SUMMARY_IMG_DIR")
_ENV_CSV_DIR = os.environ.get("CSV_DIR")
SUMMARY_IMG_DIR = (
    Path(_ENV_IMG_DIR).expanduser()
    if _ENV_IMG_DIR
    else (REPO_ROOT / "docs" / "assets" / "images" / "research")
)
SUMMARY_CSV_DIR = Path(_ENV_CSV_DIR).expanduser() if _ENV_CSV_DIR else SUMMARY_DIR
SUMMARY_CSV_PATH = SUMMARY_CSV_DIR / "local_llm_eval_summary.csv"
SUMMARY_FIG_PATH = SUMMARY_IMG_DIR / "fig_local_llm_eval.png"
STATS_OVERVIEW_PATH = SUMMARY_CSV_DIR / "local_llm_eval_stats_overview.csv"
EXPERIMENT_ID = "LOCAL_LLM_EVAL_V1"
ACTIVE_TASK_SETS = {"baseline_v3", "stress_v3"}


def _load_schema(path: Path) -> Draft202012Validator:
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


TASK_SET_VALIDATOR = _load_schema(TASK_SET_SCHEMA)
EXPERIMENT_VALIDATOR = _load_schema(EXPERIMENT_SCHEMA)


@dataclass
class TaskSet:
    task_set_id: str
    description: str
    tasks: List[Dict[str, object]]


def load_task_set(task_set_id: str) -> TaskSet:
    path = TASK_SET_DIR / f"{task_set_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"task set not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    TASK_SET_VALIDATOR.validate(payload)
    return TaskSet(
        task_set_id=payload["task_set_id"],
        description=payload.get("description", ""),
        tasks=list(payload.get("tasks", [])),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gather_env() -> Dict[str, str | None]:
    return {
        "wl_llm_mode": os.environ.get("WL_LLM_MODE"),
        "devloop_profile": os.environ.get("DEVLOOP_PROFILE"),
        "backend_code": os.environ.get("WL_LLM_BACKEND_CODE"),
        "backend_docs": os.environ.get("WL_LLM_BACKEND_DOCS"),
        "backend_design": os.environ.get("WL_LLM_BACKEND_DESIGN"),
    }


def _default_metrics() -> Dict[str, float | int | None | bool]:
    return {
        "tests_pass": None,
        "spec_violations": None,
        "spec_violation_types": [],
        "edit_size": None,
        "patch_tokens": None,
        "patch_files": None,
        "review_time_minutes": None,
        "test_runtime_seconds": None,
        "governance_veto_count": None,
        "governance_veto_latency_sec": None,
        "rollback_triggered": False,
    }


def run_test_commands(
    commands: Iterable[str],
    log_path: Path,
    header_meta: Optional[Dict[str, object]] = None,
) -> Tuple[bool, float]:
    """Execute test commands, capture output, and return (success, runtime)."""

    success = True
    total_runtime = 0.0
    logs: List[str] = []
    cmds_list: List[str] = []
    for command in commands:
        if not command:
            continue
        cmds_list.append(str(command))
        start = time.perf_counter()
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        duration = time.perf_counter() - start
        total_runtime += duration
        logs.append(
            f"$ {command}\n# exit={result.returncode} runtime={duration:.2f}s\n"
            f"{result.stdout}{result.stderr}\n"
        )
        if result.returncode != 0:
            success = False
    if logs:
        # Header with timestamp + command hash + summary (+ optional eval meta)
        ts = _now().isoformat().replace("+00:00", "Z")
        cmd_hash = hashlib.sha256("||".join(cmds_list).encode("utf-8")).hexdigest()[:12]
        rc = 0 if success else 1
        extra = []
        if header_meta and isinstance(header_meta, dict):
            mode = header_meta.get("mode")
            task_set = header_meta.get("task_set")
            cmds = header_meta.get("cmds")
            if mode:
                extra.append(f"mode={mode}")
            if task_set:
                extra.append(f"task_set={task_set}")
            if cmds is not None:
                try:
                    extra.append(f"cmds={int(cmds)}")
                except Exception:
                    extra.append(f"cmds={cmds}")
        suffix = (" " + " ".join(extra)) if extra else ""
        header = f"[local-llm-eval] ts={ts} cmd_hash={cmd_hash} rc={rc} runtime_total={total_runtime:.2f}s{suffix}"
        log_path.write_text("\n".join([header, *logs]), encoding="utf-8")
    return success, total_runtime


def run_protocol_check() -> Tuple[int, List[str]]:
    """Run protocol-check and return (violation count, labels)."""

    proc = subprocess.run(
        ["python", "-m", "scripts.dev_loop_v1", "protocol-check"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return 0, []
    lines = proc.stdout.splitlines()
    violations = []
    for line in lines:
        stripped = line.strip()
        if not stripped or not stripped.startswith("-"):
            continue
        label = stripped[1:].strip()
        colon_idx = label.find(":")
        if colon_idx > 0:
            label = label[:colon_idx].strip()
        violations.append(label or "protocol_check_failed")
    if not violations:
        violations = ["protocol_check_failed"]
    return len(violations), violations


def load_metrics_overrides(task_dir: Path) -> Dict[str, Optional[float]]:
    overrides_path = task_dir / "metrics_overrides.json"
    if not overrides_path.exists():
        return {}
    try:
        payload = json.loads(overrides_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "edit_size": payload.get("edit_size"),
        "review_time_minutes": payload.get("review_time_minutes"),
        "patch_tokens": payload.get("patch_tokens"),
        "patch_files": payload.get("patch_files"),
        "governance_veto_count": payload.get("governance_veto_count"),
        "governance_veto_latency_sec": payload.get("governance_veto_latency_sec"),
        "rollback_triggered": payload.get("rollback_triggered"),
        "spec_violation_types": payload.get("spec_violation_types"),
    }


def compute_patch_stats(
    diff_path: Path,
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    if not diff_path.exists():
        return None, None, None
    added = 0
    removed = 0
    tokens = 0
    files: set[str] = set()
    try:
        for line in diff_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("+++ b/"):
                files.add(line[6:].strip())
                continue
            if line.startswith("--- a/"):
                files.add(line[6:].strip())
                continue
            if (
                line.startswith("+++")
                or line.startswith("---")
                or line.startswith("@@")
            ):
                continue
            if line.startswith("+"):
                added += 1
                tokens += len(line[1:].split())
            elif line.startswith("-"):
                removed += 1
                tokens += len(line[1:].split())
    except Exception:
        return None, None, None
    edit_size = added + removed
    patch_files = len(files) if files else None
    return edit_size, tokens or None, patch_files


def build_manifest(
    task: Dict[str, object],
    *,
    task_set_id: str,
    mode: str,
    env_meta: Dict[str, str | None],
    governance_mode_override: Optional[str] = None,
) -> Dict[str, object]:
    timestamp = _now().isoformat().replace("+00:00", "Z")
    task_id = str(task["task_id"])
    run_label = (
        f"{task_set_id}-{mode}-{task_id}-{timestamp.replace(':', '').replace('-', '')}"
    )
    manifest: Dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "run_label": run_label,
        "timestamp": timestamp,
        "commands": task.get("commands", []),
        "artifacts": {
            "task_set": task_set_id,
            "task_id": task_id,
            "summary": str(task.get("summary", "")),
            "patch_diff": f"out/experiments/local_llm_eval/{mode}/{task_id}/patch.diff",
        },
        "invariants": task.get("invariants", []),
        "notes": task.get("summary", ""),
        "mode": mode,
        "wl_llm_mode": env_meta.get("wl_llm_mode"),
        "devloop_profile": env_meta.get("devloop_profile"),
        "backend_code": env_meta.get("backend_code"),
        "backend_docs": env_meta.get("backend_docs"),
        "backend_design": env_meta.get("backend_design"),
        "task_id": task_id,
        "task_category": task.get("category"),
        "metrics": _default_metrics(),
        "p_id": task.get("p_id"),
        "sensitivity": {
            "privacy": "internal",
            "ip": "standard",
        },
    }
    return manifest


def write_manifest(manifest: Dict[str, object], *, out_dir: Path) -> Path:
    EXPERIMENT_VALIDATOR.validate(manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest_path


def copy_task_inputs(task: Dict[str, object], target_dir: Path) -> None:
    inputs = task.get("inputs")
    if not inputs:
        return
    inputs_dir = target_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    for relative in inputs:
        src = REPO_ROOT / str(relative)
        dest = inputs_dir / Path(relative).name
        if not src.exists():
            continue
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)


def _build_seed(*parts: str) -> int:
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _parse_latency_config(value: object) -> Tuple[float, float]:
    if isinstance(value, (int, float)):
        latency = float(value)
        return latency, latency
    if isinstance(value, list) and len(value) == 2:
        lo = max(0.0, float(value[0]))
        hi = max(lo, float(value[1]))
        return lo, hi
    return 0.0, 0.0


def parse_governance_log(path: Path) -> Optional[Tuple[int, float, bool]]:
    if not path.exists():
        return None
    try:
        events = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    veto_latencies: List[float] = []
    rollback = False
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        evt = event.get("event")
        if evt == "veto":
            latency = float(event.get("latency_sec") or 0.0)
            veto_latencies.append(latency)
        if evt == "rollback":
            rollback = True
    if not veto_latencies and not rollback:
        return None
    count = len(veto_latencies)
    avg_latency = sum(veto_latencies) / count if count else 0.0
    return count, avg_latency, rollback


def simulate_governance_metrics(
    task_id: str,
    mode: str,
    config: Dict[str, object],
) -> Tuple[int, float, bool]:
    seed = int(config.get("seed") or _build_seed(task_id, mode, "gov"))
    rng = random.Random(seed)
    fp_rate = float(config.get("false_positive_rate") or 0.0)
    fn_rate = float(config.get("false_negative_rate") or 0.0)
    max_vetoes = int(config.get("max_vetoes") or 3)
    trial_count = max(1, max_vetoes)
    veto_count = 0
    for _ in range(trial_count):
        if rng.random() < fp_rate:
            veto_count += 1
    # simulate missed vetoes to avoid over-reporting when false negatives dominate
    missed = 0
    for _ in range(trial_count):
        if rng.random() < fn_rate:
            missed += 1
    veto_count = max(0, min(veto_count - missed, max_vetoes))
    lo, hi = _parse_latency_config(config.get("latency_seconds"))
    latency = rng.uniform(lo, hi) if hi > lo else lo
    rollback = bool(config.get("mode") == "offload" and veto_count > 0)
    return veto_count, latency, rollback


def derive_governance_metrics(
    task_dir: Path,
    task_meta: Dict[str, object],
    override_mode: Optional[str],
) -> Tuple[int, float, bool]:
    log_metrics = parse_governance_log(task_dir / "governance_log.json")
    if log_metrics:
        return log_metrics
    governance_cfg = dict(task_meta.get("governance") or {})
    if override_mode:
        governance_cfg["mode"] = override_mode
    mode = str(governance_cfg.get("mode") or "strict")
    if not governance_cfg:
        return 0, 0.0, False
    return simulate_governance_metrics(
        str(task_meta.get("task_id")), mode, governance_cfg
    )


def run_task_set(
    *,
    mode: str,
    task_set_id: str,
    out_root: Path,
    dry_run: bool = False,
    governance_mode: Optional[str] = None,
) -> List[Path]:
    task_set = load_task_set(task_set_id)
    env_meta = _gather_env()
    manifests: List[Path] = []
    for task in task_set.tasks:
        manifest = build_manifest(
            task,
            task_set_id=task_set.task_set_id,
            mode=mode,
            env_meta=env_meta,
            governance_mode_override=governance_mode,
        )
        target_dir = out_root / mode / str(task["task_id"])
        if dry_run:
            EXPERIMENT_VALIDATOR.validate(manifest)
            continue
        path = write_manifest(manifest, out_dir=target_dir)
        copy_task_inputs(task, target_dir)
        manifests.append(path)
    return manifests


def list_tasks(task_set_id: str) -> None:
    task_set = load_task_set(task_set_id)
    print(f"Task set: {task_set.task_set_id}\nDescription: {task_set.description}\n")
    for task in task_set.tasks:
        print(
            f"- {task['task_id']} (P={task['p_id']}, category={task['category']}): {task['summary']}"
        )


def measure_task_set(
    *,
    mode: str,
    task_set_id: str,
    out_root: Path,
    summary_csv: Path,
    summary_fig: Path,
    governance_mode: Optional[str] = None,
) -> None:
    task_set = load_task_set(task_set_id)
    task_map = {str(task["task_id"]): task for task in task_set.tasks}
    updated = 0
    for task in task_set.tasks:
        task_id = str(task["task_id"])
        task_dir = out_root / mode / task_id
        manifest_path = task_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        metrics = manifest.get("metrics") or _default_metrics()
        tests_cmds = task.get("tests", []) if task else []
        tests_pass, runtime = run_test_commands(
            tests_cmds,
            task_dir / "command_output.log",
            header_meta={
                "mode": mode,
                "task_set": task_set_id,
                "cmds": len(tests_cmds) if isinstance(tests_cmds, list) else 0,
            },
        )
        metrics["tests_pass"] = tests_pass
        metrics["test_runtime_seconds"] = runtime
        violation_count, violation_types = run_protocol_check()
        metrics["spec_violations"] = violation_count
        metrics["spec_violation_types"] = violation_types
        overrides = load_metrics_overrides(task_dir)
        edit_size, patch_tokens, patch_files = compute_patch_stats(
            task_dir / "patch.diff"
        )
        if overrides.get("edit_size") is not None:
            metrics["edit_size"] = overrides["edit_size"]
        elif edit_size is not None:
            metrics["edit_size"] = edit_size
        if overrides.get("patch_tokens") is not None:
            metrics["patch_tokens"] = overrides["patch_tokens"]
        elif patch_tokens is not None:
            metrics["patch_tokens"] = patch_tokens
        if overrides.get("patch_files") is not None:
            metrics["patch_files"] = overrides["patch_files"]
        elif patch_files is not None:
            metrics["patch_files"] = patch_files
        if overrides.get("review_time_minutes") is not None:
            metrics["review_time_minutes"] = overrides["review_time_minutes"]
        task_meta = task_map.get(task_id, {}).copy() if task_id in task_map else {}
        gov_count, gov_latency, rollback = derive_governance_metrics(
            task_dir, task_meta, governance_mode
        )
        if overrides.get("governance_veto_count") is not None:
            metrics["governance_veto_count"] = overrides["governance_veto_count"]
        else:
            metrics["governance_veto_count"] = gov_count
        if overrides.get("governance_veto_latency_sec") is not None:
            metrics["governance_veto_latency_sec"] = overrides[
                "governance_veto_latency_sec"
            ]
        else:
            metrics["governance_veto_latency_sec"] = gov_latency
        if overrides.get("rollback_triggered") is not None:
            metrics["rollback_triggered"] = overrides["rollback_triggered"]
        else:
            metrics["rollback_triggered"] = rollback
        if overrides.get("spec_violation_types") is not None:
            metrics["spec_violation_types"] = overrides["spec_violation_types"]
        manifest["metrics"] = metrics
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        updated += 1

    include_sets = ACTIVE_TASK_SETS | {task_set_id}
    results = collect_results(out_root, include_sets)
    if results:
        write_summary_csv(results, summary_csv)
        try:
            generate_summary_figure(results, summary_fig)
        except Exception as exc:  # pragma: no cover - graceful degrade on fig errors
            print(
                f"[local-llm-eval] WARN: summary figure generation skipped: {type(exc).__name__}: {exc}"
            )
        stats_dir = summary_csv.parent
        overview_path = stats_dir / "local_llm_eval_stats_overview.csv"
        write_mode_stats(results, stats_dir, overview_path)
    print(
        f"[local-llm-eval] Measured {updated} tasks for mode {mode} (summary -> {summary_csv})"
    )


def collect_results(
    out_root: Path,
    include_task_sets: Optional[set[str]] = None,
) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    if not out_root.exists():
        return entries
    for mode_dir in sorted(out_root.iterdir()):
        if not mode_dir.is_dir():
            continue
        mode = mode_dir.name
        for manifest_path in mode_dir.glob("*/manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifacts = manifest.get("artifacts") or {}
            task_set = (
                artifacts.get("task_set") if isinstance(artifacts, dict) else None
            )
            if include_task_sets and task_set not in include_task_sets:
                continue
            metrics = manifest.get("metrics", {})
            entries.append(
                {
                    "mode": manifest.get("mode", mode),
                    "task_id": manifest.get("task_id"),
                    "p_id": manifest.get("p_id"),
                    "tests_pass": metrics.get("tests_pass"),
                    "spec_violations": metrics.get("spec_violations"),
                    "spec_violation_types": metrics.get("spec_violation_types"),
                    "edit_size": metrics.get("edit_size"),
                    "patch_tokens": metrics.get("patch_tokens"),
                    "patch_files": metrics.get("patch_files"),
                    "review_time_minutes": metrics.get("review_time_minutes"),
                    "test_runtime_seconds": metrics.get("test_runtime_seconds"),
                    "governance_veto_count": metrics.get("governance_veto_count"),
                    "governance_veto_latency_sec": metrics.get(
                        "governance_veto_latency_sec"
                    ),
                    "rollback_triggered": metrics.get("rollback_triggered"),
                }
            )
    return entries


def write_summary_csv(results: List[Dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "mode",
        "task_id",
        "p_id",
        "tests_pass",
        "spec_violations",
        "spec_violation_types",
        "edit_size",
        "patch_tokens",
        "patch_files",
        "review_time_minutes",
        "test_runtime_seconds",
        "governance_veto_count",
        "governance_veto_latency_sec",
        "rollback_triggered",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)


def generate_summary_figure(results: List[Dict[str, object]], path: Path) -> None:
    if not results:
        return
    if not plt:  # pragma: no cover - optional figure generation
        print("[local-llm-eval] matplotlib not available; skipping figure (CSV only)")
        return
    by_mode: Dict[str, List[Dict[str, object]]] = {}
    for row in results:
        by_mode.setdefault(str(row.get("mode")), []).append(row)
    modes = sorted(by_mode.keys())
    success_rates: List[float] = []
    spec_fail_rates: List[float] = []
    test_fail_rates: List[float] = []
    for mode in modes:
        rows = by_mode[mode]
        total = len(rows)
        successes = [
            r
            for r in rows
            if r.get("tests_pass") and (r.get("spec_violations") or 0) == 0
        ]
        spec_fail = [r for r in rows if (r.get("spec_violations") or 0) > 0]
        test_fail = [r for r in rows if not r.get("tests_pass")]
        success_rate = (len(successes) / total) * 100.0 if total else 0.0
        spec_fail_rate = (len(spec_fail) / total) * 100.0 if total else 0.0
        test_fail_rate = (len(test_fail) / total) * 100.0 if total else 0.0
        success_rates.append(success_rate)
        spec_fail_rates.append(spec_fail_rate)
        test_fail_rates.append(test_fail_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(6, 4))
    plt.bar(modes, success_rates, color="#16a34a", label="Success")
    plt.bar(
        modes,
        spec_fail_rates,
        bottom=success_rates,
        color="#f97316",
        label="Spec violation",
    )
    plt.bar(
        modes,
        test_fail_rates,
        bottom=[s + v for s, v in zip(success_rates, spec_fail_rates, strict=False)],
        color="#dc2626",
        label="Tests failed",
    )
    plt.ylabel("Outcome (%)")
    plt.xlabel("Mode")
    plt.ylim(0, 100)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _mean_std(values: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.pstdev(values)


def write_mode_stats(
    results: List[Dict[str, object]],
    stats_dir: Path,
    overview_path: Path,
) -> None:
    by_mode: Dict[str, List[Dict[str, object]]] = {}
    for row in results:
        by_mode.setdefault(str(row.get("mode")), []).append(row)
    overview_rows: List[Dict[str, object]] = []
    for mode, rows in by_mode.items():
        total = len(rows)
        success = len(
            [
                r
                for r in rows
                if r.get("tests_pass") and (r.get("spec_violations") or 0) == 0
            ]
        )
        failure = total - success
        edit_vals = [
            float(r.get("edit_size")) for r in rows if r.get("edit_size") is not None
        ]
        token_vals = [
            float(r.get("patch_tokens"))
            for r in rows
            if r.get("patch_tokens") is not None
        ]
        veto_vals = [
            float(r.get("governance_veto_count"))
            for r in rows
            if r.get("governance_veto_count") is not None
        ]
        runtime_vals = [
            float(r.get("test_runtime_seconds"))
            for r in rows
            if r.get("test_runtime_seconds") is not None
        ]
        rollback_count = len([r for r in rows if r.get("rollback_triggered")])
        overview_rows.append(
            {
                "mode": mode,
                "tasks": total,
                "success": success,
                "failure": failure,
                "success_rate_pct": (
                    round((success / total) * 100.0, 2) if total else 0.0
                ),
                "avg_edit_size": (
                    round(statistics.mean(edit_vals), 2) if edit_vals else ""
                ),
                "avg_patch_tokens": (
                    round(statistics.mean(token_vals), 2) if token_vals else ""
                ),
                "avg_governance_veto_count": (
                    round(statistics.mean(veto_vals), 2) if veto_vals else ""
                ),
                "rollback_rate_pct": (
                    round((rollback_count / total) * 100.0, 2) if total else 0.0
                ),
                "avg_test_runtime_seconds": (
                    round(statistics.mean(runtime_vals), 2) if runtime_vals else ""
                ),
            }
        )
        stats_path = stats_dir / f"local_llm_eval_stats_{mode}.csv"
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        metrics = {
            "success_rate_pct": [100.0 * success / total] if total else [],
            "spec_violations": [float(r.get("spec_violations") or 0) for r in rows],
            "edit_size": [
                float(r.get("edit_size"))
                for r in rows
                if r.get("edit_size") is not None
            ],
            "patch_tokens": [
                float(r.get("patch_tokens"))
                for r in rows
                if r.get("patch_tokens") is not None
            ],
            "patch_files": [
                float(r.get("patch_files"))
                for r in rows
                if r.get("patch_files") is not None
            ],
            "review_time_minutes": [
                float(r.get("review_time_minutes"))
                for r in rows
                if r.get("review_time_minutes") is not None
            ],
            "test_runtime_seconds": [
                float(r.get("test_runtime_seconds"))
                for r in rows
                if r.get("test_runtime_seconds") is not None
            ],
            "governance_veto_count": [
                float(r.get("governance_veto_count"))
                for r in rows
                if r.get("governance_veto_count") is not None
            ],
            "governance_veto_latency_sec": [
                float(r.get("governance_veto_latency_sec"))
                for r in rows
                if r.get("governance_veto_latency_sec") is not None
            ],
        }
        with stats_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["metric", "mean", "std", "count"]
            )
            writer.writeheader()
            for metric, values in metrics.items():
                mean, std = _mean_std(values)
                writer.writerow(
                    {
                        "metric": metric,
                        "mean": "" if mean is None else round(mean, 4),
                        "std": "" if std is None else round(std, 4),
                        "count": len(values),
                    }
                )
    if overview_rows:
        overview_path.parent.mkdir(parents=True, exist_ok=True)
        with overview_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "mode",
                    "tasks",
                    "success",
                    "failure",
                    "success_rate_pct",
                    "avg_edit_size",
                    "avg_patch_tokens",
                    "avg_governance_veto_count",
                    "rollback_rate_pct",
                    "avg_test_runtime_seconds",
                ],
            )
            writer.writeheader()
            for row in sorted(overview_rows, key=lambda item: item["mode"]):
                writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warm Logic Local LLM Eval harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Generate manifests for a task set")
    run_parser.add_argument(
        "--mode",
        required=True,
        choices=["C0", "C1", "C2", "C3"],
        help="Evaluation condition",
    )
    run_parser.add_argument(
        "--task-set", required=True, help="Task set identifier (e.g., baseline_v1)"
    )
    run_parser.add_argument(
        "--out-dir", default=str(DEFAULT_OUT_DIR), help="Output root directory"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Validate without writing manifests"
    )
    run_parser.add_argument(
        "--governance-mode",
        choices=["strict", "lagged", "offload"],
        help="Override governance mode",
    )

    list_parser = subparsers.add_parser("list", help="Show available tasks in a set")
    list_parser.add_argument("--task-set", required=True, help="Task set identifier")

    measure_parser = subparsers.add_parser(
        "measure", help="Execute tests and update metrics"
    )
    measure_parser.add_argument(
        "--mode",
        required=True,
        choices=["C0", "C1", "C2", "C3"],
        help="Evaluation condition",
    )
    measure_parser.add_argument("--task-set", required=True, help="Task set identifier")
    measure_parser.add_argument(
        "--out-dir", default=str(DEFAULT_OUT_DIR), help="Output root directory"
    )
    measure_parser.add_argument(
        "--summary-csv",
        default=str(SUMMARY_CSV_PATH),
        help="Summary CSV path (overrides CSV_DIR when absolute)",
    )
    measure_parser.add_argument(
        "--summary-fig",
        default=str(SUMMARY_FIG_PATH),
        help="Summary figure path (overrides SUMMARY_IMG_DIR when absolute)",
    )
    measure_parser.add_argument(
        "--csv-dir", help="Directory to write CSV summaries (overrides CSV_DIR)"
    )
    measure_parser.add_argument(
        "--summary-img-dir",
        help="Directory to write summary figure (overrides SUMMARY_IMG_DIR)",
    )
    measure_parser.add_argument(
        "--governance-mode",
        choices=["strict", "lagged", "offload"],
        help="Override governance mode for metrics",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "list":
        list_tasks(args.task_set)
        return 0
    if args.command == "run":
        out_root = Path(args.out_dir)
        paths = run_task_set(
            mode=args.mode,
            task_set_id=args.task_set,
            out_root=out_root,
            dry_run=args.dry_run,
            governance_mode=getattr(args, "governance_mode", None),
        )
        if args.dry_run:
            print(
                f"Validated {len(load_task_set(args.task_set).tasks)} tasks (dry-run)"
            )
        else:
            for path in paths:
                print(f"Wrote {path}")
        return 0
    if args.command == "measure":
        # Resolve output dirs from CLI/env overrides
        csv_dir = (
            Path(args.csv_dir).expanduser()
            if getattr(args, "csv_dir", None)
            else (
                Path(os.environ.get("CSV_DIR")).expanduser()
                if os.environ.get("CSV_DIR")
                else None
            )
        )
        fig_dir = (
            Path(args.summary_img_dir).expanduser()
            if getattr(args, "summary_img_dir", None)
            else (
                Path(os.environ.get("SUMMARY_IMG_DIR")).expanduser()
                if os.environ.get("SUMMARY_IMG_DIR")
                else None
            )
        )
        summary_csv = Path(args.summary_csv)
        summary_fig = Path(args.summary_fig)
        if csv_dir and not summary_csv.is_absolute():
            summary_csv = csv_dir / summary_csv.name
        if fig_dir and not summary_fig.is_absolute():
            summary_fig = fig_dir / summary_fig.name
        measure_task_set(
            mode=args.mode,
            task_set_id=args.task_set,
            out_root=Path(args.out_dir),
            summary_csv=summary_csv,
            summary_fig=summary_fig,
            governance_mode=getattr(args, "governance_mode", None),
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
