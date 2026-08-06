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
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SpeculativeBuffer")


@dataclass
class StagedChange:
    change_id: str
    target_key: str  # e.g., "policy:thresholds:drift_max" or "code:warm_logic/kernel/ops/control.py"
    old_value: Any
    new_value: Any
    proposed_by: str
    timestamp: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300.0)  # 5 min TTL


class SpeculativeManager:
    """
    Speculative Governance Buffer.
    Allows the kernel to 'dream' of new states before committing to them.
    Used for:
    1. BFT Proposal Pipelining (Staging changes while voting).
    2. 'What-If' Simulations (Predictive Protection).
    """

    def __init__(self):
        # buffer_id -> {target_key -> StagedChange}
        self._buffers: Dict[str, Dict[str, StagedChange]] = {}
        self._active_overlay: Optional[str] = None  # Currently active speculative layer

    def create_layer(self, layer_id: str) -> None:
        """Creates a new speculative layer."""
        if layer_id not in self._buffers:
            self._buffers[layer_id] = {}
            logger.info(f"[Speculation] Created new layer: {layer_id}")

    def stage_change(
        self,
        layer_id: str,
        change_id: str,
        target: str,
        old_val: Any,
        new_val: Any,
        proposer: str,
    ) -> None:
        """Stages a single change in a specific layer."""
        if layer_id not in self._buffers:
            self.create_layer(layer_id)

        change = StagedChange(change_id, target, old_val, new_val, proposer)
        self._buffers[layer_id][target] = change
        logger.info(
            f"🌫️ [Speculation] Staged change {change_id} in {layer_id}: {target}"
        )

    def activate_layer(self, layer_id: str) -> None:
        """Sets the active overlay for the kernel to 'see'."""
        if layer_id in self._buffers:
            self._active_overlay = layer_id
            logger.warning(
                f"🔮 [Speculation] ACTIVE OVERLAY: {layer_id}. Reality is now mutable."
            )
        else:
            logger.error(f"[Speculation] Layer {layer_id} not found.")

    def deactivate_layer(self) -> None:
        """Returns to ground truth."""
        self._active_overlay = None
        logger.info(
            "⚓️ [Speculation] Overlay deactivated. Returned to Concrete Reality."
        )

    def get_effective_value(self, target: str, current_real_value: Any) -> Any:
        """
        Returns the speculative value if an overlay is active and contains the target,
        otherwise returns the real value.
        """
        if not self._active_overlay:
            return current_real_value

        layer = self._buffers.get(self._active_overlay)
        if layer and target in layer:
            return layer[target].new_value

        return current_real_value

    def commit_layer(self, layer_id: str) -> List[StagedChange]:
        """
        Finalizes the layer (ready for commit).
        Returns the list of changes to be applied to persistence.
        """
        if layer_id not in self._buffers:
            return []

        changes = list(self._buffers[layer_id].values())
        logger.info(
            f"✅ [Speculation] Committing layer {layer_id} ({len(changes)} changes)."
        )
        # Cleanup
        del self._buffers[layer_id]
        if self._active_overlay == layer_id:
            self._active_overlay = None

        return changes

    def rollback_layer(self, layer_id: str) -> None:
        """Discards the layer."""
        if layer_id in self._buffers:
            del self._buffers[layer_id]
            logger.warning(f"⏪ [Speculation] Rolled back layer {layer_id}.")

        if self._active_overlay == layer_id:
            self._active_overlay = None


# Global Singleton for the Kernel
speculative_buffer = SpeculativeManager()
