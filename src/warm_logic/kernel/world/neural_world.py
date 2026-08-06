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
[Phase 108.1-3] Neural World Model.
Implements predictive modeling, imagination, and world embeddings.
"""

import logging
import math
import random
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("NeuralWorldModel")


@dataclass
class WorldObservation:
    """An observation from the world."""

    timestamp: datetime
    state: Dict[str, float]  # Simplified state vector
    action: Optional[str] = None
    next_state: Optional[Dict[str, float]] = None
    reward: float = 0.0


class PredictiveModel:
    """
    [Phase 108.1] Predictive World Model.

    Learns to predict next state given current state and action.
    Uses a simple linear model (no GPU required).
    """

    def __init__(self, state_dim: int = 10, learning_rate: float = 0.01):
        self.state_dim = state_dim
        self.lr = learning_rate
        # Simple linear weights (state_dim x state_dim)
        self.weights = [
            [random.uniform(-0.1, 0.1) for _ in range(state_dim)]
            for _ in range(state_dim)
        ]
        self.bias = [0.0] * state_dim
        self.training_count = 0
        self.prediction_errors: deque[float] = deque(maxlen=100)
        logger.info("[PredictiveModel] Active.")

    def _state_to_vector(self, state: Dict[str, float]) -> List[float]:
        """Convert state dict to vector."""
        keys = sorted(state.keys())[: self.state_dim]
        vec = [state.get(k, 0.0) for k in keys]
        # Pad to state_dim
        while len(vec) < self.state_dim:
            vec.append(0.0)
        return vec

    def _vector_to_state(self, vec: List[float], keys: List[str]) -> Dict[str, float]:
        """Convert vector back to state dict."""
        return {k: v for k, v in zip(keys, vec)}

    def predict(self, state: Dict[str, float]) -> Dict[str, float]:
        """Predict next state."""
        x = self._state_to_vector(state)
        keys = sorted(state.keys())[: self.state_dim]

        # Linear prediction: y = Wx + b
        y = []
        for i in range(len(keys)):
            val = self.bias[i]
            for j, xj in enumerate(x):
                if j < len(self.weights[i]):
                    val += self.weights[i][j] * xj
            y.append(val)

        return self._vector_to_state(y, keys)

    def train(self, observation: WorldObservation) -> None:
        """Train on an observation (online learning)."""
        if observation.next_state is None:
            return

        x = self._state_to_vector(observation.state)
        y_true = self._state_to_vector(observation.next_state)
        y_pred = [
            self.bias[i]
            + sum(
                self.weights[i][j] * x[j]
                for j in range(min(len(x), len(self.weights[i])))
            )
            for i in range(len(y_true))
        ]

        # Calculate error
        error = sum((y_true[i] - y_pred[i]) ** 2 for i in range(len(y_true)))
        self.prediction_errors.append(error)

        # Gradient descent update
        for i in range(len(y_true)):
            delta = y_true[i] - y_pred[i]
            self.bias[i] += self.lr * delta
            for j in range(min(len(x), len(self.weights[i]))):
                self.weights[i][j] += self.lr * delta * x[j]

        self.training_count += 1

    def get_error(self) -> float:
        """Get average prediction error."""
        if not self.prediction_errors:
            return 0.0
        return float(sum(self.prediction_errors) / len(self.prediction_errors))


class ImaginationEngine:
    """
    [Phase 108.2] Imagination-Based Planning.

    Uses the predictive model to simulate future trajectories.
    """

    def __init__(self, predictor: PredictiveModel):
        self.predictor = predictor
        self.imagination_count = 0
        logger.info("[Imagination] Engine Active.")

    def imagine(
        self, start_state: Dict[str, float], actions: List[str], steps: int = 5
    ) -> List[Dict[str, float]]:
        """Imagine future states given a sequence of actions."""
        trajectory = [start_state]
        current = start_state.copy()

        for i in range(steps):
            predicted = self.predictor.predict(current)
            trajectory.append(predicted)
            current = predicted

        self.imagination_count += 1
        return trajectory

    def evaluate_plan(
        self,
        start_state: Dict[str, float],
        plan: List[str],
        goal_state: Dict[str, float],
    ) -> float:
        """Evaluate how well a plan achieves a goal."""
        trajectory = self.imagine(start_state, plan, len(plan))

        if not trajectory:
            return 0.0

        final_state = trajectory[-1]

        # Calculate distance to goal
        distance = 0.0
        for key in goal_state:
            if key in final_state:
                distance += (goal_state[key] - final_state[key]) ** 2

        # Convert to score (closer = higher)
        return 1.0 / (1.0 + math.sqrt(distance))

    def find_best_action(
        self,
        state: Dict[str, float],
        possible_actions: List[str],
        goal_state: Dict[str, float],
    ) -> Tuple[str, float]:
        """Find the best action to take."""
        best_action = possible_actions[0] if possible_actions else ""
        best_score = 0.0

        for action in possible_actions:
            score = self.evaluate_plan(state, [action], goal_state)
            if score > best_score:
                best_score = score
                best_action = action

        return best_action, best_score


class WorldEmbedding:
    """
    [Phase 108.3] World State Embedding.

    Creates dense vector representations of world states.
    Enables similarity-based retrieval and reasoning.
    """

    def __init__(self, embedding_dim: int = 32):
        self.embedding_dim = embedding_dim
        self.state_embeddings: Dict[str, List[float]] = {}
        self.encoder_weights = [
            [random.uniform(-0.1, 0.1) for _ in range(embedding_dim)] for _ in range(64)
        ]  # Max 64 features
        logger.info("[WorldEmbedding] Active.")

    def encode(self, state: Dict[str, float]) -> List[float]:
        """Encode a state into a dense vector."""
        # Create input vector
        keys = sorted(state.keys())
        values = [state[k] for k in keys]

        # Pad to 64
        while len(values) < 64:
            values.append(0.0)
        values = values[:64]

        # Simple encoding: weighted sum with tanh activation
        embedding = []
        for dim in range(self.embedding_dim):
            val = sum(
                values[i] * self.encoder_weights[i][dim] for i in range(len(values))
            )
            embedding.append(math.tanh(val))

        return embedding

    def similarity(self, state1: Dict[str, float], state2: Dict[str, float]) -> float:
        """Calculate similarity between two states."""
        e1 = self.encode(state1)
        e2 = self.encode(state2)

        # Cosine similarity
        dot = sum(a * b for a, b in zip(e1, e2))
        norm1 = math.sqrt(sum(a**2 for a in e1))
        norm2 = math.sqrt(sum(b**2 for b in e2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (norm1 * norm2)

    def store(self, name: str, state: Dict[str, float]) -> None:
        """Store a state embedding for later retrieval."""
        self.state_embeddings[name] = self.encode(state)

    def find_similar(
        self, state: Dict[str, float], top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Find similar stored states."""
        query = self.encode(state)

        similarities = []
        for name, stored in self.state_embeddings.items():
            sim = sum(a * b for a, b in zip(query, stored))
            similarities.append((name, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]


class NeuralWorldModel:
    """
    [Phase 108] Complete Neural World Model.

    Combines prediction, imagination, and embedding.
    """

    def __init__(self) -> None:
        self.predictor = PredictiveModel()
        self.imagination = ImaginationEngine(self.predictor)
        self.embedding = WorldEmbedding()
        self.observations: deque[WorldObservation] = deque(maxlen=1000)
        logger.info("[NeuralWorldModel] Complete System Active.")

    def observe(
        self,
        state: Dict[str, float],
        action: Optional[str] = None,
        next_state: Optional[Dict[str, float]] = None,
        reward: float = 0.0,
    ) -> None:
        """Record an observation and learn from it."""
        obs = WorldObservation(
            timestamp=datetime.now(),
            state=state,
            action=action,
            next_state=next_state,
            reward=reward,
        )
        self.observations.append(obs)

        # Train predictor
        if next_state:
            self.predictor.train(obs)

    def predict_next(self, state: Dict[str, float]) -> Dict[str, float]:
        """Predict the next state."""
        return self.predictor.predict(state)

    def imagine_future(
        self, state: Dict[str, float], steps: int = 5
    ) -> List[Dict[str, float]]:
        """Imagine future trajectory."""
        return self.imagination.imagine(state, [], steps)

    def plan(
        self, current: Dict[str, float], goal: Dict[str, float], actions: List[str]
    ) -> Tuple[str, float]:
        """Plan the best action to reach goal."""
        return self.imagination.find_best_action(current, actions, goal)

    def get_state_embedding(self, state: Dict[str, float]) -> List[float]:
        """Get embedding for a state."""
        return self.embedding.encode(state)

    def get_stats(self) -> Dict[str, Any]:
        """Get model statistics."""
        return {
            "observations": len(self.observations),
            "training_count": self.predictor.training_count,
            "prediction_error": self.predictor.get_error(),
            "imaginations": self.imagination.imagination_count,
            "stored_embeddings": len(self.embedding.state_embeddings),
        }


def get_neural_world_model() -> NeuralWorldModel:
    """Get a Neural World Model."""
    return NeuralWorldModel()
