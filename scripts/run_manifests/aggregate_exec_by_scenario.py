#!/usr/bin/env python3
"""Aggregate execution results grouped by CT-safe scenarios.

Scans out/run_results/*_exec.json, joins with manifest.ct_safe_scenarios,
and computes per-scenario metrics. Supports optional P-range and focus
scenarios for A/B comparison.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RESULTS_DIR = Path("out/run_results")
OUT_PATH = Path("out/run_results_by_scenario.json")


def _iter_exec_files(dir_path: Path) -> List[Path]:
    if not dir_path.exists():
        return []
    return sorted([p for p in dir_path.glob("*_exec.json") if p.is_file()])


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_p_from_label(label: str) -> Optional[str]:
    m = re.match(r"^(p\d{3})_", label)
    return m.group(1).upper() if m else None


def _parse_range(token: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if not token:
        return None, None
    t = token.strip().upper()
    try:
        if "-" in t:
            a, b = t.split("-", 1)
            return int(a.lstrip("P")), int(b.lstrip("P"))
        n = int(t.lstrip("P"))
        return n, n
    except Exception:
        return None, None


def _pnum(pid: str) -> Optional[int]:
    try:
        return int(pid.lstrip("P"))
    except Exception:
        return None


def _in_range(pid: str, r_lo: Optional[int], r_hi: Optional[int]) -> bool:
    if r_lo is None or r_hi is None:
        return True
    n = _pnum(pid)
    return n is not None and r_lo <= n <= r_hi


def _extract_pid_from_manifest_path(mpath: str) -> Optional[str]:
    # Try regex from filename first
    mm = re.search(r"/(P\d{3})_", mpath)
    if mm:
        return mm.group(1).upper()
    # Try reading manifest JSON p_id/p_series_id
    try:
        mdata = _load_json(Path(mpath))
        pid = str(mdata.get("p_id") or mdata.get("p_series_id") or "").upper()
        return pid or None
    except Exception:
        return None


def _extract_pid(data: dict) -> Optional[str]:
    # Preference order: explicit p_id in exec → manifest content/regex → label regex
    pid = None
    raw_pid = data.get("p_id") or data.get("p_series_id")
    if isinstance(raw_pid, str) and raw_pid.strip():
        pid = raw_pid.strip().upper()
    if not pid:
        mpath = data.get("manifest")
        if isinstance(mpath, str):
            pid = _extract_pid_from_manifest_path(mpath)
    if not pid:
        label = str(data.get("label") or "")
        m = re.match(r"^(p\d{3})_", label)
        if m:
            pid = m.group(1).upper()
    return pid


def collect(dir_path: Path, *, range_token: Optional[str]) -> List[dict]:
    r_lo, r_hi = _parse_range(range_token)
    items: List[dict] = []
    name_re = re.compile(r"^(p|P)(\d{3})_")
    for path in _iter_exec_files(dir_path):
        if r_lo is not None and r_hi is not None:
            m = name_re.match(path.name)
            if m:
                try:
                    n = int(m.group(2))
                    if not (r_lo <= n <= r_hi):
                        continue
                except Exception:
                    pass
        data = _load_json(path)
        label = str(data.get("label") or path.stem)
        pid = _extract_pid(data)
        if not pid or not _in_range(pid, r_lo, r_hi):
            continue
        items.append(data)
    return items


def scenarios_from_manifest(path: Path) -> List[str]:
    payload = _load_json(path)
    scen = payload.get("ct_safe_scenarios") or []
    return [s for s in scen if isinstance(s, str)]


def aggregate_by_scenario(entries: List[dict], *, focus: List[str]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for data in entries:
        label = str(data.get("label") or "")
        overall_rc = int(data.get("overall_returncode") or 0)
        steps = data.get("results") or []
        failed_steps = sum(1 for r in steps if int(r.get("returncode") or 0) != 0)
        duration = sum(float(r.get("duration_sec") or 0.0) for r in steps)
        manifest_path = data.get("manifest")
        scenarios: List[str] = []
        pid = None
        if isinstance(manifest_path, str):
            scenarios = scenarios_from_manifest(Path(manifest_path))
            # Extract pid using the same robust helper
            pid = _extract_pid({"manifest": manifest_path, "label": label})
        targets = scenarios
        if focus:
            targets = [s for s in scenarios if s in focus]
        if not targets:
            # Still register under a placeholder when focusing
            if focus:
                continue
            targets = ["<none>"]
        for s in targets:
            entry = summary.setdefault(
                s,
                {
                    "plans": 0,
                    "success": 0,
                    "fail": 0,
                    "steps": 0,
                    "failed_steps": 0,
                    "duration_sum": 0.0,
                    "rc_dist": {},
                    "labels": [],
                    "by_p": {},
                },
            )
            entry["plans"] += 1
            entry["success"] += 1 if overall_rc == 0 else 0
            entry["fail"] += 1 if overall_rc != 0 else 0
            entry["steps"] += len(steps)
            entry["failed_steps"] += failed_steps
            entry["duration_sum"] = round(float(entry["duration_sum"]) + float(duration), 3)
            entry["labels"].append(label)
            # rc distribution
            rc_key = str(overall_rc)
            entry["rc_dist"][rc_key] = int(entry["rc_dist"].get(rc_key, 0)) + 1
            # by-p breakdown
            if pid:
                byp = entry["by_p"].setdefault(pid, {"plans": 0, "success": 0, "fail": 0, "duration_sum": 0.0})
                byp["plans"] += 1
                byp["success"] += 1 if overall_rc == 0 else 0
                byp["fail"] += 1 if overall_rc != 0 else 0
                byp["duration_sum"] = round(float(byp["duration_sum"]) + float(duration), 3)
    return summary


def build_report(entries: List[dict], *, range_token: Optional[str], focus: List[str], include_by_p: bool) -> Dict[str, Any]:
    summary = aggregate_by_scenario(entries, focus=focus)
    # Post-process to add derived metrics
    for scen, meta in summary.items():
        plans = max(1, int(meta.get("plans", 0)))
        meta["success_rate"] = round(float(meta.get("success", 0)) / plans, 3)
        meta["avg_duration"] = round(float(meta.get("duration_sum", 0.0)) / plans, 3)
        if not include_by_p and "by_p" in meta:
            # drop heavy by_p if not requested
            meta.pop("by_p", None)
    report: Dict[str, Any] = {
        "range": range_token or "all",
        "scenarios": summary,
    }
    if len(focus) == 2:
        a, b = focus
        a_meta = summary.get(a, {})
        b_meta = summary.get(b, {})
        report["compare"] = {
            a: a_meta,
            b: b_meta,
            "delta": {
                "success_rate": round(float(a_meta.get("success_rate", 0.0)) - float(b_meta.get("success_rate", 0.0)), 3),
                "avg_duration": round(float(a_meta.get("avg_duration", 0.0)) - float(b_meta.get("avg_duration", 0.0)), 3),
            },
        }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate exec results by scenario")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    ap.add_argument("--range", help="Optional P range, e.g., P300-P399")
    ap.add_argument("--focus-scenario", action="append", help="Scenario ID to focus on (repeatable)")
    ap.add_argument("--out", default=str(OUT_PATH))
    ap.add_argument("--by-p", action="store_true", help="Include per-P breakdown under each scenario")
    args = ap.parse_args()

    dir_path = Path(args.results_dir)
    entries = collect(dir_path, range_token=args.range)
    focus = [s for s in (args.focus_scenario or []) if str(s).strip()]
    report = build_report(entries, range_token=args.range, focus=focus, include_by_p=bool(getattr(args, "by_p", False)))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"[exec-agg-scn] wrote {out_path} (entries={len(entries)}, focus={focus or 'all'})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
