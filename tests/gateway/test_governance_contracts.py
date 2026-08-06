from __future__ import annotations

import sys
import types

import pytest

from warm_logic.gateway.routes import governance


def test_compute_e_stab_formula_matches_rust_logic() -> None:
    e_stab = governance._compute_e_stab(0.2, 0.1)
    assert e_stab == pytest.approx(0.55)


def test_compute_mode_snapshot_uses_dict_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeLoop:
        def compute_mode(self, metrics: dict[str, float]) -> object:
            captured["metrics"] = metrics
            return types.SimpleNamespace(mode="SUSPICIOUS", reason="stub")

    monkeypatch.setitem(sys.modules, "warm_logic_rs", types.SimpleNamespace(ReflectiveLoop=FakeLoop))

    mode, e_stab, tau_ethics = governance._compute_mode_snapshot(0.2, 0.1)

    assert captured["metrics"] == {"epsilon_c": 0.2, "tau_ethics": 0.1}
    assert mode == "SUSPICIOUS"
    assert e_stab == pytest.approx(0.55)
    assert tau_ethics == pytest.approx(0.1)


def test_compute_mode_snapshot_fallback_when_rust_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "warm_logic_rs", raising=False)

    real_import = __import__

    def _import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "warm_logic_rs":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _import)

    mode, e_stab, tau_ethics = governance._compute_mode_snapshot(0.2, 0.1)

    assert mode == "SUSPICIOUS"
    assert e_stab == pytest.approx(0.55)
    assert tau_ethics == pytest.approx(0.1)
