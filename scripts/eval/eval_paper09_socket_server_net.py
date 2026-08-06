#!/usr/bin/env python3
"""
Paper 09: two-host sustained-load socket benchmark (real network).

Why this exists:
  Table 12/13 uses loopback TCP (127.0.0.1). Reviewers can dismiss tails as
  loopback artifacts. This script splits the benchmark into a server process
  (runs on one VM) and a client process (runs on another VM) so you can measure
  the same workload over an actual network path.

Protocol:
  client -> server: [seq:u64][send_ts_ns:u64][payload bytes...]
  server -> client: [seq:u64] ACK

Clock sync is NOT required: RTT is measured on the client as (ack_recv_ns - send_ts_ns).

Server API modes:
  - recv_only: receive frames and ACK (no warm_logic_rs calls)
  - set_bytesvec: store payload via SovereignKV.set_bytesvec (owned copy semantics)
  - set_vec: store payload via SovereignKV.set_vec (Vec<u8> arg conversion semantics)

This script is dependency-free (stdlib only).
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform as _platform
import selectors
import socket
import statistics
import struct
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable

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
            raise EOFError("socket closed while waiting for data")
        mv[got : got + len(chunk)] = chunk
        got += len(chunk)
    return bytes(buf)


def _recv_line(sock: socket.socket, *, limit: int = 64 * 1024) -> bytes:
    buf = bytearray()
    while True:
        if len(buf) > limit:
            raise ValueError("handshake line too large")
        # Read a chunk. For handshake, the server sends a single JSON line.
        chunk = sock.recv(min(1024, limit - len(buf)))
        if not chunk:
            raise EOFError("socket closed while waiting for handshake line")

        buf.extend(chunk)
        print(
            f"DEBUG: _recv_line got {len(chunk)} bytes, total buf: {len(buf)}",
            flush=True,
        )
        idx = buf.find(b"\n")
        if idx >= 0:
            return bytes(buf[:idx])


def _read_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _server_identity(*, run_id: str, api: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "api": api,
        "timestamp": time.time(),
        "platform": _platform.platform(),
        "python": sys.version,
        "uname": " ".join(_platform.uname()),
        "machine": _platform.machine(),
        "machine_id_etc": _read_file("/etc/machine-id"),
        "machine_id_dbus": _read_file("/var/lib/dbus/machine-id"),
        "dmi_product_uuid": _read_file("/sys/class/dmi/id/product_uuid"),
    }


def _import_warm_logic_rs() -> Any:
    # Import strategy mirrors other eval scripts.
    use_installed = os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1"
    ext_path = os.environ.get("WARM_LOGIC_RS_PYTHON_PATH")
    repo_root = os.getcwd()
    if not use_installed:
        ext_path = ext_path or os.path.join(
            repo_root, "warm_logic_rs", "python_packages_v2"
        )
        sys.path.insert(0, ext_path)
        sys.path.insert(1, repo_root)
    else:
        sys.path.append(repo_root)

    import warm_logic_rs  # type: ignore

    return warm_logic_rs


@dataclass
class _ServerConn:
    sock: socket.socket
    buf: bytearray
    got: int = 0

    def reset(self) -> None:
        self.got = 0


def _server_run(
    *,
    run_id: str,
    api: str,
    bind_host: str,
    port: int,
    conns: int,
    payload_bytes: int,
    repeats: int,
    timeout_s: float,
) -> None:
    if repeats <= 0:
        raise ValueError("repeats must be > 0")
    if conns <= 0:
        raise ValueError("conns must be > 0")
    if payload_bytes <= 0:
        raise ValueError("payload_bytes must be > 0")

    warm_logic_rs = None
    set_fn: Callable[[str, Any], Any] | None = None
    keys: list[str] = []

    if api != "recv_only":
        warm_logic_rs = _import_warm_logic_rs()
        print(
            f"Loaded warm_logic_rs from: {getattr(warm_logic_rs, '__file__', None)}",
            flush=True,
        )
        kv = warm_logic_rs.SovereignKV()
        keys = [f"k{i}" for i in range(256)]
        for k in keys:
            kv.set_bytes(k, b"x")
        if api == "set_bytesvec":
            set_fn = kv.set_bytesvec
        elif api == "set_vec":
            set_fn = kv.set_vec
        else:
            raise ValueError(f"unknown api: {api}")

    # frame_size = HEADER_STRUCT.size + payload_bytes
    ident = _server_identity(run_id=run_id, api=api)
    if warm_logic_rs is not None:
        ident["warm_logic_rs_file"] = getattr(warm_logic_rs, "__file__", None)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((bind_host, port))
    listener.listen(128)
    listener.settimeout(timeout_s)
    print(
        f"[server] listening on {bind_host}:{listener.getsockname()[1]} (api={api}, conns={conns})",
        flush=True,
    )

    selector = selectors.DefaultSelector()
    connections: dict[int, _ServerConn] = {}
    frame_size = HEADER_STRUCT.size + payload_bytes

    threads = []
    try:
        for r_idx in range(repeats):
            print(f"[server] rep {r_idx + 1}/{repeats}", flush=True)
            peer_socks: list[socket.socket] = []
            while len(peer_socks) < conns:
                sock, addr = listener.accept()
                sock.settimeout(timeout_s)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                # Handshake: Expect 'H', Send Identity
                try:
                    b = sock.recv(1)
                    if b == b"H":
                        # Send identity to prove distinct host
                        ident_to_send = _server_identity(run_id=run_id, api=api)
                        line = json.dumps(ident_to_send).encode("utf-8") + b"\n"
                        sock.sendall(line)
                        peer_socks.append(sock)
                        print(f"[server] accepted and identified {addr[0]}:{addr[1]} ({len(peer_socks)}/{conns})", flush=True)
                    else:
                        print(
                            f"[server] ignoring probe from {addr[0]}:{addr[1]}",
                            flush=True,
                        )
                        sock.close()
                except Exception as e:
                    print(
                        f"[server] handshake failed from {addr[0]}:{addr[1]}: {e}",
                        flush=True,
                    )
                    try:
                        sock.close()
                    except:
                        pass

            def handle_one(s, idx):
                print(f"[server] worker {idx} started", flush=True)
                try:
                    while True:
                        # 1. Read header
                        header_raw = _recv_exact(s, HEADER_STRUCT.size)
                        seq, _ts = HEADER_STRUCT.unpack(header_raw)
                        # 2. Read payload
                        _payload = _recv_exact(s, payload_bytes)
                        # 3. Process
                        if set_fn is not None:
                            k = keys[int(seq) % len(keys)]
                            set_fn(k, _payload)
                        # 4. ACK
                        s.sendall(ACK_STRUCT.pack(seq))
                except (EOFError, OSError):
                    print(f"[server] worker {idx} disconnected", flush=True)
                finally:
                    try:
                        s.close()
                    except:
                        pass

            for i, s in enumerate(peer_socks):
                t = threading.Thread(target=handle_one, args=(s, i), daemon=True)
                t.start()
                threads.append(t)

            for t in threads:
                t.join(timeout=timeout_s)
            print(f"[server] rep {r_idx + 1} finished", flush=True)
    finally:
        try:
            for fd, c in list(connections.items()):
                try:
                    selector.unregister(c.sock)
                except Exception:
                    pass
                try:
                    c.sock.close()
                except OSError:
                    pass
                connections.pop(fd, None)
        finally:
            try:
                listener.close()
            except OSError:
                pass


def _client_run_one_repeat(
    *,
    run_id: str,
    api: str,
    server_host: str,
    port: int,
    conns: int,
    payload_bytes: int,
    warmup_msgs_per_conn: int,
    msgs_per_conn: int,
    rate_hz: float,
    timeout_s: float,
) -> dict[str, Any]:
    interval_ns = int(1e9 / rate_hz)
    payload_fill = bytes([0xAB]) * payload_bytes

    rtts_ns: list[float] = []
    rtts_lock = threading.Lock()
    sent_total = 0
    recv_total = 0
    sent_lock = threading.Lock()

    socks: list[socket.socket | None] = [None] * conns
    server_handshakes: list[dict[str, Any] | None] = [None] * conns

    def connect_and_handshake(idx: int) -> None:
        for attempt in range(5):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(30.0)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print(
                    f"DEBUG: Connecting to {server_host}:{port} (conn {idx}, attempt {attempt + 1})...",
                    flush=True,
                )
                s.connect((server_host, port))
                # Handshake: Send 'H', Recv Identity
                s.sendall(b"H")
                # Read identity JSON
                line_bytes = _recv_line(s)
                peer_ident = json.loads(line_bytes.decode("utf-8"))
                
                print(
                    f"DEBUG: Connected and verified conn {idx} (attempt {attempt + 1})", flush=True
                )
                socks[idx] = s
                server_handshakes[idx] = peer_ident
                return
            except Exception as e:
                print(
                    f"DEBUG: Connection attempt {attempt + 1} failed for conn {idx}: {e}",
                    flush=True,
                )
                try:
                    s.close()
                except:
                    pass
                time.sleep(2.0)
        # If we get here, all 5 attempts failed
        server_handshakes[idx] = {}

    handshake_threads = []
    for i in range(conns):
        t = threading.Thread(target=connect_and_handshake, args=(i,))
        t.daemon = True
        t.start()
        handshake_threads.append(t)
        time.sleep(1.0)  # Stagger to avoid IAP/GCP infrastructure glitches

    deadline = time.time() + 60.0
    for ht in handshake_threads:
        wait_time = max(0.0, deadline - time.time())
        ht.join(timeout=wait_time)

    # Filter out failed connections
    active_socks: list[socket.socket] = [s for s in socks if s is not None]
    if len(active_socks) < conns:
        print(
            f"FATAL: Only {len(active_socks)}/{conns} connections established. Aborting entire run.",
            flush=True,
        )
        for s in active_socks:
            try:
                s.close()
            except:
                pass
        sys.exit(1)  # Force exit to keep orchestrators in sync

    print(
        f"DEBUG: {len(active_socks)} handshakes ready, starting workers...", flush=True
    )
    start_ns = time.perf_counter_ns()

    def worker(conn_idx: int, sock: socket.socket) -> None:
        nonlocal sent_total, recv_total
        next_send_ns = start_ns
        print(f"DEBUG: Worker {conn_idx} started", flush=True)
        seq_base = (conn_idx & 0xFFFF_FFFF) << 32
        total_msgs = warmup_msgs_per_conn + msgs_per_conn

        for j in range(total_msgs):
            seq = seq_base | (j & 0xFFFF_FFFF)
            send_ts = time.perf_counter_ns()
            payload = HEADER_STRUCT.pack(seq, send_ts) + payload_fill
            try:
                sock.sendall(payload)
            except OSError as e:
                print(f"DEBUG: Worker {conn_idx} send failed: {e}", flush=True)
                break
            with sent_lock:
                sent_total += 1

            try:
                ack = _recv_exact(sock, ACK_STRUCT.size)
            except Exception as e:
                print(f"DEBUG: Worker {conn_idx} recv ACK failed: {e}", flush=True)
                break
            ack_seq = ACK_STRUCT.unpack(ack)[0]
            if ack_seq != seq:
                break
            recv_ts = time.perf_counter_ns()
            with sent_lock:
                recv_total += 1
            if j >= warmup_msgs_per_conn:
                with rtts_lock:
                    rtts_ns.append(float(recv_ts - send_ts))

            next_send_ns += interval_ns
            now = time.perf_counter_ns()
            if next_send_ns > now:
                time.sleep((next_send_ns - now) / 1e9)

    threads = [
        threading.Thread(target=worker, args=(i, active_socks[i]), daemon=True)
        for i in range(len(active_socks))
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout_s)

    end_ns = time.perf_counter_ns()
    duration_s = max(1e-9, (end_ns - start_ns) / 1e9)
    throughput = recv_total / duration_s

    for s in active_socks:
        try:
            s.close()
        except OSError:
            pass

    valid_handshakes = [h for h in server_handshakes if h]
    return {
        "server_handshake_sample": valid_handshakes[0] if valid_handshakes else {},
        "sent_total": sent_total,
        "recv_total": recv_total,
        "drop_total": sent_total - recv_total,
        "duration_s": duration_s,
        "throughput_msgs_per_s": throughput,
        "rtt_p50_ns": _percentile(rtts_ns, 0.50),
        "rtt_p99_ns": _percentile(rtts_ns, 0.99),
        "rtt_p999_ns": _percentile(rtts_ns, 0.999),
    }


def _client_run(
    *,
    run_id: str,
    api: str,
    server_host: str,
    port: int,
    conns: int,
    payload_bytes: int,
    warmup_msgs_per_conn: int,
    msgs_per_conn: int,
    rate_hz: float,
    repeats: int,
    timeout_s: float,
    out_root: str,
) -> str:
    if repeats <= 0:
        raise ValueError("repeats must be > 0")

    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        thr_samples: list[float] = []
        p50_samples: list[float] = []
        p99_samples: list[float] = []
        p999_samples: list[float] = []
        drop_samples: list[float] = []
        handshake_sample: dict[str, Any] = {}

        for i in range(repeats):
            print(f"DEBUG: Starting repeat {i + 1}/{repeats}", flush=True)
            r = _client_run_one_repeat(
                run_id=run_id,
                api=api,
                server_host=server_host,
                port=port,
                conns=conns,
                payload_bytes=payload_bytes,
                warmup_msgs_per_conn=warmup_msgs_per_conn,
                msgs_per_conn=msgs_per_conn,
                rate_hz=rate_hz,
                timeout_s=timeout_s,
            )
            if not r:
                print(f"FATAL: Repeat {i + 1} failed. Aborting run.", flush=True)
                sys.exit(1)
            handshake_sample = (
                handshake_sample or r.get("server_handshake_sample") or {}
            )
            thr_samples.append(r["throughput_msgs_per_s"])
            p50_samples.append(r["rtt_p50_ns"])
            p99_samples.append(r["rtt_p99_ns"])
            p999_samples.append(r["rtt_p999_ns"])
            drop_samples.append(r["drop_total"] / max(1.0, float(r["sent_total"])))
            if i < repeats - 1:
                print("DEBUG: Cooling down between repeats...", flush=True)
                time.sleep(5.0)
    finally:
        if gc_was_enabled:
            gc.enable()

    out_dir = os.path.join(out_root, "bridge_eval", run_id)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "socket_server_net_telemetry.json")

    payload = {
        "metadata": {
            "run_id": run_id,
            "timestamp": time.time(),
            "mode": "client",
            "api": api,
            "server": {"host": server_host, "port": port},
            "conns": conns,
            "payload_bytes": payload_bytes,
            "warmup_msgs_per_conn": warmup_msgs_per_conn,
            "msgs_per_conn": msgs_per_conn,
            "rate_hz_per_conn": rate_hz,
            "repeats": repeats,
            "timeout_s": timeout_s,
            "client_platform": _platform.platform(),
            "client_python": sys.version,
            "client_uname": " ".join(_platform.uname()),
            "server_handshake_sample": handshake_sample,
            "gc_disabled": True,
        },
        "results": [
            {
                "api": api,
                "repeats": repeats,
                "conns": conns,
                "payload_bytes": payload_bytes,
                "warmup_msgs_per_conn": warmup_msgs_per_conn,
                "msgs_per_conn": msgs_per_conn,
                "rate_hz_per_conn": rate_hz,
                "drop_rate": _median_iqr(drop_samples),
                "throughput_msgs_per_s": _median_iqr(thr_samples),
                "rtt": {
                    "p50_ns": _median_iqr(p50_samples),
                    "p99_ns": _median_iqr(p99_samples),
                    "p999_ns": _median_iqr(p999_samples),
                },
            }
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"Wrote: {out_path}", flush=True)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paper 09: two-host socket sustained-load benchmark"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_srv = sub.add_parser(
        "server", help="run server (needs warm_logic_rs for set_* apis)"
    )
    p_srv.add_argument("--run-id", default="paper09_socket_server_net_server")
    p_srv.add_argument(
        "--api", required=True, choices=["recv_only", "set_bytesvec", "set_vec"]
    )
    p_srv.add_argument("--bind-host", default="0.0.0.0")
    p_srv.add_argument("--port", type=int, default=8080)
    p_srv.add_argument("--conns", type=int, default=16)
    p_srv.add_argument("--payload-bytes", type=int, default=100_000)
    p_srv.add_argument("--repeats", type=int, default=5)
    p_srv.add_argument("--timeout-s", type=float, default=120.0)

    p_cli = sub.add_parser(
        "client", help="run clients + emit telemetry (no warm_logic_rs needed)"
    )
    p_cli.add_argument("--run-id", default="paper09_socket_server_net_client")
    p_cli.add_argument("--out-root", default="out")
    p_cli.add_argument(
        "--api", required=True, choices=["recv_only", "set_bytesvec", "set_vec"]
    )
    p_cli.add_argument("--server-host", required=True)
    p_cli.add_argument("--port", type=int, default=8080)
    p_cli.add_argument("--conns", type=int, default=16)
    p_cli.add_argument("--payload-bytes", type=int, default=100_000)
    p_cli.add_argument("--warmup-msgs-per-conn", type=int, default=50)
    p_cli.add_argument("--msgs-per-conn", type=int, default=2000)
    p_cli.add_argument("--rate-hz", type=float, default=50.0)
    p_cli.add_argument("--repeats", type=int, default=5)
    p_cli.add_argument("--timeout-s", type=float, default=180.0)

    args = parser.parse_args()

    if args.cmd == "server":
        _server_run(
            run_id=args.run_id,
            api=args.api,
            bind_host=args.bind_host,
            port=args.port,
            conns=args.conns,
            payload_bytes=args.payload_bytes,
            repeats=args.repeats,
            timeout_s=args.timeout_s,
        )
        return

    if args.cmd == "client":
        _client_run(
            run_id=args.run_id,
            api=args.api,
            server_host=args.server_host,
            port=args.port,
            conns=args.conns,
            payload_bytes=args.payload_bytes,
            warmup_msgs_per_conn=args.warmup_msgs_per_conn,
            msgs_per_conn=args.msgs_per_conn,
            rate_hz=args.rate_hz,
            repeats=args.repeats,
            timeout_s=args.timeout_s,
            out_root=args.out_root,
        )
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        raise
