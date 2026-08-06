# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#!/usr/bin/env python3
"""
wlctl - WarmLogic Command Line Interface

A command-line tool for managing WarmLogic Sovereign Nodes.
Built with Typer for modern CLI UX.

Usage:
    wlctl version     # Show version and build info
    wlctl status      # Check kernel and node health
    wlctl identity    # Show current node identity
    wlctl start       # Start the Sovereign Kernel
    wlctl stop        # Stop the Sovereign Kernel
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

# Version info
_local_version_file = Path(__file__).resolve().parents[2] / "VERSION"
__version__ = (
    _local_version_file.read_text().strip()
    if _local_version_file.exists()
    else "0.0.0"
)
__era__ = 6200

app = typer.Typer(
    name="wlctl",
    help="WarmLogic Sovereign Node Control",
    add_completion=False,
    rich_markup_mode="rich",
)


def get_warm_logic_root() -> Path:
    """Find the WarmLogic project root."""
    # Check WARM_LOGIC_ROOT env var first
    if root := os.environ.get("WARM_LOGIC_ROOT"):
        return Path(root)

    # Otherwise search upward from cwd
    current = Path.cwd()
    while current != current.parent:
        has_project = (current / "pyproject.toml").exists()
        has_pkg_layout = (current / "warm_logic").is_dir() or (
            current / "src" / "warm_logic"
        ).is_dir()
        if has_project and has_pkg_layout:
            return current
        current = current.parent

    return Path.cwd()


def get_version_from_file() -> str:
    """Read version from VERSION file."""
    root = get_warm_logic_root()
    candidates = [
        _local_version_file,
        root / "src" / "warm_logic" / "VERSION",
        root / "warm_logic" / "VERSION",
    ]
    for version_file in candidates:
        if version_file.exists():
            return version_file.read_text().strip()
    return __version__


@app.command()
def version():
    """
    Display WarmLogic version and build information.
    """
    typer.echo(f"wlctl v{get_version_from_file()}")
    typer.echo(f"Era: {__era__}")
    typer.echo(f"Python: {sys.version.split()[0]}")

    # Check Rust core
    try:
        import warm_logic_rs  # type: ignore

        rust_version = getattr(warm_logic_rs, "__version__", "unknown")
        typer.echo(f"Rust Core: {rust_version}")
    except ImportError:
        typer.echo("[yellow]Rust Core: Not installed[/yellow]")


@app.command()
def status():
    """
    Check the health status of the WarmLogic kernel.
    """
    status_data = {
        "kernel": "inactive",
        "dht": "inactive",
        "consensus": "inactive",
        "identity": None,
    }

    # Check if kernel is running (via PID file or socket)
    root = get_warm_logic_root()
    pid_file = root / ".warm_logic" / "kernel.pid"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            status_data["kernel"] = "active"
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    # Check identity
    id_file = root / ".warm_logic" / "identity.json"
    if id_file.exists():
        try:
            id_data = json.loads(id_file.read_text())
            status_data["identity"] = id_data.get("node_id", "")[:16] + "..."
        except (json.JSONDecodeError, KeyError):
            pass

    # Display status
    kernel_icon = "✅" if status_data["kernel"] == "active" else "❌"
    typer.echo(f"{kernel_icon} Kernel: {status_data['kernel']}")

    if status_data["identity"]:
        typer.echo(f"🔑 Identity: {status_data['identity']}")
    else:
        typer.echo("[yellow]🔑 Identity: Not initialized[/yellow]")


@app.command()
def identity(
    show_full: bool = typer.Option(False, "--full", "-f", help="Show full key"),
):
    """
    Display the current node identity.
    """
    try:
        from warm_logic.kernel.identity.kinetic_id import KineticIdentity
    except ImportError:
        typer.echo("[red]Error: WarmLogic kernel not found in PYTHONPATH[/red]")
        raise typer.Exit(1)

    root = get_warm_logic_root()
    id_file = root / ".warm_logic" / "identity.json"

    if not id_file.exists():
        typer.echo(
            "[yellow]No identity found. Run 'wlctl init' to create one.[/yellow]"
        )
        raise typer.Exit(0)

    try:
        id_data = json.loads(id_file.read_text())
        node_id = id_data.get("node_id", "unknown")
        pub_key = id_data.get("public_key", "unknown")

        typer.echo("🔑 Sovereign Identity")
        typer.echo("-" * 40)

        if show_full:
            typer.echo(f"Node ID:    {node_id}")
            typer.echo(f"Public Key: {pub_key}")
        else:
            typer.echo(f"Node ID:    {node_id[:32]}...")
            typer.echo(f"Public Key: {pub_key[:32]}...")

    except json.JSONDecodeError:
        typer.echo("[red]Error: Corrupted identity file[/red]")
        raise typer.Exit(1)


@app.command()
def init(
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing identity"
    ),
):
    """
    Initialize a new Sovereign Node identity.
    """
    try:
        from warm_logic.kernel.identity.kinetic_id import KineticIdentity
    except ImportError:
        typer.echo("[red]Error: WarmLogic kernel not found in PYTHONPATH[/red]")
        raise typer.Exit(1)

    root = get_warm_logic_root()
    wl_dir = root / ".warm_logic"
    wl_dir.mkdir(exist_ok=True)

    id_file = wl_dir / "identity.json"

    if id_file.exists() and not force:
        typer.echo(
            "[yellow]Identity already exists. Use --force to overwrite.[/yellow]"
        )
        raise typer.Exit(0)

    # Generate new keypair
    import hashlib

    pub, priv = KineticIdentity.generate_keypair()
    pub_bytes = bytes.fromhex(pub)
    node_id = hashlib.sha256(pub_bytes).hexdigest()

    id_data = {
        "node_id": node_id,
        "public_key": pub,
        "era": __era__,
    }

    id_file.write_text(json.dumps(id_data, indent=2))
    typer.echo(f"✅ Identity created: {node_id[:16]}...")
    typer.echo(f"   Stored in: {id_file}")


@app.command()
def start(
    port: int = typer.Option(4001, "--port", "-p", help="UDP port for DHT"),
    foreground: bool = typer.Option(
        False, "--foreground", "-f", help="Run in foreground"
    ),
):
    """
    Start the Sovereign Kernel.
    """
    typer.echo(f"🚀 Starting WarmLogic Kernel on port {port}...")

    if foreground:
        typer.echo("[yellow]Running in foreground mode. Press Ctrl+C to stop.[/yellow]")
        try:
            import asyncio

            from warm_logic.kernel.kernel_loop import run_kernel_loop

            asyncio.run(run_kernel_loop(port=port))
        except ImportError as e:
            typer.echo(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
        except KeyboardInterrupt:
            typer.echo("\n🛑 Kernel stopped.")
    else:
        # Simple daemon-like start using subprocess.Popen
        root = get_warm_logic_root()
        pid_file = root / ".warm_logic" / "kernel.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                typer.echo(f"[yellow]Kernel is already running (PID {pid})[/yellow]")
                raise typer.Exit(1)
            except (ProcessLookupError, ValueError):
                pid_file.unlink()

        typer.echo("[yellow]Starting in background mode...[/yellow]")
        log_file = root / ".warm_audit.jsonl"
        with open(log_file, "a") as f:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "warm_logic.kernel.kernel_loop",
                    "--port",
                    str(port),
                ],
                stdout=f,
                stderr=f,
                start_new_session=True,
            )
        pid_file.write_text(str(proc.pid))
        typer.echo(f"✅ Kernel started in background (PID {proc.pid})")
        typer.echo(f"   Logs: {log_file}")


@app.command()
def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(20, "--lines", "-n", help="Number of lines to show"),
):
    """
    View the Sovereign Audit logs.
    """
    root = get_warm_logic_root()
    log_file = root / ".warm_audit.jsonl"

    if not log_file.exists():
        typer.echo("[yellow]No logs found yet.[/yellow]")
        raise typer.Exit(0)

    if follow:
        try:
            import subprocess

            subprocess.run(["tail", "-f", "-n", str(lines), str(log_file)])
        except KeyboardInterrupt:
            pass
    else:
        content = log_file.read_text().splitlines()
        for line in content[-lines:]:
            typer.echo(line)


@app.command()
def collect_diagnostics(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output tarball path"
    ),
):
    """
    Collect system logs and state for diagnostic purposes.
    """
    root = get_warm_logic_root()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    diag_dir = root / ".warm_logic" / f"diag_{timestamp}"
    diag_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"📁 Collecting diagnostics into {diag_dir}...")

    # 1. Collect logs
    log_file = root / ".warm_audit.jsonl"
    if log_file.exists():
        import shutil

        shutil.copy2(log_file, diag_dir / "audit.jsonl")

    # 2. Collect identity public info (no private keys!)
    id_file = root / ".warm_logic" / "identity.json"
    if id_file.exists():
        try:
            data = json.loads(id_file.read_text())
            public_info = {
                "node_id": data.get("node_id"),
                "public_key": data.get("public_key"),
                "era": data.get("era"),
            }
            (diag_dir / "identity_public.json").write_text(
                json.dumps(public_info, indent=2)
            )
        except Exception:
            pass

    # 3. Collect system info
    import platform

    sys_info = {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": sys.version,
        "timestamp": timestamp,
    }
    (diag_dir / "system_info.json").write_text(json.dumps(sys_info, indent=2))

    # 4. Create tarball
    tar_path = output or root / f"warmlogic_diag_{timestamp}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(diag_dir, arcname=diag_dir.name)

    # Cleanup temp dir
    import shutil

    shutil.rmtree(diag_dir)

    typer.echo(f"✅ Diagnostics collected: {tar_path}")


@app.command()
def stop():
    """
    Stop the Sovereign Kernel.
    """
    root = get_warm_logic_root()
    pid_file = root / ".warm_logic" / "kernel.pid"

    if not pid_file.exists():
        typer.echo("[yellow]No running kernel found.[/yellow]")
        raise typer.Exit(0)

    try:
        pid = int(pid_file.read_text().strip())
        import signal

        os.kill(pid, signal.SIGTERM)
        pid_file.unlink()
        typer.echo(f"🛑 Kernel stopped (PID {pid})")
    except (ValueError, ProcessLookupError):
        typer.echo("[yellow]Kernel not running (stale PID file removed)[/yellow]")
        pid_file.unlink(missing_ok=True)
    except PermissionError:
        typer.echo("[red]Permission denied. Try sudo.[/red]")
        raise typer.Exit(1)


def main():
    """Entry point for wlctl."""
    app()


if __name__ == "__main__":
    main()
