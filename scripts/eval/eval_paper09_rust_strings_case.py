#!/usr/bin/env python3
"""
Paper 09: Ecosystem case study (real PyO3 package).

Goal (reviewer-facing):
  - Show that the `bytes -> Vec<u8>` semantic footgun is not only a synthetic benchmark.
  - Demonstrate that a binding-local "bytes-like extractor" mitigation can remove the cliff
    without changing the Python-level signature.

Design:
  - Use a published crates.io + PyPI package: rust-strings==0.6.0.
  - Compare two builds of the same package version:
      (A) stock: original signature uses `Option<Vec<u8>>`
      (B) bytesvec: replace only the Rust arg type with `Option<BytesVec>`
          (a FromPyObject extractor that copies contiguously from bytes/buffer)
  - Measure corrected per-call latency (empty-loop corrected) for the exported function:
      rust_strings.strings(bytes=payload, min_length=<large>)

This script is self-contained:
  - Extracts the cached .crate tarball to out/bridge_eval/rust_strings_case/_src
  - Creates + caches two venvs and installs the two variants via `maturin develop`
  - Runs repeated measurements and writes a single telemetry JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


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


def _quantile(samples_sorted: list[float], q: float) -> float:
    if not samples_sorted:
        return float("nan")
    idx = int(len(samples_sorted) * q)
    idx = max(0, min(idx, len(samples_sorted) - 1))
    return samples_sorted[idx]


def _iqr(values: list[float]) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    return _quantile(xs, 0.75) - _quantile(xs, 0.25)


def _measure_empty_loop(batch: int) -> int:
    start = time.perf_counter_ns()
    for _ in range(batch):
        pass
    end = time.perf_counter_ns()
    return end - start


def measure_corrected_ns_per_call(
    func: Callable[[], Any],
    *,
    iterations: int,
    batch: int,
    warmup: int,
) -> dict[str, float | int]:
    for _ in range(warmup):
        func()

    corrected: list[float] = []
    negative = 0
    for _ in range(iterations):
        empty = _measure_empty_loop(batch)
        start = time.perf_counter_ns()
        for _ in range(batch):
            func()
        end = time.perf_counter_ns()

        per_call = (end - start - empty) / batch
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

    # The .crate is a tarball. It contains a top-level directory named <crate>-<version>.
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

    bindings = patched_dir / "src" / "python_bindings.rs"
    src = bindings.read_text(encoding="utf-8")

    if "struct BytesVec(" in src:
        return

    # 1) Imports
    if "use pyo3::types::PyBytes;" not in src:
        src = src.replace(
            "use pyo3::prelude::*;\n",
            "use pyo3::prelude::*;\nuse pyo3::types::PyBytes;\nuse pyo3::buffer::PyBuffer;\n",
        )

    # 2) Extractor definition (placed after EncodingNotFoundError -> PyErr impl)
    needle = "impl From<EncodingNotFoundError> for PyErr {\n"
    idx = src.find(needle)
    if idx < 0:
        raise RuntimeError("patch failed: could not find EncodingNotFoundError PyErr impl")
    impl_end = src.find("}\n\n", idx)
    if impl_end < 0:
        raise RuntimeError("patch failed: could not find end of EncodingNotFoundError PyErr impl")
    insert_at = impl_end + 3
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

        let buf = PyBuffer::<u8>::get(obj)?;
        Ok(BytesVec(buf.to_vec(obj.py())?))
    }
}

"""
    src = src[:insert_at] + bytesvec_def + src[insert_at:]

    # 3) Replace arg types + uses in two functions (strings + dump_strings)
    src = src.replace("bytes: Option<Vec<u8>>", "bytes: Option<BytesVec>")
    src = src.replace("RustBytesConfig::new(bytes)\n", "RustBytesConfig::new(bytes.0)\n")

    bindings.write_text(src, encoding="utf-8")


def _build_wheel_with_maturin(*, python: Path, project_dir: Path, wheel_dir: Path) -> Path:
    env = os.environ.copy()
    # Avoid maturin refusing to run when both are set (common with conda shells).
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
            "python_bindings",
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
    min_length: int,
    repeats: int,
    params: SampleParams,
) -> dict[str, Any]:
    code = r"""
import json, time, statistics, platform
from importlib import metadata

import rust_strings

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

def run_once(payload, min_length):
    # Intentionally ignore the returned list values; only touch length.
    out = rust_strings.strings(bytes=payload, min_length=min_length)
    return len(out)

"""
    # The payload is constructed in the target interpreter to avoid cross-interpreter transfer.
    code += f"""
size_bytes = {int(size_bytes)}
min_length = {int(min_length)}
payload = b"\\x01" * size_bytes
repeats = {int(repeats)}
iterations = {int(params.iterations)}
batch = {int(params.batch)}
warmup = {int(params.warmup)}

rows = []
for _rep in range(repeats):
    black_box = [0]
    def fn():
        black_box[0] ^= run_once(payload, min_length)
        return black_box[0]
    rows.append(measure_corrected_ns_per_call(fn, iterations=iterations, batch=batch, warmup=warmup))

p50s = [r["p50"] for r in rows]
p99s = [r["p99"] for r in rows]

out = {{
  "dist_version": metadata.version("rust-strings"),
  "python": platform.python_version(),
  "platform": platform.platform(),
  "size_bytes": size_bytes,
  "min_length": min_length,
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
    raw = subprocess.check_output([str(python), "-c", code], text=True)
    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--crate",
        default="out/bridge_eval/_crates_cache/rust-strings-0.6.0.crate",
        help="path to the cached rust-strings .crate tarball",
    )
    parser.add_argument(
        "--sizes",
        default="100000,10000000",
        help="comma-separated payload sizes to measure (bytes)",
    )
    parser.add_argument("--min-length", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument(
        "--out",
        default="out/bridge_eval/rust_strings_case/rust_strings_case_telemetry.json",
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

    root = Path("out/bridge_eval/rust_strings_case")
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
    min_length = int(args.min_length)

    results: dict[str, Any] = {
        "run_id": "rust_strings_case",
        "ts": time.time(),
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "inputs": {
            "crate_path": str(crate_path),
            "crate_sha256": _sha256(crate_path),
            "sizes": sizes,
            "min_length": min_length,
            "repeats": repeats,
            "params": {
                "iterations": params.iterations,
                "batch": params.batch,
                "warmup": params.warmup,
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
                    min_length=min_length,
                    repeats=repeats,
                    params=params,
                )
            )
        results["variants"][variant] = {
            "python": str(python),
            "sizes": per_size,
        }

    out_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
