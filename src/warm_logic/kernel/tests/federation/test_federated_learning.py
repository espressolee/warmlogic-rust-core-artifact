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
Federated Learning Tests

Tests for the privacy-preserving distributed ML pipeline.
"""

import unittest

import numpy as np

from warm_logic.kernel.federation.federated_learning import (
    AggregationStrategy,
    DifferentialPrivacyConfig,
    FederatedLearningCoordinator,
    FederatedLearningParticipant,
    FLRound,
    FLState,
    ModelUpdate,
    SecureAggregator,
)


class TestModelUpdate(unittest.TestCase):
    """Test ModelUpdate dataclass."""

    def test_model_update_creation(self):
        weights = {"layer1": np.array([1.0, 2.0, 3.0])}
        update = ModelUpdate(
            node_id="test-node",
            round_id=1,
            weights=weights,
            num_samples=100,
            loss=0.5,
        )
        self.assertEqual(update.node_id, "test-node")
        self.assertEqual(update.round_id, 1)
        self.assertEqual(update.num_samples, 100)
        self.assertEqual(update.loss, 0.5)

    def test_model_update_hash(self):
        weights = {"layer1": np.array([1.0, 2.0, 3.0])}
        update = ModelUpdate(
            node_id="test-node",
            round_id=1,
            weights=weights,
            num_samples=100,
            loss=0.5,
        )
        hash1 = update.compute_hash()
        self.assertEqual(len(hash1), 64)  # SHA256 hex

        # Same weights should produce same hash
        update2 = ModelUpdate(
            node_id="other-node",
            round_id=2,
            weights=weights,
            num_samples=200,
            loss=0.3,
        )
        hash2 = update2.compute_hash()
        self.assertEqual(hash1, hash2)

        # Different weights should produce different hash
        update3 = ModelUpdate(
            node_id="test-node",
            round_id=1,
            weights={"layer1": np.array([1.0, 2.0, 4.0])},
            num_samples=100,
            loss=0.5,
        )
        hash3 = update3.compute_hash()
        self.assertNotEqual(hash1, hash3)


class TestFLRound(unittest.TestCase):
    """Test FLRound dataclass."""

    def test_round_creation(self):
        fl_round = FLRound(
            round_id=1,
            global_model_hash="abc123",
            participants=["node-1", "node-2", "node-3"],
            min_participants=2,
        )
        self.assertEqual(fl_round.round_id, 1)
        self.assertEqual(fl_round.state, FLState.IDLE)
        self.assertFalse(fl_round.has_quorum())

    def test_round_quorum(self):
        fl_round = FLRound(
            round_id=1,
            global_model_hash="abc123",
            participants=["node-1", "node-2", "node-3"],
            min_participants=2,
        )

        # Add one update
        fl_round.updates["node-1"] = ModelUpdate(
            node_id="node-1",
            round_id=1,
            weights={},
            num_samples=100,
            loss=0.5,
        )
        self.assertFalse(fl_round.has_quorum())

        # Add second update
        fl_round.updates["node-2"] = ModelUpdate(
            node_id="node-2",
            round_id=1,
            weights={},
            num_samples=100,
            loss=0.4,
        )
        self.assertTrue(fl_round.has_quorum())


class TestSecureAggregator(unittest.TestCase):
    """Test SecureAggregator class."""

    def test_federated_averaging(self):
        aggregator = SecureAggregator(
            strategy=AggregationStrategy.FEDAVG,
            dp_config=DifferentialPrivacyConfig(epsilon=float("inf")),  # No DP
        )

        # Create updates with known weights
        update1 = ModelUpdate(
            node_id="node-1",
            round_id=1,
            weights={"layer1": np.array([1.0, 2.0, 3.0])},
            num_samples=100,
            loss=0.5,
        )
        update2 = ModelUpdate(
            node_id="node-2",
            round_id=1,
            weights={"layer1": np.array([3.0, 4.0, 5.0])},
            num_samples=100,
            loss=0.4,
        )

        # Aggregate (equal weighting since same num_samples)
        aggregated = aggregator.aggregate([update1, update2], total_samples=200)

        expected = np.array([2.0, 3.0, 4.0])  # Average
        np.testing.assert_array_almost_equal(aggregated["layer1"], expected)

    def test_federated_averaging_weighted(self):
        aggregator = SecureAggregator(
            strategy=AggregationStrategy.FEDAVG,
            dp_config=DifferentialPrivacyConfig(epsilon=float("inf")),
        )

        # Node 1 has more samples, should have more weight
        update1 = ModelUpdate(
            node_id="node-1",
            round_id=1,
            weights={"layer1": np.array([1.0])},
            num_samples=300,  # 75%
            loss=0.5,
        )
        update2 = ModelUpdate(
            node_id="node-2",
            round_id=1,
            weights={"layer1": np.array([5.0])},
            num_samples=100,  # 25%
            loss=0.4,
        )

        aggregated = aggregator.aggregate([update1, update2], total_samples=400)

        # Expected: 0.75 * 1.0 + 0.25 * 5.0 = 2.0
        expected = np.array([2.0])
        np.testing.assert_array_almost_equal(aggregated["layer1"], expected)

    def test_coordinate_median(self):
        aggregator = SecureAggregator(strategy=AggregationStrategy.MEDIAN)

        updates = [
            ModelUpdate(
                node_id=f"node-{i}",
                round_id=1,
                weights={"layer1": np.array([float(i)])},
                num_samples=100,
                loss=0.5,
            )
            for i in [1, 2, 3, 4, 100]  # 100 is outlier
        ]

        aggregated = aggregator.aggregate(updates, total_samples=500)

        # Median should be 3.0 (robust to outlier)
        expected = np.array([3.0])
        np.testing.assert_array_almost_equal(aggregated["layer1"], expected)

    def test_gradient_clipping(self):
        dp_config = DifferentialPrivacyConfig(clip_norm=1.0)
        aggregator = SecureAggregator(dp_config=dp_config)

        # Large gradient
        weights = {"layer1": np.array([10.0, 10.0])}  # Norm = sqrt(200) ≈ 14.14

        clipped = aggregator.clip_gradients(weights)

        # After clipping, norm should be <= 1.0
        clipped_norm = np.sqrt(np.sum(clipped["layer1"] ** 2))
        self.assertLessEqual(clipped_norm, 1.0 + 1e-6)


class TestFederatedLearningCoordinator(unittest.TestCase):
    """Test FederatedLearningCoordinator class."""

    def test_coordinator_initialization(self):
        coordinator = FederatedLearningCoordinator(node_id="coordinator")
        self.assertEqual(coordinator.node_id, "coordinator")
        self.assertIsNone(coordinator.current_round)
        self.assertEqual(len(coordinator.completed_rounds), 0)

    def test_initialize_global_model(self):
        coordinator = FederatedLearningCoordinator(node_id="coordinator")
        model = {
            "layer1": np.array([1.0, 2.0]),
            "layer2": np.array([3.0, 4.0, 5.0]),
        }
        coordinator.initialize_global_model(model)

        retrieved = coordinator.get_global_model()
        self.assertEqual(len(retrieved), 2)
        np.testing.assert_array_equal(retrieved["layer1"], model["layer1"])

    def test_start_round(self):
        coordinator = FederatedLearningCoordinator(
            node_id="coordinator", min_participants=2
        )
        coordinator.initialize_global_model({"layer1": np.array([1.0])})

        fl_round = coordinator.start_round(["node-1", "node-2", "node-3"])

        self.assertEqual(fl_round.round_id, 1)
        self.assertEqual(fl_round.state, FLState.TRAINING)
        self.assertEqual(len(fl_round.participants), 3)

    def test_submit_update_and_aggregate(self):
        coordinator = FederatedLearningCoordinator(
            node_id="coordinator", min_participants=2
        )
        coordinator.initialize_global_model({"layer1": np.array([0.0])})

        # Use no-DP aggregator for deterministic testing
        coordinator.aggregator = SecureAggregator(
            dp_config=DifferentialPrivacyConfig(epsilon=float("inf"))
        )

        coordinator.start_round(["node-1", "node-2"])

        # Submit updates
        update1 = ModelUpdate(
            node_id="node-1",
            round_id=1,
            weights={"layer1": np.array([2.0])},
            num_samples=100,
            loss=0.5,
        )
        update2 = ModelUpdate(
            node_id="node-2",
            round_id=1,
            weights={"layer1": np.array([4.0])},
            num_samples=100,
            loss=0.3,
        )

        result1 = coordinator.submit_update(update1)
        self.assertTrue(result1)
        self.assertEqual(coordinator.current_round.state, FLState.TRAINING)

        result2 = coordinator.submit_update(update2)
        self.assertTrue(result2)

        # Should have aggregated and completed
        self.assertEqual(coordinator.current_round.state, FLState.COMPLETED)

        # Check aggregated model (should be average: 3.0)
        model = coordinator.get_global_model()
        np.testing.assert_array_almost_equal(model["layer1"], np.array([3.0]))

    def test_reject_invalid_update(self):
        coordinator = FederatedLearningCoordinator(node_id="coordinator")
        coordinator.initialize_global_model({"layer1": np.array([0.0])})
        coordinator.start_round(["node-1", "node-2"])

        # Wrong round ID
        update = ModelUpdate(
            node_id="node-1",
            round_id=999,
            weights={"layer1": np.array([2.0])},
            num_samples=100,
            loss=0.5,
        )
        result = coordinator.submit_update(update)
        self.assertFalse(result)

        # Non-participant
        update2 = ModelUpdate(
            node_id="node-999",
            round_id=1,
            weights={"layer1": np.array([2.0])},
            num_samples=100,
            loss=0.5,
        )
        result2 = coordinator.submit_update(update2)
        self.assertFalse(result2)

    def test_round_completion_callback(self):
        completed_rounds = []

        def on_complete(fl_round):
            completed_rounds.append(fl_round.round_id)

        coordinator = FederatedLearningCoordinator(
            node_id="coordinator", min_participants=1
        )
        coordinator.on_round_complete(on_complete)
        coordinator.aggregator = SecureAggregator(
            dp_config=DifferentialPrivacyConfig(epsilon=float("inf"))
        )

        coordinator.initialize_global_model({"layer1": np.array([0.0])})
        coordinator.start_round(["node-1"])

        update = ModelUpdate(
            node_id="node-1",
            round_id=1,
            weights={"layer1": np.array([1.0])},
            num_samples=100,
            loss=0.5,
        )
        coordinator.submit_update(update)

        self.assertEqual(completed_rounds, [1])

    def test_training_history(self):
        coordinator = FederatedLearningCoordinator(
            node_id="coordinator", min_participants=1
        )
        coordinator.aggregator = SecureAggregator(
            dp_config=DifferentialPrivacyConfig(epsilon=float("inf"))
        )
        coordinator.initialize_global_model({"layer1": np.array([0.0])})

        # Complete two rounds
        for round_num in range(1, 3):
            coordinator.start_round(["node-1"])
            update = ModelUpdate(
                node_id="node-1",
                round_id=round_num,
                weights={"layer1": np.array([float(round_num)])},
                num_samples=100,
                loss=0.5 / round_num,
            )
            coordinator.submit_update(update)

        history = coordinator.get_training_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["round_id"], 1)
        self.assertEqual(history[1]["round_id"], 2)


class TestFederatedLearningParticipant(unittest.TestCase):
    """Test FederatedLearningParticipant class."""

    def test_participant_initialization(self):
        participant = FederatedLearningParticipant(node_id="participant-1")
        self.assertEqual(participant.node_id, "participant-1")

    def test_local_training(self):
        participant = FederatedLearningParticipant(node_id="participant-1")

        global_weights = {"layer1": np.array([1.0, 2.0, 3.0])}
        local_data = None  # Dummy

        update = participant.train_local(
            global_weights=global_weights,
            local_data=local_data,
            round_id=1,
            epochs=1,
        )

        self.assertEqual(update.node_id, "participant-1")
        self.assertEqual(update.round_id, 1)
        self.assertIn("layer1", update.weights)
        self.assertGreater(update.loss, 0)
        self.assertEqual(update.num_samples, 100)  # Default dummy

    def test_local_training_with_dp(self):
        dp_config = DifferentialPrivacyConfig(clip_norm=0.5)
        participant = FederatedLearningParticipant(
            node_id="participant-1", dp_config=dp_config
        )

        # Large weights should be clipped
        global_weights = {"layer1": np.array([100.0, 100.0])}
        local_data = None

        update = participant.train_local(
            global_weights=global_weights,
            local_data=local_data,
            round_id=1,
        )

        # Weights should be clipped
        clipped_norm = np.sqrt(np.sum(update.weights["layer1"] ** 2))
        self.assertLessEqual(clipped_norm, 0.5 + 1e-6)

    def test_custom_training_function(self):
        def custom_train(global_weights, local_data, epochs):
            # Double all weights
            trained = {k: v * 2 for k, v in global_weights.items()}
            return trained, 0.1, 500

        participant = FederatedLearningParticipant(
            node_id="participant-1", local_train_fn=custom_train
        )

        global_weights = {"layer1": np.array([1.0, 2.0])}
        update = participant.train_local(global_weights, None, round_id=1)

        np.testing.assert_array_equal(update.weights["layer1"], np.array([2.0, 4.0]))
        self.assertEqual(update.loss, 0.1)
        self.assertEqual(update.num_samples, 500)


class TestEndToEndFederatedLearning(unittest.TestCase):
    """End-to-end federated learning tests."""

    def test_full_training_cycle(self):
        """Test complete FL cycle with coordinator and participants."""
        # Setup coordinator
        coordinator = FederatedLearningCoordinator(
            node_id="coordinator", min_participants=2
        )
        coordinator.aggregator = SecureAggregator(
            dp_config=DifferentialPrivacyConfig(epsilon=float("inf"))
        )

        # Initialize global model
        initial_model = {
            "weights": np.array([0.5, 0.5, 0.5]),
            "bias": np.array([0.1]),
        }
        coordinator.initialize_global_model(initial_model)

        # Setup participants
        participant1 = FederatedLearningParticipant(node_id="node-1")
        participant2 = FederatedLearningParticipant(node_id="node-2")

        # Run 3 rounds
        for round_num in range(1, 4):
            # Start round
            fl_round = coordinator.start_round(["node-1", "node-2"])

            # Get global model
            global_model = coordinator.get_global_model()

            # Participants train locally
            update1 = participant1.train_local(global_model, None, round_num)
            update2 = participant2.train_local(global_model, None, round_num)

            # Submit updates
            coordinator.submit_update(update1)
            coordinator.submit_update(update2)

            # Verify round completed
            self.assertEqual(coordinator.current_round.state, FLState.COMPLETED)

        # Verify training history
        history = coordinator.get_training_history()
        self.assertEqual(len(history), 3)

        # Verify model evolved
        final_model = coordinator.get_global_model()
        self.assertIn("weights", final_model)
        self.assertIn("bias", final_model)


if __name__ == "__main__":
    unittest.main()
