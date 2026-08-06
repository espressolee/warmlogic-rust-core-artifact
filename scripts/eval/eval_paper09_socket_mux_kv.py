#!/usr/bin/env python3
"""
Paper 09: I/O-adjacent workload (more realistic than a single socketpair).

Multi-connection socket multiplexing (selectors) → store in SovereignKV.

Goal:
- Reduce the "single-connection toy" criticism by multiplexing many concurrent sockets.
- Provide both latency (p50/p99) and throughput (msgs/sec) evidence that the
  `Vec<u8>` conversion semantic choice can dominate an I/O-adjacent pipeline.

Workload (fixed-size frames):
  Producers: N threads, each sends (warmup + measured) frames over its socket.
  Consumer:  selectors loop reads frames into preallocated bytearrays and, for each full frame,
             optionally stores it in Rust SovereignKV using one of:
               - recv_only
               - set_bytesvec  (BytesVec extractor; contiguous copy)
               - set_vec       (Vec<u8> arg conversion; differs stock vs patched PyO3)

This is still not a production server benchmark (no real network, no TLS, no asyncio),
but it meaningfully increases "realism" versus a single socketpair while staying
dependency-free and reproducible.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import selectors
import socket
import statistics
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


# Import strategy (match eval_bridge_v3.py)
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


@dataclass
class ConnState:
    sock: socket.socket
    buf: bytearray
    want: int
    got: int = 0
    warmup_remaining: int = 0
    measured_remaining: int = 0

    def reset_frame(self) -> None:
        self.got = 0


def _make_payload(size: int) -> bytes:
    return bytes([0xAB]) * size


def _run_one_repeat(
    *,
    api: str,
    payload_size: int,
    conns: int,
    warmup_frames_per_conn: int,
    frames_per_conn: int,
    key_count: int,
) -> dict[str, Any]:
    if conns <= 0:
        raise ValueError("conns must be > 0")
    if frames_per_conn <= 0:
        raise ValueError("frames_per_conn must be > 0")

    payload = _make_payload(payload_size)

    kv = warm_logic_rs.SovereignKV()
    keys = [f"k{i}" for i in range(key_count)]
    for k in keys:
        kv.set_bytes(k, b"x")

    set_fn: Callable[[str, Any], Any] | None
    if api == "recv_only":
        set_fn = None
    elif api == "set_bytesvec":
        set_fn = kv.set_bytesvec
    elif api == "set_vec":
        set_fn = kv.set_vec
    else:
        raise ValueError(f"unknown api: {api}")

    selector = selectors.DefaultSelector()
    states: dict[int, ConnState] = {}
    writers: list[threading.Thread] = []
    writer_socks: list[socket.socket] = []

    def start_writer(w_sock: socket.socket) -> threading.Thread:
        def writer() -> None:
            try:
                total = warmup_frames_per_conn + frames_per_conn
                for _ in range(total):
                    w_sock.sendall(payload)
                try:
                    w_sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
            finally:
                try:
                    w_sock.close()
                except OSError:
                    pass

        th = threading.Thread(target=writer, daemon=True)
        th.start()
        return th

    # Create N socketpairs.
    for _ in range(conns):
        r_sock, w_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        r_sock.setblocking(False)
        st = ConnState(
            sock=r_sock,
            buf=bytearray(payload_size),
            want=payload_size,
            warmup_remaining=warmup_frames_per_conn,
            measured_remaining=frames_per_conn,
        )
        selector.register(r_sock, selectors.EVENT_READ)
        states[r_sock.fileno()] = st
        writer_socks.append(w_sock)
        writers.append(start_writer(w_sock))

    e2e_lat: list[float] = []
    set_lat: list[float] = []
    recv_lat: list[float] = []

    measured_total = conns * frames_per_conn
    measured_done = 0

    t_start = time.perf_counter_ns()

    try:
        while measured_done < measured_total and states:
            events = selector.select(timeout=1.0)
            if not events:
                raise RuntimeError("timeout waiting for socket events")

            for key, _mask in events:
                sock: socket.socket = key.fileobj  # type: ignore[assignment]
                st = states.get(sock.fileno())
                if st is None:
                    continue

                t0 = time.perf_counter_ns()
                try:
                    n = sock.recv_into(memoryview(st.buf)[st.got :])
                except BlockingIOError:
                    continue

                if n == 0:
                    selector.unregister(sock)
                    sock.close()
                    states.pop(sock.fileno(), None)
                    continue

                st.got += n
                if st.got < st.want:
                    continue

                # Full frame read.
                t1 = time.perf_counter_ns()

                if st.warmup_remaining > 0:
                    st.warmup_remaining -= 1
                    st.reset_frame()
                    continue

                if st.measured_remaining <= 0:
                    # Should not happen, but don't crash measurement.
                    st.reset_frame()
                    continue

                if set_fn is not None:
                    set_fn(keys[measured_done % key_count], st.buf)
                t2 = time.perf_counter_ns()

                recv_lat.append(float(t1 - t0))
                set_lat.append(float(t2 - t1))
                e2e_lat.append(float(t2 - t0))

                measured_done += 1
                st.measured_remaining -= 1
                st.reset_frame()

                if measured_done >= measured_total:
                    break

        t_end = time.perf_counter_ns()
    finally:
        for w in writer_socks:
            try:
                w.close()
            except OSError:
                pass
        for st in list(states.values()):
            try:
                selector.unregister(st.sock)
            except Exception:
                pass
            try:
                st.sock.close()
            except OSError:
                pass
        selector.close()

        for th in writers:
            th.join(timeout=5.0)

    duration_s = max(1e-9, (t_end - t_start) / 1e9)
    throughput = measured_done / duration_s if duration_s > 0 else float("nan")

    return {
        "measured_total": measured_total,
        "measured_done": measured_done,
        "duration_s": duration_s,
        "throughput_msgs_per_s": throughput,
        "recv_p50_ns": statistics.median(recv_lat) if recv_lat else float("nan"),
        "recv_p99_ns": _p99(recv_lat),
        "set_p50_ns": statistics.median(set_lat) if set_lat else float("nan"),
        "set_p99_ns": _p99(set_lat),
        "e2e_p50_ns": statistics.median(e2e_lat) if e2e_lat else float("nan"),
        "e2e_p99_ns": _p99(e2e_lat),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paper 09: socket multiplexing → SovereignKV"
    )
    parser.add_argument("--run-id", default="paper09_socket_mux_kv")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--conns", type=int, default=8)
    parser.add_argument("--warmup-frames-per-conn", type=int, default=50)
    parser.add_argument("--frames-per-conn", type=int, default=200)
    parser.add_argument("--keys", type=int, default=256)
    parser.add_argument("--size", type=int, default=1_000_000)
    args = parser.parse_args()

    apis = ["recv_only", "set_bytesvec", "set_vec"]

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        results: list[dict[str, Any]] = []
        for api in apis:
            thr_samples: list[float] = []
            e2e_p50_samples: list[float] = []
            e2e_p99_samples: list[float] = []
            for _ in range(args.repeats):
                r = _run_one_repeat(
                    api=api,
                    payload_size=args.size,
                    conns=args.conns,
                    warmup_frames_per_conn=args.warmup_frames_per_conn,
                    frames_per_conn=args.frames_per_conn,
                    key_count=args.keys,
                )
                thr_samples.append(r["throughput_msgs_per_s"])
                e2e_p50_samples.append(r["e2e_p50_ns"])
                e2e_p99_samples.append(r["e2e_p99_ns"])

            results.append(
                {
                    "api": api,
                    "repeats": args.repeats,
                    "conns": args.conns,
                    "frames_per_conn": args.frames_per_conn,
                    "payload_size_bytes": args.size,
                    "throughput_msgs_per_s": _median_iqr(thr_samples),
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
    out_path = os.path.join(out_dir, "socket_mux_kv_telemetry.json")
    payload = {
        "metadata": {
            "run_id": args.run_id,
            "timestamp": time.time(),
            "repeats": args.repeats,
            "conns": args.conns,
            "warmup_frames_per_conn": args.warmup_frames_per_conn,
            "frames_per_conn": args.frames_per_conn,
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
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

