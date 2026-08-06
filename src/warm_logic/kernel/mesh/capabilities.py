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
from enum import Enum, auto
from typing import Dict


class PeerCapability(Enum):
    """
    Defines specific functional roles within the WarmLogic fleet.
    """

    LLM_REASONING = auto()  # High-power logic (Mac/Cloud)
    SENSOR_STREAM = auto()  # Edge data collection (Milk-V)
    PQC_VALIDATION = auto()  # Cryptographic verification
    VECTOR_STORAGE = auto()  # Large-scale memory
    PERSISTENT_LEDGER = auto()  # Economic/Governance records


class CapabilityRegistry:
    """
    Manages and scores node capabilities.
    """

    @staticmethod
    def get_local_capabilities() -> Dict[str, int]:
        """
        Determines the current node's capability scores via active benchmarking.
        """
        import importlib

        caps = {}

        # ACTIVE BENCHMARK 
        reasoning_score = CapabilityRegistry.benchmark_cpu_performance()
        caps[PeerCapability.LLM_REASONING.name] = reasoning_score

        # 100% score for sensors if on Edge (RISC-V) hardware
        import platform

        if "riscv" in platform.machine().lower():
            caps[PeerCapability.SENSOR_STREAM.name] = 100

        caps[PeerCapability.PERSISTENT_LEDGER.name] = 80

        try:
            rust_loader = importlib.import_module("warm_logic.kernel.rust_loader")
            if getattr(rust_loader, "HAS_RUST_CORE", False):
                caps[PeerCapability.PQC_VALIDATION.name] = 100
        except ImportError:
            pass

        return caps

    @staticmethod
    def benchmark_cpu_performance() -> int:
        """Runs a 100ms compute spike to score reasoning capability."""
        import time

        start = time.time()
        count = 0
        # Target: 1 million iterations for 100 score on high-end hardware
        while time.time() - start < 0.1:
            count += 1

        # Normalize: Mac Studio (M2) gets ~5M in 0.1s -> score 100
        # Milk-V Duo S gets ~50k -> score 1
        score = min(100, int(count / 50000))
        return max(1, score)

    @staticmethod
    def verify_capability_score(claimed_caps: Dict[str, int]) -> bool:
        """
        Remote verification of claimed capabilities.
        In a full implementation, this sends a specific 'Challenge Probe' to the peer.
        """
        # Prototype: We assume any score > 100 is a lie/overflow
        for score in claimed_caps.values():
            if score > 100 or score < 0:
                return False
        return True

    @staticmethod
    def is_root_authority(caps: Dict[str, int]) -> bool:
        """Heuristic check to see if a node qualifies as a root authority."""
        return caps.get(PeerCapability.LLM_REASONING.name, 0) >= 80
