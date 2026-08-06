import argparse
import json
import math
import statistics
from pathlib import Path


def _log10(x: float) -> float:
    return math.log10(x)


def _fit_slope_loglog(points: list[tuple[int, float]]) -> float:
    # Fit y = a + b x in log10 space, where x=log10(size), y=log10(latency_ns).
    xs = [_log10(float(s)) for s, _y in points]
    ys = [_log10(max(float(y), 1e-12)) for _s, y in points]
    if len(xs) < 2:
        return float("nan")
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    var = sum((x - x_mean) ** 2 for x in xs)
    return cov / var if var > 0 else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="out/bridge_eval/bridge_eval_v3_pyo3_patch/full_telemetry.json",
        help="telemetry json produced by eval_bridge_v3.py",
    )
    parser.add_argument(
        "--out",
        default="out/bridge_eval/classification/bridge_eval_v3_pyo3_patch.json",
    )
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text())
    agg = data["aggregate"]
    # log-log classification needs strictly positive sizes (log10(0) is undefined)
    sizes = sorted({int(r["size_bytes"]) for r in agg if int(r["size_bytes"]) > 0})
    by_path: dict[str, dict[int, float]] = {}
    for r in agg:
        s = int(r["size_bytes"])
        if s <= 0:
            continue
        by_path.setdefault(r["path"], {})[s] = float(r["p50_median"])

    # Reference baseline for "expected contiguous copy cost"
    ref_path = "Copy (PyBytes to_vec)"
    ref_size = 10_000_000
    ref_ns = by_path.get(ref_path, {}).get(ref_size)

    small_size = 1024 if 1024 in sizes else (1000 if 1000 in sizes else None)

    report = {
        "input": args.input,
        "sizes": sizes,
        "ref": {"path": ref_path, "size": ref_size, "p50_ns": ref_ns},
        "small_size_bytes": small_size,
    }
    rows = []
    for path, m in by_path.items():
        pts = [(s, m[s]) for s in sizes if s in m]
        slope = _fit_slope_loglog(pts)
        ratio_10mb_over_small = None
        if small_size is not None and small_size in m and ref_size in m and m[small_size] > 0:
            ratio_10mb_over_small = m[ref_size] / m[small_size]
        factor_vs_copy = None
        if ref_ns and ref_size in m and ref_ns > 0:
            factor_vs_copy = m[ref_size] / ref_ns
        rows.append(
            {
                "path": path,
                "slope_loglog": slope,
                "p50_ns_at_small": m.get(small_size) if small_size is not None else None,
                "p50_ns_at_10mb": m.get(ref_size),
                "ratio_10mb_over_small": ratio_10mb_over_small,
                "factor_vs_copy_pybytes_10mb": factor_vs_copy,
            }
        )

    rows.sort(key=lambda r: (float("inf") if math.isnan(r["slope_loglog"]) else r["slope_loglog"], r["path"]))
    report["rows"] = rows

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Scaling classification (log-log slope):")
    for r in rows:
        slope = r["slope_loglog"]
        p10 = r["p50_ns_at_10mb"]
        f = r["factor_vs_copy_pybytes_10mb"]
        if p10 is None:
            continue
        extra = ""
        if f is not None and f > 10:
            extra = f"  [ANOMALY vs contiguous copy: {f:.1f}x]"
        print(f"- {r['path']:<24} slope={slope:>5.2f}  p50@10MB={p10:>12,.0f} ns{extra}")

    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
