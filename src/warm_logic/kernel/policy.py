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
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from warm_logic.kernel.observability.telemetry import TelemetryProvider
from warm_logic.kernel.ops.speculative_buffer import speculative_buffer
from warm_logic.kernel.substrate.axiomatic_guard import axiomatic_guard
from warm_logic.kernel.zanzibar import zanzibar

logger = logging.getLogger("PolicyEngine")
tracer = TelemetryProvider().get_tracer("warmlogic.kernel.policy")

__path__: list[str] = []

# Consolidated Policy Engine
# -----------------------------------------------------------------------------


@dataclass
class PolicyResult:
    approved: bool
    reason: str
    metadata: Optional[Dict[str, Any]] = None


def normalize_govsat(*args: Any, **kwargs: Any) -> None:
    pass


class TenantPolicy:
    """Represents a tenant-specific operational policy."""

    def __init__(self, tenant_id: str, rules: Dict[str, Any]):
        self.tenant_id = tenant_id
        self.rules = rules


# --- FUNCTIONS ---


def ct_policy_decision(
    namespace: str, obj: str, rel: str, user: str
) -> Tuple[bool, str]:
    """Formal CT policy decision logic based on Zanzibar relationship graph."""
    if zanzibar.check(namespace, obj, rel, user):
        return True, "ZANZIBAR_APPROVED"
    return False, "ZANZIBAR_DENIED"


def evaluate_os_policy(state: Any) -> PolicyResult:
    """Evaluates the global OS state against safety invariants."""
    # hardware attestation enforcement: Real security invariants.
    if state is None:
        return PolicyResult(approved=False, reason="CRITICAL: OS State is None")

    # Basic invariant: Kernel must be in a valid operational state
    status = getattr(state, "state", "UNKNOWN")
    if status == "HALT":
        return PolicyResult(
            approved=False, reason="INVARIANT_VIOLATION: Kernel is HALTED"
        )

    return PolicyResult(approved=True, reason="INVARIANT_CHECK_PASSED")


def load_guard_thresholds(path: str | Path | None = None) -> Dict[str, float]:
    """Loads operational guard thresholds from YAML/JSON."""
    if path is None:
        # Default to system config if not provided
        path = Path("config/security/thresholds.yaml")

    p = Path(path)
    # Speculative Governance: Check for staged policy overrides
    real_policy = {}
    if p.exists():
        real_policy = _load_yaml_policy(p)
    else:
        logger.warning(f"Guard thresholds file missing: {p}. Using defaults.")
        real_policy = {"drift_max": 0.8, "health_min": 0.5, "latency_max": 2000.0}

    # Apply speculative overlay if active
    final_policy = real_policy.copy()
    for k, v in real_policy.items():
        key_target = f"policy:thresholds:{k}"
        final_policy[k] = speculative_buffer.get_effective_value(key_target, v)

    return final_policy


def apply_guard_policy(
    snapshot: Dict[str, Any], thresholds: Dict[str, float]
) -> PolicyResult:
    """Applies guard-rail logic to a system snapshot."""
    # hardware attestation enforcement: Active Guardrails
    drift = snapshot.get("drift_score", 0.0)
    health = snapshot.get("governance_health", 1.0)

    if drift > thresholds.get("drift_max", 0.8):
        return PolicyResult(
            approved=False, reason=f"GUARD_VIOLATION: Drift ({drift}) > Max"
        )

    if health < thresholds.get("health_min", 0.5):
        return PolicyResult(
            approved=False, reason=f"GUARD_VIOLATION: Health ({health}) < Min"
        )

    return PolicyResult(approved=True, reason="GUARD_CHECK_PASSED")


def get_tenant_policy(org_id: str, tenant_id: str) -> TenantPolicy:
    """Retrieves the active policy for a specific tenant."""
    # Return empty policy is fine, but it shouldn't auto-approve anything.
    return TenantPolicy(tenant_id, {})


@axiomatic_guard
def configure_guard_thresholds(
    drift_max: Optional[float] = None,
    health_min: Optional[float] = None,
    path: str | Path | None = None,
) -> None:
    """Configures and persists operational guard thresholds."""
    if path is None:
        path = Path("config/security/thresholds.yaml")

    current = load_guard_thresholds(path)
    if drift_max is not None:
        current["drift_max"] = drift_max
    if health_min is not None:
        current["health_min"] = health_min

    p = Path(path)
    if not p.parent.exists():
        raise RuntimeError(f"Config directory missing: {p.parent}")

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        yaml.dump(current, f)
    logger.info(f"Guard thresholds updated and persisted to {p}")


# Internal Helpers
def _load_yaml_policy(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            data = yaml.safe_load(path.read_text())
            if data is None:
                return {}
            if isinstance(data, dict):
                return data
            return {}
    except Exception as e:
        raise RuntimeError(f"CRITICAL: Failed to load policy from {path}: {e}")
    raise FileNotFoundError(f"CRITICAL: Policy file missing: {path}")


def _guard_safe_window(history: List[Dict[str, float]]) -> bool:
    """
    Uses trajectory analysis to determine if the system is within a safe
    operational window. Returns True if trends are stable or improving.
    """
    if not history:
        raise RuntimeError("History cannot be empty for safe window analysis")
    if len(history) < 2:
        return True  # Not enough data to determine drift velocity

    # Calculate drift velocity (rate of change)
    # Simple linear approximation between last two points
    latest = history[-1]
    previous = history[-2]

    dt = latest.get("timestamp", 0.0) - previous.get("timestamp", 0.0)
    if dt <= 0:
        return True

    drift_v = (latest.get("drift_score", 0.0) - previous.get("drift_score", 0.0)) / dt
    health_v = (
        latest.get("governance_health", 1.0) - previous.get("governance_health", 1.0)
    ) / dt

    # If drift is increasing rapidly or health is plummeting, the window is closing
    if drift_v > 0.1:  # Rapidly diverging
        logger.warning(f"DIVERGENCE DETECTED: Drift velocity {drift_v:.4f}")
        return False

    if health_v < -0.1:  # Rapidly deteriorating
        logger.warning(f"DETERIORATION DETECTED: Health velocity {health_v:.4f}")
        return False

    return True


@axiomatic_guard
def enforce_critical_directive(directive_id: str, action: Callable) -> PolicyResult:
    """
    Executes a critical governance directive.
    Requires hardware-attested environment validation via @axiomatic_guard.
    """
    logger.info(f"[Governance] Enforcing Critical Directive: {directive_id}")
    try:
        with tracer.start_as_current_span("enforce_critical_directive") as span:
            span.set_attribute("directive_id", directive_id)
            action()
        return PolicyResult(approved=True, reason=f"DIRECTIVE_ENFORCED: {directive_id}")
    except Exception as e:
        logger.error(f"[Governance] Directive Execution Failed: {e}")
        return PolicyResult(approved=False, reason=f"EXECUTION_FAILED: {e}")


# =============================================================================
# [P3xx] Policy Hot-Reload Engine
# Runtime policy updates without kernel restart
# =============================================================================

import threading
import time
import hashlib


@dataclass
class PolicyVersion:
    """Immutable policy snapshot with version tracking."""

    version: str
    content_hash: str
    thresholds: Dict[str, float]
    timestamp: float
    source_path: str


class PolicyHotReloader:
    """
    Runtime Policy Hot-Reload Engine.

    Features:
    - File system watch for policy changes
    - Atomic policy swaps with rollback
    - Validation before application
    - Telemetry on all policy transitions
    - Thread-safe concurrent access
    """

    _instance: Optional["PolicyHotReloader"] = None
    _lock = threading.Lock()

    def __init__(self, watch_path: str | Path | None = None):
        self._watch_path = (
            Path(watch_path) if watch_path else Path("config/security/thresholds.yaml")
        )
        self._current_policy: Optional[PolicyVersion] = None
        self._policy_history: List[PolicyVersion] = []
        self._callbacks: List[
            Callable[[Optional[PolicyVersion], PolicyVersion], None]
        ] = []
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_mtime: float = 0.0

    @classmethod
    def get_instance(cls, watch_path: str | Path | None = None) -> "PolicyHotReloader":
        """Singleton access to the policy reloader."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = PolicyHotReloader(watch_path)
        return cls._instance

    def _compute_hash(self, content: Dict[str, Any]) -> str:
        """Compute deterministic hash of policy content."""
        import json

        serialized = json.dumps(content, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _create_version(
        self, thresholds: Dict[str, float], source: str
    ) -> PolicyVersion:
        """Create a new policy version object."""
        content_hash = self._compute_hash(thresholds)
        return PolicyVersion(
            version=f"v{len(self._policy_history) + 1}-{content_hash}",
            content_hash=content_hash,
            thresholds=thresholds.copy(),
            timestamp=time.time(),
            source_path=source,
        )

    def load_initial(self) -> PolicyVersion:
        """Load the initial policy from disk."""
        thresholds = load_guard_thresholds(self._watch_path)
        self._current_policy = self._create_version(thresholds, str(self._watch_path))
        self._policy_history.append(self._current_policy)
        logger.info(
            f"🔄 [HotReload] Initial policy loaded: {self._current_policy.version}"
        )
        return self._current_policy

    def get_current_policy(self) -> Optional[PolicyVersion]:
        """Get the currently active policy version."""
        return self._current_policy

    def get_thresholds(self) -> Dict[str, float]:
        """Get current policy thresholds (thread-safe)."""
        with self._lock:
            if self._current_policy is None:
                self.load_initial()
            return (
                self._current_policy.thresholds.copy() if self._current_policy else {}
            )

    def _validate_policy(self, thresholds: Dict[str, float]) -> Tuple[bool, str]:
        """Validate policy thresholds before application."""
        # Drift max must be between 0 and 1
        drift = thresholds.get("drift_max", 0.8)
        if not (0.0 <= drift <= 1.0):
            return False, f"INVALID: drift_max ({drift}) must be in [0.0, 1.0]"

        # Health min must be between 0 and 1
        health = thresholds.get("health_min", 0.5)
        if not (0.0 <= health <= 1.0):
            return False, f"INVALID: health_min ({health}) must be in [0.0, 1.0]"

        # Latency max must be positive
        latency = thresholds.get("latency_max", 2000.0)
        if latency <= 0:
            return False, f"INVALID: latency_max ({latency}) must be positive"

        return True, "VALID"

    def reload(self, force: bool = False) -> Tuple[bool, str]:
        """
        Attempt to reload policy from disk.

        Args:
            force: If True, reload even if content unchanged.

        Returns:
            (success, message)
        """
        with self._lock:
            try:
                # Check if file exists
                if not self._watch_path.exists():
                    return False, f"POLICY_FILE_MISSING: {self._watch_path}"

                # Load new thresholds
                new_thresholds = _load_yaml_policy(self._watch_path)

                # Check for actual changes
                new_hash = self._compute_hash(new_thresholds)
                if (
                    not force
                    and self._current_policy
                    and new_hash == self._current_policy.content_hash
                ):
                    return True, "NO_CHANGE"

                # Validate before applying
                valid, msg = self._validate_policy(new_thresholds)
                if not valid:
                    logger.error(f"[HotReload] Policy validation failed: {msg}")
                    return False, msg

                # Create new version
                old_policy = self._current_policy
                new_policy = self._create_version(new_thresholds, str(self._watch_path))

                # Atomic swap
                self._current_policy = new_policy
                self._policy_history.append(new_policy)

                # Emit telemetry
                with tracer.start_as_current_span("policy_hot_reload") as span:
                    span.set_attribute(
                        "old_version", old_policy.version if old_policy else "none"
                    )
                    span.set_attribute("new_version", new_policy.version)
                    span.set_attribute("content_hash", new_policy.content_hash)

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(old_policy, new_policy)
                    except Exception as e:
                        logger.warning(f"[HotReload] Callback error: {e}")

                logger.info(
                    f"✅ [HotReload] Policy updated: {old_policy.version if old_policy else 'initial'} -> {new_policy.version}"
                )
                return True, f"RELOADED: {new_policy.version}"

            except Exception as e:
                logger.error(f"[HotReload] Reload failed: {e}")
                return False, f"RELOAD_ERROR: {e}"

    def rollback(self, steps: int = 1) -> Tuple[bool, str]:
        """
        Rollback to a previous policy version.

        Args:
            steps: Number of versions to roll back.

        Returns:
            (success, message)
        """
        with self._lock:
            if len(self._policy_history) <= steps:
                return False, "INSUFFICIENT_HISTORY"

            target_idx = len(self._policy_history) - 1 - steps
            target = self._policy_history[target_idx]

            old_policy = self._current_policy
            self._current_policy = target

            logger.warning(
                f"⚠️ [HotReload] ROLLBACK: {old_policy.version if old_policy else 'none'} -> {target.version}"
            )
            return True, f"ROLLED_BACK: {target.version}"

    def register_callback(
        self, callback: Callable[[Optional[PolicyVersion], PolicyVersion], None]
    ) -> None:
        """Register a callback for policy change notifications."""
        self._callbacks.append(callback)

    def start_watch(self, interval: float = 5.0) -> None:
        """
        Start background file watcher thread.

        Args:
            interval: Seconds between file checks.
        """
        if self._watch_thread is not None and self._watch_thread.is_alive():
            logger.warning("[HotReload] Watch thread already running")
            return

        self._stop_event.clear()

        def _watch_loop() -> None:
            logger.info(f"[HotReload] Starting file watch on {self._watch_path}")
            while not self._stop_event.is_set():
                try:
                    if self._watch_path.exists():
                        mtime = self._watch_path.stat().st_mtime
                        if mtime > self._last_mtime:
                            self._last_mtime = mtime
                            self.reload()
                except Exception as e:
                    logger.error(f"[HotReload] Watch error: {e}")

                self._stop_event.wait(interval)

            logger.info("[HotReload] File watch stopped")

        self._watch_thread = threading.Thread(target=_watch_loop, daemon=True)
        self._watch_thread.start()

    def stop_watch(self) -> None:
        """Stop the background file watcher."""
        self._stop_event.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=10.0)
            self._watch_thread = None

    def get_history(self) -> List[PolicyVersion]:
        """Get policy version history."""
        with self._lock:
            return self._policy_history.copy()


# Convenience function for global access
def get_policy_reloader() -> PolicyHotReloader:
    """Get the global PolicyHotReloader instance."""
    return PolicyHotReloader.get_instance()
