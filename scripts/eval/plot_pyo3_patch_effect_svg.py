import argparse
import json
import math
from pathlib import Path


def _log10(x: float) -> float:
    return math.log10(x)


def _svg_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _nice_ticks_log10(y_min: float, y_max: float) -> list[float]:
    lo = int(math.floor(_log10(max(y_min, 1e-12))))
    hi = int(math.ceil(_log10(max(y_max, 1e-12))))
    return [10**e for e in range(lo, hi + 1)]


def _format_size(bytes_count: int) -> str:
    if bytes_count < 1024:
        return f"{bytes_count}B"
    if bytes_count < 1024 * 1024:
        return f"{bytes_count // 1024}KiB"
    return f"{bytes_count // (1024 * 1024)}MiB"


def _render_plot(
    *,
    title: str,
    subtitle: str,
    out_path: Path,
    sizes: list[int],
    series: dict[str, list[tuple[int, float]]],  # name -> [(size, y)]
) -> None:
    width = 960
    height = 540
    margin = {"l": 80, "r": 260, "t": 70, "b": 70}

    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]

    x_vals = [_log10(float(s)) for s in sizes]
    x_min, x_max = min(x_vals), max(x_vals)

    y_all: list[float] = []
    for pts in series.values():
        for _s, y in pts:
            y_all.append(y)
    if not y_all:
        raise ValueError("no data to plot")

    y_min = min(y_all)
    y_max = max(y_all)
    ticks = _nice_ticks_log10(y_min, y_max)

    def x_map(size_bytes: int) -> float:
        x = _log10(float(size_bytes))
        return margin["l"] + plot_w * (x - x_min) / (x_max - x_min)

    def y_map(v: float) -> float:
        v = max(v, 1e-12)
        lo = _log10(max(y_min, 1e-12))
        hi = _log10(max(y_max, 1e-12))
        return margin["t"] + plot_h * (1.0 - (_log10(v) - lo) / (hi - lo))

    palette = {
        "Sequence semantics baseline": "#dc2626",  # red
        "Vec<u8> arg (fast path)": "#16a34a",  # green
        "Copy (PyBytes to_vec) baseline": "#2563eb",  # blue
    }

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    parts.append(
        f'<text x="{margin["l"]}" y="28" font-family="ui-sans-serif, system-ui" font-size="20" fill="#111827">{_svg_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{margin["l"]}" y="50" font-family="ui-sans-serif, system-ui" font-size="12" fill="#374151">{_svg_escape(subtitle)}</text>'
    )

    x0 = margin["l"]
    y0 = margin["t"]
    parts.append(
        f'<rect x="{x0}" y="{y0}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#e5e7eb"/>'
    )

    # X ticks: use sizes directly
    for s in sizes:
        xv = x_map(s)
        parts.append(
            f'<line x1="{xv:.2f}" y1="{y0+plot_h}" x2="{xv:.2f}" y2="{y0+plot_h+6}" stroke="#9ca3af"/>'
        )
        parts.append(
            f'<text x="{xv:.2f}" y="{y0+plot_h+22}" font-family="ui-sans-serif, system-ui" font-size="10" text-anchor="middle" fill="#374151">{_svg_escape(_format_size(s))}</text>'
        )
    parts.append(
        f'<text x="{x0 + plot_w/2:.2f}" y="{height-18}" font-family="ui-sans-serif, system-ui" font-size="12" text-anchor="middle" fill="#111827">Payload size</text>'
    )

    # Y ticks
    for t in ticks:
        yv = y_map(t)
        parts.append(f'<line x1="{x0-6}" y1="{yv:.2f}" x2="{x0}" y2="{yv:.2f}" stroke="#9ca3af"/>')
        label = f"1e{int(round(_log10(t)))}"
        parts.append(
            f'<text x="{x0-10}" y="{yv+3:.2f}" font-family="ui-sans-serif, system-ui" font-size="10" text-anchor="end" fill="#374151">{_svg_escape(label)}</text>'
        )
        parts.append(f'<line x1="{x0}" y1="{yv:.2f}" x2="{x0+plot_w}" y2="{yv:.2f}" stroke="#f3f4f6"/>')

    parts.append(
        f'<text x="18" y="{y0 + plot_h/2:.2f}" font-family="ui-sans-serif, system-ui" font-size="12" text-anchor="middle" fill="#111827" transform="rotate(-90, 18, {y0 + plot_h/2:.2f})">Latency (ns / call, log10)</text>'
    )

    # Lines + legend
    legend_x = margin["l"] + plot_w + 20
    legend_y = margin["t"] + 20

    for i, (name, pts) in enumerate(series.items()):
        color = palette.get(name, "#6b7280")
        pts_sorted = sorted(pts, key=lambda p: p[0])
        d = " ".join(f"{x_map(s):.2f},{y_map(v):.2f}" for s, v in pts_sorted)
        parts.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
        for s, v in pts_sorted:
            parts.append(f'<circle cx="{x_map(s):.2f}" cy="{y_map(v):.2f}" r="3" fill="{color}"/>')
        ly = legend_y + i * 18
        parts.append(f'<rect x="{legend_x}" y="{ly-10}" width="12" height="12" fill="{color}"/>')
        parts.append(
            f'<text x="{legend_x+18}" y="{ly}" font-family="ui-sans-serif, system-ui" font-size="11" fill="#111827">{_svg_escape(name)}</text>'
        )

    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")


def load_aggregate(path: Path) -> dict[tuple[str, int], dict]:
    data = json.loads(path.read_text())
    agg = {}
    for row in data["aggregate"]:
        agg[(row["path"], int(row["size_bytes"]))] = row
    return agg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="out/bridge_eval/bridge_eval_v3_pyo3_patch/full_telemetry.json",
        help="telemetry json produced by eval_bridge_v3.py",
    )
    parser.add_argument(
        "--out",
        default="src/warm_logic/docs/papers/09_boundary_elimination/figures/fig_vec_u8_patch_effect.svg",
    )
    args = parser.parse_args()

    agg = load_aggregate(Path(args.input))
    # We plot payload size on a log-x axis, so size=0 cannot be represented.
    # Keep the 0B measurements in telemetry, but omit them from plots.
    sizes = sorted({s for (_p, s) in agg.keys() if s > 0})

    series = {
        "Sequence semantics baseline": [
            (s, float(agg[("Copy (Sequence to Vec<u8>)", s)]["p50_median"])) for s in sizes
        ],
        "Vec<u8> arg (fast path)": [
            (s, float(agg[("Copy (Vec<u8> arg)", s)]["p50_median"])) for s in sizes
        ],
        "Copy (PyBytes to_vec) baseline": [
            (s, float(agg[("Copy (PyBytes to_vec)", s)]["p50_median"])) for s in sizes
        ],
    }

    _render_plot(
        title="Vec<u8> Extraction Semantics: Sequence vs Fast Path",
        subtitle="p50 median across repeats; corrected by empty-loop subtraction; log-log",
        out_path=Path(args.out),
        sizes=sizes,
        series=series,
    )

    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()
