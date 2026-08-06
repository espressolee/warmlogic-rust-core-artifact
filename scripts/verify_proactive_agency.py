import asyncio
import logging
import os
import sys
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

from warm_logic.kernel.agent.proactive import ProactiveAgencyEngine
from warm_logic.kernel.intelligence.discovery_engine import StrategicTask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProactiveTest")


async def test_proactive_agency():
    logger.info("Starting Proactive Agency (Level 5) Test...")

    # 1. Mock Kernel & Discovery Engine
    kernel_api = MagicMock()
    pae = ProactiveAgencyEngine(kernel_api, autonomy_level=5)

    # Mock StrategicDiscoveryEngine to return a set goal
    mock_goal = StrategicTask(
        id="STRAT-MOCK-001",
        title="Enhance Quantum Resistance",
        description="Upgrade mesh to use CRYSTALS-Dilithium for all node identities.",
        rationale="Current RSA/ECC signatures are vulnerable to future Shor-class threats.",
        risk_assessment="Low compatibility risk with nodes.",
        priority="HIGH",
    )

    pae.discovery_engine.discover_strategic_goals = MagicMock(return_value=[mock_goal])

    # 2. Set short tick interval for test
    pae.set_tick_interval(1)

    # 3. Trigger manual evolution
    logger.info("Heartbeat Triggered: Proactive Agency scanning for system gaps...")
    await pae.evolve()

    logger.info("Proactive Agency Test Complete.")


if __name__ == "__main__":
    asyncio.run(test_proactive_agency())
