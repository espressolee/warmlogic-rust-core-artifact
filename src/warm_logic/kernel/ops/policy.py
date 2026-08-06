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
"""Plugin Policy (Phase 24 - Repaired)."""

import importlib.metadata as metadata
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ENTRY_POINT_GROUP = "warm_logic.plugins"


@dataclass
class PluginRecord:
    """Metadata record for a plugin."""

    name: str
    package: Optional[str] = None
    entry_point: Optional[str] = None
    min_version: Optional[str] = None
    editions_allowed: Set[str] = field(default_factory=set)
    modules_required: Set[str] = field(default_factory=set)
    signature: Optional[str] = None
    signature_path: Optional[Path] = None

    def __post_init__(self) -> None:
        # Normalize sets
        self.editions_allowed = {
            str(e).lower().strip() for e in self.editions_allowed if str(e).strip()
        }
        self.modules_required = {
            str(m).lower().strip() for m in self.modules_required if str(m).strip()
        }


from warm_logic.kernel import rust_loader

# Initialize Rust Core
rust_core = rust_loader.load_rust_core()
_RUST_POLICY: Optional[Any] = None

if rust_loader.HAS_RUST_CORE:
    _RUST_POLICY = rust_core.PolicyEngine()


def verify_plugin(
    name: str, flags: Any, registry: Dict[str, PluginRecord]
) -> List[str]:
    """Verifies a plugin against feature flags and registry data."""
    errors = []
    record = registry.get(name)
    if not record:
        return [f"plugin {name} not present in registry"]

    # 🦀 : Rust-Native Verification
    if _RUST_POLICY and record.signature:
        # Register if not already present (simplified for Phase 1)
        # In a real system, the registry would be backed by the Rust engine directly.
        rust_rec = rust_core.PolicyRecord(
            record.name, record.min_version or "0.0.0", record.signature
        )
        _RUST_POLICY.register_plugin_py(rust_rec)

        if not _RUST_POLICY.verify_plugin_py(name, record.signature):
            errors.append(f"🦀 RUST_POLICY_VIOLATION: Signature mismatch for {name}")

    # Edition check
    edition = getattr(flags, "edition", "standard").lower()
    if record.editions_allowed and edition not in record.editions_allowed:
        errors.append(f"edition {edition} not allowed for plugin {name}")

    # Modules check
    missing_modules = record.modules_required - flags.modules
    if missing_modules:
        errors.append(f"missing required modules for {name}: {missing_modules}")

    # Package check
    if record.package:
        try:
            ver = metadata.version(record.package)
            if record.min_version and ver < record.min_version:
                errors.append(
                    f"package {record.package} version {ver} < required {record.min_version}"
                )
        except metadata.PackageNotFoundError:
            errors.append(f"package {record.package} not installed")

    # Entry point check
    eps = _load_entry_points()
    if record.entry_point and record.entry_point not in eps:
        errors.append(f"entry point {record.entry_point} not registered")

    # Signature check
    if record.signature_path:
        if not record.signature_path.exists():
            errors.append(f"signature file missing: {record.signature_path}")
        elif record.signature:
            actual_sig = record.signature_path.read_text(encoding="utf-8").strip()
            if actual_sig != record.signature:
                errors.append(f"signature mismatch for {name}")

    return errors


def load_registry(path: Path) -> Dict[str, PluginRecord]:
    """Loads the plugin registry from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"CRITICAL: Plugin registry missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        plugins = {}
        for p in data.get("plugins", []):
            if "name" not in p:
                continue
            name = p["name"]
            # Resolve signature path relative to registry
            sig_path = p.get("signature_path")
            if sig_path:
                sig_path = _resolve_signature_path(path, sig_path)

            plugins[name] = PluginRecord(
                name=name,
                package=p.get("package"),
                entry_point=p.get("entry_point"),
                min_version=p.get("min_version"),
                editions_allowed=set(p.get("editions_allowed", [])),
                modules_required=set(p.get("modules_required", [])),
                signature=p.get("signature"),
                signature_path=sig_path,
            )
        return plugins
    except Exception as e:
        raise RuntimeError(f"CRITICAL: Failed to load plugin registry from {path}: {e}")


def installed_plugins(registry: Dict[str, PluginRecord]) -> List[str]:
    """Returns a list of installed and valid plugins."""
    installed = []
    eps = _load_entry_points()
    for name, record in registry.items():
        if record.entry_point in eps:
            try:
                if record.package:
                    metadata.version(record.package)
                installed.append(name)
            except metadata.PackageNotFoundError:
                pass
    return installed


def _load_entry_points() -> Dict[str, Any]:
    """Loads plugin entry points across modern and legacy metadata APIs."""

    def _to_map(raw: Any) -> Dict[str, Any]:
        entries: Any
        if raw is None:
            return {}
        if hasattr(raw, "select"):
            try:
                entries = raw.select(group=ENTRY_POINT_GROUP)
            except Exception:
                entries = []
        elif isinstance(raw, dict):
            entries = raw.get(ENTRY_POINT_GROUP, [])
        else:
            entries = raw
        if isinstance(entries, (str, bytes)):
            return {}
        try:
            iterator = iter(entries)
        except TypeError:
            return {}
        out: Dict[str, Any] = {}
        for ep in iterator:
            name = getattr(ep, "name", None)
            if name:
                out[str(name)] = ep
        return out

    # Python 3.10+: direct group query may return EntryPoints/list.
    try:
        direct = metadata.entry_points(group=ENTRY_POINT_GROUP)  # type: ignore[call-arg]
        mapped = _to_map(direct)
        if mapped:
            return mapped
    except TypeError:
        pass
    except Exception:
        pass

    # Legacy and compatibility path: inspect no-arg result.
    try:
        return _to_map(metadata.entry_points())
    except Exception:
        return {}


def _resolve_signature_path(registry_path: Path, sig_rel_path: str) -> Path:
    """Resolves a signature path relative to the registry file."""
    p = Path(sig_rel_path)
    if p.is_absolute():
        return p
    return registry_path.parent / p
