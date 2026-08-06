import argparse
import json
import math
from pathlib import Path
from typing import Iterable


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


def _nice_ticks_linear(y_min: float, y_max: float, step: float) -> list[float]:
    start = math.floor(y_min / step) * step
    end = math.ceil(y_max / step) * step
    ticks = []
    y = start
    while y <= end + 1e-9:
        ticks.append(y)
        y += step
    return ticks


def _nice_ticks_log10(y_min: float, y_max: float) -> list[float]:
    lo = int(math.floor(_log10(max(y_min, 1e-12))))
    hi = int(math.ceil(_log10(max(y_max, 1e-12))))
    return [10**e for e in range(lo, hi + 1)]


def _path_color(name: str) -> str:
    palette = [
        "#2563eb",  # blue
        "#16a34a",  # green
        "#dc2626",  # red
        "#7c3aed",  # purple
        "#ea580c",  # orange
        "#0f766e",  # teal
        "#6b7280",  # gray
    ]
    idx = abs(hash(name)) % len(palette)
    return palette[idx]


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
    x_label: str,
    y_label: str,
    y_scale: str,  # "linear" | "log10"
    y_tick_step: float | None = None,
) -> None:
    width = 960
    height = 540
    margin = {"l": 80, "r": 220, "t": 70, "b": 70}

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

    if y_scale == "linear":
        y_min = 0.0
        y_max = max(y_all) * 1.05
        ticks = _nice_ticks_linear(y_min, y_max, y_tick_step or 10.0)

        def y_map(v: float) -> float:
            return margin["t"] + plot_h * (1.0 - (v - y_min) / (y_max - y_min))

    elif y_scale == "log10":
        y_min = min(y_all)
        y_max = max(y_all)
        ticks = _nice_ticks_log10(y_min, y_max)

        def y_map(v: float) -> float:
            v = max(v, 1e-12)
            lo = _log10(max(y_min, 1e-12))
            hi = _log10(max(y_max, 1e-12))
            return margin["t"] + plot_h * (1.0 - (_log10(v) - lo) / (hi - lo))

    else:
        raise ValueError(f"unknown y_scale: {y_scale}")

    def x_map(size_bytes: int) -> float:
        x = _log10(float(size_bytes))
        return margin["l"] + plot_w * (x - x_min) / (x_max - x_min)

    # Start SVG
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

    # Axes box
    x0 = margin["l"]
    y0 = margin["t"]
    parts.append(
        f'<rect x="{x0}" y="{y0}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#e5e7eb"/>'
    )

    # X ticks (powers of 10 within range)
    for s in sizes:
        xv = x_map(s)
        parts.append(f'<line x1="{xv:.2f}" y1="{y0+plot_h}" x2="{xv:.2f}" y2="{y0+plot_h+6}" stroke="#9ca3af"/>')
        parts.append(
            f'<text x="{xv:.2f}" y="{y0+plot_h+22}" font-family="ui-sans-serif, system-ui" font-size="10" text-anchor="middle" fill="#374151">{_svg_escape(_format_size(s))}</text>'
        )

    parts.append(
        f'<text x="{x0 + plot_w/2:.2f}" y="{height-18}" font-family="ui-sans-serif, system-ui" font-size="12" text-anchor="middle" fill="#111827">{_svg_escape(x_label)}</text>'
    )

    # Y ticks
    for t in ticks:
        yv = y_map(t)
        parts.append(f'<line x1="{x0-6}" y1="{yv:.2f}" x2="{x0}" y2="{yv:.2f}" stroke="#9ca3af"/>')
        label = f"{t:g}" if y_scale == "linear" else f"1e{int(round(_log10(t)))}"
        parts.append(
            f'<text x="{x0-10}" y="{yv+3:.2f}" font-family="ui-sans-serif, system-ui" font-size="10" text-anchor="end" fill="#374151">{_svg_escape(label)}</text>'
        )
        parts.append(
            f'<line x1="{x0}" y1="{yv:.2f}" x2="{x0+plot_w}" y2="{yv:.2f}" stroke="#f3f4f6"/>'
        )

    parts.append(
        f'<text x="18" y="{y0 + plot_h/2:.2f}" font-family="ui-sans-serif, system-ui" font-size="12" text-anchor="middle" fill="#111827" transform="rotate(-90, 18, {y0 + plot_h/2:.2f})">{_svg_escape(y_label)}</text>'
    )

    # Lines + legend
    legend_x = margin["l"] + plot_w + 20
    legend_y = margin["t"] + 20

    for i, (name, pts) in enumerate(sorted(series.items(), key=lambda kv: kv[0])):
        color = _path_color(name)
        pts_sorted = sorted(pts, key=lambda p: p[0])
        d = " ".join(f"{x_map(s):.2f},{y_map(v):.2f}" for s, v in pts_sorted)
        parts.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
        # markers
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
        "--out-dir",
        default="src/warm_logic/docs/papers/09_boundary_elimination/figures",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out_dir)

    agg = load_aggregate(input_path)
    # We plot payload size on a log-x axis, so size=0 cannot be represented.
    # Keep the 0B measurements in telemetry, but omit them from plots.
    sizes = sorted({s for (_p, s) in agg.keys() if s > 0})

    o1_names = ["C noop", "Null (PyBytes)", "Acquire buffer (len_bytes)", "Null (PyBuffer)"]
    o1_series = {
        name: [(s, float(agg[(name, s)]["p50_median"])) for s in sizes] for name in o1_names
    }

    _render_plot(
        title="Boundary Overhead (O(1) paths)",
        subtitle="p50 median across repeats; corrected by empty-loop subtraction; x=payload size (log)",
        out_path=out_dir / "fig_o1_boundary_p50.svg",
        sizes=sizes,
        series=o1_series,
        x_label="Payload size",
        y_label="Latency (ns / call)",
        y_scale="linear",
        y_tick_step=10.0,
    )

    on_names = [
        "Copy (PyBytes to_vec)",
        "Copy (Buffer to_vec)",
        "Copy (BytesVec arg)",
        "Copy (Vec<u8> arg)",
        "Copy (Sequence to Vec<u8>)",
        "Consume (PyBytes)",
    ]
    on_series = {
        name: [(s, float(agg[(name, s)]["p50_median"])) for s in sizes] for name in on_names
    }
    _render_plot(
        title="Boundary Costs (O(N) paths)",
        subtitle="p50 median across repeats; corrected by empty-loop subtraction; log-log",
        out_path=out_dir / "fig_on_scaling_p50.svg",
        sizes=sizes,
        series=on_series,
        x_label="Payload size",
        y_label="Latency (ns / call, log10)",
        y_scale="log10",
    )

    print(f"Wrote: {out_dir / 'fig_o1_boundary_p50.svg'}")
    print(f"Wrote: {out_dir / 'fig_on_scaling_p50.svg'}")


if __name__ == "__main__":
    main()
