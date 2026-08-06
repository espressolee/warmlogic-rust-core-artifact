#!/usr/bin/env python3
"""
Paper 09: FastAPI+uvicorn ASGI app used by eval_paper09_fastapi_server_load.py.

This is intentionally minimal:
  - no Pydantic models
  - no JSON parsing
  - request bodies are read as raw bytes and forwarded to SovereignKV

Endpoints:
  - GET  /_identity     : returns a small JSON identity record (sanity/debug)
  - POST /recv_only     : read body, return 8-byte seq
  - POST /set_bytesvec  : read body, kv.set_bytesvec(key, body), return 8-byte seq
  - POST /set_vec       : read body, kv.set_vec(key, body), return 8-byte seq

Body format: 16-byte header (seq:uint64, send_ts_ns:uint64) + filler bytes.
"""

from __future__ import annotations

import os
import struct
import sys
from typing import Any

from fastapi import FastAPI, Request, Response

import warm_logic_rs


BODY_HDR_STRUCT = struct.Struct("!QQ")  # seq, send_ts_ns
SEQ_STRUCT = struct.Struct("!Q")  # seq


app = FastAPI()

_kv = warm_logic_rs.SovereignKV()
_keys = [f"k{i}" for i in range(256)]
for _k in _keys:
    _kv.set_bytes(_k, b"x")


def _key_for(*, seq: int, client_port: int) -> str:
    # Reduce artificial lock contention: otherwise, all conns tend to hammer the same small key prefix.
    return _keys[(seq + client_port) % len(_keys)]


@app.get("/_identity")
async def identity() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "python": sys.version,
        "platform": sys.platform,
        "warm_logic_rs": getattr(warm_logic_rs, "__file__", None),
    }


async def _handle(request: Request, api: str) -> Response:
    body = await request.body()
    if len(body) < BODY_HDR_STRUCT.size:
        return Response(status_code=400, content=b"")

    seq, _send_ts = BODY_HDR_STRUCT.unpack_from(body, 0)
    client_port = int(getattr(getattr(request, "client", None), "port", 0) or 0)
    key = _key_for(seq=int(seq), client_port=client_port)

    if api == "recv_only":
        pass
    elif api == "set_bytesvec":
        _kv.set_bytesvec(key, body)
    elif api == "set_vec":
        _kv.set_vec(key, body)
    else:
        return Response(status_code=404, content=b"")

    return Response(
        status_code=200,
        media_type="application/octet-stream",
        content=SEQ_STRUCT.pack(int(seq)),
    )


@app.post("/recv_only")
async def recv_only(request: Request) -> Response:
    return await _handle(request, "recv_only")


@app.post("/set_bytesvec")
async def set_bytesvec(request: Request) -> Response:
    return await _handle(request, "set_bytesvec")


@app.post("/set_vec")
async def set_vec(request: Request) -> Response:
    return await _handle(request, "set_vec")

