#!/usr/bin/env python3
"""
Collect "stock PyO3" telemetry for Paper 09 without mutating the repo's pinned patched build.

Strategy:
- Copy `rust_core/` into `out/bridge_eval/_stock_pyo3_src/`
- Remove `[patch.crates-io]` from the copied Cargo.toml so Cargo resolves PyO3 from crates.io
- Pin the PyO3 dependency to v0.22.6 (same as the vendored patched version) for apples-to-apples comparison
- Build a wheel via maturin and install it into a temporary venv
- Run `scripts/eval/eval_bridge_v3.py` with `WARM_LOGIC_RS_USE_INSTALLED=1`
"""

from __future__ import annotations

import argparse
import os
import re
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
    if not python.exists():
        raise RuntimeError(f"venv python not found at: {python}")
    _run([str(python), "-m", "pip", "install", "-U", "pip", "wheel"])

    if os.environ.get("OFFLINE_CARGO", "0") != "1":
        _run([str(python), "-m", "pip", "install", "maturin"])
    return python


def _strip_patch_crates_io(cargo_toml_text: str) -> str:
    # Remove the entire `[patch.crates-io]` section if present.
    lines = cargo_toml_text.splitlines()
    out: list[str] = []
    in_patch = False
    for line in lines:
        if re.match(r"^\[patch\.crates-io\]\s*$", line.strip()):
            in_patch = True
            continue
        if in_patch:
            if line.startswith("[") and line.strip().endswith("]"):
                in_patch = False
                out.append(line)
            else:
                continue
        else:
            out.append(line)
    text = "\n".join(out).rstrip() + "\n"
    return text


def _pin_pyo3_version(cargo_toml_text: str, *, version: str) -> str:
    # Pin the pyo3 dependency version while preserving the rest of the inline table.
    # Example line:
    #   pyo3 = { version = "0.22.0", features = [...], optional = true }
    lines = cargo_toml_text.splitlines()
    out: list[str] = []
    changed = 0
    for line in lines:
        if (
            line.strip().startswith("pyo3")
            and "version" in line
            and "{" in line
            and "}" in line
        ):
            new_line, n = re.subn(
                r'(version\s*=\s*")([^"]+)(")',
                r"\g<1>" + version + r"\g<3>",
                line,
            )
            if n:
                changed += 1
                out.append(new_line)
                continue
        out.append(line)
    if changed != 1:
        raise RuntimeError(
            f"Expected to patch exactly 1 pyo3 version, but changed {changed}."
        )
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="bridge_eval_v3_stock_pyo3")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--pyo3-version", default="0.22.6")
    args = parser.parse_args()
    args.offline_cargo = os.environ.get("OFFLINE_CARGO", "0") == "1"

    out_dir = OUT_ROOT / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    src_dir = OUT_ROOT / "_stock_pyo3_src"
    venv_dir = OUT_ROOT / "_stock_pyo3_venv"
    wheels_dir = OUT_ROOT / "_stock_pyo3_wheels"

    if src_dir.exists():
        shutil.rmtree(src_dir)
    if wheels_dir.exists():
        shutil.rmtree(wheels_dir)

    print(f"Repo root: {REPO_ROOT}")
    print(f"Build dir: {src_dir}")
    print(f"Wheel dir: {wheels_dir}")
    print(f"Venv dir: {venv_dir}")
    print(f"Telemetry dir: {out_dir}")

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

    cargo_toml_path = src_dir / "Cargo.toml"
    cargo_text = cargo_toml_path.read_text(encoding="utf-8")
    cargo_text = _strip_patch_crates_io(cargo_text)
    cargo_text = _pin_pyo3_version(cargo_text, version=args.pyo3_version)
    cargo_toml_path.write_text(cargo_text, encoding="utf-8")

    python = _ensure_venv(venv_dir)
    target = _rust_host_target()

    wheels_dir.mkdir(parents=True, exist_ok=True)
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
    print(f"\nOK: wrote telemetry: {telemetry_path}")


if __name__ == "__main__":
    main()
