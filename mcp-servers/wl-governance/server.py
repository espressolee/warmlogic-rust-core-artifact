#!/usr/bin/env python3
"""
WarmLogic Governance MCP Server

Provides governance-related tools for Claude Code integration:
- P-Series protocol validation
- Reality enforcement checks
- ROOT_MANIFEST queries
- Era context information
- Band validation

P-Series: P4xx (DevOps Band)
"""

import os
import re
import subprocess
import sys
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
app = FastMCP("wl-governance")


# === P-Series Protocol Tools ===


@app.tool()
async def p_series_check(
    commit_range: str = "HEAD~10..HEAD", strict: bool = False
) -> str:
    """
    Check P-Series protocol compliance for commits.

    Args:
        commit_range: Git commit range to check (default: last 10)
        strict: If True, fail on any violation

    Returns:
        Compliance report with violations and suggestions
    """
    os.chdir(PROJECT_ROOT)

    # Load valid bands from manifest
    manifest_path = PROJECT_ROOT / "ROOT_MANIFEST.yaml"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        valid_bands = manifest.get("operational_bands", {})
    else:
        valid_bands = {
            "P0xx": "Foundation & Identity",
            "P1xx": "Consensus & Ledger",
            "P2xx": "Mesh & Networking",
            "P3xx": "Governance & Sovereignty",
            "P4xx": "DevOps",
        }

    band_pattern = re.compile(r"P[0-4]\d{2}")

    result = subprocess.run(
        ["git", "log", "--oneline", commit_range],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    commits = [c for c in result.stdout.strip().split("\n") if c]
    violations = []
    compliant = []

    for commit in commits:
        match = band_pattern.search(commit)
        if match:
            compliant.append(
                {"hash": commit[:7], "band": match.group(), "message": commit[8:]}
            )
        else:
            # Detect suggested band from changed files
            files_result = subprocess.run(
                ["git", "show", "--name-only", "--format=", commit[:7]],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )
            files = files_result.stdout.strip().split("\n")
            suggested = _detect_band(files)

            violations.append(
                {
                    "hash": commit[:7],
                    "message": commit[8:],
                    "suggested_band": suggested,
                    "files": files[:3],
                }
            )

    # Build report
    report = [
        "P-Series Protocol Check",
        "=" * 50,
        f"Range: {commit_range}",
        f"Total commits: {len(commits)}",
        f"Compliant: {len(compliant)}",
        f"Violations: {len(violations)}",
        "",
    ]

    if violations:
        report.append("Violations:")
        for v in violations[:5]:
            report.append(f"  {v['hash']}: {v['message'][:50]}")
            report.append(f"    Suggested: {v['suggested_band']}")
        report.append("")
        report.append("Fix with: git commit --amend -m 'P3xx: <message>'")

    if not violations:
        report.append("Status: PASS - All commits compliant")
    elif strict:
        report.append("\nStatus: FAIL (strict mode)")
    else:
        report.append(f"\nStatus: {len(violations)} violations found")

    return "\n".join(report)


def _detect_band(files: list) -> str:
    """Detect P-Series band from file paths."""
    band_map = {
        "kernel/identity": "P0xx (Foundation)",
        "kernel/hardware": "P0xx (Foundation)",
        "consensus": "P1xx (Consensus)",
        "bft": "P1xx (Consensus)",
        "ledger": "P1xx (Ledger)",
        "mesh": "P2xx (Mesh)",
        "beacon": "P2xx (Mesh)",
        "governance": "P3xx (Governance)",
        "policy": "P3xx (Governance)",
        "quorum": "P3xx (Governance)",
        ".github": "P4xx (DevOps)",
        "scripts": "P4xx (DevOps)",
        ".claude": "P4xx (DevOps)",
        "docs": "P4xx (DevOps)",
        "mcp-servers": "P4xx (DevOps)",
    }

    for file in files:
        for pattern, band in band_map.items():
            if pattern in file.lower():
                return band
    return "P4xx (DevOps)"


# === Reality Enforcement Tools ===


@app.tool()
async def reality_enforce(scope: str = "all", fix: bool = False) -> str:
    """
    Check reality enforcement constraints.

    Args:
        scope: "all", "stubs", "paths", "attestation"
        fix: If True, attempt auto-fixes for path violations

    Returns:
        Reality enforcement report
    """
    os.chdir(PROJECT_ROOT)
    violations = []
    fixed = []
    src_path = PROJECT_ROOT / "src" / "warm_logic"

    if not src_path.exists():
        src_path = PROJECT_ROOT / "warm_logic"

    # 1. Check for stubs (not fixable)
    if scope in ["all", "stubs"]:
        stub_patterns = [
            (r"STUB_\w+", "Simulation stub"),
            (r"MOCK_\w+", "Mock in production"),
            (r"FAKE_\w+", "Fake implementation"),
        ]

        for py_file in src_path.rglob("*.py"):
            if "test" in str(py_file).lower():
                continue
            try:
                content = py_file.read_text()
                for pattern, desc in stub_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        violations.append(
                            {
                                "file": str(py_file.relative_to(PROJECT_ROOT)),
                                "type": desc,
                                "matches": matches[:3],
                                "fixable": False,
                            }
                        )
            except Exception:
                pass

    # 2. Check for absolute paths (fixable)
    if scope in ["all", "paths"]:
        path_patterns = [
            (r'/Users/\w+/[^\s"\']+', "macOS absolute path"),
            (r'/home/\w+/[^\s"\']+', "Linux absolute path"),
        ]

        for py_file in src_path.rglob("*.py"):
            if "test" in str(py_file).lower():
                continue
            try:
                content = py_file.read_text()
                for pattern, desc in path_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        violations.append(
                            {
                                "file": str(py_file.relative_to(PROJECT_ROOT)),
                                "type": desc,
                                "matches": matches[:3],
                                "fixable": True,
                            }
                        )
            except Exception:
                pass

    # 3. Check attestation modules
    if scope in ["all", "attestation"]:
        required_modules = [
            "warm_logic/kernel/hardware/confidential.py",
            "src/warm_logic/kernel/hardware/confidential.py",
        ]
        found = False
        for module in required_modules:
            if (PROJECT_ROOT / module).exists():
                found = True
                break
        if not found:
            violations.append(
                {
                    "file": "warm_logic/kernel/hardware/confidential.py",
                    "type": "Missing attestation module",
                    "fixable": False,
                }
            )

    # Build report
    report = [
        "Reality Enforcement Report",
        "=" * 50,
        f"Scope: {scope}",
        f"Violations: {len(violations)}",
        "",
    ]

    if violations:
        report.append("Violations:")
        for v in violations:
            status = "[FIXABLE]" if v.get("fixable") else "[MANUAL]"
            report.append(f"  {status} {v['file']}")
            report.append(f"    Type: {v['type']}")
            if "matches" in v:
                report.append(
                    f"    Found: {', '.join(str(m)[:30] for m in v['matches'][:2])}"
                )
        report.append("")
        report.append("Status: VIOLATIONS DETECTED")
    else:
        report.append("Status: PASS - Reality enforced")

    return "\n".join(report)


# === Manifest Query Tools ===


@app.tool()
async def manifest_query(query: str = "", action: str = "list") -> str:
    """
    Query ROOT_MANIFEST.yaml for module information.

    Args:
        query: Dot-notation path or module name
        action: "list", "get", "find", "validate"

    Returns:
        Requested manifest data
    """
    manifest_path = PROJECT_ROOT / "ROOT_MANIFEST.yaml"

    if not manifest_path.exists():
        return "ERROR: ROOT_MANIFEST.yaml not found"

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    if action == "list":
        modules = manifest.get("modules", {})
        lines = [f"WarmLogic Modules (Era {manifest.get('era', 'unknown')})", "=" * 50]
        for name, config in modules.items():
            path = Path(config.get("path", ""))
            exists = "✓" if (PROJECT_ROOT / path).exists() else "✗"
            lines.append(f"\n{exists} {name}:")
            lines.append(f"    Path: {config.get('path', 'N/A')}")
            lines.append(f"    Desc: {config.get('description', 'N/A')[:50]}")
        return "\n".join(lines)

    elif action == "find":
        modules = manifest.get("modules", {})
        matches = []
        query_lower = query.lower()
        for name, config in modules.items():
            searchable = f"{name} {config.get('description', '')} {config.get('path', '')}".lower()
            if query_lower in searchable:
                matches.append((name, config))

        if not matches:
            return f"No modules matching '{query}'"

        lines = [f"Found {len(matches)} modules matching '{query}':"]
        for name, config in matches:
            lines.append(f"  - {name}: {config.get('path')}")
        return "\n".join(lines)

    elif action == "validate":
        modules = manifest.get("modules", {})
        issues = []
        for name, config in modules.items():
            path = PROJECT_ROOT / config.get("path", "")
            if not path.exists():
                issues.append(f"{name}: path not found")

        if issues:
            return "Validation FAILED:\n" + "\n".join(f"  - {i}" for i in issues)
        return f"Validation PASSED: All {len(modules)} modules valid"

    else:  # action == "get"
        if not query:
            return yaml.dump(manifest)

        parts = query.split(".")
        result = manifest
        for part in parts:
            if isinstance(result, dict):
                result = result.get(part, {})
            else:
                return f"Invalid path: {query}"

        if result:
            return (
                yaml.dump(result) if isinstance(result, (dict, list)) else str(result)
            )
        return f"No value found for: {query}"


# === Era Context Tools ===


@app.tool()
async def era_context() -> str:
    """
    Get current Era context from ROOT_MANIFEST.yaml.

    Returns:
        Era information including version, bands, and standards
    """
    manifest_path = PROJECT_ROOT / "ROOT_MANIFEST.yaml"

    if not manifest_path.exists():
        return "ERROR: ROOT_MANIFEST.yaml not found"

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    era = manifest.get("era", "unknown")
    version = manifest.get("version", "unknown")
    last_vibration = manifest.get("last_vibration", "unknown")

    bands = manifest.get(
        "operational_bands",
        {
            "P0xx": "Foundation & Identity",
            "P1xx": "Consensus & Ledger",
            "P2xx": "Mesh & Networking",
            "P3xx": "Governance & Sovereignty",
            "P4xx": "DevOps",
        },
    )

    standards = manifest.get("standards", {})

    report = [
        "WarmLogic Era Context",
        "=" * 50,
        f"Era: {era}",
        f"Version: {version}",
        f"Last Vibration: {last_vibration}",
        "",
        "Operational Bands:",
    ]

    for band, desc in bands.items():
        report.append(f"  {band}: {desc}")

    if standards:
        report.append("")
        report.append("Standards:")
        for std, value in standards.items():
            report.append(f"  {std}: {value}")

    return "\n".join(report)


# === Band Validation Tools ===


@app.tool()
async def band_validate(band: str, files: Optional[list] = None) -> str:
    """
    Validate P-Series band assignment for files.

    Args:
        band: P-Series band (e.g., "P3xx")
        files: List of file paths to validate (or staged files if None)

    Returns:
        Validation result with recommendations
    """
    os.chdir(PROJECT_ROOT)

    # Normalize band format
    band_match = re.match(r"P([0-4])\d{2}", band)
    if not band_match:
        return f"Invalid band format: {band}. Use P0xx, P1xx, P2xx, P3xx, or P4xx"

    band_category = f"P{band_match.group(1)}xx"

    valid_bands = {
        "P0xx": "Foundation & Identity",
        "P1xx": "Consensus & Ledger",
        "P2xx": "Mesh & Networking",
        "P3xx": "Governance & Sovereignty",
        "P4xx": "DevOps",
    }

    if band_category not in valid_bands:
        return f"Unknown band: {band_category}"

    # Get files to validate
    if files is None:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        files = [f for f in result.stdout.strip().split("\n") if f]

    if not files:
        return f"Band {band} ({valid_bands[band_category]}) - No files to validate"

    # Check if files match band
    mismatches = []
    for file in files:
        suggested = _detect_band([file])
        suggested_match = re.match(r"(P\dxx)", suggested)
        suggested_category = suggested_match.group(1) if suggested_match else None

        if suggested_category and suggested_category != band_category:
            mismatches.append(
                {"file": file, "expected": suggested, "assigned": band_category}
            )

    report = [
        f"Band Validation: {band}",
        f"Description: {valid_bands[band_category]}",
        f"Files: {len(files)}",
        "",
    ]

    if mismatches:
        report.append("Potential mismatches:")
        for m in mismatches[:5]:
            report.append(f"  - {m['file']}")
            report.append(f"    Expected: {m['expected']}")
            report.append(f"    Assigned: {m['assigned']}")
        report.append("")
        report.append(
            "Consider using the suggested band, or confirm this is intentional."
        )
    else:
        report.append(f"All {len(files)} files match band {band_category}")

    return "\n".join(report)


# === Main Entry Point ===

if __name__ == "__main__":
    app.run()
