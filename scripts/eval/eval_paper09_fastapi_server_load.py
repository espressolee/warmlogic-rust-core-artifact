#!/usr/bin/env python3
"""
Paper 09: sustained FastAPI+uvicorn (ASGI) workload under fixed arrival rate (loopback).

Why this exists:
  - Reviewers can dismiss raw TCP framing as "too synthetic" (Table 12/14).
  - ThreadingHTTPServer (Table 16) keeps dependencies at stdlib, but it is still sync.
  - This script wraps the same boundary choice in a widely-recognized async web stack
    (FastAPI + uvicorn) while keeping the *measurement philosophy* identical:
      open-loop arrival rate, multiple connections, and tail metrics (p50/p99/p999).

What it is (and is not):
  - Still not a production benchmark (no TLS, no reverse proxy, single process, loopback).
  - Designed as confirmatory evidence: can the `set_vec` conversion choice still surface
    in an ASGI/HTTP-shaped path under sustained load?

Server:
  - Uvicorn serving scripts.eval.paper09_fastapi_app:app on 127.0.0.1.
  - Forced to asyncio + h11 to keep stock vs patched comparable, regardless of extras.
Clients:
  - N persistent keep-alive connections.
  - Each connection sends fixed-size POST bodies at fixed open-loop rate (msgs/sec).
  - Server echoes an 8-byte seq; clients compute RTT.

Output schema mirrors eval_paper09_http_server_load.py so update_paper09_tables.py can render it.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import signal
import socket
import statistics
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


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


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        try:
            s.close()
        except OSError:
            pass


def _wait_port_open(*, port: int, timeout_s: float, proc: subprocess.Popen[bytes]) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            out = b""
            try:
                if proc.stdout is not None:
                    out = proc.stdout.read()  # type: ignore[assignment]
            except Exception:
                out = b""
            tail = out[-4000:].decode("utf-8", errors="replace") if out else ""
            extra = f"\n--- uvicorn output tail ---\n{tail}" if tail else ""
            raise RuntimeError(f"uvicorn exited early (rc={proc.returncode}){extra}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("timeout waiting for uvicorn port to open")

def _start_server(*, timeout_s: float) -> tuple[subprocess.Popen[bytes], int]:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "scripts.eval.paper09_fastapi_app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "0",  # placeholder; filled per attempt
        "--log-level",
        "warning",
        "--no-access-log",
        "--loop",
        "asyncio",
        "--http",
        "h11",
        "--lifespan",
        "off",
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    port_idx = cmd.index("--port") + 1
    last_err: BaseException | None = None
    for _attempt in range(10):
        port = _pick_free_port()
        cmd_run = cmd.copy()
        cmd_run[port_idx] = str(port)
        proc = subprocess.Popen(
            cmd_run,
            cwd=os.getcwd(),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_port_open(port=port, timeout_s=timeout_s, proc=proc)
            return proc, port
        except BaseException as e:  # noqa: BLE001
            last_err = e
            _stop_server(proc, timeout_s=timeout_s)
            time.sleep(0.05)
    raise RuntimeError(f"failed to start uvicorn after retries: {last_err}")


def _stop_server(proc: subprocess.Popen[bytes], timeout_s: float) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            pass


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

    proc, port = _start_server(timeout_s=timeout_s)

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
        _stop_server(proc, timeout_s=timeout_s)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paper 09: FastAPI+uvicorn fixed-rate server-load benchmark"
    )
    parser.add_argument("--run-id", default="paper09_fastapi_server_load")
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

    # Capture dependency versions from this environment (stock vs patched venv).
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401

        fastapi_ver = getattr(fastapi, "__version__", None)
        uvicorn_ver = getattr(uvicorn, "__version__", None)
    except Exception:
        fastapi_ver = None
        uvicorn_ver = None

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
    out_path = os.path.join(out_dir, "fastapi_server_load_telemetry.json")
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
            "stack": {
                "fastapi": fastapi_ver,
                "uvicorn": uvicorn_ver,
                "loop": "asyncio",
                "http_impl": "h11",
            },
        },
        "results": results,
    }
    Path(out_path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
