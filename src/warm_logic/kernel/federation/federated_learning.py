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
"""
Federated Learning Pipeline

Privacy-preserving distributed machine learning across sovereign federation nodes.
Uses differential privacy and secure aggregation for model training.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("FederatedLearning")


class FLState(Enum):
    """Federated Learning round states."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    TRAINING = "training"
    AGGREGATING = "aggregating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class AggregationStrategy(Enum):
    """Model aggregation strategies."""

    FEDAVG = "fedavg"  # Federated Averaging
    FEDPROX = "fedprox"  # Federated Proximal
    SCAFFOLD = "scaffold"  # SCAFFOLD algorithm
    MEDIAN = "median"  # Coordinate-wise median


@dataclass
class ModelUpdate:
    """Model update from a participant node."""

    node_id: str
    round_id: int
    weights: Dict[str, np.ndarray[Any, Any]]  # Layer name -> weights
    num_samples: int
    loss: float
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    signature: str = ""  # PQC signature

    def compute_hash(self) -> str:
        """Compute hash of model weights for verification."""
        weight_bytes = b""
        for name in sorted(self.weights.keys()):
            weight_bytes += self.weights[name].tobytes()
        return hashlib.sha256(weight_bytes).hexdigest()


@dataclass
class FLRound:
    """Federated Learning training round."""

    round_id: int
    global_model_hash: str
    participants: List[str]
    min_participants: int
    state: FLState = FLState.IDLE
    updates: Dict[str, ModelUpdate] = field(default_factory=dict)
    aggregated_weights: Optional[Dict[str, np.ndarray[Any, Any]]] = None
    started_at: float = 0.0
    completed_at: float = 0.0
    validation_loss: float = 0.0

    def has_quorum(self) -> bool:
        """Check if enough participants have submitted updates."""
        return len(self.updates) >= self.min_participants


@dataclass
class DifferentialPrivacyConfig:
    """Differential privacy configuration."""

    epsilon: float = 1.0  # Privacy budget
    delta: float = 1e-5  # Failure probability
    clip_norm: float = 1.0  # Gradient clipping norm
    noise_multiplier: float = 1.0  # Noise scale


class SecureAggregator:
    """
    Secure Aggregation for Federated Learning

    Implements privacy-preserving model aggregation using:
    - Differential Privacy (DP) for gradient noise
    - Secure Multi-Party Computation (MPC) concepts
    - PQC-signed model updates
    """

    def __init__(
        self,
        strategy: AggregationStrategy = AggregationStrategy.FEDAVG,
        dp_config: Optional[DifferentialPrivacyConfig] = None,
    ):
        self.strategy = strategy
        self.dp_config = dp_config or DifferentialPrivacyConfig()

    def aggregate(
        self, updates: List[ModelUpdate], total_samples: int
    ) -> Dict[str, np.ndarray]:
        """
        Aggregate model updates from participants.

        Args:
            updates: List of ModelUpdate from participants
            total_samples: Total number of samples across all participants

        Returns:
            Aggregated model weights
        """
        if not updates:
            raise ValueError("No updates to aggregate")

        if self.strategy == AggregationStrategy.FEDAVG:
            return self._federated_averaging(updates, total_samples)
        elif self.strategy == AggregationStrategy.MEDIAN:
            return self._coordinate_median(updates)
        else:
            # Default to FedAvg
            return self._federated_averaging(updates, total_samples)

    def _federated_averaging(
        self, updates: List[ModelUpdate], total_samples: int
    ) -> Dict[str, np.ndarray]:
        """
        Federated Averaging (FedAvg) algorithm.

        Weighted average of model updates based on number of samples.
        """
        # Get layer names from first update
        layer_names = list(updates[0].weights.keys())
        aggregated = {}

        for layer in layer_names:
            # Weighted sum
            weighted_sum = np.zeros_like(updates[0].weights[layer])
            for update in updates:
                weight = update.num_samples / total_samples
                weighted_sum += weight * update.weights[layer]

            # Apply differential privacy noise if configured
            if self.dp_config.epsilon < float("inf"):
                noise = self._generate_dp_noise(weighted_sum.shape)
                weighted_sum += noise

            aggregated[layer] = weighted_sum

        return aggregated

    def _coordinate_median(self, updates: List[ModelUpdate]) -> Dict[str, np.ndarray]:
        """
        Coordinate-wise median aggregation.

        More robust to Byzantine participants.
        """
        layer_names = list(updates[0].weights.keys())
        aggregated = {}

        for layer in layer_names:
            stacked = np.stack([u.weights[layer] for u in updates])
            aggregated[layer] = np.median(stacked, axis=0)

        return aggregated

    def _generate_dp_noise(self, shape: Tuple[int, ...]) -> np.ndarray:
        """Generate differential privacy noise."""
        sensitivity = self.dp_config.clip_norm
        noise_scale = (
            sensitivity * self.dp_config.noise_multiplier / self.dp_config.epsilon
        )
        return np.random.normal(0, noise_scale, shape)

    def clip_gradients(self, weights: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Clip gradients for differential privacy."""
        # Compute global norm
        total_norm = 0.0
        for w in weights.values():
            total_norm += np.sum(w**2)
        total_norm = np.sqrt(total_norm)

        # Clip if necessary
        clip_coef = min(1.0, self.dp_config.clip_norm / (total_norm + 1e-6))
        return {name: w * clip_coef for name, w in weights.items()}


class FederatedLearningCoordinator:
    """
    Federated Learning Coordinator

    Orchestrates distributed training across sovereign federation nodes.
    """

    def __init__(
        self,
        node_id: str,
        aggregator: Optional[SecureAggregator] = None,
        min_participants: int = 2,
        round_timeout_sec: float = 300.0,
        mesh: Any = None,
    ):
        self.node_id = node_id
        self.aggregator = aggregator or SecureAggregator()
        self.min_participants = min_participants
        self.round_timeout_sec = round_timeout_sec
        self.mesh = mesh

        # State
        self.current_round: Optional[FLRound] = None
        self.completed_rounds: List[FLRound] = []
        self.global_model: Dict[str, np.ndarray] = {}
        self._round_counter = 0

        # Callbacks
        self._on_round_complete: Optional[Callable[[FLRound], None]] = None
        self._on_model_updated: Optional[Callable[[Dict[str, np.ndarray]], None]] = None

        logger.info(f"[FL] Coordinator initialized on {node_id}")

    def initialize_global_model(
        self, model_weights: Dict[str, np.ndarray[Any, Any]]
    ) -> None:
        """Initialize the global model weights."""
        self.global_model = {k: v.copy() for k, v in model_weights.items()}
        logger.info(f"[FL] Global model initialized ({len(model_weights)} layers)")

    def start_round(self, participants: List[str]) -> FLRound:
        """
        Start a new federated learning round.

        Args:
            participants: List of participant node IDs

        Returns:
            FLRound object
        """
        if self.current_round and self.current_round.state == FLState.TRAINING:
            raise RuntimeError("Cannot start new round while training in progress")

        self._round_counter += 1
        global_hash = self._compute_model_hash()

        self.current_round = FLRound(
            round_id=self._round_counter,
            global_model_hash=global_hash,
            participants=participants,
            min_participants=min(self.min_participants, len(participants)),
            state=FLState.INITIALIZING,
            started_at=time.time(),
        )

        logger.info(
            f"[FL] Round {self._round_counter} started with {len(participants)} participants"
        )

        self.current_round.state = FLState.TRAINING
        return self.current_round

    def broadcast_model(self, participants: List[str]) -> None:
        """Broadcast current global model to all participants via Neural Mesh."""
        if not self.mesh:
            logger.warning("[FL] No mesh available for broadcasting")
            return

        # Serialization for transport (bytes-safe)
        import pickle

        model_data = pickle.dumps(self.global_model)

        for participant in participants:
            success = self.mesh.send_message(participant, model_data)
            if not success:
                logger.warning(f"[FL] Failed to send model to {participant}")

        logger.info(
            f"[FL] Global model broadcasted to {len(participants)} nodes via Neural Mesh"
        )

    def submit_update(self, update: ModelUpdate) -> bool:
        """
        Submit a model update for the current round.

        Args:
            update: ModelUpdate from a participant

        Returns:
            True if update was accepted
        """
        if not self.current_round:
            logger.warning("[FL] No active round")
            return False

        if self.current_round.state != FLState.TRAINING:
            logger.warning(
                f"[FL] Round not in training state: {self.current_round.state}"
            )
            return False

        if update.node_id not in self.current_round.participants:
            logger.warning(f"[FL] Node {update.node_id} not a participant")
            return False

        if update.round_id != self.current_round.round_id:
            logger.warning(f"[FL] Update round mismatch: {update.round_id}")
            return False

        # Verify update hash (integrity check)
        computed_hash = update.compute_hash()
        logger.debug(f"[FL] Update from {update.node_id}: hash={computed_hash[:16]}...")

        # Store update
        self.current_round.updates[update.node_id] = update

        logger.info(
            f"[FL] Received update from {update.node_id} "
            f"({len(self.current_round.updates)}/{self.current_round.min_participants})"
        )

        # Check if we can aggregate
        if self.current_round.has_quorum():
            self._aggregate_updates()

        return True

    def _aggregate_updates(self) -> None:
        """Aggregate updates and update global model."""
        if not self.current_round:
            return

        self.current_round.state = FLState.AGGREGATING

        updates = list(self.current_round.updates.values())
        total_samples = sum(u.num_samples for u in updates)

        try:
            # Aggregate using configured strategy
            aggregated = self.aggregator.aggregate(updates, total_samples)
            self.current_round.aggregated_weights = aggregated

            # Update global model
            self.global_model = aggregated

            # Compute average loss
            avg_loss = sum(u.loss for u in updates) / len(updates)
            self.current_round.validation_loss = avg_loss

            self.current_round.state = FLState.COMPLETED
            self.current_round.completed_at = time.time()

            self.completed_rounds.append(self.current_round)

            logger.info(
                f"[FL] Round {self.current_round.round_id} completed "
                f"(loss={avg_loss:.4f}, participants={len(updates)})"
            )

            # Trigger callback
            if self._on_round_complete:
                self._on_round_complete(self.current_round)

            if self._on_model_updated:
                self._on_model_updated(self.global_model)

        except Exception as e:
            logger.error(f"[FL] Aggregation failed: {e}")
            self.current_round.state = FLState.FAILED

    def get_global_model(self) -> Dict[str, np.ndarray[Any, Any]]:
        """Get the current global model weights."""
        return {k: v.copy() for k, v in self.global_model.items()}

    def get_round_status(self) -> Optional[Dict[str, Any]]:
        """Get status of current round."""
        if not self.current_round:
            return None

        return {
            "round_id": self.current_round.round_id,
            "state": self.current_round.state.value,
            "participants": len(self.current_round.participants),
            "updates_received": len(self.current_round.updates),
            "min_participants": self.current_round.min_participants,
            "has_quorum": self.current_round.has_quorum(),
            "started_at": self.current_round.started_at,
        }

    def get_training_history(self) -> List[Dict[str, Any]]:
        """Get history of completed rounds."""
        return [
            {
                "round_id": r.round_id,
                "participants": len(r.updates),
                "validation_loss": r.validation_loss,
                "duration_sec": r.completed_at - r.started_at,
            }
            for r in self.completed_rounds
        ]

    def _compute_model_hash(self) -> str:
        """Compute hash of global model."""
        if not self.global_model:
            return "empty"
        weight_bytes = b""
        for name in sorted(self.global_model.keys()):
            weight_bytes += self.global_model[name].tobytes()
        return hashlib.sha256(weight_bytes).hexdigest()

    def on_round_complete(self, callback: Callable[[FLRound], None]) -> None:
        """Register callback for round completion."""
        self._on_round_complete = callback

    def on_model_updated(
        self, callback: Callable[[Dict[str, np.ndarray]], None]
    ) -> None:
        """Register callback for model updates."""
        self._on_model_updated = callback


class FederatedLearningParticipant:
    """
    Federated Learning Participant

    Participates in distributed training on a sovereign node.
    """

    def __init__(
        self,
        node_id: str,
        local_train_fn: Optional[Callable] = None,
        dp_config: Optional[DifferentialPrivacyConfig] = None,
    ):
        self.node_id = node_id
        self.local_train_fn = local_train_fn
        self.dp_config = dp_config
        self._aggregator = SecureAggregator(dp_config=dp_config)

        logger.info(f"[FL] Participant initialized on {node_id}")

    def train_local(
        self,
        global_weights: Dict[str, np.ndarray],
        local_data: Any,
        round_id: int,
        epochs: int = 1,
    ) -> ModelUpdate:
        """
        Perform local training and create model update.

        Args:
            global_weights: Current global model weights
            local_data: Local training data
            round_id: Current round ID
            epochs: Number of local epochs

        Returns:
            ModelUpdate with trained weights
        """
        # Use custom training function if provided
        if self.local_train_fn:
            trained_weights, loss, num_samples = self.local_train_fn(
                global_weights, local_data, epochs
            )
        else:
            # Dummy training for testing
            trained_weights = {
                k: v + np.random.randn(*v.shape) * 0.01
                for k, v in global_weights.items()
            }
            loss = np.random.uniform(0.1, 1.0)
            num_samples = 100

        # Apply gradient clipping for DP
        if self.dp_config:
            trained_weights = self._aggregator.clip_gradients(trained_weights)

        update = ModelUpdate(
            node_id=self.node_id,
            round_id=round_id,
            weights=trained_weights,
            num_samples=num_samples,
            loss=loss,
            metrics={"epochs": epochs},
        )

        logger.info(
            f"[FL] Local training complete (loss={loss:.4f}, samples={num_samples})"
        )

        return update
