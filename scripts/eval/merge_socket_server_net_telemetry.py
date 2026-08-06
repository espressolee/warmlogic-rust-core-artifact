#!/usr/bin/env python3
"""
Merge Paper 09 two-host socket benchmark telemetry (real-network) across APIs.

`eval_paper09_socket_server_net.py client` typically emits one JSON file per API.
Table 14 expects a single combined file:

  {"metadata": {...}, "results": [{"api": "...", ...}, ...]}

This utility merges multiple input JSON files into one combined JSON while being
strict about experimental conditions:
- All runs must share the same config (conns, payload_bytes, warmup, msgs_per_conn, repeats).
- Each (api, rate_hz_per_conn) condition must appear exactly once.

If you want to merge multiple configs (e.g., msgs_per_conn=100 and msgs_per_conn=500),
that is a different experiment and should be represented explicitly in the paper.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

STRICT_CONFIG_KEYS: tuple[str, ...] = (
    "conns",
    "payload_bytes",
    "warmup_msgs_per_conn",
    "msgs_per_conn",
    "repeats",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _floatish(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Paper 09 socket_server_net telemetry across APIs"
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="input files; optionally prefix with api= (e.g., set_vec=out/.../telemetry.json)",
    )
    parser.add_argument("--out", required=True, help="output combined JSON path")
    parser.add_argument("--run-id", default="paper09_socket_server_net_merged")
    args = parser.parse_args()

    input_specs: list[tuple[str | None, Path]] = []
    for item in args.inputs:
        s = str(item)
        if "=" in s:
            raw_api, raw_path = s.split("=", 1)
            input_specs.append((raw_api.strip() or None, Path(raw_path)))
        else:
            input_specs.append((None, Path(s)))

    merged_meta_base: dict[str, Any] | None = None
    config_ref: dict[str, Any] | None = None

    rows_by_key: dict[tuple[str, float], dict[str, Any]] = {}
    inputs_by_key: dict[str, str] = {}
    inputs_by_api_candidates: dict[str, set[str]] = {}
    server_handshake_samples: dict[str, dict[str, Any]] = {}

    for expected_api, path in input_specs:
        if not path.exists():
            print(f"WARNING: skipping missing file: {path}")
            continue

        try:
            data = _load_json(path)
        except Exception as e:
            print(f"WARNING: Failed to load {path}: {e}")
            continue

        md = data.get("metadata") or {}
        if merged_meta_base is None:
            merged_meta_base = dict(md)

        file_results = data.get("results", []) or []
        api_label = expected_api or str(md.get("api") or "").strip() or None
        if api_label:
            inputs_by_api_candidates.setdefault(api_label, set()).add(str(path))

        hs = md.get("server_handshake_sample")
        if hs:
            hs_api = str(hs.get("api") or api_label or "").strip() or None
            if hs_api and hs_api not in server_handshake_samples:
                server_handshake_samples[hs_api] = hs

        for row in file_results:
            api = str(row.get("api") or "").strip()
            if not api:
                continue
            if expected_api and api != expected_api:
                raise SystemExit(
                    f"Input label mismatch: expected api={expected_api} but found api={api} in {path}"
                )

            rate = _floatish(row.get("rate_hz_per_conn"))
            key = (api, rate)
            if key in rows_by_key:
                raise SystemExit(
                    f"Duplicate condition (api={api}, rate_hz_per_conn={rate}) while merging {path}. "
                    "This indicates overlapping inputs (e.g., baseline + sweep) or repeated runs."
                )

            cfg = {k: row.get(k) for k in STRICT_CONFIG_KEYS}
            if config_ref is None:
                config_ref = cfg
            elif cfg != config_ref:
                raise SystemExit(
                    f"Config mismatch for (api={api}, rate={rate}) in {path}: {cfg} != {config_ref}. "
                    "Do not merge runs with different configs into one telemetry file."
                )

            rows_by_key[key] = row
            inputs_by_key[f"{api}@{rate:.0f}"] = str(path)

    if not rows_by_key:
        raise SystemExit("No results found in inputs")

    apis = sorted({api for api, _ in rows_by_key.keys()})
    rates = sorted({rate for _, rate in rows_by_key.keys()})
    is_multirate = len(rates) > 1

    inputs_field: dict[str, Any]
    if not is_multirate:
        # Match the existing single-rate (GCP) merged schema: inputs keyed by API.
        inputs_by_api: dict[str, str] = {}
        for api in apis:
            paths = inputs_by_api_candidates.get(api) or set()
            if len(paths) == 1:
                inputs_by_api[api] = sorted(paths)[0]
        inputs_field = inputs_by_api or inputs_by_key
        mode = "merged"
    else:
        inputs_field = inputs_by_key
        mode = "merged_multirate"

    merged_results = [
        rows_by_key[k] for k in sorted(rows_by_key.keys(), key=lambda x: (x[0], x[1]))
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if merged_meta_base is None:
        merged_meta_base = {}

    payload: dict[str, Any] = {
        "metadata": {
            "run_id": str(args.run_id),
            "timestamp": time.time(),
            "mode": mode,
            "apis": apis,
            "inputs": inputs_field,
            "server_handshake_samples": server_handshake_samples,
            **(config_ref or {}),
            **(
                {"rates_hz_per_conn": rates}
                if is_multirate
                else {"rate_hz_per_conn": rates[0]}
            ),
            **{
                k: merged_meta_base.get(k)
                for k in (
                    "server",
                    "timeout_s",
                    "client_platform",
                    "client_python",
                    "client_uname",
                )
            },
        },
        "results": merged_results,
    }

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
