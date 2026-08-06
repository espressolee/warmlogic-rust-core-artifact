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
"""[P0xx] Kernel API - Public interface for WarmLogic kernel operations."""

from __future__ import annotations

import logging
import threading

__path__: list[str] = []
logger = logging.getLogger("KernelAPI")

from dataclasses import dataclass
from typing import Any

from warm_logic.kernel import rust_loader

# Consolidated System API & Authentication
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ModeDecisionContext:
    active_mode: str
    metrics: dict[str, Any]


@dataclass(frozen=True)
class ModeDecision:
    mode: str
    reason: str


@dataclass(frozen=True)
class ModeRule:
    trigger: str
    target_mode: str


_RUST_LOOP = None
_rust_loop_lock = threading.Lock()


def compute_mode(ctx: ModeDecisionContext) -> ModeDecision:
    """
    Computes the operational mode based on decision context (thread-safe).
    Phase 30: Stability Envelope (E_stab) - Delegated to Rust Core
    """
    global _RUST_LOOP
    if rust_loader.HAS_RUST_CORE:
        if _RUST_LOOP is None:
            with _rust_loop_lock:
                if _RUST_LOOP is None:  # Double-checked locking
                    rs = rust_loader.load_rust_core()
                    _RUST_LOOP = rs.ReflectiveLoop()

        # Delegate to Rust
        res = _RUST_LOOP.compute_mode(dict(ctx.metrics))
        return ModeDecision(mode=res.mode, reason=res.reason)

    # hardware attestation enforcement: No more Python fallbacks for core logic.
    raise RuntimeError("CRITICAL: Rust Core missing. Mode computation is disabled.")


# --- AUTHENTICATION STUBS DELETED ---
# Previous SAML stubs removed as they provided false security guarantees.
# Real implementation required via `warm_logic_rs`.


# Internal Helpers
def _normalize_gov_action(value: Any) -> str | None:
    return str(value) if value else None


def _normalize_ct_action(value: Any) -> str:
    return str(value)


from warm_logic.kernel.ops.metrics import SystemMetrics

_metrics_monitor = SystemMetrics()


class ModuleRegistry:
    """
    Plugin Architecture for Modular Sovereignty.
    Enables 'Dominion' modules (Brain) to register with the 'Basal' core (Shield).
    """

    _handlers: dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, handler: Any) -> None:
        cls._handlers[name] = handler
        logger.info(f"[Registry] Module '{name}' registered.")

    @classmethod
    def get(cls, name: str) -> Any | None:
        return cls._handlers.get(name)

    @classmethod
    def has_module(cls, name: str) -> bool:
        return name in cls._handlers


def trigger_intelligence_tick(metrics: dict[str, Any]) -> Any:
    """Calls the Dominion Intelligence handler if registered."""
    handler = ModuleRegistry.get("dominion.intelligence")
    if handler:
        return handler(metrics)
    return None


def _drift_alarm(_extras: dict[str, Any] | None = None) -> bool:
    """
    Electronic Policy & Alarm (EPA).
    Fires if system drift exceeds the stability envelope.
    """
    if _metrics_monitor.is_critical():
        logger.error("DRIFT ALARM FIRE: Stability Envelope Breached!")
        # Autonomous Veto Logic (Dominion-aware)
        veto_handler = ModuleRegistry.get("dominion.veto")
        if veto_handler:
            veto_handler("DRIFT_BREACH")
        return True
    return False
