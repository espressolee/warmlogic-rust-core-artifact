#!/usr/bin/env python3
"""
Paper 09: Ecosystem case study (real PyO3 package).

Goal (reviewer-facing):
  - Show that the `bytes -> Vec<u8>` semantic footgun is not only a synthetic benchmark.
  - Demonstrate that a binding-local "bytes-like extractor" mitigation can remove the cliff
    without changing the Python-level signature.

Design:
  - Use a published crates.io + PyPI package: vtracer (crate v0.6.5; PyPI version per pyproject).
  - Compare two builds of the same published source tarball:
      (A) stock: original signature uses `img_bytes: Vec<u8>`
      (B) bytesvec: replace only the Rust arg type with `img_bytes: BytesVec`
          (a FromPyObject extractor that copies contiguously from bytes/buffer, else falls back)
  - Measure corrected per-call latency for:
      vtracer.convert_raw_image_to_svg(payload, "bmp")

Payload choice (important):
  - The benchmark uses a valid 1x1 BMP header and pads trailing bytes to reach the target length.
    This keeps decode/convert work ~constant while forcing the boundary conversion cost to scale
    with input length. This is aligned with the paper's scope (boundary + conversion policy), not
    an attempt to benchmark image vectorization quality or throughput.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SampleParams:
    iterations: int
    batch: int
    warmup: int


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _ensure_venv(venv_dir: Path) -> tuple[Path, Path]:
    if not venv_dir.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    python = (venv_dir / "bin" / "python").absolute()
    pip = (venv_dir / "bin" / "pip").absolute()

    subprocess.check_call([str(python), "-m", "pip", "install", "-U", "pip"])
    subprocess.check_call([str(python), "-m", "pip", "install", "maturin==1.11.5"])
    return python, pip


def _extract_crate(crate_path: Path, *, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(crate_path) as tf:
        members = tf.getmembers()
        top_level = {m.name.split("/", 1)[0] for m in members if m.name and "/" in m.name}
        if len(top_level) != 1:
            raise RuntimeError(f"unexpected crate layout: top_level={sorted(top_level)}")
        (root_name,) = tuple(top_level)

        root_dir = dst_dir / root_name
        if root_dir.exists():
            return root_dir
        tf.extractall(dst_dir)
        if not root_dir.exists():
            raise RuntimeError(f"extract failed: missing {root_dir}")
        return root_dir


def _apply_bytesvec_patch(*, stock_dir: Path, patched_dir: Path) -> None:
    if patched_dir.exists():
        return
    shutil.copytree(stock_dir, patched_dir)

    bindings = patched_dir / "src" / "python.rs"
    src = bindings.read_text(encoding="utf-8")

    if "struct BytesVec(" in src:
        return

    # 1) Import needed for the extractor
    if "use pyo3::types::PyBytes;" not in src:
        src = src.replace(
            "use pyo3::{exceptions::PyException, prelude::*};\n",
            "use pyo3::{exceptions::PyException, prelude::*};\n"
            "use pyo3::types::PyBytes;\n"
            "use pyo3::buffer::PyBuffer;\n",
        )

    # 2) Insert BytesVec definition just before the first #[pyfunction]
    needle = "/// Python binding\n"
    idx = src.find(needle)
    if idx < 0:
        raise RuntimeError("patch failed: could not find python binding header")

    bytesvec_def = """\
/// A bytes-like extractor which copies via contiguous buffer APIs instead of per-element sequence extraction.
///
/// This mirrors the `BytesVec` mitigation discussed in Paper 09: when a binding needs owned bytes,
/// forcing contiguous-copy semantics avoids pathological `bytes -> Vec<u8>` element-wise conversion.
struct BytesVec(Vec<u8>);

impl<'py> FromPyObject<'py> for BytesVec {
    fn extract(obj: &'py PyAny) -> PyResult<Self> {
        if let Ok(b) = obj.downcast::<PyBytes>() {
            return Ok(BytesVec(b.as_bytes().to_vec()));
        }

        if let Ok(buf) = PyBuffer::<u8>::get(obj) {
            return Ok(BytesVec(buf.to_vec(obj.py())?));
        }

        // Preserve the broader (but slow) "sequence of ints" semantics as a fallback.
        Ok(BytesVec(obj.extract::<Vec<u8>>()?))
    }
}

"""
    src = src[:idx] + bytesvec_def + src[idx:]

    # 3) Patch only convert_raw_image_to_svg's first arg type.
    src = src.replace("img_bytes: Vec<u8>,", "img_bytes: BytesVec,")

    # 4) Fix call sites in this function body.
    src = src.replace("Cursor::new(img_bytes)", "Cursor::new(img_bytes.0)")

    bindings.write_text(src, encoding="utf-8")


def _build_wheel_with_maturin(*, python: Path, project_dir: Path, wheel_dir: Path) -> Path:
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)

    wheel_dir = wheel_dir.absolute()
    wheel_dir.mkdir(parents=True, exist_ok=True)
    for old in wheel_dir.glob("*.whl"):
        old.unlink()

    subprocess.check_call(
        [
            str(python),
            "-m",
            "maturin",
            "build",
            "--release",
            "--features",
            "pyo3/extension-module,python-binding",
            "--out",
            str(wheel_dir),
            "-q",
        ],
        cwd=project_dir,
        env=env,
    )

    wheels = sorted(wheel_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise RuntimeError(f"maturin build produced no wheels in {wheel_dir}")
    return wheels[-1]


def _pip_install_wheel(*, pip: Path, wheel: Path) -> None:
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    subprocess.check_call([str(pip), "install", "--force-reinstall", str(wheel)], env=env)


def _run_variant_measurement(
    *,
    python: Path,
    size_bytes: int,
    repeats: int,
    params: SampleParams,
) -> dict[str, Any]:
    code = r"""
import json, time, statistics, platform
from importlib import metadata

import vtracer

def _quantile(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    idx = int(len(xs) * q)
    idx = max(0, min(idx, len(xs)-1))
    return xs[idx]

def _iqr(values):
    if not values:
        return float("nan")
    xs = sorted(values)
    return _quantile(xs, 0.75) - _quantile(xs, 0.25)

def _measure_empty_loop(batch):
    start = time.perf_counter_ns()
    for _ in range(batch):
        pass
    end = time.perf_counter_ns()
    return end - start

def measure_corrected_ns_per_call(fn, *, iterations, batch, warmup):
    for _ in range(warmup):
        fn()

    corrected=[]
    negative=0
    for _ in range(iterations):
        empty=_measure_empty_loop(batch)
        start=time.perf_counter_ns()
        for _ in range(batch):
            fn()
        end=time.perf_counter_ns()
        per_call=(end-start-empty)/batch
        if per_call < 0:
            negative += 1
            per_call = 0.0
        corrected.append(per_call)
    corrected.sort()
    return {
        "iterations": iterations,
        "batch": batch,
        "p50": _quantile(corrected, 0.50),
        "p99": _quantile(corrected, 0.99),
        "negatives_clamped": negative,
    }

def make_bmp_1x1_padded(size_bytes: int):
    # 1x1 24-bit BMP with a 40-byte BITMAPINFOHEADER; pixel row padded to 4 bytes.
    base_len = 14 + 40 + 4
    if size_bytes < base_len:
        raise ValueError(f"size_bytes too small for BMP: {size_bytes} < {base_len}")

    file_size = size_bytes
    offset = 54
    image_size = 4
    width = 1
    height = 1

    def le16(x): return int(x).to_bytes(2, "little", signed=False)
    def le32(x): return int(x).to_bytes(4, "little", signed=False)

    header = b"".join([
        b"BM",
        le32(file_size),
        le16(0), le16(0),
        le32(offset),
        le32(40),
        le32(width),
        le32(height),
        le16(1),
        le16(24),
        le32(0),
        le32(image_size),
        le32(0),
        le32(0),
        le32(0),
        le32(0),
    ])
    pixel = b"\x00\x00\x00\x00"
    base = header + pixel
    assert len(base) == base_len, (len(base), base_len)
    return base + (b"\x00" * (size_bytes - base_len)), base_len

"""
    code += f"""
size_bytes = {int(size_bytes)}
repeats = {int(repeats)}
iterations = {int(params.iterations)}
batch = {int(params.batch)}
warmup = {int(params.warmup)}

payload, base_len = make_bmp_1x1_padded(size_bytes)

rows = []
for _rep in range(repeats):
    black_box = [0]
    def fn():
        svg = vtracer.convert_raw_image_to_svg(payload, "bmp")
        black_box[0] ^= len(svg)
        return black_box[0]
    rows.append(measure_corrected_ns_per_call(fn, iterations=iterations, batch=batch, warmup=warmup))

p50s = [r["p50"] for r in rows]
p99s = [r["p99"] for r in rows]

out = {{
  "dist_version": metadata.version("vtracer"),
  "python": platform.python_version(),
  "platform": platform.platform(),
  "size_bytes": size_bytes,
  "payload": {{
    "kind": "bmp_1x1_padded",
    "base_len": base_len,
    "format_arg": "bmp",
  }},
  "params": {{
    "repeats": repeats,
    "iterations": iterations,
    "batch": batch,
    "warmup": warmup,
  }},
  "per_repeat": rows,
  "summary": {{
    "p50_median": statistics.median(p50s),
    "p50_iqr": _iqr(p50s),
    "p99_median": statistics.median(p99s),
    "p99_iqr": _iqr(p99s),
  }},
}}
print(json.dumps(out))
"""
    raw = subprocess.check_output(
        [str(python), "-c", code],
        text=True,
        cwd=str(Path("out/bridge_eval/vtracer_case").absolute()),
    )
    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--crate",
        default="out/bridge_eval/_crates_cache/vtracer-0.6.5.crate",
        help="path to the cached vtracer .crate tarball",
    )
    parser.add_argument(
        "--sizes",
        default="100000,10000000",
        help="comma-separated payload sizes to measure (bytes)",
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument(
        "--out",
        default="out/bridge_eval/vtracer_case/vtracer_case_telemetry.json",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    crate_path = Path(args.crate)
    if not crate_path.exists():
        raise FileNotFoundError(crate_path)

    sizes = [int(x.strip()) for x in str(args.sizes).split(",") if x.strip()]
    if not sizes:
        raise ValueError("--sizes produced empty list")

    root = Path("out/bridge_eval/vtracer_case")
    src_root = root / "_src"
    stock_src = _extract_crate(crate_path, dst_dir=src_root)
    bytesvec_src = src_root / f"{stock_src.name}-bytesvec"
    _apply_bytesvec_patch(stock_dir=stock_src, patched_dir=bytesvec_src)

    stock_venv = root / "stock" / ".venv"
    bytesvec_venv = root / "bytesvec" / ".venv"
    stock_python, stock_pip = _ensure_venv(stock_venv)
    bytesvec_python, bytesvec_pip = _ensure_venv(bytesvec_venv)

    wheel_root = root / "_wheels"
    stock_wheel = _build_wheel_with_maturin(
        python=stock_python,
        project_dir=stock_src,
        wheel_dir=wheel_root / "stock",
    )
    _pip_install_wheel(pip=stock_pip, wheel=stock_wheel)

    bytesvec_wheel = _build_wheel_with_maturin(
        python=bytesvec_python,
        project_dir=bytesvec_src,
        wheel_dir=wheel_root / "bytesvec",
    )
    _pip_install_wheel(pip=bytesvec_pip, wheel=bytesvec_wheel)

    params = SampleParams(
        iterations=int(args.iterations),
        batch=int(args.batch),
        warmup=int(args.warmup),
    )
    repeats = int(args.repeats)

    results: dict[str, Any] = {
        "run_id": "vtracer_case",
        "ts": time.time(),
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "inputs": {
            "crate_path": str(crate_path),
            "crate_sha256": _sha256(crate_path),
            "sizes": sizes,
            "repeats": repeats,
            "params": {
                "iterations": params.iterations,
                "batch": params.batch,
                "warmup": params.warmup,
            },
            "payload": {
                "kind": "bmp_1x1_padded",
                "format_arg": "bmp",
            },
        },
        "variants": {},
    }

    for variant, python in [
        ("stock", stock_python),
        ("bytesvec", bytesvec_python),
    ]:
        per_size: list[dict[str, Any]] = []
        for size in sizes:
            per_size.append(
                _run_variant_measurement(
                    python=python,
                    size_bytes=size,
                    repeats=repeats,
                    params=params,
                )
            )
        results["variants"][variant] = {
            "python": str(python),
            "sizes": per_size,
        }

    out_path.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

