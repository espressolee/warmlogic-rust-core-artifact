#!/usr/bin/env python3
"""Aggregate run plan execution results into a single summary JSON.

Scans out/run_results/*_exec.json files, optionally filters by P-range,
and emits an aggregate summary with per-P stats and overall counts.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


RESULTS_DIR = Path("out/run_results")
OUT_PATH = Path("out/run_results_summary.json")


@dataclass
class ExecEntry:
    p_id: str
    label: str
    overall_rc: int
    steps: int
    failed_steps: int
    duration_sum: float
    manifest: Optional[Path]
    log_path: Optional[Path]
    plan_path: Optional[Path]


def _iter_exec_files(dir_path: Path) -> List[Path]:
    if not dir_path.exists():
        return []
    return sorted([p for p in dir_path.glob("*_exec.json") if p.is_file()])


def _parse_p_from_label(label: str) -> Optional[str]:
    m = re.match(r"^(p\d{3})_", label)
    return m.group(1).upper() if m else None


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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


def collect_exec_entries(dir_path: Path, *, range_token: Optional[str]) -> List[ExecEntry]:
    r_lo, r_hi = _parse_range(range_token)
    entries: List[ExecEntry] = []
    name_re = re.compile(r"^(p|P)(\d{3})_")
    for path in _iter_exec_files(dir_path):
        # Prefilter by filename if possible to reduce IO
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
        pid = _parse_p_from_label(label)
        if not pid:
            # Try to parse from manifest path
            mpath = data.get("manifest")
            if isinstance(mpath, str):
                mm = re.search(r"/(p\d{3})_", mpath)
                if mm:
                    pid = mm.group(1).upper()
        if not pid:
            continue
        if not _in_range(pid, r_lo, r_hi):
            continue
        results = data.get("results") or []
        steps = len(results)
        failed_steps = sum(1 for r in results if int(r.get("returncode") or 0) != 0)
        duration_sum = sum(float(r.get("duration_sec") or 0.0) for r in results)
        overall_rc = int(data.get("overall_returncode") or 0)
        manifest_path = Path(data["manifest"]) if isinstance(data.get("manifest"), str) else None
        log_path = Path(data["log_path"]) if isinstance(data.get("log_path"), str) else None
        plan_path = Path(data["plan_path"]) if isinstance(data.get("plan_path"), str) else None
        entries.append(
            ExecEntry(
                p_id=pid,
                label=label,
                overall_rc=overall_rc,
                steps=steps,
                failed_steps=failed_steps,
                duration_sum=round(duration_sum, 3),
                manifest=manifest_path,
                log_path=log_path,
                plan_path=plan_path,
            )
        )
    return entries


def attach_manifest_scenarios(entries: List[ExecEntry]) -> Dict[str, List[str]]:
    per_p: Dict[str, List[str]] = {}
    for e in entries:
        if not e.manifest:
            continue
        payload = _load_json(e.manifest)
        scenarios = payload.get("ct_safe_scenarios") or []
        if isinstance(scenarios, list):
            current = per_p.setdefault(e.p_id, [])
            for s in scenarios:
                if isinstance(s, str) and s not in current:
                    current.append(s)
    return per_p


def build_summary(entries: List[ExecEntry], *, include_scenarios: bool) -> Dict[str, Any]:
    total_plans = len(entries)
    rc_dist: Dict[str, int] = {}
    total_steps = sum(e.steps for e in entries)
    total_failed_steps = sum(e.failed_steps for e in entries)
    total_duration = round(sum(e.duration_sum for e in entries), 3)
    per_p: Dict[str, Dict[str, Any]] = {}

    for e in entries:
        rc_key = str(e.overall_rc)
        rc_dist[rc_key] = rc_dist.get(rc_key, 0) + 1
        meta = per_p.setdefault(
            e.p_id,
            {"plans": 0, "failures": 0, "steps": 0, "failed_steps": 0, "duration_sum": 0.0, "labels": []},
        )
        meta["plans"] += 1
        meta["failures"] += 1 if e.overall_rc != 0 else 0
        meta["steps"] += e.steps
        meta["failed_steps"] += e.failed_steps
        meta["duration_sum"] = round(float(meta["duration_sum"]) + e.duration_sum, 3)
        meta["labels"].append(e.label)

    summary: Dict[str, Any] = {
        "range": None,
        "totals": {
            "plans": total_plans,
            "steps": total_steps,
            "failed_steps": total_failed_steps,
            "duration_sum": total_duration,
            "rc_dist": rc_dist,
        },
        "per_p": per_p,
    }
    if include_scenarios:
        summary["per_p_scenarios"] = attach_manifest_scenarios(entries)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate plan execution results")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    ap.add_argument("--range", help="Optional P range, e.g., P300-P399")
    ap.add_argument("--out", default=str(OUT_PATH))
    ap.add_argument("--include-scenarios", action="store_true")
    ap.add_argument("--export-csv", help="Optional CSV output path for per-P summary")
    args = ap.parse_args()

    dir_path = Path(args.results_dir)
    entries = collect_exec_entries(dir_path, range_token=args.range)
    summary = build_summary(entries, include_scenarios=args.include_scenarios)
    summary["range"] = args.range or "all"
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"[exec-agg] wrote {out_path} (plans={len(entries)}, range={args.range or 'all'})"
    )
    # Optional CSV export (per-P rows)
    if getattr(args, "export_csv", None):
        try:
            import csv  # noqa: WPS433
        except Exception:
            csv = None  # type: ignore
        if csv:
            csv_path = Path(args.export_csv)
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["p_id", "plans", "success", "fail", "steps", "failed_steps", "duration_sum"])  # header
                for pid, meta in sorted(summary.get("per_p", {}).items()):
                    plans = int(meta.get("plans", 0))
                    fails = int(meta.get("failures", 0))
                    succ = max(0, plans - fails)
                    writer.writerow(
                        [
                            pid,
                            plans,
                            succ,
                            fails,
                            int(meta.get("steps", 0)),
                            int(meta.get("failed_steps", 0)),
                            float(meta.get("duration_sum", 0.0)),
                        ]
                    )
            print(f"[exec-agg] wrote CSV → {csv_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
