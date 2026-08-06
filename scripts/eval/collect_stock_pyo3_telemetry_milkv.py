#!/usr/bin/env python3
"""
MILK-V PATCHED VERSION: bypasses local build and uses pre-built cross-compiled binary.
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
    return "riscv64gc-unknown-linux-musl"


def _ensure_venv(venv_dir: Path) -> Path:
    python = venv_dir / "bin" / "python"
    if python.exists():
        return python
    _run([sys.executable, "-m", "venv", str(venv_dir)])
    return python


def _strip_patch_crates_io(cargo_toml_text: str) -> str:
    return cargo_toml_text


def _pin_pyo3_version(cargo_toml_text: str, *, version: str) -> str:
    return cargo_toml_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="bridge_eval_v3_stock_pyo3")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--pyo3-version", default="0.22.6")
    args = parser.parse_args()
    args.offline_cargo = True

    out_dir = OUT_ROOT / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    venv_dir = OUT_ROOT / "_stock_pyo3_venv"
    python = _ensure_venv(venv_dir)

    # Manual installation of pre-built SO
    site_packages = (
        venv_dir
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    if not site_packages.exists():
        out = subprocess.check_output(
            [str(python), "-c", "import site; print(site.getsitepackages()[0])"],
            text=True,
        ).strip()
        site_packages = Path(out)

    artifact = Path("./scripts/eval/warm_logic_rs_stock.so")
    dest = site_packages / "warm_logic_rs.so"
    print(f"Installing {artifact} -> {dest}")
    shutil.copy2(artifact, dest)

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

    print(f"\nOK: wrote telemetry: {out_dir / 'full_telemetry.json'}")


if __name__ == "__main__":
    main()
