#!/usr/bin/env python3
"""
Collect "patched PyO3" telemetry for Paper 09 by building the wheel from the current repo state
and running `eval_bridge_v3.py` against the installed wheel (venv-local).

This avoids relying on a prebuilt `.so` sitting in the repo and makes the stock-vs-patched
comparison more apples-to-apples.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO_ROOT / "out" / "bridge_eval"


def _run(
    cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None, env=env)


def _rust_host_target() -> str:
    out = subprocess.check_output(["rustc", "-vV"], text=True)
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split("host:", 1)[1].strip()
    raise RuntimeError("Failed to detect rust host target (rustc -vV)")


def _ensure_venv(venv_dir: Path) -> Path:
    python = venv_dir / "bin" / "python"
    if python.exists():
        return python
    _run([sys.executable, "-m", "venv", str(venv_dir)])
    _run([str(python), "-m", "pip", "install", "-U", "pip", "wheel"])

    if os.environ.get("OFFLINE_CARGO", "0") != "1":
        _run([str(python), "-m", "pip", "install", "maturin"])
    return python


def _assert_patched_vec_u8_fast(telemetry_path: Path) -> None:
    # "Patched PyO3" is defined by a contiguous fast path for `Copy (Vec<u8> arg)` at large sizes.
    # If this is not true, the most likely explanation is that the patch override is not active
    # (e.g., missing `[patch.crates-io]` in `rust_core/Cargo.toml`).
    size_bytes = 10_000_000
    max_p50_ns = (
        5_000_000  # 5ms is an extremely conservative upper bound for the fast path.
    )
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    for row in data.get("aggregate", []):
        if (
            str(row.get("path")) == "Copy (Vec<u8> arg)"
            and int(row.get("size_bytes")) == size_bytes
        ):
            p50 = float(row.get("p50_median"))
            if p50 > max_p50_ns:
                raise RuntimeError(
                    "Patched wheel sanity check failed: expected a contiguous fast path.\n"
                    f"- path: Copy (Vec<u8> arg)\n"
                    f"- size_bytes: {size_bytes}\n"
                    f"- p50_median: {p50:.0f} ns\n"
                    f"- expected: <= {max_p50_ns} ns\n"
                    "\n"
                    "This usually means the PyO3 patch override is not active.\n"
                    'Check `rust_core/Cargo.toml` for `[patch.crates-io] pyo3 = { path = "vendor/pyo3-0.22.6" }`.\n'
                )
            return
    raise RuntimeError(
        f"Missing Copy (Vec<u8> arg) for size={size_bytes} in: {telemetry_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="bridge_eval_v3_pyo3_patch")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument(
        "--venv-dir",
        default=str(OUT_ROOT / "_patched_pyo3_venv"),
        help="Venv directory to use (allows parallel Python-version sweeps).",
    )
    parser.add_argument(
        "--wheels-dir",
        default=str(OUT_ROOT / "_patched_pyo3_wheels"),
        help="Wheel output directory (allows parallel Python-version sweeps).",
    )
    args = parser.parse_args()
    args.offline_cargo = os.environ.get("OFFLINE_CARGO", "0") == "1"

    out_dir = OUT_ROOT / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    venv_dir = Path(args.venv_dir)
    wheels_dir = Path(args.wheels_dir)
    src_dir = OUT_ROOT / "_patched_pyo3_src"

    if src_dir.exists():
        shutil.rmtree(src_dir)
    if wheels_dir.exists():
        shutil.rmtree(wheels_dir)

    # Build from a clean staging copy to avoid accidentally packaging local build artifacts.
    # Note: the Rust extension package lives under `rust_core/` in this repo.
    shutil.copytree(
        REPO_ROOT / "rust_core",
        src_dir,
        ignore=shutil.ignore_patterns(
            "target",
            "target_junk",
            "__pycache__",
            "*.log",
            "*.err",
            "tmp",
        ),
    )
    shutil.rmtree(src_dir / "dist", ignore_errors=True)
    for p in src_dir.glob("warm_logic_rs-*.dist-info"):
        shutil.rmtree(p, ignore_errors=True)

    wheels_dir.mkdir(parents=True, exist_ok=True)

    python = _ensure_venv(venv_dir)
    target = _rust_host_target()

    env = os.environ.copy()
    cargo_bin = str(Path.home() / ".cargo" / "bin")
    if cargo_bin not in env.get("PATH", ""):
        env["PATH"] = f"{cargo_bin}:{env.get('PATH', '')}"

    if args.offline_cargo:
        print("!!! RUNNING OFFLINE CARGO BUILD (Bypassing Maturin) !!!")
        # Direct cargo build
        _run(
            [
                "cargo",
                "build",
                "--release",
                "--offline",
                "--lib",
                "--features",
                "python",
            ],
            cwd=src_dir,
            env=env,
        )
        # Find the .so / .dylib
        # rust_core uses crate-type = ["cdylib", "rlib"] -> libwarm_logic_rs.so
        # We need to install it into site-packages
        site_packages = (
            venv_dir
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )
        if not site_packages.exists():
            # Try to find it via python (could be lib64 etc)
            out = subprocess.check_output(
                [str(python), "-c", "import site; print(site.getsitepackages()[0])"],
                text=True,
            ).strip()
            site_packages = Path(out)

        # Copy artifact
        # On Linux it's libwarm_logic_rs.so
        # On Mac it's libwarm_logic_rs.dylib
        # We rename to warm_logic_rs.so (or .abi3.so) for python to pick it up
        release_dir = src_dir / "target" / "release"
        artifact = release_dir / "libwarm_logic_rs.so"
        if not artifact.exists():
            artifact = (
                release_dir / "libwarm_logic_rs.dylib"
            )  # Mac fallback just in case

        if not artifact.exists():
            # Try checking for any libwarm_logic_rs.*
            libs = list(release_dir.glob("libwarm_logic_rs.*"))
            if libs:
                artifact = libs[0]

        if not artifact.exists():
            raise RuntimeError(f"Could not find build artifact in {release_dir}")

        dest = site_packages / "warm_logic_rs.so"
        print(f"Installing {artifact} -> {dest}")
        shutil.copy2(artifact, dest)

    else:
        _run(
            [
                str(python),
                "-m",
                "maturin",
                "build",
                "--release",
                "--target",
                target,
                "--features",
                "python",
                "--out",
                str(wheels_dir),
            ],
            cwd=src_dir,
            env=env,
        )

        whls = sorted(wheels_dir.glob("*.whl"))
        if not whls:
            raise RuntimeError(f"No wheels produced in: {wheels_dir}")
        wheel = whls[-1]
        _run([str(python), "-m", "pip", "install", "--force-reinstall", str(wheel)])

    env = os.environ.copy()
    env["WARM_LOGIC_RS_USE_INSTALLED"] = "1"

    _run(
        [
            str(python),
            str(REPO_ROOT / "scripts" / "eval" / "eval_bridge_v3.py"),
            "--run-id",
            args.run_id,
            "--repeats",
            str(args.repeats),
            "--warmup",
            str(args.warmup),
        ],
        cwd=REPO_ROOT,
        env=env,
    )

    telemetry_path = out_dir / "full_telemetry.json"
    if not telemetry_path.exists():
        raise RuntimeError(f"Expected telemetry at: {telemetry_path}")
    _assert_patched_vec_u8_fast(telemetry_path)
    print(f"\nOK: wrote telemetry: {telemetry_path}")


if __name__ == "__main__":
    main()
