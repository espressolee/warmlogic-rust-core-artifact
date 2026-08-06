import logging
import unittest

from warm_logic.kernel.ops.control import KernelContext, KernelLoop, ResonanceOptimizer

# Setup logging to see the optimization messages
logging.basicConfig(level=logging.INFO)


class _DummyLoopEngine:
    """Deterministic loop engine fallback for environments without Rust loop core."""

    def __init__(self):
        self.alpha = 0.5
        self.beta = 0.5

    def update_coefficients(self, alpha: float, beta: float) -> None:
        self.alpha = alpha
        self.beta = beta


class TestAdaptiveLogic(unittest.TestCase):
    def setUp(self):
        self.ctx = KernelContext()
        self.loop = KernelLoop(self.ctx)
        if self.loop.optimizer is None:
            self.loop.optimizer = ResonanceOptimizer(_DummyLoopEngine())

    def test_optimizer_initialization(self):
        """Verifies that optimizer path initializes in both Rust and fallback modes."""
        self.assertIsNotNone(self.loop.optimizer)
        self.assertIsNotNone(self.loop.optimizer.loop_engine)

    def test_logic_adaptation_high_resonance(self):
        """Verifies that high resonance increases stability focus (alpha)."""
        # Initial state should be 0.5/0.5
        self.assertEqual(self.loop.optimizer.alpha, 0.5)
        self.assertEqual(self.loop.optimizer.beta, 0.5)

        # Simulate 3 ticks of high resonance
        metrics = {"epsilon_c": 0.95, "tau_ethics": 0.1}
        for _ in range(3):
            self.loop.tick(metrics)

        # Alpha should have increased
        self.assertGreater(self.loop.optimizer.alpha, 0.5)
        self.assertLess(self.loop.optimizer.beta, 0.5)

        # Verify Rust coefficients match
        if hasattr(self.loop.optimizer.loop_engine, "alpha"):
            self.assertEqual(
                self.loop.optimizer.loop_engine.alpha, self.loop.optimizer.alpha
            )

    def test_logic_adaptation_ethical_pressure(self):
        """Verifies that high ethics focus (beta) increases under pressure."""
        # Reset to baseline
        self.loop.optimizer.alpha = 0.5
        self.loop.optimizer.beta = 0.5

        # Simulate ethical pressure
        metrics = {"epsilon_c": 0.5, "tau_ethics": 0.8}
        self.loop.tick(metrics)

        # Beta should increase
        self.assertGreater(self.loop.optimizer.beta, 0.5)
        self.assertLess(self.loop.optimizer.alpha, 0.5)

    def test_logic_safety_reset(self):
        """Verifies that low resonance resets coefficients to balanced safety."""
        # Set to extreme performance mode
        self.loop.optimizer.alpha = 0.9
        self.loop.optimizer.beta = 0.1

        # Simulate instability
        metrics = {"epsilon_c": 0.2, "tau_ethics": 0.1}
        self.loop.tick(metrics)

        # Should reset to 0.5/0.5
        self.assertEqual(self.loop.optimizer.alpha, 0.5)
        self.assertEqual(self.loop.optimizer.beta, 0.5)


if __name__ == "__main__":
    unittest.main()
