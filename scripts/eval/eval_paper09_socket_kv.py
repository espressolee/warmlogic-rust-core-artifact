#!/usr/bin/env python3
"""
Paper 09 I/O-adjacent micro-workload: socket receive → store in SovereignKV.

Motivation:
- Strengthen external validity beyond pure in-process microbenchmarks.
- Show that the PyO3 `Vec<u8>` extraction semantic mismatch can dominate an operation even when
  the bytes originate from an OS I/O path.

Workload:
  Producer thread: send N payloads over a unix-domain socket (SOCK_STREAM).
  Consumer thread: recv_into a preallocated bytearray until a full payload is read, then
                   store the bytes in a Rust DashMap-backed store (SovereignKV).

We compare three consumer variants:
  - recv_only: receive and discard (I/O baseline)
  - set_bytesvec: SovereignKV.set_bytesvec(key, value)  # BytesVec extractor (contiguous copy)
  - set_vec:      SovereignKV.set_vec(key, value)       # Vec<u8> arg conversion (stock vs patched differs)

This script is intended to be run twice (stock + patched wheels) and summarized in the paper.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import socket
import statistics
import sys
import threading
import time
from typing import Any, Callable


# Import strategy (match eval_bridge_v3.py):
use_installed = os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1"
ext_path = os.environ.get("WARM_LOGIC_RS_PYTHON_PATH")
repo_root = os.getcwd()
if not use_installed:
    ext_path = ext_path or os.path.join(repo_root, "warm_logic_rs", "python_packages_v2")
    sys.path.insert(0, ext_path)
    sys.path.insert(1, repo_root)
else:
    sys.path.append(repo_root)

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError as e:
    print(f"ERROR: Cannot import warm_logic_rs: {e}")
    sys.exit(1)


def _median_iqr(values: list[float]) -> dict[str, float]:
    xs = sorted(values)
    if not xs:
        return {"median": float("nan"), "iqr": float("nan")}
    q1 = xs[int(len(xs) * 0.25)]
    q3 = xs[int(len(xs) * 0.75)]
    return {"median": statistics.median(xs), "iqr": q3 - q1}


def _p99(values: list[float]) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    idx = int(0.99 * (len(xs) - 1))
    return xs[idx]


def _recv_exact_into(sock: socket.socket, buf: bytearray) -> None:
    view = memoryview(buf)
    want = len(buf)
    got = 0
    while got < want:
        n = sock.recv_into(view[got:])
        if n == 0:
            raise RuntimeError("socket closed early")
        got += n


def _run_one_repeat(
    *,
    api: str,
    payload_size: int,
    warmup_messages: int,
    messages: int,
    key_count: int,
) -> dict[str, float]:
    r_sock, w_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    payload = bytes([0xAB]) * payload_size
    recv_buf = bytearray(payload_size)

    # Small stable key set to avoid unbounded map growth.
    keys = [f"k{i}" for i in range(key_count)]

    kv = warm_logic_rs.SovereignKV()
    for k in keys:
        kv.set_bytes(k, b"x")

    def writer() -> None:
        try:
            for _ in range(warmup_messages + messages):
                w_sock.sendall(payload)
            try:
                w_sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
        finally:
            w_sock.close()

    th = threading.Thread(target=writer, daemon=True)
    th.start()

    # Dispatch for store call.
    set_fn: Callable[[str, Any], Any] | None
    if api == "recv_only":
        set_fn = None
    elif api == "set_bytesvec":
        set_fn = kv.set_bytesvec
    elif api == "set_vec":
        set_fn = kv.set_vec
    else:
        raise ValueError(f"unknown api: {api}")

    recv_lat: list[float] = []
    set_lat: list[float] = []
    e2e_lat: list[float] = []

    try:
        for i in range(warmup_messages + messages):
            t0 = time.perf_counter_ns()
            _recv_exact_into(r_sock, recv_buf)
            t1 = time.perf_counter_ns()

            if set_fn is not None:
                set_fn(keys[i % key_count], recv_buf)
            t2 = time.perf_counter_ns()

            if i >= warmup_messages:
                recv_lat.append(float(t1 - t0))
                set_lat.append(float(t2 - t1))
                e2e_lat.append(float(t2 - t0))

        th.join(timeout=5.0)
    finally:
        r_sock.close()
        try:
            w_sock.close()
        except OSError:
            pass

    return {
        "recv_p50_ns": statistics.median(recv_lat),
        "recv_p99_ns": _p99(recv_lat),
        "set_p50_ns": statistics.median(set_lat),
        "set_p99_ns": _p99(set_lat),
        "e2e_p50_ns": statistics.median(e2e_lat),
        "e2e_p99_ns": _p99(e2e_lat),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper 09: socket ingest → SovereignKV workload")
    parser.add_argument("--run-id", default="paper09_socket_kv")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup-messages", type=int, default=50)
    parser.add_argument("--messages", type=int, default=1000)
    parser.add_argument("--keys", type=int, default=64)
    parser.add_argument("--size", type=int, default=1_000_000, help="payload bytes per message")
    args = parser.parse_args()

    apis = ["recv_only", "set_bytesvec", "set_vec"]

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        results: list[dict[str, Any]] = []
        for api in apis:
            recv_p50_samples: list[float] = []
            recv_p99_samples: list[float] = []
            set_p50_samples: list[float] = []
            set_p99_samples: list[float] = []
            e2e_p50_samples: list[float] = []
            e2e_p99_samples: list[float] = []

            for _ in range(args.repeats):
                r = _run_one_repeat(
                    api=api,
                    payload_size=args.size,
                    warmup_messages=args.warmup_messages,
                    messages=args.messages,
                    key_count=args.keys,
                )
                recv_p50_samples.append(r["recv_p50_ns"])
                recv_p99_samples.append(r["recv_p99_ns"])
                set_p50_samples.append(r["set_p50_ns"])
                set_p99_samples.append(r["set_p99_ns"])
                e2e_p50_samples.append(r["e2e_p50_ns"])
                e2e_p99_samples.append(r["e2e_p99_ns"])

            results.append(
                {
                    "api": api,
                    "repeats": args.repeats,
                    "recv": {
                        "p50_ns": _median_iqr(recv_p50_samples),
                        "p99_ns": _median_iqr(recv_p99_samples),
                    },
                    "set": {
                        "p50_ns": _median_iqr(set_p50_samples),
                        "p99_ns": _median_iqr(set_p99_samples),
                    },
                    "e2e": {
                        "p50_ns": _median_iqr(e2e_p50_samples),
                        "p99_ns": _median_iqr(e2e_p99_samples),
                    },
                }
            )
    finally:
        if gc_was_enabled:
            gc.enable()

    out_dir = f"out/bridge_eval/{args.run_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "socket_kv_telemetry.json")
    payload = {
        "metadata": {
            "run_id": args.run_id,
            "timestamp": time.time(),
            "repeats": args.repeats,
            "warmup_messages": args.warmup_messages,
            "messages": args.messages,
            "keys": args.keys,
            "payload_size_bytes": args.size,
            "gc_disabled": True,
            "platform": sys.platform,
            "python": sys.version,
            "import": {
                "use_installed": use_installed,
                "python_path": ext_path if not use_installed else None,
                "module_file": getattr(warm_logic_rs, "__file__", None),
            },
        },
        "results": results,
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
