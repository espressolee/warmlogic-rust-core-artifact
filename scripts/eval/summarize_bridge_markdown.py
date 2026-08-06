import argparse
import json
from pathlib import Path


def _fmt_ns(x: float | None) -> str:
    if x is None:
        return "NA"
    if x >= 1_000_000:
        return f"{x/1_000_000:.3f} ms"
    if x >= 1_000:
        return f"{x/1_000:.3f} µs"
    return f"{x:.2f} ns"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="out/bridge_eval/bridge_eval_v3_pyo3_patch/full_telemetry.json",
        help="telemetry json produced by eval_bridge_v3.py",
    )
    parser.add_argument("--out", default=None, help="output markdown path (optional)")
    parser.add_argument("--size-o1", type=int, default=1000)
    parser.add_argument("--size-on", type=int, default=10_000_000)
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text())
    agg = {(r["path"], int(r["size_bytes"])): r for r in data["aggregate"]}

    o1_paths = ["Python noop", "C noop", "Null (PyBytes)", "Acquire buffer (len_bytes)", "Null (PyBuffer)"]
    on_paths = [
        "Copy (PyBytes to_vec)",
        "Copy (Buffer to_vec)",
        "Copy (BytesVec arg)",
        "Copy (Vec<u8> arg)",
        "Consume (PyBytes)",
    ]

    lines: list[str] = []
    lines.append(f"# Telemetry summary: `{args.input}`")
    lines.append("")
    lines.append("## O(1) paths")
    lines.append(f"Size: `{args.size_o1}` bytes")
    lines.append("")
    lines.append("| Path | p50 (median) | p99 (median) | p50 IQR | p99 IQR |")
    lines.append("|---|---:|---:|---:|---:|")
    for p in o1_paths:
        r = agg.get((p, args.size_o1))
        if not r:
            continue
        lines.append(
            f"| {p} | {_fmt_ns(float(r['p50_median']))} | {_fmt_ns(float(r['p99_median']))} | {float(r['p50_iqr']):.2f} ns | {float(r['p99_iqr']):.2f} ns |"
        )

    lines.append("")
    lines.append("## O(N) paths")
    lines.append(f"Size: `{args.size_on}` bytes")
    lines.append("")
    lines.append("| Path | p50 (median) | p99 (median) | p50 IQR | p99 IQR |")
    lines.append("|---|---:|---:|---:|---:|")
    for p in on_paths:
        r = agg.get((p, args.size_on))
        if not r:
            continue
        lines.append(
            f"| {p} | {_fmt_ns(float(r['p50_median']))} | {_fmt_ns(float(r['p99_median']))} | {_fmt_ns(float(r['p50_iqr']))} | {_fmt_ns(float(r['p99_iqr']))} |"
        )

    out = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Wrote: {args.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()
