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
from __future__ import annotations

import argparse
import asyncio
import logging

from warm_logic.kernel.ops.control import KernelContext, KernelLoop

logger = logging.getLogger(__name__)


def _default_metrics() -> dict[str, float]:
    return {"epsilon_c": 1.0, "tau_ethics": 0.0}


async def run_kernel_loop(port: int = 4001, tick_interval: float = 1.0) -> None:
    """
    Run the sovereign kernel loop.

    Args:
        port: Retained for CLI compatibility with historical startup flags.
        tick_interval: Seconds between loop ticks.
    """
    if tick_interval <= 0:
        raise ValueError("tick_interval must be > 0")

    ctx = KernelContext()
    loop = KernelLoop(ctx)
    logger.info("WarmLogic kernel loop started on UDP port %s", port)

    try:
        while True:
            loop.tick(_default_metrics())
            await asyncio.sleep(tick_interval)
    except asyncio.CancelledError:
        logger.info("WarmLogic kernel loop cancelled")
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WarmLogic kernel loop runner")
    parser.add_argument("--port", type=int, default=4001, help="UDP port for DHT")
    parser.add_argument(
        "--tick-interval",
        type=float,
        default=1.0,
        help="Tick interval in seconds",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    asyncio.run(run_kernel_loop(port=args.port, tick_interval=args.tick_interval))


if __name__ == "__main__":
    main()
