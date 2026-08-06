#!/usr/bin/env python3
"""
Paper 09: sustained HTTP/1.1 "server-like" workload under fixed arrival rate (loopback).

Why this exists:
  - The paper already includes a fixed-rate raw-socket workload (Table 12/14).
  - Reviewers can still dismiss raw TCP framing as "too synthetic".
  - This script keeps the same *measurement philosophy* (open-loop rate, tail metrics),
    but wraps the payload path in a familiar HTTP request/response loop using only stdlib.

What it is (and is not):
  - It is still not a production benchmark (no TLS, no asyncio, no reverse proxy).
  - It *does* exercise Python HTTP parsing + request dispatch and the exact boundary choice:
      recv_only vs SovereignKV.set_bytesvec vs SovereignKV.set_vec
    where `set_vec` triggers `bytes -> Vec<u8>` conversion in the binding layer.

Model:
  - ThreadingHTTPServer (loopback).
  - N persistent keep-alive connections.
  - Each connection sends fixed-size POST bodies at a fixed open-loop rate (msgs/sec).
  - Server echoes an 8-byte sequence number; clients compute RTT.

Output schema intentionally mirrors eval_paper09_socket_server_load.py so it can be
rendered with the same table logic if/when wired into the paper.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import socket
import statistics
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


SEQ_STRUCT = struct.Struct("!Q")  # seq
BODY_HDR_STRUCT = struct.Struct("!QQ")  # seq, send_ts_ns
HTTP_DELIM = b"\r\n\r\n"


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


class _Paper09HTTPServer(ThreadingHTTPServer):
    daemon_threads = True  # ensure handler threads don't block process exit

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, _Paper09Handler)
        self.kv = warm_logic_rs.SovereignKV()
        self.keys = [f"k{i}" for i in range(256)]
        for k in self.keys:
            self.kv.set_bytes(k, b"x")
        self._first_error: BaseException | None = None
        self._err_lock = threading.Lock()

    def record_error(self, e: BaseException) -> None:
        with self._err_lock:
            if self._first_error is None:
                self._first_error = e

    def first_error(self) -> BaseException | None:
        with self._err_lock:
            return self._first_error


class _Paper09Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:  # noqa: D401
        # Silence default stderr logging (it pollutes runs and adds noise).
        return

    def do_POST(self) -> None:  # noqa: N802 (stdlib API)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0:
                self.send_error(411, "Content-Length required")
                return

            body = self.rfile.read(n)
            if len(body) != n:
                raise RuntimeError(f"short read: expected {n}, got {len(body)}")

            if len(body) < BODY_HDR_STRUCT.size:
                raise RuntimeError("body too small for seq+ts header")

            seq, _send_ts = BODY_HDR_STRUCT.unpack_from(body, 0)
            # Reduce artificial lock contention by mixing connection identity into the key choice.
            # (Otherwise, all connections hammer the same small prefix of keys in lockstep.)
            client_port = int(self.client_address[1])
            key_idx = (int(seq) + client_port) % len(self.server.keys)  # type: ignore[attr-defined]
            key = self.server.keys[key_idx]  # type: ignore[attr-defined]

            path = self.path.split("?", 1)[0]
            if path == "/recv_only":
                pass
            elif path == "/set_bytesvec":
                self.server.kv.set_bytesvec(key, body)  # type: ignore[attr-defined]
            elif path == "/set_vec":
                self.server.kv.set_vec(key, body)  # type: ignore[attr-defined]
            else:
                self.send_error(404, "unknown path")
                return

            # Echo seq (8 bytes) so clients can match RTT without parsing headers.
            payload = SEQ_STRUCT.pack(int(seq))
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(payload)
            self.close_connection = False
        except BaseException as e:  # noqa: BLE001
            try:
                self.server.record_error(e)  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                self.send_error(500, "internal error")
            except Exception:
                # If headers are already sent or socket is broken, ignore.
                pass


def _recv_http_response(sock: socket.socket, buf: bytearray) -> int:
    # Read headers.
    while True:
        idx = buf.find(HTTP_DELIM)
        if idx != -1:
            header_end = idx + len(HTTP_DELIM)
            header = bytes(buf[:header_end])
            del buf[:header_end]
            break
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError("socket closed while waiting for HTTP headers")
        buf.extend(chunk)

    # Minimal status check (avoid full HTTP parser).
    first_line = header.split(b"\r\n", 1)[0]
    if b" 200 " not in first_line and not first_line.endswith(b" 200"):
        raise RuntimeError(f"non-200 response: {first_line!r}")

    body_len: int | None = None
    for line in header.split(b"\r\n")[1:]:
        if not line:
            break
        if line.lower().startswith(b"content-length:"):
            body_len = int(line.split(b":", 1)[1].strip() or b"0")
            break
    if body_len is None:
        raise RuntimeError("missing Content-Length in response")

    while len(buf) < body_len:
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError("socket closed while waiting for HTTP body")
        buf.extend(chunk)

    body = bytes(buf[:body_len])
    del buf[:body_len]
    if len(body) != SEQ_STRUCT.size:
        raise RuntimeError(f"unexpected body length: {len(body)}")
    (seq,) = SEQ_STRUCT.unpack(body)
    return int(seq)


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
    if payload_bytes < BODY_HDR_STRUCT.size:
        raise ValueError(f"payload_bytes must be >= {BODY_HDR_STRUCT.size}")
    if msgs_per_conn <= 0:
        raise ValueError("msgs_per_conn must be > 0")
    if rate_hz <= 0:
        raise ValueError("rate_hz must be > 0")

    # Start server.
    server = _Paper09HTTPServer(("127.0.0.1", 0))
    server.timeout = timeout_s
    port = int(server.server_address[1])

    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()

    req_prefix = (
        f"POST /{api} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Connection: keep-alive\r\n"
        "Content-Type: application/octet-stream\r\n"
        f"Content-Length: {payload_bytes}\r\n"
        "\r\n"
    ).encode("ascii")
    filler = bytes([0xAB]) * (payload_bytes - BODY_HDR_STRUCT.size)

    client_socks: list[socket.socket] = []
    recv_total = 0
    rtts_ns: list[float] = []
    lock = threading.Lock()
    stop = threading.Event()

    try:
        # Establish N persistent connections.
        for _ in range(conns):
            s = socket.create_connection(("127.0.0.1", port), timeout=timeout_s)
            s.settimeout(timeout_s)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client_socks.append(s)

        # Warmup (closed-loop).
        for s in client_socks:
            buf = bytearray()
            for i in range(warmup_msgs_per_conn):
                seq = i
                send_ts = time.perf_counter_ns()
                body = BODY_HDR_STRUCT.pack(seq, send_ts) + filler
                s.sendall(req_prefix + body)
                _ = _recv_http_response(s, buf)

        # Measured open-loop phase (sender+receiver threads per connection).
        interval_s = 1.0 / rate_hz
        sent_total = conns * msgs_per_conn

        send_ts_by_conn: list[list[int]] = [[0] * msgs_per_conn for _ in range(conns)]

        def sender(conn_idx: int, sock: socket.socket) -> None:
            t0 = time.perf_counter()
            for i in range(msgs_per_conn):
                if stop.is_set():
                    return
                # Open-loop schedule.
                deadline = t0 + (i * interval_s)
                while True:
                    now = time.perf_counter()
                    if now >= deadline:
                        break
                    time.sleep(min(0.001, deadline - now))

                seq = i
                send_ts = time.perf_counter_ns()
                send_ts_by_conn[conn_idx][seq] = send_ts
                body = BODY_HDR_STRUCT.pack(seq, send_ts) + filler
                sock.sendall(req_prefix + body)

        def receiver(conn_idx: int, sock: socket.socket) -> None:
            nonlocal recv_total
            buf = bytearray()
            for _ in range(msgs_per_conn):
                if stop.is_set():
                    return
                seq = _recv_http_response(sock, buf)
                now = time.perf_counter_ns()
                send_ts = send_ts_by_conn[conn_idx][seq]
                if send_ts:
                    rtt = now - send_ts
                    with lock:
                        rtts_ns.append(float(rtt))
                        recv_total += 1

        threads: list[threading.Thread] = []
        for idx, s in enumerate(client_socks):
            threads.append(threading.Thread(target=sender, args=(idx, s), daemon=True))
            threads.append(threading.Thread(target=receiver, args=(idx, s), daemon=True))

        t_start = time.perf_counter_ns()
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

        srv_err = server.first_error()
        if srv_err is not None:
            raise RuntimeError(f"server error: {srv_err}")

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
        for s in client_socks:
            try:
                s.close()
            except OSError:
                pass
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass
        th.join(timeout=timeout_s)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper 09: HTTP server load benchmark")
    parser.add_argument("--run-id", default="paper09_http_server_load")
    parser.add_argument("--out-root", default="out")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--conns", type=int, default=4)
    parser.add_argument("--payload-bytes", type=int, default=100_000)
    parser.add_argument("--warmup-msgs-per-conn", type=int, default=10)
    parser.add_argument("--msgs-per-conn", type=int, default=100)
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

            for _ in range(int(args.repeats)):
                r = _run_one_repeat(
                    api=api,
                    payload_bytes=int(args.payload_bytes),
                    conns=int(args.conns),
                    warmup_msgs_per_conn=int(args.warmup_msgs_per_conn),
                    msgs_per_conn=int(args.msgs_per_conn),
                    rate_hz=float(args.rate_hz),
                    timeout_s=float(args.timeout_s),
                )
                thr_samples.append(float(r["throughput_msgs_per_s"]))
                p50_samples.append(float(r["rtt_p50_ns"]))
                p99_samples.append(float(r["rtt_p99_ns"]))
                p999_samples.append(float(r["rtt_p999_ns"]))
                drop_samples.append(float(r["drop_total"]) / max(1.0, float(r["sent_total"])))

            results.append(
                {
                    "api": api,
                    "repeats": int(args.repeats),
                    "conns": int(args.conns),
                    "payload_bytes": int(args.payload_bytes),
                    "warmup_msgs_per_conn": int(args.warmup_msgs_per_conn),
                    "msgs_per_conn": int(args.msgs_per_conn),
                    "rate_hz_per_conn": float(args.rate_hz),
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

    out_dir = os.path.join(args.out_root, "bridge_eval", str(args.run_id))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "http_server_load_telemetry.json")
    payload = {
        "metadata": {
            "run_id": str(args.run_id),
            "timestamp": time.time(),
            "repeats": int(args.repeats),
            "conns": int(args.conns),
            "payload_bytes": int(args.payload_bytes),
            "warmup_msgs_per_conn": int(args.warmup_msgs_per_conn),
            "msgs_per_conn": int(args.msgs_per_conn),
            "rate_hz_per_conn": float(args.rate_hz),
            "timeout_s": float(args.timeout_s),
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
