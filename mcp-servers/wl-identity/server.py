#!/usr/bin/env python3
"""
WarmLogic Identity MCP Server

Provides identity and attestation tools for Claude Code integration:
- Sovereign key status
- Hardware attestation checks
- ML-DSA-65 key management

P-Series: P0xx (Foundation Band)
"""

import os
import sys
from pathlib import Path

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
app = FastMCP("wl-identity")


# === Key Status ===


@app.tool()
async def key_status() -> str:
    """
    Check ML-DSA-65 sovereign key status.

    Returns:
        Key status and metadata
    """
    report = ["Sovereign Key Status", "=" * 50]

    key_paths = [
        PROJECT_ROOT / ".keys" / "sovereign.pub",
        PROJECT_ROOT / ".keys" / "sovereign.key",
        PROJECT_ROOT / "keys" / "sovereign.pub",
        PROJECT_ROOT / "keys" / "sovereign.key",
    ]

    found_keys = []
    for path in key_paths:
        if path.exists():
            found_keys.append(path)
            report.append(f"  {path.name}: EXISTS")
            report.append(f"    Path: {path}")
            report.append(f"    Size: {path.stat().st_size} bytes")

    if not found_keys:
        report.append("  No sovereign keys found")
        report.append("")
        report.append("Expected locations:")
        report.append("  - .keys/sovereign.pub")
        report.append("  - .keys/sovereign.key")

    # Check for PQC module in Rust core
    report.append("")
    try:
        import warm_logic_rs

        pqc_available = hasattr(warm_logic_rs, "PQCKeypair") or hasattr(
            warm_logic_rs, "pqc"
        )

        if pqc_available:
            report.append("PQC Module: Available in Rust core")
        else:
            report.append("PQC Module: Not exposed (check Rust exports)")

        # List crypto-related exports
        crypto_modules = [
            m
            for m in dir(warm_logic_rs)
            if any(k in m.lower() for k in ["key", "sign", "crypto", "pqc", "dsa"])
        ]
        if crypto_modules:
            report.append(f"Crypto exports: {', '.join(crypto_modules)}")

    except ImportError:
        report.append("Rust Core: Not available")
        report.append("Run: /wl-build rust")

    return "\n".join(report)


# === Hardware Attestation ===


@app.tool()
async def attestation(check_type: str = "all") -> str:
    """
    Check hardware attestation status.

    Args:
        check_type: "tpm", "hsm", "all"

    Returns:
        Attestation status report
    """
    report = ["Hardware Attestation", "=" * 50]

    # TPM check
    if check_type in ["tpm", "all"]:
        report.append("")
        report.append("TPM Status:")

        tpm_paths = [
            Path("/dev/tpm0"),
            Path("/dev/tpmrm0"),
        ]

        tpm_found = False
        for path in tpm_paths:
            if path.exists():
                tpm_found = True
                report.append(f"  Device: {path} (available)")
                break

        if not tpm_found:
            report.append("  Device: Not detected")
            report.append("  Mode: Simulation (development)")

        # Check for TPM binding module
        tpm_module_paths = [
            PROJECT_ROOT / "warm_logic" / "kernel" / "hardware" / "tpm_binding.py",
            PROJECT_ROOT
            / "src"
            / "warm_logic"
            / "kernel"
            / "hardware"
            / "tpm_binding.py",
        ]

        for path in tpm_module_paths:
            if path.exists():
                report.append(f"  Binding: {path.relative_to(PROJECT_ROOT)}")
                break
        else:
            report.append("  Binding: Module not found")

    # HSM check
    if check_type in ["hsm", "all"]:
        report.append("")
        report.append("HSM Status:")

        pkcs11_paths = [
            Path("/usr/lib/softhsm/libsofthsm2.so"),
            Path("/usr/local/lib/softhsm/libsofthsm2.so"),
            Path("/opt/homebrew/lib/softhsm/libsofthsm2.so"),
        ]

        hsm_found = False
        for path in pkcs11_paths:
            if path.exists():
                hsm_found = True
                report.append(f"  SoftHSM: {path}")
                break

        if not hsm_found:
            report.append("  SoftHSM: Not installed")

        # Check for HSM slots
        try:
            import subprocess

            result = subprocess.run(
                ["softhsm2-util", "--show-slots"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                slot_count = result.stdout.count("Slot ")
                report.append(f"  Slots: {slot_count} available")
        except Exception:
            pass

    # Attestation module check
    report.append("")
    report.append("Attestation Module:")

    att_paths = [
        PROJECT_ROOT / "warm_logic" / "kernel" / "hardware" / "confidential.py",
        PROJECT_ROOT / "src" / "warm_logic" / "kernel" / "hardware" / "confidential.py",
    ]

    for path in att_paths:
        if path.exists():
            report.append(f"  Module: {path.relative_to(PROJECT_ROOT)}")

            # Quick check for content
            try:
                content = path.read_text()
                if "STUB" in content:
                    report.append("  Status: STUB implementation detected")
                elif "TPM" in content or "attestation" in content.lower():
                    report.append("  Status: Real implementation")
                else:
                    report.append("  Status: Unknown implementation")
            except Exception:
                pass
            break
    else:
        report.append("  Module: NOT FOUND")
        report.append("  Required: warm_logic/kernel/hardware/confidential.py")

    # Summary
    report.append("")
    report.append("Summary:")

    if check_type == "all":
        tpm_ok = any(Path(p).exists() for p in ["/dev/tpm0", "/dev/tpmrm0"])
        hsm_ok = any(Path(p).exists() for p in pkcs11_paths)
        module_ok = any(p.exists() for p in att_paths)

        if tpm_ok or hsm_ok:
            report.append("  Hardware: Available for production")
        else:
            report.append("  Hardware: Development mode (simulation)")

        if module_ok:
            report.append("  Software: Attestation module present")
        else:
            report.append("  Software: Attestation module MISSING")

    return "\n".join(report)


# === Identity Info ===


@app.tool()
async def identity_info() -> str:
    """
    Get WarmLogic identity configuration.

    Returns:
        Identity configuration summary
    """
    report = ["WarmLogic Identity Configuration", "=" * 50]

    # Check sovereign.yaml
    sovereign_paths = [
        PROJECT_ROOT / "sovereign.yaml",
        PROJECT_ROOT / "config" / "sovereign.yaml",
    ]

    for path in sovereign_paths:
        if path.exists():
            report.append(f"Sovereign Config: {path.relative_to(PROJECT_ROOT)}")
            try:
                import yaml

                with open(path) as f:
                    config = yaml.safe_load(f)

                if config:
                    report.append("")
                    for key, value in list(config.items())[:10]:
                        if isinstance(value, dict):
                            report.append(f"  {key}:")
                            for k, v in list(value.items())[:3]:
                                report.append(f"    {k}: {v}")
                        else:
                            report.append(f"  {key}: {value}")
            except Exception as e:
                report.append(f"  Error reading: {e}")
            break
    else:
        report.append("Sovereign Config: Not found")

    # Check ROOT_MANIFEST for identity module
    report.append("")
    manifest_path = PROJECT_ROOT / "ROOT_MANIFEST.yaml"
    if manifest_path.exists():
        try:
            import yaml

            with open(manifest_path) as f:
                manifest = yaml.safe_load(f)

            modules = manifest.get("modules", {})
            identity_modules = {
                k: v
                for k, v in modules.items()
                if "identity" in k.lower() or "hardware" in k.lower()
            }

            if identity_modules:
                report.append("Identity-related Modules:")
                for name, config in identity_modules.items():
                    report.append(f"  - {name}: {config.get('path', 'N/A')}")
        except Exception:
            pass

    # Era info
    report.append("")
    try:
        import yaml

        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        report.append(f"Era: {manifest.get('era', 'unknown')}")
        report.append(f"Version: {manifest.get('version', 'unknown')}")
    except Exception:
        pass

    return "\n".join(report)


# === Main Entry Point ===

if __name__ == "__main__":
    app.run()
