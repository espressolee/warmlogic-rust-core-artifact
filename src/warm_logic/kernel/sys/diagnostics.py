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
import logging
import os
import platform
import time
from typing import Any, Dict

import psutil

logger = logging.getLogger("SiliconHealth")


class SiliconHealthMonitor:
    """
    [Phase 86.2] Silicon Health Monitor.
    Tracks physical hardware metrics to ensure the kernel is operating within safety bounds.
    """

    def __init__(self):
        self.start_time = time.time()

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """
        Gathers real-time hardware telemetry.
        """
        try:
            uptime = int(time.time() - psutil.boot_time())
        except Exception:
            uptime = 0

        try:
            cpu_usage_pct = psutil.cpu_percent(interval=None)
        except Exception:
            cpu_usage_pct = 0.0

        try:
            vm = psutil.virtual_memory()
            memory_usage_pct = vm.percent
            memory_available_mb = vm.available // (1024 * 1024)
        except Exception:
            memory_usage_pct = 0.0
            memory_available_mb = 0

        try:
            load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
        except Exception:
            load_avg = (0, 0, 0)

        stats = {
            "uptime": uptime,
            "cpu_usage_pct": cpu_usage_pct,
            "memory_usage_pct": memory_usage_pct,
            "memory_available_mb": memory_available_mb,
            "load_avg": load_avg,
            "timestamp": time.time(),
        }

        # Attempt to get thermal data (Linux specific)
        try:
            if platform.system() == "Linux":
                # Typical path for thermal zones on arm/riscv linux
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    stats["thermal_c"] = int(f.read().strip()) / 1000.0
        except Exception:
            pass

        return stats

    def verify_safety_bounds(self) -> bool:
        """
        Checks if the node should enter 'Safe Mode' due to hardware stress.
        """
        stats = self.get_stats()

        # 1. Critical Memory Pressure (Edge nodes: 512MB total)
        if stats["memory_available_mb"] < 50:
            logger.warning("[Health] CRITICAL MEMORY PRESSURE detected.")
            return False

        # 2. Thermal Throttling Prevention
        if stats.get("thermal_c", 0) > 85.0:
            logger.warning("[Health] THERMAL LIMIT EXCEEDED.")
            return False

        return True
