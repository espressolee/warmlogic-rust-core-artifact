#!/usr/bin/env python3
"""
Paper 09: auto-generate tables in paper.md from telemetry.
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path


def _fmt_cell_ns(ns: float, *, bold: bool = False) -> str:
    if ns >= 1_000_000:  # ms
        s = f"{ns / 1_000_000:.1f} ms"
    elif ns >= 1_000:  # µs
        s = f"{ns / 1_000:.0f} µs"
    else:
        s = f"{ns:.1f} ns"
    return f"**{s}**" if bold else s


def _fmt_iqr_ns(iqr_ns: float, *, main_ns: float) -> str:
    if 0.0 < iqr_ns < 1.0:
        return "<1 ns"

    # Keep parentheses readable by avoiding ns in the µs/ms regimes.
    if main_ns >= 1_000_000:  # ms-scale main
        if iqr_ns >= 1_000_000:
            return f"{iqr_ns / 1_000_000:.1f} ms"
        us = iqr_ns / 1_000
        if us >= 1.0:
            return f"{us:.0f} µs"
        if us >= 0.1:
            return f"{us:.1f} µs"
        return f"{iqr_ns:.0f} ns"

    if main_ns >= 1_000:  # µs-scale main
        us = iqr_ns / 1_000
        if us >= 1.0:
            return f"{us:.0f} µs"
        if us >= 0.1:
            return f"{us:.1f} µs"
        return f"{iqr_ns:.0f} ns"

    return _fmt_cell_ns(iqr_ns, bold=False)


def _fmt_cell_with_iqr_ns(ns: float, iqr_ns: float, *, bold: bool = False) -> str:
    main = _fmt_cell_ns(ns, bold=bold)
    return f"{main} ({_fmt_iqr_ns(iqr_ns, main_ns=ns)})"


def _render_table_1(*, combined: dict) -> str:
    kib = 1024
    on_size = 10_000_000
    rows: list[tuple[str, int, bool]] = [
        ("Null (PyBytes)", kib, False),
        ("Null (PyBuffer)", kib, False),
        ("Acquire buffer (len_bytes)", kib, False),
        ("Copy (PyBytes to_vec)", on_size, False),
        ("Copy (Buffer to_vec)", on_size, False),
        ("Copy (Vec<u8> arg)", on_size, False),
        ("Copy (Sequence to Vec<u8>)", on_size, True),
        ("Consume (PyBytes)", on_size, False),
    ]

    def _host_label_base(host: dict) -> str:
        md = host.get("metadata", {}) or {}
        cpu = str(md.get("cpu", "")).strip() or "unknown"
        platform = str(md.get("platform", "")).strip()

        if platform.startswith("macOS"):
            return f"macOS ({cpu})"
        if platform.startswith("Linux"):
            suffix = ""
            # Heuristics to keep labels short but informative.
            if "linuxkit" in platform:
                suffix = ", Docker"
            elif "-gcp-" in platform or platform.endswith("-gcp"):
                suffix = ", GCP VM"
            return f"Linux ({cpu}{suffix})"

        os_name = platform.split("-", 1)[0] if platform else "UnknownOS"
        return f"{os_name} ({cpu})"

    hosts = combined["hosts"]
    base_labels = [_host_label_base(h) for h in hosts]
    label_counts = Counter(base_labels)
    label_seen: dict[str, int] = defaultdict(int)

    labels: list[str] = []
    for base, host in zip(base_labels, hosts):
        if label_counts[base] == 1:
            labels.append(base)
            continue

        label_seen[base] += 1
        md = host.get("metadata", {}) or {}
        run_id = str(md.get("run_id", "")).strip()

        # Prefer a stable short suffix (e.g., vm1/vm2/vm3) when available.
        suffix = ""
        if run_id:
            m = re.search(r"(?:^|_)(vm\d+)(?:_|$)", run_id)
            if m:
                suffix = m.group(1)
        if not suffix:
            suffix = f"run{label_seen[base]}"

        labels.append(f"{base} [{suffix}]")

    header = "| Path | Size | " + " | ".join(labels) + " |"
    sep = "| :--- | ---: | " + " | ".join(":---:" for _ in hosts) + " |"
    out: list[str] = [header, sep]

    for path, size, bold in rows:
        key = f"{path}|{size}"
        row_data = combined["by_key"].get(key)
        if not row_data:
            continue
        cells = []
        h_to_stats = {
            r["host"]: (float(r["p50_median"]), float(r.get("p50_iqr", 0.0)))
            for r in row_data["per_host"]
        }
        for h in hosts:
            val, iqr = h_to_stats.get(h["host"], (0.0, 0.0))
            cells.append(_fmt_cell_with_iqr_ns(val, iqr, bold=bold))
        size_label = "1KiB" if size == kib else "10MB"
        out.append(
            f"| {path:<27} | {size_label:>4} | "
            + " | ".join(f"{c:>12}" for c in cells)
            + " |"
        )
    return "\n".join(out) + "\n"


def _load_e2e(path: Path) -> dict[tuple[int, str], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[int, str], dict] = {}
    for row in data["results"]:
        out[(int(row["message_size_bytes"]), str(row["variant"]))] = row
    return out


def _render_table_2(*, e2e: dict) -> str:
    sizes = [100, 1000, 10_000, 100_000]
    out: list[str] = []
    out.append(
        "| Message size | view (µs) | vec (µs) | sequence (µs) | sequence / view |"
    )
    out.append("| ---: | ---: | ---: | ---: | ---: |")
    for size in sizes:
        view_row = e2e[(size, "view")]["pipeline"]
        vec_row = e2e[(size, "vec")]["pipeline"]
        seq_row = e2e[(size, "sequence")]["pipeline"]

        view_us = float(view_row["median"]) / 1000.0
        vec_us = float(vec_row["median"]) / 1000.0
        seq_us = float(seq_row["median"]) / 1000.0

        view_iqr_us = float(view_row.get("iqr", 0.0)) / 1000.0
        vec_iqr_us = float(vec_row.get("iqr", 0.0)) / 1000.0
        seq_iqr_us = float(seq_row.get("iqr", 0.0)) / 1000.0

        ratio = seq_us / view_us if view_us > 0 else float("nan")
        size_label = (
            f"{size} B"
            if size < 1000
            else (
                f"{size // 1000} KB" if size < 1_000_000 else f"{size // 1_000_000} MB"
            )
        )
        out.append(
            f"| {size_label:>6} | {view_us:.2f} ({view_iqr_us:.2f}) | {vec_us:.2f} ({vec_iqr_us:.2f}) | {seq_us:.2f} ({seq_iqr_us:.2f}) | {ratio:.2f}× |"
        )
    return "\n".join(out) + "\n"


def _load_vec_u8_variants(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["input"]): row for row in data["aggregate"]}


def _load_vec_u8_semantics(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_vec_u8_semantics_matrix(data: dict) -> dict[tuple[str, str], dict[str, object]]:
    """
    Returns a mapping (api, variant) -> {expected: str, ok: bool}.

    We AND `ok` across sizes to get a single "this (api, variant) passed" bit for the report.
    """

    out: dict[tuple[str, str], dict[str, object]] = {}
    for row in data.get("cases", []) or []:
        api = str(row.get("api") or "")
        variant = str(row.get("variant") or "")
        expected = str(row.get("expected") or "")
        ok = bool(row.get("ok"))
        if not (api and variant and expected):
            continue

        key = (api, variant)
        if key not in out:
            out[key] = {"expected": expected, "ok": ok}
            continue

        prev_expected = str(out[key]["expected"])
        if prev_expected != expected:
            raise ValueError(
                f"inconsistent expected outcome in semantics JSON for (api={api}, variant={variant}): "
                f"{prev_expected!r} vs {expected!r}"
            )
        out[key]["ok"] = bool(out[key]["ok"]) and ok

    return out


def _render_table_22_vec_u8_semantics(*, stock: dict, patched: dict) -> str:
    s_meta = stock.get("metadata", {}) or {}
    p_meta = patched.get("metadata", {}) or {}

    variants = list(s_meta.get("variants") or [])
    if not variants:
        variants = list(p_meta.get("variants") or [])

    if not variants:
        return _render_table_22_na()

    s = _extract_vec_u8_semantics_matrix(stock)
    p = _extract_vec_u8_semantics_matrix(patched)

    apis = [
        ("SovereignKV.set_bytes", "`set_bytes` (PyBytes)"),
        ("SovereignKV.set_bytesvec", "`set_bytesvec` (BytesVec)"),
        ("SovereignKV.set_vec", "`set_vec` (`Vec<u8>`)"),
    ]

    def _cell(api: str, variant: str) -> str:
        s_row = s.get((api, variant))
        p_row = p.get((api, variant))
        if not s_row or not p_row:
            return "N/A"

        s_expected = str(s_row.get("expected") or "")
        p_expected = str(p_row.get("expected") or "")
        if s_expected != p_expected:
            return "DIFF"

        if not (bool(s_row.get("ok")) and bool(p_row.get("ok"))):
            return "FAIL"

        if s_expected == "accept":
            return "Accept"
        if s_expected == "reject":
            return "Reject"
        return "N/A"

    out: list[str] = []
    out.append("| Input | " + " | ".join([label for _, label in apis]) + " |")
    out.append("|---|---:|---:|---:|")
    for variant in variants:
        out.append(
            "| "
            + variant
            + " | "
            + " | ".join(_cell(api, variant) for api, _ in apis)
            + " |"
        )
    return "\n".join(out) + "\n"


def _render_table_22_na() -> str:
    out: list[str] = []
    out.append("| Input | `set_bytes` (PyBytes) | `set_bytesvec` (BytesVec) | `set_vec` (`Vec<u8>`) |")
    out.append("|---|---:|---:|---:|")
    out.append(
        "| N/A | N/A (run `python3 scripts/eval/verify_paper09_vec_u8_semantics.py` under both stock + patched wheels) | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _render_table_3(*, stock: dict[str, dict], patched: dict[str, dict]) -> str:
    order = [
        "bytes",
        "bytearray",
        "memoryview(bytes)",
        "memoryview(bytearray)",
        "array('B')",
    ]
    out: list[str] = []
    out.append(
        "| Input | Stock p50 | Stock p99 | Patched p50 | Patched p99 | Speedup (p50) | Speedup (p99) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|")
    for name in order:
        s = stock.get(name)
        p = patched.get(name)
        if not s or not p:
            continue
        s_p50 = float(s["p50_median"])
        s_p50_iqr = float(s.get("p50_iqr", 0.0))
        s_p99 = float(s["p99_median"])
        s_p99_iqr = float(s.get("p99_iqr", 0.0))
        p_p50 = float(p["p50_median"])
        p_p50_iqr = float(p.get("p50_iqr", 0.0))
        p_p99 = float(p["p99_median"])
        p_p99_iqr = float(p.get("p99_iqr", 0.0))
        speedup_p50 = (s_p50 / p_p50) if p_p50 > 0 else float("nan")
        speedup_p99 = (s_p99 / p_p99) if p_p99 > 0 else float("nan")
        out.append(
            f"| {name} | {_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | {_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_p50_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} | {speedup_p50:,.0f}× | {speedup_p99:,.0f}× |"
        )
    return "\n".join(out) + "\n"


def _replace_block(text: str, *, begin: str, end: str, replacement: str) -> str:
    lines = text.splitlines()
    try:
        i0 = lines.index(begin)
        i1 = lines.index(end)
    except ValueError as e:
        raise RuntimeError(f"Missing marker: {e}") from e
    if i1 <= i0:
        raise RuntimeError(f"Bad marker order: {begin} before {end}")
    new_lines = lines[: i0 + 1] + replacement.rstrip("\n").splitlines() + lines[i1:]
    return "\n".join(new_lines).rstrip() + "\n"


def _load_sovkv(path: Path) -> dict[tuple[str, str], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict] = {}
    for row in data["results"]:
        out[(str(row["op"]), str(row["api"]))] = row
    return out


def _render_table_4(
    *, stock: dict[tuple[str, str], dict], patched: dict[tuple[str, str], dict]
) -> str:
    rows = [
        ("set", "set_bytes", "SET (set_bytes)"),
        ("set", "set_bytesvec", "SET (set_bytesvec)"),
        ("set", "set_vec", "SET (set_vec / Vec<u8> arg)"),
        ("get", "get_bytes", "GET (get_bytes)"),
    ]

    out: list[str] = []
    out.append(
        "| Operation | Stock p50 | Stock p99 | Patched p50 | Patched p99 | Speedup (p50) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|")

    for op, api, label in rows:
        s = stock.get((op, api))
        p = patched.get((op, api))
        if not s or not p:
            continue
        s_p50 = float(s["p50_ns"]["median"])
        s_p50_iqr = float(s["p50_ns"].get("iqr", 0.0))
        s_p99 = float(s["p99_ns"]["median"])
        s_p99_iqr = float(s["p99_ns"].get("iqr", 0.0))

        p_p50 = float(p["p50_ns"]["median"])
        p_p50_iqr = float(p["p50_ns"].get("iqr", 0.0))
        p_p99 = float(p["p99_ns"]["median"])
        p_p99_iqr = float(p["p99_ns"].get("iqr", 0.0))

        speedup = (s_p50 / p_p50) if p_p50 > 0 else float("nan")
        out.append(
            f"| {label} | {_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | {_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_p50_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} | {speedup:,.1f}× |"
        )
    return "\n".join(out) + "\n"


def _load_socket_kv(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["api"]): row for row in data["results"]}


def _render_table_5(*, stock: dict[str, dict], patched: dict[str, dict]) -> str:
    rows = [
        ("recv_only", "E2E (recv_only)"),
        ("set_bytesvec", "E2E (recv → set_bytesvec)"),
        ("set_vec", "E2E (recv → set_vec / Vec<u8> arg)"),
    ]

    out: list[str] = []
    out.append(
        "| Operation | Stock p50 | Stock p99 | Patched p50 | Patched p99 | Speedup (p50) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|")

    for api, label in rows:
        s = stock.get(api)
        p = patched.get(api)
        if not s or not p:
            continue

        s_p50 = float(s["e2e"]["p50_ns"]["median"])
        s_p50_iqr = float(s["e2e"]["p50_ns"].get("iqr", 0.0))
        s_p99 = float(s["e2e"]["p99_ns"]["median"])
        s_p99_iqr = float(s["e2e"]["p99_ns"].get("iqr", 0.0))

        p_p50 = float(p["e2e"]["p50_ns"]["median"])
        p_p50_iqr = float(p["e2e"]["p50_ns"].get("iqr", 0.0))
        p_p99 = float(p["e2e"]["p99_ns"]["median"])
        p_p99_iqr = float(p["e2e"]["p99_ns"].get("iqr", 0.0))

        speedup = (s_p50 / p_p50) if p_p50 > 0 else float("nan")
        out.append(
            f"| {label} | {_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | {_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_p50_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} | {speedup:,.1f}× |"
        )

    return "\n".join(out) + "\n"


def _load_pybind11_case(path: Path) -> dict[tuple[str, str], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict] = {}
    for row in data["aggregate"]:
        out[(str(row["input"]), str(row["mode"]))] = row
    return out


def _render_table_6(*, data: dict[tuple[str, str], dict]) -> str:
    inputs = ["bytearray", "memoryview(bytes)"]
    out: list[str] = []
    out.append(
        "| Input | vector_arg p50 | vector_arg p99 | buffer_copy p50 | buffer_copy p99 | Slowdown (p50) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|")
    for inp in inputs:
        v = data.get((inp, "vector_arg"))
        c = data.get((inp, "buffer_copy"))
        if not v or not c:
            continue

        v_p50 = float(v["p50_median"])
        v_p50_iqr = float(v.get("p50_iqr", 0.0))
        v_p99 = float(v["p99_median"])
        v_p99_iqr = float(v.get("p99_iqr", 0.0))

        c_p50 = float(c["p50_median"])
        c_p50_iqr = float(c.get("p50_iqr", 0.0))
        c_p99 = float(c["p99_median"])
        c_p99_iqr = float(c.get("p99_iqr", 0.0))

        slowdown = (v_p50 / c_p50) if c_p50 > 0 else float("nan")
        out.append(
            f"| {inp} | {_fmt_cell_with_iqr_ns(v_p50, v_p50_iqr)} | {_fmt_cell_with_iqr_ns(v_p99, v_p99_iqr)} | {_fmt_cell_with_iqr_ns(c_p50, c_p50_iqr)} | {_fmt_cell_with_iqr_ns(c_p99, c_p99_iqr)} | {slowdown:,.0f}× |"
        )
    return "\n".join(out) + "\n"


def _render_table_6_na() -> str:
    out: list[str] = []
    out.append(
        "| Input | vector_arg p50 | vector_arg p99 | buffer_copy p50 | buffer_copy p99 | Slowdown (p50) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|")
    out.append(
        "| bytearray | N/A (run `python3 scripts/eval/eval_paper09_pybind11_case.py`) | N/A | N/A | N/A | N/A |"
    )
    out.append(
        "| memoryview(bytes) | N/A (run `python3 scripts/eval/eval_paper09_pybind11_case.py`) | N/A | N/A | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _load_cython_case(path: Path) -> dict[tuple[str, str], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict] = {}
    for row in data.get("aggregate", []):
        out[(str(row["input"]), str(row["mode"]))] = row
    return out


def _render_table_15(*, data: dict[tuple[str, str], dict]) -> str:
    inputs = ["bytes", "bytearray", "memoryview(bytes)"]
    out: list[str] = []
    out.append(
        "| Input | vector_arg p50 | vector_arg p99 | buffer_copy p50 | buffer_copy p99 | Slowdown (p50) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|")
    for inp in inputs:
        v = data.get((inp, "vector_arg"))
        c = data.get((inp, "buffer_copy"))
        if not c:
            continue

        c_p50 = float(c["p50_median"])
        c_p50_iqr = float(c.get("p50_iqr", 0.0))
        c_p99 = float(c["p99_median"])
        c_p99_iqr = float(c.get("p99_iqr", 0.0))

        if v:
            v_p50 = float(v["p50_median"])
            v_p50_iqr = float(v.get("p50_iqr", 0.0))
            v_p99 = float(v["p99_median"])
            v_p99_iqr = float(v.get("p99_iqr", 0.0))
            slowdown = (v_p50 / c_p50) if c_p50 > 0 else float("nan")
            out.append(
                f"| {inp} | {_fmt_cell_with_iqr_ns(v_p50, v_p50_iqr)} | {_fmt_cell_with_iqr_ns(v_p99, v_p99_iqr)} | "
                f"{_fmt_cell_with_iqr_ns(c_p50, c_p50_iqr)} | {_fmt_cell_with_iqr_ns(c_p99, c_p99_iqr)} | {slowdown:,.0f}× |"
            )
        else:
            out.append(
                f"| {inp} | N/A | N/A | {_fmt_cell_with_iqr_ns(c_p50, c_p50_iqr)} | {_fmt_cell_with_iqr_ns(c_p99, c_p99_iqr)} | N/A |"
            )
    return "\n".join(out) + "\n"


def _render_table_15_na() -> str:
    out: list[str] = []
    out.append(
        "| Input | vector_arg p50 | vector_arg p99 | buffer_copy p50 | buffer_copy p99 | Slowdown (p50) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|")
    out.append("| N/A | N/A (run `eval_paper09_cython_case.py`) | N/A | N/A | N/A | N/A |")
    return "\n".join(out) + "\n"


def _load_socket_mux_kv(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["api"]): row for row in data["results"]}


def _load_capi_anchor(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["path"]): row for row in data["aggregate"]}


def _render_table_8(*, data: dict[str, dict]) -> str:
    order = [
        "Copy (C-API PyBytes clone)",
        "Copy (C-API buffer clone)",
        "Copy (PyBytes to_vec)",
        "Copy (Buffer to_vec)",
        "Copy (BytesVec arg)",
        "Copy (Vec<u8> arg)",
    ]
    out: list[str] = []
    out.append("| Path | p50 | p99 |")
    out.append("| :--- | ---: | ---: |")
    for name in order:
        row = data.get(name)
        if not row:
            continue
        p50 = float(row["p50_median"])
        p50_iqr = float(row.get("p50_iqr", 0.0))
        p99 = float(row["p99_median"])
        p99_iqr = float(row.get("p99_iqr", 0.0))
        out.append(
            f"| {name} | {_fmt_cell_with_iqr_ns(p50, p50_iqr)} | {_fmt_cell_with_iqr_ns(p99, p99_iqr)} |"
        )
    return "\n".join(out) + "\n"


def _render_table_8_na() -> str:
    out: list[str] = []
    out.append("| Path | p50 | p99 |")
    out.append("| :--- | ---: | ---: |")
    out.append(
        "| Copy (C-API PyBytes clone) | N/A (run `python3 -m pip install -e scripts/eval/capi_baseline` + `python3 scripts/eval/eval_paper09_capi_anchor.py`) | N/A |"
    )
    return "\n".join(out) + "\n"


def _render_table_7(*, stock: dict[str, dict], patched: dict[str, dict]) -> str:
    rows = [
        ("recv_only", "recv_only"),
        ("set_bytesvec", "set_bytesvec"),
        ("set_vec", "set_vec"),
    ]
    out: list[str] = []
    out.append(
        "| API | Stock throughput | Patched throughput | Stock e2e p50 | Patched e2e p50 | Stock e2e p99 | Patched e2e p99 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|")

    for api, label in rows:
        s = stock.get(api)
        p = patched.get(api)
        if not s or not p:
            continue

        s_thr = float(s["throughput_msgs_per_s"]["median"])
        s_thr_iqr = float(s["throughput_msgs_per_s"].get("iqr", 0.0))
        p_thr = float(p["throughput_msgs_per_s"]["median"])
        p_thr_iqr = float(p["throughput_msgs_per_s"].get("iqr", 0.0))

        s_p50 = float(s["e2e"]["p50_ns"]["median"])
        s_p50_iqr = float(s["e2e"]["p50_ns"].get("iqr", 0.0))
        p_p50 = float(p["e2e"]["p50_ns"]["median"])
        p_p50_iqr = float(p["e2e"]["p50_ns"].get("iqr", 0.0))

        s_p99 = float(s["e2e"]["p99_ns"]["median"])
        s_p99_iqr = float(s["e2e"]["p99_ns"].get("iqr", 0.0))
        p_p99 = float(p["e2e"]["p99_ns"]["median"])
        p_p99_iqr = float(p["e2e"]["p99_ns"].get("iqr", 0.0))

        def _fmt_thr(v: float, iqr: float) -> str:
            return f"{v:,.0f} ({iqr:,.0f})"

        out.append(
            f"| {label} | {_fmt_thr(s_thr, s_thr_iqr)} | {_fmt_thr(p_thr, p_thr_iqr)} | {_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_p50_iqr)} | {_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} |"
        )

    return "\n".join(out) + "\n"


def _load_python_sweep(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("results", []))


def _render_table_9(*, rows: list[dict]) -> str:
    out: list[str] = []
    out.append(
        "| CPython | Stock `Vec<u8>` p50 | Patched `Vec<u8>` p50 | Speedup (p50) |"
    )
    out.append("|---:|---:|---:|---:|")
    for r in rows:
        pyver = str(r.get("python_version", ""))
        s = r.get("stock", {}) or {}
        p = r.get("patched", {}) or {}
        s_p50 = float(s.get("p50_median", 0.0))
        s_iqr = float(s.get("p50_iqr", 0.0))
        p_p50 = float(p.get("p50_median", 0.0))
        p_iqr = float(p.get("p50_iqr", 0.0))
        speedup = (s_p50 / p_p50) if p_p50 > 0 else float("nan")
        out.append(
            f"| {pyver} | {_fmt_cell_with_iqr_ns(s_p50, s_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_iqr)} | {speedup:,.0f}× |"
        )
    return "\n".join(out) + "\n"


def _render_table_9_na() -> str:
    out: list[str] = []
    out.append(
        "| CPython | Stock `Vec<u8>` p50 | Patched `Vec<u8>` p50 | Speedup (p50) |"
    )
    out.append("|---:|---:|---:|---:|")
    out.append(
        "| N/A | N/A (run `python3 scripts/eval/eval_paper09_python_sweep.py`) | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _load_gil_tradeoff(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in data.get("aggregate", []):
        out[str(row["path"])] = row
    return out


def _render_table_10(*, data: dict[str, dict]) -> str:
    order = [
        "Sum (PyBytes, hold GIL)",
        "Sum (PyBytes, allow_threads)",
        "Sum (bytearray buffer, hold GIL)",
        "Sum (bytearray buffer, allow_threads; copy+sum)",
    ]
    out: list[str] = []
    out.append("| Pattern | p50 | p99 |")
    out.append("| :--- | ---: | ---: |")
    for name in order:
        r = data.get(name)
        if not r:
            continue
        p50 = float(r.get("p50_median", 0.0))
        p50_iqr = float(r.get("p50_iqr", 0.0))
        p99 = float(r.get("p99_median", 0.0))
        p99_iqr = float(r.get("p99_iqr", 0.0))
        out.append(
            f"| {name} | {_fmt_cell_with_iqr_ns(p50, p50_iqr)} | {_fmt_cell_with_iqr_ns(p99, p99_iqr)} |"
        )
    return "\n".join(out) + "\n"


def _render_table_10_na() -> str:
    out: list[str] = []
    out.append("| Pattern | p50 | p99 |")
    out.append("| :--- | ---: | ---: |")
    out.append(
        "| N/A | N/A (run `python3 scripts/eval/eval_paper09_gil_tradeoff.py`) | N/A |"
    )
    return "\n".join(out) + "\n"


def _load_gil_concurrency(path: Path) -> dict[tuple[str, int], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, int], dict] = {}
    for row in data.get("results", []):
        key = (str(row.get("pattern", "")), int(row.get("threads", 0)))
        out[key] = row
    return out


def _render_table_11(
    *, stock: dict[tuple[str, int], dict], patched: dict[tuple[str, int], dict]
) -> str:
    patterns = [
        "Sum (PyBytes, allow_threads)",
        "Sum (BytesVec, allow_threads)",
        "Sum (Vec<u8> arg, allow_threads)",
    ]
    threads_order = [1, 8]

    def _fmt_thr(v: float, iqr: float) -> str:
        return f"{v:,.0f} ({iqr:,.0f})"

    out: list[str] = []
    out.append(
        "| Pattern | Threads | Stock throughput | Patched throughput | Stock call p99 | Patched call p99 | Stock call p999 | Patched call p999 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|")

    for pat in patterns:
        for th in threads_order:
            s = stock.get((pat, th))
            p = patched.get((pat, th))
            if not s or not p:
                continue

            s_thr = float(s["throughput_calls_per_s"]["median"])
            s_thr_iqr = float(s["throughput_calls_per_s"].get("iqr", 0.0))
            p_thr = float(p["throughput_calls_per_s"]["median"])
            p_thr_iqr = float(p["throughput_calls_per_s"].get("iqr", 0.0))

            s_p99 = float(s["call_p99_ns"]["median"])
            s_p99_iqr = float(s["call_p99_ns"].get("iqr", 0.0))
            p_p99 = float(p["call_p99_ns"]["median"])
            p_p99_iqr = float(p["call_p99_ns"].get("iqr", 0.0))

            s_p999 = float(s["call_p999_ns"]["median"])
            s_p999_iqr = float(s["call_p999_ns"].get("iqr", 0.0))
            p_p999 = float(p["call_p999_ns"]["median"])
            p_p999_iqr = float(p["call_p999_ns"].get("iqr", 0.0))

            out.append(
                f"| {pat} | {th} | {_fmt_thr(s_thr, s_thr_iqr)} | {_fmt_thr(p_thr, p_thr_iqr)} | "
                f"{_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} | "
                f"{_fmt_cell_with_iqr_ns(s_p999, s_p999_iqr)} | {_fmt_cell_with_iqr_ns(p_p999, p_p999_iqr)} |"
            )

    return "\n".join(out) + "\n"


def _render_table_11_na() -> str:
    out: list[str] = []
    out.append(
        "| Pattern | Threads | Stock throughput | Patched throughput | Stock call p99 | Patched call p99 | Stock call p999 | Patched call p999 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    out.append(
        "| N/A | N/A | N/A (run `eval_paper09_gil_concurrency.py` stock+patched) | N/A | N/A | N/A | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _load_socket_server_load(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _extract_socket_server_load(data)


def _extract_socket_server_load(data: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in data.get("results", []):
        api = str(row.get("api", ""))
        if api in out:
            raise ValueError(
                f"duplicate socket_server_load row for api={api}; "
                "did you accidentally pass a multi-rate (or otherwise non-aggregated) telemetry file?"
            )
        out[api] = row
    return out


def _load_json_from_pack(pack_path: Path, *, filename: str) -> dict:
    with tarfile.open(pack_path, "r:gz") as tf:
        names = tf.getnames()
        member = None
        for name in names:
            if Path(name).name == filename:
                member = tf.getmember(name)
                break
        if member is None:
            raise FileNotFoundError(f"{pack_path} does not contain {filename}")
        f = tf.extractfile(member)
        if f is None:
            raise ValueError(f"failed to read {member.name} from {pack_path}")
        return json.loads(f.read().decode("utf-8"))


def _load_socket_server_load_from_paper09_pack(
    pack_path: Path,
) -> tuple[dict[str, dict], dict[str, dict]]:
    stock = _load_json_from_pack(
        pack_path, filename="socket_server_load_telemetry_stock.json"
    )
    patched = _load_json_from_pack(
        pack_path, filename="socket_server_load_telemetry_patched.json"
    )
    return _extract_socket_server_load(stock), _extract_socket_server_load(patched)


def _render_table_12(*, stock: dict[str, dict], patched: dict[str, dict]) -> str:
    apis = ["recv_only", "set_bytesvec", "set_vec"]

    def _fmt_thr(v: float, iqr: float) -> str:
        return f"{v:,.0f} ({iqr:,.0f})"

    out: list[str] = []
    out.append(
        "| API | Stock throughput | Patched throughput | Stock RTT p50 | Patched RTT p50 | Stock RTT p99 | Patched RTT p99 | Stock RTT p999 | Patched RTT p999 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for api in apis:
        s = stock.get(api)
        p = patched.get(api)
        if not s or not p:
            continue

        s_thr = float(s["throughput_msgs_per_s"]["median"])
        s_thr_iqr = float(s["throughput_msgs_per_s"].get("iqr", 0.0))
        p_thr = float(p["throughput_msgs_per_s"]["median"])
        p_thr_iqr = float(p["throughput_msgs_per_s"].get("iqr", 0.0))

        s_p50 = float(s["rtt"]["p50_ns"]["median"])
        s_p50_iqr = float(s["rtt"]["p50_ns"].get("iqr", 0.0))
        p_p50 = float(p["rtt"]["p50_ns"]["median"])
        p_p50_iqr = float(p["rtt"]["p50_ns"].get("iqr", 0.0))

        s_p99 = float(s["rtt"]["p99_ns"]["median"])
        s_p99_iqr = float(s["rtt"]["p99_ns"].get("iqr", 0.0))
        p_p99 = float(p["rtt"]["p99_ns"]["median"])
        p_p99_iqr = float(p["rtt"]["p99_ns"].get("iqr", 0.0))

        s_p999 = float(s["rtt"]["p999_ns"]["median"])
        s_p999_iqr = float(s["rtt"]["p999_ns"].get("iqr", 0.0))
        p_p999 = float(p["rtt"]["p999_ns"]["median"])
        p_p999_iqr = float(p["rtt"]["p999_ns"].get("iqr", 0.0))

        out.append(
            f"| {api} | {_fmt_thr(s_thr, s_thr_iqr)} | {_fmt_thr(p_thr, p_thr_iqr)} | "
            f"{_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_p50_iqr)} | "
            f"{_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} | "
            f"{_fmt_cell_with_iqr_ns(s_p999, s_p999_iqr)} | {_fmt_cell_with_iqr_ns(p_p999, p_p999_iqr)} |"
        )

    return "\n".join(out) + "\n"


def _render_table_12_na() -> str:
    out: list[str] = []
    out.append(
        "| API | Stock throughput | Patched throughput | Stock RTT p50 | Patched RTT p50 | Stock RTT p99 | Patched RTT p99 | Stock RTT p999 | Patched RTT p999 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    out.append(
        "| N/A | N/A (run `eval_paper09_socket_server_load.py` stock+patched) | N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _render_table_16_na() -> str:
    out: list[str] = []
    out.append(
        "| API | Stock throughput | Patched throughput | Stock RTT p50 | Patched RTT p50 | Stock RTT p99 | Patched RTT p99 | Stock RTT p999 | Patched RTT p999 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    out.append(
        "| N/A | N/A (run `eval_paper09_http_server_load.py` stock+patched) | N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _render_table_18_na() -> str:
    out: list[str] = []
    out.append(
        "| API | Stock throughput | Patched throughput | Stock RTT p50 | Patched RTT p50 | Stock RTT p99 | Patched RTT p99 | Stock RTT p999 | Patched RTT p999 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    out.append(
        "| N/A | N/A (run `eval_paper09_fastapi_server_load.py` stock+patched) | N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _render_table_19_prevalence(*, data: dict) -> str:
    meta = data.get("metadata", {}) or {}
    agg = data.get("aggregate", {}) or {}
    src = meta.get("source", {}) or {}
    scan = meta.get("scan", {}) or {}

    ts = str(meta.get("timestamp_iso", "")).strip()
    selection = str(src.get("selection", "")).strip()
    limit = scan.get("limit")

    crates_scanned = int(agg.get("crates_scanned", 0) or 0)
    crates_with_exports = int(agg.get("crates_with_pyo3_exports", 0) or 0)
    crates_with_vec = int(agg.get("crates_with_vec_u8_arg", 0) or 0)

    pyfunction_total = int(agg.get("pyfunction_total", 0) or 0)
    pyfunction_with_vec = int(agg.get("pyfunction_with_vec_u8", 0) or 0)
    pymethod_total = int(agg.get("pymethod_total", 0) or 0)
    pymethod_with_vec = int(agg.get("pymethod_with_vec_u8", 0) or 0)

    def _ratio(n: int, d: int) -> str:
        if d <= 0:
            return "N/A"
        return f"{n:,} / {d:,} ({(n / d) * 100:.1f}%)"

    def _pct(n: int, d: int) -> str:
        if d <= 0:
            return "N/A"
        return f"{(n / d) * 100:.1f}%"

    out: list[str] = []
    out.append("| Metric | Value |")
    out.append("|---|---:|")
    out.append(f"| Snapshot (UTC) | {ts or 'N/A'} |")
    if selection:
        sel = selection
        if limit is not None:
            sel = f"{sel}; limit={int(limit)}"
        out.append(f"| Selection | {sel} |")
    out.append(f"| Unique crates scanned | {crates_scanned:,} |")
    out.append(f"| … with any PyO3 exports | {crates_with_exports:,} |")
    out.append(f"| … with exported `Vec<u8>` args | {crates_with_vec:,} |")
    out.append(
        f"| Hit rate (crate-level; among exporting crates) | {_ratio(crates_with_vec, crates_with_exports)} |"
    )
    out.append(f"| Exported `#[pyfunction]` signatures scanned | {pyfunction_total:,} |")
    out.append(
        f"| … with `Vec<u8>` arg | {pyfunction_with_vec:,} ({_pct(pyfunction_with_vec, pyfunction_total)}) |"
    )
    out.append(f"| Exported `#[pymethods]` signatures scanned | {pymethod_total:,} |")
    out.append(
        f"| … with `Vec<u8>` arg | {pymethod_with_vec:,} ({_pct(pymethod_with_vec, pymethod_total)}) |"
    )

    hit_crates: list[dict] = [
        c for c in (data.get("crates") or []) if c.get("has_vec_u8_arg")
    ]
    hit_crates.sort(key=lambda c: int(c.get("downloads") or 0), reverse=True)
    hit_names = [f"`{c.get('crate', '')}`" for c in hit_crates if c.get("crate")]
    if hit_names:
        out.append("")
        out.append(
            f"Example hit crates (top snapshot; n={len(hit_names)}): " + ", ".join(hit_names)
        )
    return "\n".join(out) + "\n"


def _render_table_19_na() -> str:
    out: list[str] = []
    out.append("| Metric | Value |")
    out.append("|---|---:|")
    out.append(
        "| N/A | N/A (run `python3 scripts/eval/scan_pyo3_vec_u8_prevalence.py --limit 500 --out out/bridge_eval/pyo3_vec_u8_prevalence/pyo3_vec_u8_prevalence_top500.json`) |"
    )
    return "\n".join(out) + "\n"


def _render_table_20_rust_strings_case(*, data: dict) -> str:
    variants = data.get("variants", {}) or {}
    stock = variants.get("stock", {}) or {}
    bytesvec = variants.get("bytesvec", {}) or {}

    def _index_by_size(v: dict) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for row in v.get("sizes", []) or []:
            size = int(row.get("size_bytes") or 0)
            if size:
                out[size] = row
        return out

    s_by_size = _index_by_size(stock)
    b_by_size = _index_by_size(bytesvec)
    sizes = sorted(set(s_by_size.keys()) & set(b_by_size.keys()))
    if not sizes:
        return _render_table_20_na()

    def _fmt_size(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.0f}MB"
        if n >= 1_000:
            return f"{n / 1_000:.0f}KB"
        return f"{n}B"

    out: list[str] = []
    out.append(
        "| Size | Stock p50 | BytesVec p50 | Speedup (p50) | Stock p99 | BytesVec p99 | Speedup (p99) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|")

    for size in sizes:
        s = s_by_size[size].get("summary", {}) or {}
        b = b_by_size[size].get("summary", {}) or {}

        s_p50 = float(s.get("p50_median") or 0.0)
        s_p50_iqr = float(s.get("p50_iqr") or 0.0)
        s_p99 = float(s.get("p99_median") or 0.0)
        s_p99_iqr = float(s.get("p99_iqr") or 0.0)

        b_p50 = float(b.get("p50_median") or 0.0)
        b_p50_iqr = float(b.get("p50_iqr") or 0.0)
        b_p99 = float(b.get("p99_median") or 0.0)
        b_p99_iqr = float(b.get("p99_iqr") or 0.0)

        speed_p50 = (s_p50 / b_p50) if (s_p50 > 0.0 and b_p50 > 0.0) else float("nan")
        speed_p99 = (s_p99 / b_p99) if (s_p99 > 0.0 and b_p99 > 0.0) else float("nan")

        out.append(
            f"| {_fmt_size(size)} | {_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | "
            f"{_fmt_cell_with_iqr_ns(b_p50, b_p50_iqr)} | {speed_p50:,.1f}× | "
            f"{_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(b_p99, b_p99_iqr)} | "
            f"{speed_p99:,.1f}× |"
        )

    return "\n".join(out) + "\n"


def _render_table_20_na() -> str:
    out: list[str] = []
    out.append(
        "| Size | Stock p50 | BytesVec p50 | Speedup (p50) | Stock p99 | BytesVec p99 | Speedup (p99) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|")
    out.append("| N/A | N/A (run `python3 scripts/eval/eval_paper09_rust_strings_case.py`) | N/A | N/A | N/A | N/A | N/A |")
    return "\n".join(out) + "\n"


def _render_table_21_vtracer_case(*, data: dict) -> str:
    variants = data.get("variants", {}) or {}
    stock = variants.get("stock", {}) or {}
    bytesvec = variants.get("bytesvec", {}) or {}

    def _index_by_size(v: dict) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for row in v.get("sizes", []) or []:
            size = int(row.get("size_bytes") or 0)
            if size:
                out[size] = row
        return out

    s_by_size = _index_by_size(stock)
    b_by_size = _index_by_size(bytesvec)
    sizes = sorted(set(s_by_size.keys()) & set(b_by_size.keys()))
    if not sizes:
        return _render_table_21_na()

    def _fmt_size(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.0f}MB"
        if n >= 1_000:
            return f"{n / 1_000:.0f}KB"
        return f"{n}B"

    out: list[str] = []
    out.append(
        "| Size | Stock p50 | BytesVec p50 | Speedup (p50) | Stock p99 | BytesVec p99 | Speedup (p99) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|")

    for size in sizes:
        s = s_by_size[size].get("summary", {}) or {}
        b = b_by_size[size].get("summary", {}) or {}

        s_p50 = float(s.get("p50_median") or 0.0)
        s_p50_iqr = float(s.get("p50_iqr") or 0.0)
        s_p99 = float(s.get("p99_median") or 0.0)
        s_p99_iqr = float(s.get("p99_iqr") or 0.0)

        b_p50 = float(b.get("p50_median") or 0.0)
        b_p50_iqr = float(b.get("p50_iqr") or 0.0)
        b_p99 = float(b.get("p99_median") or 0.0)
        b_p99_iqr = float(b.get("p99_iqr") or 0.0)

        speed_p50 = (s_p50 / b_p50) if (s_p50 > 0.0 and b_p50 > 0.0) else float("nan")
        speed_p99 = (s_p99 / b_p99) if (s_p99 > 0.0 and b_p99 > 0.0) else float("nan")

        out.append(
            f"| {_fmt_size(size)} | {_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | "
            f"{_fmt_cell_with_iqr_ns(b_p50, b_p50_iqr)} | {speed_p50:,.1f}× | "
            f"{_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(b_p99, b_p99_iqr)} | "
            f"{speed_p99:,.1f}× |"
        )

    return "\n".join(out) + "\n"


def _render_table_21_na() -> str:
    out: list[str] = []
    out.append(
        "| Size | Stock p50 | BytesVec p50 | Speedup (p50) | Stock p99 | BytesVec p99 | Speedup (p99) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|")
    out.append("| N/A | N/A (run `python3 scripts/eval/eval_paper09_vtracer_case.py`) | N/A | N/A | N/A | N/A | N/A |")
    return "\n".join(out) + "\n"


def _extract_socket_server_load_multirate(data: dict) -> dict[tuple[str, float], dict]:
    out: dict[tuple[str, float], dict] = {}
    for row in data.get("results", []):
        api = str(row.get("api", ""))
        rate = float(row.get("rate_hz_per_conn", 0.0))
        key = (api, rate)
        if key in out:
            raise ValueError(
                f"duplicate socket_server_net row for (api={api}, rate_hz_per_conn={rate}); "
                "fix the merge inputs (do not mix baseline + sweep, or repeated runs) before generating tables."
            )
        out[key] = row
    return out


def _render_table_14(*, stock_data: dict, patched_data: dict) -> str:
    # Check if multirate
    is_multi = stock_data.get("metadata", {}).get("mode") == "merged_multirate"

    if not is_multi:
        s = _extract_socket_server_load(stock_data)
        p = _extract_socket_server_load(patched_data)
        return _render_table_12(stock=s, patched=p)

    # Multirate rendering
    s_rows = _extract_socket_server_load_multirate(stock_data)
    p_rows = _extract_socket_server_load_multirate(patched_data)

    # In the paper table, stock vs patched must be the same experimental config
    # (otherwise it is not a controlled comparison).
    _STRICT = (
        "conns",
        "payload_bytes",
        "warmup_msgs_per_conn",
        "msgs_per_conn",
        "repeats",
    )

    # Identify all (api, rate) pairs
    keys = sorted(
        list(set(s_rows.keys()) | set(p_rows.keys())), key=lambda k: (k[0], k[1])
    )

    def _fmt_thr(v: float, iqr: float) -> str:
        return f"{v:,.0f} ({iqr:,.0f})"

    out: list[str] = []
    out.append(
        "| API | Rate (Hz) | Stock throughput | Patched throughput | Stock RTT p50 | Patched RTT p50 | Stock RTT p99 | Patched RTT p99 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|")

    for api, rate in keys:
        s = s_rows.get((api, rate))
        p = p_rows.get((api, rate))

        if not s or not p:
            continue

        s_cfg = {k: s.get(k) for k in _STRICT}
        p_cfg = {k: p.get(k) for k in _STRICT}
        if s_cfg != p_cfg:
            raise ValueError(
                f"socket_server_net multirate config mismatch for (api={api}, rate={rate:.0f}): "
                f"stock={s_cfg} patched={p_cfg}"
            )

        s_thr = float(s["throughput_msgs_per_s"]["median"])
        s_thr_iqr = float(s["throughput_msgs_per_s"].get("iqr", 0.0))
        p_thr = float(p["throughput_msgs_per_s"]["median"])
        p_thr_iqr = float(p["throughput_msgs_per_s"].get("iqr", 0.0))

        s_p50 = float(s["rtt"]["p50_ns"]["median"])
        s_p50_iqr = float(s["rtt"]["p50_ns"].get("iqr", 0.0))
        p_p50 = float(p["rtt"]["p50_ns"]["median"])
        p_p50_iqr = float(p["rtt"]["p50_ns"].get("iqr", 0.0))

        s_p99 = float(s["rtt"]["p99_ns"]["median"])
        s_p99_iqr = float(s["rtt"]["p99_ns"].get("iqr", 0.0))
        p_p99 = float(p["rtt"]["p99_ns"]["median"])
        p_p99_iqr = float(p["rtt"]["p99_ns"].get("iqr", 0.0))

        out.append(
            f"| {api} | {rate:.0f} | {_fmt_thr(s_thr, s_thr_iqr)} | {_fmt_thr(p_thr, p_thr_iqr)} | "
            f"{_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_p50_iqr)} | "
            f"{_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} |"
        )

    return "\n".join(out) + "\n"


def _render_table_14_multi(
    *,
    clouds: list[str],
    stock_by_cloud: dict[str, dict[str, dict]],
    patched_by_cloud: dict[str, dict[str, dict]],
) -> str:
    apis = ["recv_only", "set_bytesvec", "set_vec"]

    def _fmt_thr(v: float, iqr: float) -> str:
        return f"{v:,.0f} ({iqr:,.0f})"

    out: list[str] = []
    out.append(
        "| Cloud | API | Stock throughput | Patched throughput | Stock RTT p50 | Patched RTT p50 | Stock RTT p99 | Patched RTT p99 | Stock RTT p999 | Patched RTT p999 |"
    )
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for cloud in clouds:
        stock_raw = stock_by_cloud.get(cloud)
        patched_raw = patched_by_cloud.get(cloud)
        if not stock_raw or not patched_raw:
            continue

        stock = _extract_socket_server_load(stock_raw)
        patched = _extract_socket_server_load(patched_raw)

        cloud_label = cloud.upper()
        for api in apis:
            s = stock.get(api)
            p = patched.get(api)
            if not s or not p:
                continue

            s_thr = float(s["throughput_msgs_per_s"]["median"])
            s_thr_iqr = float(s["throughput_msgs_per_s"].get("iqr", 0.0))
            p_thr = float(p["throughput_msgs_per_s"]["median"])
            p_thr_iqr = float(p["throughput_msgs_per_s"].get("iqr", 0.0))

            s_p50 = float(s["rtt"]["p50_ns"]["median"])
            s_p50_iqr = float(s["rtt"]["p50_ns"].get("iqr", 0.0))
            p_p50 = float(p["rtt"]["p50_ns"]["median"])
            p_p50_iqr = float(p["rtt"]["p50_ns"].get("iqr", 0.0))

            s_p99 = float(s["rtt"]["p99_ns"]["median"])
            s_p99_iqr = float(s["rtt"]["p99_ns"].get("iqr", 0.0))
            p_p99 = float(p["rtt"]["p99_ns"]["median"])
            p_p99_iqr = float(p["rtt"]["p99_ns"].get("iqr", 0.0))

            s_p999 = float(s["rtt"]["p999_ns"]["median"])
            s_p999_iqr = float(s["rtt"]["p999_ns"].get("iqr", 0.0))
            p_p999 = float(p["rtt"]["p999_ns"]["median"])
            p_p999_iqr = float(p["rtt"]["p999_ns"].get("iqr", 0.0))

            out.append(
                f"| {cloud_label} | {api} | {_fmt_thr(s_thr, s_thr_iqr)} | {_fmt_thr(p_thr, p_thr_iqr)} | "
                f"{_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_p50_iqr)} | "
                f"{_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} | "
                f"{_fmt_cell_with_iqr_ns(s_p999, s_p999_iqr)} | {_fmt_cell_with_iqr_ns(p_p999, p_p999_iqr)} |"
            )

    return "\n".join(out) + "\n"


def _render_table_14_multi_na() -> str:
    out: list[str] = []
    out.append(
        "| Cloud | API | Stock throughput | Patched throughput | Stock RTT p50 | Patched RTT p50 | Stock RTT p99 | Patched RTT p99 | Stock RTT p999 | Patched RTT p999 |"
    )
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    out.append(
        "| N/A | N/A | N/A (run `eval_paper09_socket_server_net.py` + merge) | N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _render_table_14_na() -> str:
    out: list[str] = []
    out.append(
        "| API | Stock throughput | Patched throughput | Stock RTT p50 | Patched RTT p50 | Stock RTT p99 | Patched RTT p99 | Stock RTT p999 | Patched RTT p999 |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    out.append(
        "| N/A | N/A (run `eval_paper09_socket_server_net.py` + merge) | N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _render_table_13_x86(*, packs: list[Path]) -> str:
    """
    Table 13: x86_64 replication of the sustained-load socket benchmark (Table 12 config),
    summarized as stock vs patched set_vec RTT improvements per VM.
    """

    out: list[str] = []
    out.append(
        "| VM | Stock `set_vec` RTT p50 | Patched `set_vec` RTT p50 | Speedup (p50) | Stock `set_vec` RTT p99 | Patched `set_vec` RTT p99 | Speedup (p99) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|")

    for pack_path in packs:
        try:
            stock, patched = _load_socket_server_load_from_paper09_pack(pack_path)
            s = stock.get("set_vec")
            p = patched.get("set_vec")
            if not s or not p:
                continue

            s_p50 = float(s["rtt"]["p50_ns"]["median"])
            s_p50_iqr = float(s["rtt"]["p50_ns"].get("iqr", 0.0))
            p_p50 = float(p["rtt"]["p50_ns"]["median"])
            p_p50_iqr = float(p["rtt"]["p50_ns"].get("iqr", 0.0))

            s_p99 = float(s["rtt"]["p99_ns"]["median"])
            s_p99_iqr = float(s["rtt"]["p99_ns"].get("iqr", 0.0))
            p_p99 = float(p["rtt"]["p99_ns"]["median"])
            p_p99_iqr = float(p["rtt"]["p99_ns"].get("iqr", 0.0))

            speed_p50 = (s_p50 / p_p50) if p_p50 > 0 else float("nan")
            speed_p99 = (s_p99 / p_p99) if p_p99 > 0 else float("nan")

            m = re.search(r"(vm\d+)", pack_path.name)
            label = m.group(1) if m else pack_path.stem

            out.append(
                f"| {label} | {_fmt_cell_with_iqr_ns(s_p50, s_p50_iqr)} | {_fmt_cell_with_iqr_ns(p_p50, p_p50_iqr)} | "
                f"{speed_p50:,.1f}× | {_fmt_cell_with_iqr_ns(s_p99, s_p99_iqr)} | {_fmt_cell_with_iqr_ns(p_p99, p_p99_iqr)} | {speed_p99:,.1f}× |"
            )
        except Exception:
            # Missing/invalid pack; skip rather than crashing paper generation.
            continue

    if len(out) <= 2:
        return _render_table_13_na()
    return "\n".join(out) + "\n"


def _render_table_13_na() -> str:
    out: list[str] = []
    out.append(
        "| VM | Stock `set_vec` RTT p50 | Patched `set_vec` RTT p50 | Speedup (p50) | Stock `set_vec` RTT p99 | Patched `set_vec` RTT p99 | Speedup (p99) |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|")
    out.append(
        "| N/A | N/A (provide x86_64 paper09 packs) | N/A | N/A | N/A | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def _render_table_17_x86_isolated(*, packs: list[Path]) -> str:
    """
    Table 17: less-noisy x86_64 bridge microbench reproduction.

    Input packs are tarballs produced by scripts/eval/collect_host_pack.sh which contain
    a full_telemetry.json from eval_bridge_v3.py (patched build).
    """

    kib = 1024
    on_size = 10_000_000
    rows: list[tuple[str, int, bool]] = [
        ("Null (PyBytes)", kib, False),
        ("Null (PyBuffer)", kib, False),
        ("Acquire buffer (len_bytes)", kib, False),
        ("Copy (PyBytes to_vec)", on_size, False),
        ("Copy (Buffer to_vec)", on_size, False),
        ("Copy (Vec<u8> arg)", on_size, False),
        ("Copy (Sequence to Vec<u8>)", on_size, True),
        ("Consume (PyBytes)", on_size, False),
    ]

    runs: list[dict] = []
    labels: list[str] = []
    for pack_path in packs:
        data = _load_json_from_pack(pack_path, filename="full_telemetry.json")
        md = data.get("metadata", {}) or {}
        run_id = str(md.get("run_id", "")).strip() or pack_path.stem
        m = re.search(r"(run\d+)", run_id)
        label = m.group(1) if m else run_id

        agg = {(str(r["path"]), int(r["size_bytes"])): r for r in data.get("aggregate", [])}
        runs.append({"label": label, "agg": agg})
        labels.append(label)

    header = "| Path | Size | " + " | ".join(labels) + " |"
    sep = "| :--- | ---: | " + " | ".join(":---:" for _ in labels) + " |"
    out: list[str] = [header, sep]

    for path, size, bold in rows:
        size_label = "1KiB" if size == kib else "10MB"
        cells: list[str] = []
        for run in runs:
            row = run["agg"].get((path, size))
            if not row:
                cells.append("N/A")
                continue
            p50 = float(row["p50_median"])
            p50_iqr = float(row.get("p50_iqr", 0.0))
            cells.append(_fmt_cell_with_iqr_ns(p50, p50_iqr, bold=bold))

        out.append(
            f"| {path:<27} | {size_label:>4} | "
            + " | ".join(f"{c:>12}" for c in cells)
            + " |"
        )

    return "\n".join(out) + "\n"


def _render_table_17_na() -> str:
    out: list[str] = []
    out.append("| Path | Size | run1 | run2 | run3 |")
    out.append("| :--- | ---: | :---: | :---: | :---: |")
    out.append(
        "| N/A | N/A | N/A (provide `x86_64_isolated_run*_pack.tgz`) | N/A | N/A |"
    )
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paper",
        default="src/warm_logic/docs/papers/09_boundary_elimination/paper.md",
    )
    parser.add_argument(
        "--combined", default="out/bridge_eval/multi_host/combined.json"
    )
    parser.add_argument(
        "--e2e",
        default="out/bridge_eval/e2e_bytes_macos_arm64/e2e_bytes_telemetry.json",
    )
    parser.add_argument(
        "--vec-u8-stock",
        default="out/bridge_eval/vec_u8_input_variants_stock/vec_u8_input_variants.json",
    )
    parser.add_argument(
        "--vec-u8-patched",
        default="out/bridge_eval/vec_u8_input_variants_patched/vec_u8_input_variants.json",
    )
    parser.add_argument(
        "--vec-u8-semantics-stock",
        default="out/bridge_eval/vec_u8_semantics_stock_macos_arm64/vec_u8_semantics.json",
        help="semantic verifier JSON produced by verify_paper09_vec_u8_semantics.py (stock wheel)",
    )
    parser.add_argument(
        "--vec-u8-semantics-patched",
        default="out/bridge_eval/vec_u8_semantics_patched_macos_arm64/vec_u8_semantics.json",
        help="semantic verifier JSON produced by verify_paper09_vec_u8_semantics.py (patched wheel)",
    )
    parser.add_argument(
        "--sovkv-stock",
        default="out/bridge_eval/sovkv_stock_macos_arm64/sovkv_telemetry.json",
    )
    parser.add_argument(
        "--sovkv-patched",
        default="out/bridge_eval/sovkv_patched_macos_arm64/sovkv_telemetry.json",
    )
    parser.add_argument(
        "--socket-kv-stock",
        default="out/bridge_eval/socket_kv_stock_macos_arm64/socket_kv_telemetry.json",
    )
    parser.add_argument(
        "--socket-kv-patched",
        default="out/bridge_eval/socket_kv_patched_macos_arm64/socket_kv_telemetry.json",
    )
    parser.add_argument(
        "--pybind11",
        default="out/bridge_eval/pybind11_case/pybind11_case_telemetry.json",
    )
    parser.add_argument(
        "--cython-case",
        default="out/bridge_eval/cython_case/cython_case_telemetry.json",
    )
    parser.add_argument(
        "--socket-mux-kv-stock",
        default="out/bridge_eval/socket_mux_kv_stock_macos_arm64/socket_mux_kv_telemetry.json",
    )
    parser.add_argument(
        "--socket-mux-kv-patched",
        default="out/bridge_eval/socket_mux_kv_patched_macos_arm64/socket_mux_kv_telemetry.json",
    )
    parser.add_argument(
        "--capi-anchor",
        default="out/bridge_eval/capi_anchor_macos_arm64/capi_anchor_telemetry.json",
    )
    parser.add_argument(
        "--python-sweep",
        default="out/bridge_eval/python_sweep/paper09_python_sweep.json",
    )
    parser.add_argument(
        "--gil-tradeoff",
        default="out/bridge_eval/gil_tradeoff/gil_tradeoff.json",
    )
    parser.add_argument(
        "--gil-concurrency-stock",
        default="out/bridge_eval/gil_concurrency_stock_macos_arm64/gil_concurrency.json",
    )
    parser.add_argument(
        "--gil-concurrency-patched",
        default="out/bridge_eval/gil_concurrency_patched_macos_arm64/gil_concurrency.json",
    )
    parser.add_argument(
        "--socket-server-load-stock",
        default="out/bridge_eval/socket_server_load_stock_macos_arm64/socket_server_load_telemetry.json",
    )
    parser.add_argument(
        "--socket-server-load-patched",
        default="out/bridge_eval/socket_server_load_patched_macos_arm64/socket_server_load_telemetry.json",
    )
    parser.add_argument(
        "--http-server-load-stock",
        default="out/bridge_eval/http_server_load_stock_macos_arm64/http_server_load_telemetry.json",
    )
    parser.add_argument(
        "--http-server-load-patched",
        default="out/bridge_eval/http_server_load_patched_macos_arm64/http_server_load_telemetry.json",
    )
    parser.add_argument(
        "--fastapi-server-load-stock",
        default="out/bridge_eval/fastapi_server_load_stock_macos_arm64/fastapi_server_load_telemetry.json",
    )
    parser.add_argument(
        "--fastapi-server-load-patched",
        default="out/bridge_eval/fastapi_server_load_patched_macos_arm64/fastapi_server_load_telemetry.json",
    )
    parser.add_argument(
        "--pyo3-vec-u8-prevalence",
        default="out/bridge_eval/pyo3_vec_u8_prevalence/pyo3_vec_u8_prevalence_top500.json",
        help="crates.io snapshot JSON produced by scan_pyo3_vec_u8_prevalence.py (Table 19 input)",
    )
    parser.add_argument(
        "--rust-strings-case",
        default="out/bridge_eval/rust_strings_case/rust_strings_case_telemetry.json",
        help="telemetry JSON produced by eval_paper09_rust_strings_case.py (Table 20 input)",
    )
    parser.add_argument(
        "--vtracer-case",
        default="out/bridge_eval/vtracer_case/vtracer_case_telemetry.json",
        help="telemetry JSON produced by eval_paper09_vtracer_case.py (Table 21 input)",
    )
    parser.add_argument(
        "--socket-server-load-x86-packs",
        default="out/bridge_eval/x86_64_cloud_vm1_paper09_pack.tgz,out/bridge_eval/x86_64_cloud_vm2_paper09_pack.tgz,out/bridge_eval/x86_64_cloud_vm3_paper09_pack.tgz",
        help="comma-separated list of x86_64 paper09 pack tgz files (Table 13 input)",
    )
    parser.add_argument(
        "--socket-server-net-clouds",
        default="gcp,aws",
        help="comma-separated list of cloud providers to include in Table 14 (missing telemetry is skipped)",
    )
    parser.add_argument(
        "--x86-64-isolated-packs",
        default="out/bridge_eval/x86_64_isolated_run1_pack.tgz,out/bridge_eval/x86_64_isolated_run2_pack.tgz,out/bridge_eval/x86_64_isolated_run3_pack.tgz",
        help="comma-separated list of x86_64 'less-noisy' bridge host pack tgz files (Table 17 input)",
    )
    parser.add_argument(
        "--cloud", default="gcp", help="cloud provider (gcp, aws, azure)"
    )
    args_pre, _ = parser.parse_known_args()
    cloud = args_pre.cloud

    parser.add_argument(
        "--socket-server-net-stock",
        default=f"out/bridge_eval/socket_server_net_stock_{cloud}_x86_64/socket_server_net_telemetry.json",
    )
    parser.add_argument(
        "--socket-server-net-patched",
        default=f"out/bridge_eval/socket_server_net_patched_{cloud}_x86_64/socket_server_net_telemetry.json",
    )
    args = parser.parse_args()

    paper_path = Path(args.paper)
    paper_text = paper_path.read_text(encoding="utf-8")

    combined_data = json.loads(Path(args.combined).read_text(encoding="utf-8"))
    e2e = _load_e2e(Path(args.e2e))
    v_stock = _load_vec_u8_variants(Path(args.vec_u8_stock))
    v_patched = _load_vec_u8_variants(Path(args.vec_u8_patched))
    semantics_stock_path = Path(args.vec_u8_semantics_stock)
    semantics_patched_path = Path(args.vec_u8_semantics_patched)
    if semantics_stock_path.exists() and semantics_patched_path.exists():
        semantics_stock = _load_vec_u8_semantics(semantics_stock_path)
        semantics_patched = _load_vec_u8_semantics(semantics_patched_path)
        table22 = _render_table_22_vec_u8_semantics(
            stock=semantics_stock, patched=semantics_patched
        )
    else:
        table22 = _render_table_22_na()
    sovkv_stock = _load_sovkv(Path(args.sovkv_stock))
    sovkv_patched = _load_sovkv(Path(args.sovkv_patched))
    socket_kv_stock = _load_socket_kv(Path(args.socket_kv_stock))
    socket_kv_patched = _load_socket_kv(Path(args.socket_kv_patched))
    socket_mux_stock_path = Path(args.socket_mux_kv_stock)
    socket_mux_patched_path = Path(args.socket_mux_kv_patched)
    if socket_mux_stock_path.exists() and socket_mux_patched_path.exists():
        socket_mux_stock = _load_socket_mux_kv(socket_mux_stock_path)
        socket_mux_patched = _load_socket_mux_kv(socket_mux_patched_path)
        table7 = _render_table_7(stock=socket_mux_stock, patched=socket_mux_patched)
    else:
        table7 = (
            "\n".join(
                [
                    "| API | Stock throughput | Patched throughput | Stock e2e p50 | Patched e2e p50 | Stock e2e p99 | Patched e2e p99 |",
                    "|---|---:|---:|---:|---:|---:|---:|",
                    "| recv_only | N/A (run `eval_paper09_socket_mux_kv.py` stock+patched) | N/A | N/A | N/A | N/A | N/A |",
                    "| set_bytesvec | N/A (run `eval_paper09_socket_mux_kv.py` stock+patched) | N/A | N/A | N/A | N/A | N/A |",
                    "| set_vec | N/A (run `eval_paper09_socket_mux_kv.py` stock+patched) | N/A | N/A | N/A | N/A | N/A |",
                ]
            )
            + "\n"
        )
    pybind11_path = Path(args.pybind11)
    if pybind11_path.exists():
        pybind11_case = _load_pybind11_case(pybind11_path)
        table6 = _render_table_6(data=pybind11_case)
    else:
        table6 = _render_table_6_na()

    cython_path = Path(args.cython_case)
    if cython_path.exists():
        cython_case = _load_cython_case(cython_path)
        table15 = _render_table_15(data=cython_case)
    else:
        table15 = _render_table_15_na()

    capi_path = Path(args.capi_anchor)
    if capi_path.exists():
        capi = _load_capi_anchor(capi_path)
        table8 = _render_table_8(data=capi)
    else:
        table8 = _render_table_8_na()

    sweep_path = Path(args.python_sweep)
    if sweep_path.exists():
        sweep_rows = _load_python_sweep(sweep_path)
        table9 = _render_table_9(rows=sweep_rows)
    else:
        table9 = _render_table_9_na()

    gil_path = Path(args.gil_tradeoff)
    if gil_path.exists():
        gil = _load_gil_tradeoff(gil_path)
        table10 = _render_table_10(data=gil)
    else:
        table10 = _render_table_10_na()

    gil_conc_stock_path = Path(args.gil_concurrency_stock)
    gil_conc_patched_path = Path(args.gil_concurrency_patched)
    if gil_conc_stock_path.exists() and gil_conc_patched_path.exists():
        gil_conc_stock = _load_gil_concurrency(gil_conc_stock_path)
        gil_conc_patched = _load_gil_concurrency(gil_conc_patched_path)
        table11 = _render_table_11(stock=gil_conc_stock, patched=gil_conc_patched)
    else:
        table11 = _render_table_11_na()

    server_stock_path = Path(args.socket_server_load_stock)
    server_patched_path = Path(args.socket_server_load_patched)
    if server_stock_path.exists() and server_patched_path.exists():
        server_stock = _load_socket_server_load(server_stock_path)
        server_patched = _load_socket_server_load(server_patched_path)
        table12 = _render_table_12(stock=server_stock, patched=server_patched)
    else:
        table12 = _render_table_12_na()

    http_stock_path = Path(args.http_server_load_stock)
    http_patched_path = Path(args.http_server_load_patched)
    if http_stock_path.exists() and http_patched_path.exists():
        http_stock = _load_socket_server_load(http_stock_path)
        http_patched = _load_socket_server_load(http_patched_path)
        table16 = _render_table_12(stock=http_stock, patched=http_patched)
    else:
        table16 = _render_table_16_na()

    fastapi_stock_path = Path(args.fastapi_server_load_stock)
    fastapi_patched_path = Path(args.fastapi_server_load_patched)
    if fastapi_stock_path.exists() and fastapi_patched_path.exists():
        fastapi_stock = _load_socket_server_load(fastapi_stock_path)
        fastapi_patched = _load_socket_server_load(fastapi_patched_path)
        table18 = _render_table_12(stock=fastapi_stock, patched=fastapi_patched)
    else:
        table18 = _render_table_18_na()

    x86_packs = [
        Path(p.strip())
        for p in str(args.socket_server_load_x86_packs).split(",")
        if p.strip()
    ]
    x86_packs = [p for p in x86_packs if p.exists()]
    if x86_packs:
        table13 = _render_table_13_x86(packs=x86_packs)
    else:
        table13 = _render_table_13_na()

    isolated_packs = [
        Path(p.strip())
        for p in str(args.x86_64_isolated_packs).split(",")
        if p.strip()
    ]
    isolated_packs = [p for p in isolated_packs if p.exists()]
    if isolated_packs:
        table17 = _render_table_17_x86_isolated(packs=isolated_packs)
    else:
        table17 = _render_table_17_na()

    net_clouds = [
        c.strip() for c in str(args.socket_server_net_clouds).split(",") if c.strip()
    ]
    if net_clouds:
        net_stock_by_cloud: dict[str, dict[str, dict]] = {}
        net_patched_by_cloud: dict[str, dict[str, dict]] = {}
        for c in net_clouds:
            stock_path = Path(
                f"out/bridge_eval/socket_server_net_stock_{c}_x86_64/socket_server_net_telemetry.json"
            )
            patched_path = Path(
                f"out/bridge_eval/socket_server_net_patched_{c}_x86_64/socket_server_net_telemetry.json"
            )
            if not (stock_path.exists() and patched_path.exists()):
                continue

            net_stock_by_cloud[c] = json.loads(stock_path.read_text(encoding="utf-8"))
            net_patched_by_cloud[c] = json.loads(
                patched_path.read_text(encoding="utf-8")
            )

        if net_stock_by_cloud and net_patched_by_cloud:
            if len(net_clouds) == 1:
                c = net_clouds[0]
                table14 = _render_table_14(
                    stock_data=net_stock_by_cloud[c],
                    patched_data=net_patched_by_cloud[c],
                )
            else:
                table14 = _render_table_14_multi(
                    clouds=net_clouds,
                    stock_by_cloud=net_stock_by_cloud,
                    patched_by_cloud=net_patched_by_cloud,
                )
        else:
            table14 = _render_table_14_multi_na()
    else:
        net_stock_path = Path(args.socket_server_net_stock)
        net_patched_path = Path(args.socket_server_net_patched)
        if net_stock_path.exists() and net_patched_path.exists():
            net_stock = _load_socket_server_load(net_stock_path)
            net_patched = _load_socket_server_load(net_patched_path)
            table14 = _render_table_14(stock=net_stock, patched=net_patched)
        else:
            table14 = _render_table_14_na()

    table1 = _render_table_1(combined=combined_data)
    table2 = _render_table_2(e2e=e2e)
    table3 = _render_table_3(stock=v_stock, patched=v_patched)
    table4 = _render_table_4(stock=sovkv_stock, patched=sovkv_patched)
    table5 = _render_table_5(stock=socket_kv_stock, patched=socket_kv_patched)
    prevalence_path = Path(args.pyo3_vec_u8_prevalence)
    if prevalence_path.exists():
        table19 = _render_table_19_prevalence(
            data=json.loads(prevalence_path.read_text(encoding="utf-8"))
        )
    else:
        table19 = _render_table_19_na()

    rust_strings_path = Path(args.rust_strings_case)
    if rust_strings_path.exists():
        table20 = _render_table_20_rust_strings_case(
            data=json.loads(rust_strings_path.read_text(encoding="utf-8"))
        )
    else:
        table20 = _render_table_20_na()

    vtracer_path = Path(args.vtracer_case)
    if vtracer_path.exists():
        table21 = _render_table_21_vtracer_case(
            data=json.loads(vtracer_path.read_text(encoding="utf-8"))
        )
    else:
        table21 = _render_table_21_na()

    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE1_AUTO_BEGIN -->",
        end="<!-- TABLE1_AUTO_END -->",
        replacement=table1,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE2_AUTO_BEGIN -->",
        end="<!-- TABLE2_AUTO_END -->",
        replacement=table2,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE3_AUTO_BEGIN -->",
        end="<!-- TABLE3_AUTO_END -->",
        replacement=table3,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE4_AUTO_BEGIN -->",
        end="<!-- TABLE4_AUTO_END -->",
        replacement=table4,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE5_AUTO_BEGIN -->",
        end="<!-- TABLE5_AUTO_END -->",
        replacement=table5,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE6_AUTO_BEGIN -->",
        end="<!-- TABLE6_AUTO_END -->",
        replacement=table6,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE7_AUTO_BEGIN -->",
        end="<!-- TABLE7_AUTO_END -->",
        replacement=table7,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE8_AUTO_BEGIN -->",
        end="<!-- TABLE8_AUTO_END -->",
        replacement=table8,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE9_AUTO_BEGIN -->",
        end="<!-- TABLE9_AUTO_END -->",
        replacement=table9,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE10_AUTO_BEGIN -->",
        end="<!-- TABLE10_AUTO_END -->",
        replacement=table10,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE11_AUTO_BEGIN -->",
        end="<!-- TABLE11_AUTO_END -->",
        replacement=table11,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE12_AUTO_BEGIN -->",
        end="<!-- TABLE12_AUTO_END -->",
        replacement=table12,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE13_AUTO_BEGIN -->",
        end="<!-- TABLE13_AUTO_END -->",
        replacement=table13,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE14_AUTO_BEGIN -->",
        end="<!-- TABLE14_AUTO_END -->",
        replacement=table14,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE15_AUTO_BEGIN -->",
        end="<!-- TABLE15_AUTO_END -->",
        replacement=table15,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE16_AUTO_BEGIN -->",
        end="<!-- TABLE16_AUTO_END -->",
        replacement=table16,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE17_AUTO_BEGIN -->",
        end="<!-- TABLE17_AUTO_END -->",
        replacement=table17,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE18_AUTO_BEGIN -->",
        end="<!-- TABLE18_AUTO_END -->",
        replacement=table18,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE19_AUTO_BEGIN -->",
        end="<!-- TABLE19_AUTO_END -->",
        replacement=table19,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE20_AUTO_BEGIN -->",
        end="<!-- TABLE20_AUTO_END -->",
        replacement=table20,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE21_AUTO_BEGIN -->",
        end="<!-- TABLE21_AUTO_END -->",
        replacement=table21,
    )
    paper_text = _replace_block(
        paper_text,
        begin="<!-- TABLE22_AUTO_BEGIN -->",
        end="<!-- TABLE22_AUTO_END -->",
        replacement=table22,
    )

    paper_path.write_text(paper_text, encoding="utf-8")
    print(f"Wrote: {paper_path}")


if __name__ == "__main__":
    main()
