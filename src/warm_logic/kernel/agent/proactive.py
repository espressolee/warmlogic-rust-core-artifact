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
Proactive Agency Engine
The "Godhead" module for Level 5 Autonomy.
Binds Goal Discovery to Execution via Consensus.
"""

import asyncio
import logging
import time
from typing import Any

from warm_logic.kernel.intelligence.discovery_engine import (
    StrategicDiscoveryEngine,
    StrategicTask,
)

logger = logging.getLogger("ProactiveAgency")


class ProactiveAgencyEngine:
    """
    Handles autonomous goal setting and system evolution.
    """

    def __init__(self, kernel_api: Any, autonomy_level: int = 5) -> None:
        self.kernel = kernel_api
        self.autonomy_level = autonomy_level
        self.discovery_engine = StrategicDiscoveryEngine(workspace=".")
        self.running = False
        self._last_tick: float = 0.0
        self._tick_interval: float = 3600.0  # 1 hour default for high-level goals

    async def start(self) -> None:
        """Starts the Evolutionary Heartbeat."""
        if self.autonomy_level < 5:
            logger.warning(
                f"Autonomy Level {self.autonomy_level} is too low for Proactive Agency."
            )
            return

        self.running = True
        logger.info("Proactive Agency Engine Online (Level 5).")
        asyncio.create_task(self._evolutionary_heartbeat())

    async def stop(self) -> None:
        self.running = False
        logger.info("Proactive Agency Engine Shutdown.")

    async def _evolutionary_heartbeat(self) -> None:
        """
        The kernel-level loop for self-improvement.
        """
        while self.running:
            try:
                now = time.time()
                if now - self._last_tick >= self._tick_interval:
                    logger.info("Evolutionary Tick: Discovering new goals...")
                    await self.evolve()
                    self._last_tick = now
            except Exception as e:
                logger.error(f"Error in Proactive Agency Heartbeat: {e}")

            await asyncio.sleep(60)  # check interval every minute

    async def evolve(self) -> None:
        """
        Scans state, identifies goals, and proposes them to the mesh.
        """
        # 1. Discover Strategic Goals
        goals = self.discovery_engine.discover_strategic_goals()
        if not goals:
            logger.info("No new strategic goals identified.")
            return

        for goal in goals:
            logger.info(f"New Goal Discovered: {goal.title}")
            # 2. Submit to Consensus (Phase 77.3)
            # In a real mesh, this would call self.kernel.bft.propose(goal)
            await self._propose_goal_to_mesh(goal)

    async def _propose_goal_to_mesh(self, goal: StrategicTask) -> None:
        """
        Submits a goal to the consensus engine.
        Level 5 agents must wait for quorum before executing self-set goals.
        """
        logger.info(f" Proposing goal '{goal.title}' for mesh ratification...")
        # Simulated BFT Quorum
        await asyncio.sleep(1)
        logger.info(f"Goal '{goal.title}' RATIFIED by mesh.")

        # 3. Execution (Hand off to Task Engine)
        # self.kernel.task_engine.execute(goal)
        logger.info(f"Executing autonomous task: {goal.title}")

    def set_tick_interval(self, seconds: int) -> None:
        self._tick_interval = seconds
        logger.info(f"Evolutionary Tick interval set to {seconds}s.")
