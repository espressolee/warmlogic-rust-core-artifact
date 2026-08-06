import asyncio
import logging
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

from warm_logic.kernel.mesh.plugins import PluginManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PluginTest")


async def test_plugins():
    # Mock kernel API
    kernel_api = {"name": "WarmLogicKernel"}

    plugins_dir = os.path.abspath("plugins")
    pm = PluginManager(kernel_api, plugins_dir)

    logger.info("Starting Plugin Manager Test...")

    # 1. Load HelloPlugin
    success = await pm.load_plugin("HelloPlugin")
    if success:
        logger.info("Load test passed.")
    else:
        logger.error("Load test failed.")
        return

    # 2. List plugins
    active = pm.list_plugins()
    logger.info(f"Active Plugins: {active}")

    # 3. Unload HelloPlugin
    success = await pm.unload_plugin("HelloPlugin")
    if success:
        logger.info("Unload test passed.")
    else:
        logger.error("Unload test failed.")


if __name__ == "__main__":
    asyncio.run(test_plugins())
