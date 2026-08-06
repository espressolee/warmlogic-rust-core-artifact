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
Entropy Source for Deterministic Simulation.

Enforces Axiom 04 (Execution Determinism) by providing a centralized,
seeded Random Number Generator (RNG) for all physical models.

Global `random` and `numpy.random` usage is strictly forbidden
in the Reality Engine.
"""

import hashlib
import random
from typing import Union


class WarmLogicRNG:
    """
    Deterministic Random Number Generator wrapper.

    Wraps python's random.Random to ensure isolated state management.
    Supports hierarchical seeding via `derived_rng`.
    """

    def __init__(self, seed: Union[int, str, bytes]):
        """
        Initialize RNG with a seed.

        Args:
            seed: Initial seed (int, str, or bytes).
        """
        self._seed = self._normalize_seed(seed)
        self._rng = random.Random(self._seed)

    def _normalize_seed(self, seed: Union[int, str, bytes]) -> int:
        """Convert any seed type to a stable integer."""
        if isinstance(seed, int):
            return seed

        # Hash string/bytes to get a stable integer
        if isinstance(seed, str):
            data = seed.encode("utf-8")
        else:
            data = seed

        digest = hashlib.sha256(data).digest()
        return int.from_bytes(digest, byteorder="big")

    def derived_rng(self, context: str) -> "WarmLogicRNG":
        """
        Create a new RNG branch derived from the current state and context.

        Guarantees that `parent.derived_rng("child")` always produces
        the same sequence if `parent` is in the same state.

        Args:
            context: String identifier for the new branch (e.g. "IMU_Noise").
        """
        # Mix current state with context to form new seed
        # robustly: get a random int from current stream, mix with context hash
        base_val = self._rng.getrandbits(256)
        context_hash = int.from_bytes(
            hashlib.sha256(context.encode("utf-8")).digest(), byteorder="big"
        )
        new_seed = base_val ^ context_hash
        return WarmLogicRNG(new_seed)

    # --- Proxy Methods (Add more as needed) ---

    def random(self) -> float:
        """Return float in [0.0, 1.0)."""
        return self._rng.random()

    def uniform(self, a: float, b: float) -> float:
        """Return random float in [a, b]."""
        return self._rng.uniform(a, b)

    def gauss(self, mu: float, sigma: float) -> float:
        """Gaussian distribution."""
        return self._rng.gauss(mu, sigma)

    def randint(self, a: int, b: int) -> int:
        """Return random integer in [a, b]."""
        return self._rng.randint(a, b)

    def choice(self, seq):
        """Choose a random element from a non-empty sequence."""
        return self._rng.choice(seq)
