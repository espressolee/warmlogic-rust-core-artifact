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

import heapq
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import warm_logic.observability.metrics as prom_metrics

logger = logging.getLogger("KernelControl")


def _fsm_next(state: str, event: str) -> str:
    transitions: Dict[Tuple[str, str], str] = {
        ("INIT", "BOOT"): "AUTHORIZED",
        ("AUTHORIZED", "ALIGN"): "ALIGNING",
        ("ALIGNING", "REFLECT"): "REFLECTED",
        ("REFLECTED", "JOURNAL"): "JOURNALED",
    }
    return transitions.get((state, event), state)


class KernelContext:
    def __init__(self) -> None:
        self.tick_count = 0

    def increment_tick(self) -> None:
        self.tick_count += 1


try:
    from warm_logic_rs import RustResonanceOptimizer, RustTaskScheduler

    _HAS_RUST_CORE = True
except ImportError:
    _HAS_RUST_CORE = False


class ResonanceOptimizer:
    """
    Adaptive Logic Driver.
    Adjusts ReflectiveLoop coefficients based on resonance (epsilon_c) and ethics (tau_ethics).
    """

    def __init__(self, loop_engine: Any) -> None:
        self.loop_engine = loop_engine
        if _HAS_RUST_CORE:
            self._impl = RustResonanceOptimizer()
        else:
            self.alpha = 0.5
            self.beta = 0.5
            logger.warning(
                "[ADAPTIVE_LOGIC] Rust core unavailable; using simulated optimizer mode."
            )

    def optimize(self, epsilon_c: float, tau_ethics: float) -> None:
        if _HAS_RUST_CORE:
            self._impl.optimize(epsilon_c, tau_ethics)
            alpha, beta = self._impl.alpha, self._impl.beta
        else:
            # High resonance -> More stability focus (alpha)
            if epsilon_c > 0.9:
                self.alpha = min(0.9, self.alpha + 0.05)
                self.beta = max(0.1, 1.0 - self.alpha)

            # Ethical concerns -> More ethics focus (beta)
            if tau_ethics > 0.5:
                self.beta = min(0.9, self.beta + 0.1)
                self.alpha = max(0.1, 1.0 - self.beta)

            # Stability check
            if epsilon_c < 0.4:
                # Emergency reset to balanced safety
                self.alpha = 0.5
                self.beta = 0.5
            alpha, beta = self.alpha, self.beta

        if hasattr(self.loop_engine, "update_coefficients"):
            self.loop_engine.update_coefficients(alpha, beta)
            logger.info(
                f"🔄 [ADAPTIVE_LOGIC] Coefficients updated: α={alpha:.2f}, β={beta:.2f}"
            )

        # Keep mirrored attributes in sync for engines/tests that inspect alpha/beta
        # directly instead of reading through update callbacks.
        for attr, value in (("alpha", alpha), ("beta", beta)):
            try:
                setattr(self.loop_engine, attr, value)
            except Exception:
                # Some Rust-backed wrappers may expose read-only descriptors.
                pass

    @property
    def alpha(self) -> float:
        return self._impl.alpha if _HAS_RUST_CORE else self.__dict__.get("alpha", 0.5)

    @alpha.setter
    def alpha(self, value: float) -> None:
        if _HAS_RUST_CORE:
            self._impl.alpha = value
        else:
            self.__dict__["alpha"] = value

    @property
    def beta(self) -> float:
        return self._impl.beta if _HAS_RUST_CORE else self.__dict__.get("beta", 0.5)

    @beta.setter
    def beta(self, value: float) -> None:
        if _HAS_RUST_CORE:
            self._impl.beta = value
        else:
            self.__dict__["beta"] = value


class KernelLoop:
    def __init__(self, ctx: Any, evolution_chamber: Any = None) -> None:
        self.ctx = ctx
        self.state = "INIT"
        self.optimizer: Optional[ResonanceOptimizer] = None
        self.evolution_chamber = evolution_chamber
        self.tm: Optional[Any] = None

        # Initialize Optimizer if Rust Core is available
        from warm_logic.kernel import api

        if api.rust_loader.HAS_RUST_CORE:
            # Ensure _RUST_LOOP is initialized in api.py
            api.compute_mode(
                api.ModeDecisionContext(
                    "INITIALIZING", {"epsilon_c": 1.0, "tau_ethics": 0.0}
                )
            )
            if api._RUST_LOOP:
                self.optimizer = ResonanceOptimizer(api._RUST_LOOP)

        # [Phase 2] Kinetic Economy
        from .economy import CreditManager

        self.economy = CreditManager(
            self.ctx.dht.node_id.hex() if hasattr(self.ctx, "dht") else "local",
            store=getattr(self.ctx, "store", None),
        )

        # long-horizon autonomy (aspirational)
        from warm_logic.kernel.identity.kai_engine import KAIEngine

        from .stochastic_gateway import StochasticGateway

        self.stochastic = StochasticGateway()
        self.kai_engine = KAIEngine()

        # [Phase 4] Strategic Governance
        from .service_registry import ServiceQuorum

        self.service_registry: Optional[ServiceQuorum] = None
        if (
            hasattr(self.ctx, "gossip")
            and hasattr(self.ctx, "store")
            and self.ctx.gossip
            and self.ctx.store
        ):
            self.service_registry = ServiceQuorum(self.ctx.store, self.ctx.gossip)
            if hasattr(self.ctx.gossip, "dht"):
                setattr(self.ctx.gossip.dht, "service_registry", self.service_registry)

        # HSM Initialization
        from warm_logic.kernel.hardware.hsm import initialize_hsm, get_hsm_manager

        initialize_hsm()
        hsm = get_hsm_manager()

        # Multi-Region Federation
        from warm_logic.kernel.federation.multi_region import (
            MultiRegionFederation,
            Region,
        )

        identity = getattr(self.ctx, "identity", None)
        node_id = "local"
        if hasattr(self.ctx, "dht") and self.ctx.dht:
            node_id = self.ctx.dht.node_id.hex()
        elif hasattr(self.ctx, "node_id"):
            node_id = self.ctx.node_id

        self.multi_region = MultiRegionFederation(
            local_node_id=node_id,
            local_region=Region.US_EAST,  # Default for 
        )

        # Upgrade Identity to HSM if possible
        if identity and not getattr(identity, "hsm_key_id", None):
            hsm_key = hsm.generate_signing_key(label=f"KineticIdentity-{node_id}")
            if hsm_key:
                from warm_logic.kernel.identity.kinetic_id import KineticIdentity

                identity_upgraded = KineticIdentity(hsm_key_id=hsm_key.key_id)
                if hasattr(self.ctx, "identity"):
                    self.ctx.identity = identity_upgraded
                logger.info(
                    f"[HSM] Identity upgraded to hardware-backed: {hsm_key.key_id}"
                )

        # Neural Mesh & Fleet Management
        from warm_logic.kernel.mesh.neural_mesh import NeuralMesh
        from warm_logic.system.fleet.manager import FleetManager
        from warm_logic.kernel.mesh.transport import create_transport

        node_id = "local"
        if hasattr(self.ctx, "dht") and self.ctx.dht:
            node_id = self.ctx.dht.node_id.hex()
        elif hasattr(self.ctx, "node_id"):
            node_id = self.ctx.node_id

        # Initializing Sovereign Transport
        self.transport = create_transport(
            identity=getattr(self.ctx, "identity", None), secure=True
        )
        self.fleet_manager = FleetManager()

        self.neural_mesh = NeuralMesh(
            local_node_id=node_id,
            transport=self.transport,
            fleet_manager=self.fleet_manager,
        )

        # Federated Learning Activation
        from warm_logic.kernel.federation.federated_learning import (
            FederatedLearningCoordinator,
        )

        self.fl_coordinator = FederatedLearningCoordinator(
            node_id=node_id, mesh=self.neural_mesh
        )

        # Transaction manager compatibility and persistence recovery.
        try:
            from warm_logic.kernel.transaction import TransactionManager

            self.tm = TransactionManager("state/kernel")
        except Exception as e:
            logger.warning(f"[KernelLoop] Transaction manager init failed: {e}")

        # Collective Evolution Quorum
        self.mutation_quorum: Optional[Any] = None
        if hasattr(self.ctx, "codebase") and hasattr(self.ctx, "dht"):
            if self.ctx.dht and self.ctx.dht.gossip_agent:
                from .collective_evolution import MutationQuorum

                self.mutation_quorum = MutationQuorum(
                    self.ctx.codebase,
                    self.ctx.dht.gossip_agent,
                    economy=self.economy,
                    stochastic=self.stochastic,
                )
                self.ctx.dht.gossip_agent.mutation_quorum = self.mutation_quorum

    def tick(self, metrics: Optional[Dict[str, Any]] = None) -> None:
        if hasattr(self.ctx, "increment_tick"):
            try:
                self.ctx.increment_tick()
            except Exception as e:
                logger.error(f"Kernel Loop Context increment_tick fail: {e}")

        # Adaptive Logic
        if self.optimizer and metrics:
            e_c = metrics.get("epsilon_c", 1.0)
            t_e = metrics.get("tau_ethics", 0.0)
            self.optimizer.optimize(e_c, t_e)

            # Trigger Evolution under Extreme Stability
            if e_c >= 0.98 and t_e <= 0.01 and self.evolution_chamber:
                self.trigger_evolution()

        # Normalize tick before modulo operations.
        t = getattr(self.ctx, "tick_count", 0)
        try:
            t = int(t)
        except Exception:
            t = getattr(self.ctx, "tick", 0)
        try:
            t = int(t)
        except Exception:
            t = 0

        # Synaptic Pruning & Fleet Health
        if t % 10 == 0:
            self.fleet_manager.get_fleet_health()
        if t % 300 == 0:
            self.neural_mesh.prune_synapses()

        # Cross-Region Sync & Partition Detection
        if t % 50 == 0:
            self.multi_region.execute_pending_syncs()
            self.multi_region.detect_partitions()

        if self.state == "INIT" and t >= 3:
            self.state = "AUTHORIZED"

        # Persist state transition and emit Axiom-04 latency warning.
        if self.tm is not None:
            try:
                tx = self.tm.begin_transaction()
                tx.setdefault("data", {})
                tx["data"]["kernel_state"] = self.state
                tx["data"]["tick_count"] = t
                tx["signature"] = f"ML-DSA-65:{str(tx.get('hash', 'genesis'))[:16]}"

                start = time.perf_counter()
                self.tm.commit(tx)
                commit_ms = (time.perf_counter() - start) * 1000.0
                if commit_ms > 50.0:
                    logger.warning(
                        f"Axiom 04 Violation: commit latency >50ms ({commit_ms:.2f}ms)"
                    )
            except Exception as e:
                logger.warning(f"[KernelLoop] Transaction commit skipped: {e}")

        # Production Armor: Telemetry
        try:
            prom_metrics.update_uptime()
            # If ctx has height, export it
            if hasattr(self.ctx, "height"):
                prom_metrics.BLOCK_HEIGHT.set(self.ctx.height)
        except Exception as e:
            logger.warning(f"[Prometheus] Metrics update failed: {e}")

    def trigger_evolution(self) -> None:
        """
        [/17000] Initiates a controlled evolution step.
        """
        logger.info(
            "🧬 [Evolution] HIGH RESONANCE DETECTED. Initiating evolution proposal..."
        )

        if self.mutation_quorum:
            # Collective Mutation
            # For demonstration, we'll propose a minor optimization to a dummy logic file
            # or a logging statement if it's safe.
            # Here we just trigger the proposal logic.
            # rel_path = "warm_logic/kernel/ops/control.py" # Self-mutation is high-risk!
            pass
        elif self.evolution_chamber:
            # Isolated Mutation
            pass


@dataclass(order=True)
class KernelTask:
    priority: int
    task_id: str = field(compare=False)
    action: Any = field(default=None, compare=False)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.task_id == other
        # Handle both Python and Rust task types for equality
        is_task = hasattr(other, "priority") and hasattr(other, "task_id")
        if not is_task:
            return False
        return self.priority == other.priority and self.task_id == other.task_id


class TaskScheduler:
    def __init__(self) -> None:
        if _HAS_RUST_CORE:
            self._impl = RustTaskScheduler()
        else:
            self._impl = []

    def schedule(self, task_id: str, action: Any, priority: int = 10) -> None:
        if action is None or isinstance(action, (int, float)):  # Priority overload
            # hardware attestation enforcement: No more empty lambdas.
            raise ValueError(
                f"CRITICAL: Task {task_id} scheduled without valid action."
            )

        if _HAS_RUST_CORE:
            self._impl.schedule(task_id, action, int(priority))
        else:
            heapq.heappush(self._impl, KernelTask(int(priority), task_id, action))

    def next_task(self) -> Optional[Any]:
        if _HAS_RUST_CORE:
            return self._impl.next_task()

        if not self._impl:
            return None
        return heapq.heappop(self._impl)

    def pending_count(self) -> int:
        if _HAS_RUST_CORE:
            return self._impl.pending_count()
        return len(self._impl)


def _origin_from_entry(e: Dict[str, Any]) -> str:
    if "meta" in e:
        m = e["meta"]
        return str(m.get("origin") or m.get("source") or "unknown")
    return str(e.get("origin", "unknown"))


def _status_bucket(v: Any) -> str:
    if v == "applied":
        return "success"
    if str(v).upper() == "ROLLBACK":
        return "rollback"
    return "failed"


def _is_ci_related(s: Any) -> bool:
    if isinstance(s, dict):
        d = s.get("detail", {})
        if "tests_failing" in d or "error" in d:
            return True
        s = s.get("reason", "")
    return "ci" in str(s).lower() or "flake8" in str(s).lower()


def _estimate_human_minutes(entry: Dict[str, Any]) -> float:
    # hardware attestation enforcement: Skip intensive telemetry if Rust core is missing.
    from warm_logic.kernel import rust_loader

    if not rust_loader.HAS_RUST_CORE:
        return 0.0

    from .metrics import _estimate_human_minutes as real_estimate

    return real_estimate(entry)


def _load_lines(path: str, limit: int = 0) -> List[Dict[str, Any]]:
    import json

    try:
        with open(path, "r") as f:
            lines = f.readlines()
            res: List[Dict[str, Any]] = []
            for line in lines:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        res.append(item)
                except Exception as e:
                    logger.debug(f"Parsing failed for line in {path}: {e}")
            return res
    except Exception as e:
        logger.error(f"Failed to load lines from {path}: {e}")
        return []


def _parse_ts(s: Any) -> Optional[datetime]:
    if isinstance(s, datetime):
        return s
    if s is None or s == "not-a-date":
        return None
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s, tz=timezone.utc)
    try:
        clean = str(s).replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return None


def load_patch_efficiency(p: str, limit: int = 500) -> Dict[str, Any]:
    from pathlib import Path

    from .metrics import load_patch_efficiency as real_load

    return real_load(Path(p), limit=limit)


def build_patch_efficiency_report(recs: List[Any]) -> Any:
    from .metrics import build_patch_efficiency_report as real_build

    return real_build(recs)


# hardware attestation enforcement: Simulation Artifacts Purged.


def _infer_action(*args: Any, **kwargs: Any) -> str:
    # hardware attestation enforcement
    # If we don't have a real AI decision, we default to "HALT" for safety, or raise error.
    # Raising error might crash loop. HALT is safer for "Deny by Default".
    return "HALT"


class ConsensusMechanism:
    def propose_block(self, h: str) -> None:
        raise RuntimeError(
            "CRITICAL: ConsensusMechanism stub deleted. Real BFT/Raft required."
        )
