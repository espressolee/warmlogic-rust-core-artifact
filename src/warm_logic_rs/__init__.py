"""Python package shim for the Rust extension module.

This package is required by maturin mixed-project metadata generation.
Prefer ``warm_logic_rs.warm_logic_rs`` when present, but gracefully fall back
to top-level extension wheels (``warm_logic_rs*.so/.pyd/.dylib``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import site
import sys


def _extend_package_path() -> None:
    bases: list[str] = []
    try:
        bases.extend(site.getsitepackages())
    except AttributeError:
        pass
    user_site = site.getusersitepackages()
    if isinstance(user_site, str):
        bases.append(user_site)
    for base in bases:
        candidate = Path(base) / "warm_logic_rs"
        if candidate.is_dir():
            candidate_path = str(candidate)
            if candidate_path not in __path__:
                __path__.append(candidate_path)


def _load_top_level_extension() -> object | None:
    patterns = ("warm_logic_rs*.so", "warm_logic_rs*.pyd", "warm_logic_rs*.dylib")
    for raw_entry in sys.path:
        if not raw_entry:
            continue
        base = Path(raw_entry)
        if not base.exists() or not base.is_dir():
            continue
        for pattern in patterns:
            for candidate in sorted(base.glob(pattern)):
                spec = importlib.util.spec_from_file_location(
                    "warm_logic_rs._native_fallback",
                    candidate,
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    return None


def _reexport(module: object) -> None:
    names = getattr(module, "__all__", None)
    if names is None:
        names = [name for name in dir(module) if not name.startswith("_")]
    for name in names:
        globals()[name] = getattr(module, name)
    globals()["__all__"] = list(names)


_extend_package_path()

try:
    from .warm_logic_rs import *  # type: ignore[F401,F403]
except ModuleNotFoundError:
    fallback = _load_top_level_extension()
    if fallback is None:
        raise
    sys.modules[f"{__name__}.warm_logic_rs"] = fallback
    _reexport(fallback)
