# ==========================================================
# Module: write_cluster_state.py
# Project: Warm Logic — Model Layer
# Description: Auto-inserted header (add description).
# Author: espressolee
# ==========================================================

#!/usr/bin/env python3
"""Aggregate per-node os_state JSONs into a cluster_state (P227 skeleton)."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _discover_nodes(nodes_dir: Path) -> List[Path]:
    return sorted([p for p in nodes_dir.glob("*.json") if p.is_file()])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write cluster_state from node os_state JSONs")
    parser.add_argument("--nodes-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cluster-id", type=str, default="demo-cluster")
    args = parser.parse_args(argv)

    nodes = []
    now = time.time()
    for node_file in _discover_nodes(args.nodes_dir):
        data = _load_json(node_file)
        nodes.append(
            {
                "node_id": node_file.stem,
                "role": data.get("role", "worker"),
                "status": data.get("status", "unknown"),
                "timestamp": data.get("timestamp") or now,
                "os_state": data.get("os_state", {}),
            }
        )

    payload: Dict[str, Any] = {
        "cluster_id": args.cluster_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "nodes": nodes,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[cluster-state] wrote {args.out} nodes={len(nodes)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
