#!/usr/bin/env python3
"""
WarmLogic Runtime MCP Server

Provides runtime status and testing tools for Claude Code integration:
- Rust core status
- Test execution
- Coverage reporting
- Module health checks
- Dependency analysis

P-Series: P4xx (DevOps Band)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("MCP package not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)


# Find project root
def find_project_root() -> Path:
    """Find WarmLogic project root by looking for ROOT_MANIFEST.yaml"""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "ROOT_MANIFEST.yaml").exists():
            return parent
    return current


PROJECT_ROOT = find_project_root()
app = FastMCP("wl-runtime")


# === Rust Core Status ===


@app.tool()
async def rust_status(verbose: bool = False) -> str:
    """
    Check Rust core build status and health.

    Args:
        verbose: Show detailed module information

    Returns:
        Rust core status report
    """
    os.chdir(PROJECT_ROOT)
    report = ["Rust Core Status", "=" * 50]

    try:
        # Try to import warm_logic_rs
        import importlib

        spec = importlib.util.find_spec("warm_logic_rs")

        if spec is None:
            raise ImportError("warm_logic_rs not found")

        import warm_logic_rs

        # Basic info
        version = getattr(warm_logic_rs, "__version__", "unknown")
        so_path = (
            Path(warm_logic_rs.__file__) if hasattr(warm_logic_rs, "__file__") else None
        )

        report.extend(
            [
                "Status: READY",
                f"Version: {version}",
            ]
        )

        if so_path and so_path.exists():
            mtime = datetime.fromtimestamp(so_path.stat().st_mtime)
            age = datetime.now() - mtime
            report.extend(
                [
                    f"Built: {mtime.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Age: {age.days}d {age.seconds // 3600}h {(age.seconds % 3600) // 60}m",
                    f"Path: {so_path}",
                ]
            )

        report.append("")

        # Module list
        modules = [m for m in dir(warm_logic_rs) if not m.startswith("_")]
        report.append(f"Modules ({len(modules)}):")

        if verbose:
            for mod in modules:
                obj = getattr(warm_logic_rs, mod)
                report.append(f"  - {mod}: {type(obj).__name__}")
        else:
            report.append(
                f"  {', '.join(modules[:8])}{'...' if len(modules) > 8 else ''}"
            )

        # Check if rebuild needed
        rs_src = PROJECT_ROOT / "warm_logic_rs" / "src"
        if rs_src.exists() and so_path and so_path.exists():
            rs_files = list(rs_src.glob("**/*.rs"))
            if rs_files:
                newest_rs = max(f.stat().st_mtime for f in rs_files)
                if newest_rs > so_path.stat().st_mtime:
                    report.extend(
                        [
                            "",
                            "WARNING: Rust sources newer than build",
                            "Run: /wl-build rust",
                        ]
                    )

    except ImportError as e:
        report.extend(
            [
                "Status: NOT BUILT",
                f"Error: {e}",
                "",
                "To build:",
                "  cd warm_logic_rs && maturin develop",
            ]
        )

    return "\n".join(report)


# === Test Runner ===


@app.tool()
async def test_runner(
    scope: str = "fast", parallel: bool = True, verbose: bool = False
) -> str:
    """
    Run tests with intelligent caching and filtering.

    Args:
        scope: "fast", "all", "rust", "python", or specific path
        parallel: Run tests in parallel
        verbose: Show detailed output

    Returns:
        Test execution results
    """
    os.chdir(PROJECT_ROOT)
    report = ["WarmLogic Test Runner", "=" * 50]
    start_time = datetime.now()

    # Build command based on scope
    if scope == "rust":
        cmd = ["cargo", "test"]
        if verbose:
            cmd.extend(["--", "--nocapture"])
        cwd = str(PROJECT_ROOT / "warm_logic_rs")
    else:
        cmd = ["pytest"]
        if scope == "fast":
            cmd.extend(["-m", "not slow"])
        elif scope != "all":
            cmd.append(scope)

        if parallel:
            cmd.extend(["-n", "auto"])
        if verbose:
            cmd.append("-v")
        else:
            cmd.extend(["--tb=short", "-q"])
        cwd = str(PROJECT_ROOT)

    report.extend([f"Scope: {scope}", f"Command: {' '.join(cmd)}", ""])

    # Run tests
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=300,  # 5 minute timeout
        )

        duration = (datetime.now() - start_time).total_seconds()
        output = result.stdout + result.stderr

        report.append("Results:")
        report.append("-" * 30)

        # Extract summary
        for line in output.split("\n"):
            if any(
                kw in line.lower()
                for kw in ["passed", "failed", "error", "skipped", "test result"]
            ):
                report.append(line.strip())

        report.extend(
            ["", f"Duration: {duration:.1f}s", f"Exit code: {result.returncode}"]
        )

        if result.returncode != 0:
            report.extend(["", "Failures (last 15 lines):", "-" * 30])
            report.extend(output.strip().split("\n")[-15:])

    except subprocess.TimeoutExpired:
        report.append("ERROR: Test timeout (5 minutes)")
    except FileNotFoundError as e:
        report.append(f"ERROR: Command not found - {e}")

    return "\n".join(report)


# === Coverage Report ===


@app.tool()
async def coverage_report(format: str = "summary", threshold: int = 70) -> str:
    """
    Get code coverage metrics.

    Args:
        format: "summary", "json", "files"
        threshold: Minimum coverage percentage

    Returns:
        Coverage report
    """
    os.chdir(PROJECT_ROOT)

    cache_file = PROJECT_ROOT / ".coverage.json"

    # Check if we need to regenerate
    regenerate = False
    if not cache_file.exists():
        regenerate = True
    else:
        age = datetime.now().timestamp() - cache_file.stat().st_mtime
        if age > 300:  # 5 minutes
            regenerate = True

    if regenerate:
        # Run coverage
        try:
            subprocess.run(
                [
                    "pytest",
                    "--cov=warm_logic",
                    "--cov-report=json:.coverage.json",
                    "-q",
                    "--tb=no",
                    "-m",
                    "not slow",
                ],
                capture_output=True,
                cwd=PROJECT_ROOT,
                timeout=120,
            )
        except Exception:
            pass

    if not cache_file.exists():
        return "Coverage data not available. Run: /wl-coverage run"

    try:
        data = json.loads(cache_file.read_text())
    except json.JSONDecodeError:
        return "Coverage data corrupted. Run: /wl-coverage run"

    totals = data.get("totals", {})
    files = data.get("files", {})

    total_pct = totals.get("percent_covered", 0)

    report = [
        "Coverage Report",
        "=" * 50,
        f"Total Coverage: {total_pct:.1f}%",
        f"Threshold: {threshold}%",
        f"Status: {'PASS' if total_pct >= threshold else 'FAIL'}",
        "",
    ]

    if format == "summary":
        report.extend(
            [
                f"Lines: {totals.get('covered_lines', 0)}/{totals.get('num_statements', 0)}",
                f"Branches: {totals.get('covered_branches', 0)}/{totals.get('num_branches', 0)}",
            ]
        )

    elif format == "files":
        report.append("Files below threshold:")
        sorted_files = sorted(
            files.items(),
            key=lambda x: x[1].get("summary", {}).get("percent_covered", 100),
        )
        for path, info in sorted_files[:10]:
            pct = info.get("summary", {}).get("percent_covered", 0)
            if pct < threshold:
                report.append(f"  {pct:5.1f}% {path}")

    elif format == "json":
        return json.dumps(data, indent=2)[:5000]

    return "\n".join(report)


# === Module Health ===


@app.tool()
async def module_health(module: Optional[str] = None) -> str:
    """
    Check health of WarmLogic modules from ROOT_MANIFEST.

    Args:
        module: Specific module name or None for all

    Returns:
        Module health report
    """
    manifest_path = PROJECT_ROOT / "ROOT_MANIFEST.yaml"

    if not manifest_path.exists():
        return "ROOT_MANIFEST.yaml not found"

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    modules = manifest.get("modules", {})

    if module and module not in modules:
        return f"Module not found: {module}\nAvailable: {', '.join(modules.keys())}"

    targets = {module: modules[module]} if module else modules

    report = ["Module Health Check", "=" * 50]

    for name, config in targets.items():
        path = PROJECT_ROOT / config.get("path", "")
        entry = config.get("entry")
        files = config.get("files", [])

        status = "OK"
        issues = []

        # Check path exists
        if not path.exists():
            status = "MISSING"
            issues.append(f"Path not found: {path}")
        else:
            # Check entry file
            if entry and not (path / entry).exists():
                status = "PARTIAL"
                issues.append(f"Entry not found: {entry}")

            # Check listed files
            for f in files:
                if not (path / f).exists():
                    status = "PARTIAL"
                    issues.append(f"File not found: {f}")

            # Count Python files
            py_count = len(list(path.rglob("*.py")))

        status_icon = {"OK": "✓", "PARTIAL": "⚠", "MISSING": "✗"}.get(status, "?")
        report.append(f"\n{status_icon} {name}:")
        report.append(f"    Status: {status}")
        report.append(f"    Path: {config.get('path', 'N/A')}")

        if status == "OK":
            report.append(f"    Files: {py_count} .py files")

        for issue in issues[:3]:
            report.append(f"    ISSUE: {issue}")

    return "\n".join(report)


# === Dependency Tree ===


@app.tool()
async def dependency_tree(module: Optional[str] = None) -> str:
    """
    Show dependency relationships between modules.

    Args:
        module: Focus on specific module or show all

    Returns:
        Dependency tree visualization
    """
    os.chdir(PROJECT_ROOT)

    report = ["Dependency Tree", "=" * 50, ""]

    # Check for warm_logic structure
    src_paths = [PROJECT_ROOT / "src" / "warm_logic", PROJECT_ROOT / "warm_logic"]

    src_path = None
    for p in src_paths:
        if p.exists():
            src_path = p
            break

    if not src_path:
        report.append("warm_logic source not found")
        return "\n".join(report)

    # Build simple tree
    def build_tree(path: Path, prefix: str = "", depth: int = 0) -> list:
        if depth > 3:
            return []

        lines = []
        items = sorted(path.iterdir())

        # Separate dirs and files
        dirs = [i for i in items if i.is_dir() and not i.name.startswith("_")]
        py_files = [
            i for i in items if i.suffix == ".py" and not i.name.startswith("_")
        ]

        for i, d in enumerate(dirs):
            is_last = (i == len(dirs) - 1) and not py_files
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{d.name}/")
            new_prefix = prefix + ("    " if is_last else "│   ")
            lines.extend(build_tree(d, new_prefix, depth + 1))

        # Show first few py files
        for i, f in enumerate(py_files[:5]):
            is_last = i == len(py_files[:5]) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{f.name}")

        if len(py_files) > 5:
            lines.append(f"{prefix}    ... +{len(py_files) - 5} more")

        return lines

    report.append("warm_logic/")
    report.extend(build_tree(src_path))

    # Check Rust
    rs_path = PROJECT_ROOT / "warm_logic_rs" / "src"
    if rs_path.exists():
        report.extend(["", "warm_logic_rs/src/"])
        rs_files = list(rs_path.glob("*.rs"))
        for f in rs_files[:5]:
            report.append(f"├── {f.name}")

    return "\n".join(report)


# === Main Entry Point ===

if __name__ == "__main__":
    app.run()
