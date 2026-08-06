#!/usr/bin/env python3
"""
Paper 09: sustained socket "server-like" workload under fixed arrival rate.

Goal:
- Provide a harder-to-dismiss, sustained-load signal than tight-loop microbenchmarks.
- Keep it dependency-free (stdlib only) and reproducible.
- Stress the exact boundary choice this paper is about: how a binding converts
  bytes-like / buffer-exported payloads into an owned Vec<u8> in Rust.

Model:
  - N client connections (loopback TCP).
  - Each client sends fixed-size frames at a fixed open-loop rate (msgs/sec).
  - Server multiplexes connections with selectors, and for each full frame:
      recv payload -> optionally store via SovereignKV using one of:
        recv_only, set_bytesvec, set_vec
      -> send 8-byte ACK (sequence number).
  - Clients compute RTT as (ack_recv_ns - send_ts_ns).

This is still not a production benchmark (no real network, no TLS, no asyncio),
but it adds: (1) real sockets, (2) sustained load, and (3) tail metrics (p99/p999).
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import selectors
import socket
import statistics
import struct
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


# Import strategy (match other eval scripts).
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


HEADER_STRUCT = struct.Struct("!QQ")  # seq, send_ts_ns
ACK_STRUCT = struct.Struct("!Q")  # seq


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    if q <= 0:
        return min(values)
    if q >= 1:
        return max(values)
    xs = sorted(values)
    idx = int(q * (len(xs) - 1))
    return xs[idx]


def _median_iqr(values: list[float]) -> dict[str, float]:
    xs = sorted(values)
    if not xs:
        return {"median": float("nan"), "iqr": float("nan")}
    q1 = xs[int(len(xs) * 0.25)]
    q3 = xs[int(len(xs) * 0.75)]
    return {"median": statistics.median(xs), "iqr": q3 - q1}


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray(n)
    mv = memoryview(buf)
    got = 0
    while got < n:
        chunk = sock.recv(n - got)
        if not chunk:
            raise EOFError("socket closed while waiting for ACK")
        mv[got : got + len(chunk)] = chunk
        got += len(chunk)
    return bytes(buf)


@dataclass
class _ServerConn:
    sock: socket.socket
    buf: bytearray
    got: int = 0

    def reset(self) -> None:
        self.got = 0


def _run_one_repeat(
    *,
    api: str,
    payload_bytes: int,
    conns: int,
    warmup_msgs_per_conn: int,
    msgs_per_conn: int,
    rate_hz: float,
    timeout_s: float,
) -> dict[str, Any]:
    if conns <= 0:
        raise ValueError("conns must be > 0")
    if payload_bytes <= 0:
        raise ValueError("payload_bytes must be > 0")
    if msgs_per_conn <= 0:
        raise ValueError("msgs_per_conn must be > 0")
    if rate_hz <= 0:
        raise ValueError("rate_hz must be > 0")

    kv = warm_logic_rs.SovereignKV()
    keys = [f"k{i}" for i in range(256)]
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

    frame_size = HEADER_STRUCT.size + payload_bytes
    payload_fill = bytes([0xAB]) * payload_bytes

    ready = threading.Event()
    stop = threading.Event()
    server_exc: list[BaseException] = []

    server_host = "127.0.0.1"
    server_port_box: list[int] = []

    def server_thread() -> None:
        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((server_host, 0))
            listener.listen(conns)
            listener.settimeout(timeout_s)
            server_port_box.append(listener.getsockname()[1])
            ready.set()

            selector = selectors.DefaultSelector()
            connections: dict[int, _ServerConn] = {}
            try:
                # Accept N connections.
                for _ in range(conns):
                    sock, _addr = listener.accept()
                    sock.settimeout(timeout_s)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    selector.register(sock, selectors.EVENT_READ)
                    connections[sock.fileno()] = _ServerConn(sock=sock, buf=bytearray(frame_size))

                while connections and not stop.is_set():
                    events = selector.select(timeout=0.5)
                    if not events:
                        continue

                    for key, _mask in events:
                        sock: socket.socket = key.fileobj  # type: ignore[assignment]
                        st = connections.get(sock.fileno())
                        if st is None:
                            continue

                        n = sock.recv_into(memoryview(st.buf)[st.got :])
                        if n == 0:
                            selector.unregister(sock)
                            sock.close()
                            connections.pop(sock.fileno(), None)
                            continue

                        st.got += n
                        if st.got < frame_size:
                            continue

                        # Full frame.
                        seq, _send_ts = HEADER_STRUCT.unpack_from(st.buf, 0)
                        if set_fn is not None:
                            payload_view = memoryview(st.buf)[HEADER_STRUCT.size :]
                            set_fn(keys[int(seq) % len(keys)], payload_view)
                        sock.sendall(ACK_STRUCT.pack(seq))
                        st.reset()
            finally:
                try:
                    selector.close()
                except Exception:
                    pass
                try:
                    listener.close()
                except Exception:
                    pass
        except BaseException as e:  # noqa: BLE001
            server_exc.append(e)
            stop.set()
            ready.set()

    th_server = threading.Thread(target=server_thread, daemon=True)
    th_server.start()

    if not ready.wait(timeout=timeout_s):
        stop.set()
        raise RuntimeError("server failed to start in time")
    if server_exc:
        raise RuntimeError(f"server error: {server_exc[0]}")

    port = server_port_box[0]

    client_socks: list[socket.socket] = []
    try:
        for _ in range(conns):
            s = socket.create_connection((server_host, port), timeout=timeout_s)
            s.settimeout(timeout_s)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client_socks.append(s)

        # Warmup: closed-loop to avoid "startup backlog" contaminating measurement.
        for s in client_socks:
            for i in range(warmup_msgs_per_conn):
                seq = i
                send_ts = time.perf_counter_ns()
                frame = HEADER_STRUCT.pack(seq, send_ts) + payload_fill
                s.sendall(frame)
                _recv_exact(s, ACK_STRUCT.size)

        # Measured open-loop phase.
        interval_s = 1.0 / rate_hz
        rtts_ns: list[float] = []
        sent_total = conns * msgs_per_conn
        recv_total = 0
        lock = threading.Lock()

        send_ts_by_conn: list[list[int]] = [[0] * msgs_per_conn for _ in range(conns)]

        def sender(conn_idx: int, sock: socket.socket) -> None:
            t0 = time.perf_counter()
            for i in range(msgs_per_conn):
                seq = i
                send_ts = time.perf_counter_ns()
                send_ts_by_conn[conn_idx][i] = send_ts
                frame = HEADER_STRUCT.pack(seq, send_ts) + payload_fill
                sock.sendall(frame)
                target = t0 + (i + 1) * interval_s
                now = time.perf_counter()
                if target > now:
                    time.sleep(target - now)
            try:
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass

        def receiver(conn_idx: int, sock: socket.socket) -> None:
            nonlocal recv_total
            for _ in range(msgs_per_conn):
                ack = _recv_exact(sock, ACK_STRUCT.size)
                (seq,) = ACK_STRUCT.unpack(ack)
                idx = int(seq)
                if 0 <= idx < msgs_per_conn:
                    sent_ts = send_ts_by_conn[conn_idx][idx]
                    if sent_ts:
                        rtt = float(time.perf_counter_ns() - sent_ts)
                        with lock:
                            rtts_ns.append(rtt)
                            recv_total += 1
            try:
                sock.close()
            except OSError:
                pass

        t_start = time.perf_counter_ns()
        threads: list[threading.Thread] = []
        for i, s in enumerate(client_socks):
            threads.append(threading.Thread(target=receiver, args=(i, s), daemon=True))
        for i, s in enumerate(client_socks):
            threads.append(threading.Thread(target=sender, args=(i, s), daemon=True))

        for t in threads:
            t.start()

        deadline = time.time() + timeout_s
        for t in threads:
            remaining = max(0.0, deadline - time.time())
            t.join(timeout=remaining)

        t_end = time.perf_counter_ns()

        if any(t.is_alive() for t in threads):
            stop.set()
            raise RuntimeError("timeout waiting for client threads to finish")

        duration_s = max(1e-9, (t_end - t_start) / 1e9)
        throughput = recv_total / duration_s

        return {
            "sent_total": sent_total,
            "recv_total": recv_total,
            "drop_total": sent_total - recv_total,
            "duration_s": duration_s,
            "throughput_msgs_per_s": throughput,
            "rtt_p50_ns": _percentile(rtts_ns, 0.50),
            "rtt_p99_ns": _percentile(rtts_ns, 0.99),
            "rtt_p999_ns": _percentile(rtts_ns, 0.999),
        }
    finally:
        stop.set()
        try:
            for s in client_socks:
                try:
                    s.close()
                except OSError:
                    pass
        finally:
            th_server.join(timeout=timeout_s)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper 09: socket server load benchmark")
    parser.add_argument("--run-id", default="paper09_socket_server_load")
    parser.add_argument("--out-root", default="out")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--conns", type=int, default=8)
    parser.add_argument("--payload-bytes", type=int, default=100_000)
    parser.add_argument("--warmup-msgs-per-conn", type=int, default=20)
    parser.add_argument("--msgs-per-conn", type=int, default=200)
    parser.add_argument("--rate-hz", type=float, default=50.0)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument(
        "--apis",
        default="recv_only,set_bytesvec,set_vec",
        help="comma-separated list; subset of recv_only,set_bytesvec,set_vec",
    )
    args = parser.parse_args()

    apis = [a.strip() for a in args.apis.split(",") if a.strip()]

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        results: list[dict[str, Any]] = []
        for api in apis:
            thr_samples: list[float] = []
            p50_samples: list[float] = []
            p99_samples: list[float] = []
            p999_samples: list[float] = []
            drop_samples: list[float] = []

            for _ in range(args.repeats):
                r = _run_one_repeat(
                    api=api,
                    payload_bytes=args.payload_bytes,
                    conns=args.conns,
                    warmup_msgs_per_conn=args.warmup_msgs_per_conn,
                    msgs_per_conn=args.msgs_per_conn,
                    rate_hz=args.rate_hz,
                    timeout_s=args.timeout_s,
                )
                thr_samples.append(r["throughput_msgs_per_s"])
                p50_samples.append(r["rtt_p50_ns"])
                p99_samples.append(r["rtt_p99_ns"])
                p999_samples.append(r["rtt_p999_ns"])
                drop_samples.append(r["drop_total"] / max(1.0, float(r["sent_total"])))

            results.append(
                {
                    "api": api,
                    "repeats": args.repeats,
                    "conns": args.conns,
                    "payload_bytes": args.payload_bytes,
                    "warmup_msgs_per_conn": args.warmup_msgs_per_conn,
                    "msgs_per_conn": args.msgs_per_conn,
                    "rate_hz_per_conn": args.rate_hz,
                    "drop_rate": _median_iqr(drop_samples),
                    "throughput_msgs_per_s": _median_iqr(thr_samples),
                    "rtt": {
                        "p50_ns": _median_iqr(p50_samples),
                        "p99_ns": _median_iqr(p99_samples),
                        "p999_ns": _median_iqr(p999_samples),
                    },
                }
            )
    finally:
        if gc_was_enabled:
            gc.enable()

    out_dir = os.path.join(args.out_root, "bridge_eval", args.run_id)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "socket_server_load_telemetry.json")
    payload = {
        "metadata": {
            "run_id": args.run_id,
            "timestamp": time.time(),
            "repeats": args.repeats,
            "conns": args.conns,
            "payload_bytes": args.payload_bytes,
            "warmup_msgs_per_conn": args.warmup_msgs_per_conn,
            "msgs_per_conn": args.msgs_per_conn,
            "rate_hz_per_conn": args.rate_hz,
            "timeout_s": args.timeout_s,
            "apis": apis,
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
