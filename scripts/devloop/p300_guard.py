#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def _enforce_prefix_guard_if_available(p_id: int) -> None:
    """Enforce P3xx execution policy via warm_logic prefix_guard when available.

    This is the authoritative path under v4 SSOT (partner-pilot mode). In unit
    tests that operate on a temp root without the repo import path, this falls
    back to the legacy automation_window_v3.json behavior.
    """

    try:
        from warm_logic.app.devloop import prefix_guard
    except Exception as exc:  # pragma: no cover - repo import unavailable
        raise ImportError("warm_logic prefix_guard unavailable") from exc

    # Only enforce P300+ here; P0–P299 are handled elsewhere.
    if p_id < 300:
        return
    prefix_guard.ensure_can_execute_p(p_id)


def load_automation_window_v3(root: Path) -> dict:
    path = root / "meta" / "automation_window_v3.json"
    if not path.exists():
        # fallback to sample
        path = root / "meta" / "automation_window_v3.sample.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_pband_allowed(p_id: int, scope: str, root: Path) -> None:
    if p_id < 300:
        # Legacy window can optionally disable P0–P299; keep behaviour as-is.
        window = load_automation_window_v3(root)
        if not window or window.get("allow_p0_299", True):
            return
        raise RuntimeError("P0–P299 automation disabled by automation_window_v3")

    # Prefer v4 SSOT/prefix_guard enforcement when `root` is a full repo checkout.
    # This ensures "sealed by default" holds even for local/sandbox scopes unless explicitly
    # enabled via governance decisions / status SSOT.
    if (root / "warm_logic").exists() and (
        root / "meta" / "WarmLogic_P_Status_v4.json"
    ).exists():
        try:
            _enforce_prefix_guard_if_available(p_id)
            return
        except ImportError:
            # No repo import path (e.g., isolated unit tests); fall back to legacy window.
            pass

    window = load_automation_window_v3(root)
    if (window.get("proto_version") or "").upper() != "WLPV3":
        raise RuntimeError(
            "P300-band requires proto_version=WLPv3 in automation_window_v3"
        )
    if not bool(window.get("allow_p300_band")):
        raise RuntimeError("P300-band automation disallowed under current window")
    scopes = window.get("scopes") or []
    if scope not in scopes:
        raise RuntimeError(f"Scope {scope} not authorised for P300-band")


def ensure_pband_allowed_str(p_id_token: str, scope: str, root: Path) -> None:
    """Parse a P token (e.g., "P320") and enforce P-band guard.

    For P<300, returns immediately. For invalid tokens, raises RuntimeError.
    """
    try:
        n = (
            int(str(p_id_token).lstrip("Pp"))
            if str(p_id_token).lstrip("Pp").isdigit()
            else None
        )
    except Exception:
        n = None
    if n is None:
        raise RuntimeError(f"invalid P id: {p_id_token}")
    if n < 300:
        return
    check_pband_allowed(n, scope, root)


def ensure_mode_allowed(mode: str, root: Path) -> None:
    """Ensure the requested P300 mode is allowed by the automation window.

    If no modes are specified in the window, treat as allowed (backward compatible).
    """
    wnd = load_automation_window_v3(root)
    modes = wnd.get("allowed_p300_modes") or []
    if modes and mode not in modes:
        raise RuntimeError(f"P300 mode '{mode}' not allowed (allowed: {sorted(modes)})")


def validate_surfaces(paths: list[str], forbidden_globs: list[str]) -> None:
    """Validate that no path matches forbidden globs.

    Paths are relative to repo root; globs may include **.
    """
    import fnmatch

    globs = [g for g in (forbidden_globs or []) if str(g).strip()]
    for p in paths or []:
        rel = str(p).lstrip("./")
        if any(fnmatch.fnmatch(rel, pat) for pat in globs):
            raise RuntimeError(f"forbidden surface touched: {rel}")


def get_forbidden_surfaces(root: Path) -> list[str]:
    """Return forbidden surfaces from automation_window_v3.json or defaults.

    Defaults mirror Tier‑0/Tier‑1 sensitive areas if window lacks explicit list.
    """
    wnd = load_automation_window_v3(root)
    fs = wnd.get("forbidden_surfaces") if isinstance(wnd, dict) else None
    if isinstance(fs, list) and fs:
        return [str(x) for x in fs if str(x).strip()]
    return [
        "spec/schema/**",
        "meta/WarmLogic_P_Status*.json",
        "states/**",
        "run_manifests/**",
        "governance/**",
    ]


__all__ = [
    "load_automation_window_v3",
    "check_pband_allowed",
    "ensure_pband_allowed_str",
    "ensure_mode_allowed",
    "validate_surfaces",
    "get_forbidden_surfaces",
]
