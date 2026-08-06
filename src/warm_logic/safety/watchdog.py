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
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

# Configure Watchdog Logging (Separate from Daemon)
Path("out/logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [WATCHDOG] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("out/logs/watchdog.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Watchdog")


class Watchdog:
    """
    [Phase 69] The Hard Kill Switch.
    Monitors a target PID for resource abuse.
    If thresholds are exceeded, executes a hard kill (SIGKILL).
    """

    def __init__(
        self,
        target_pid: int,
        cpu_limit_percent: float = 90.0,
        mem_limit_mb: float = 2048.0,
        patience_seconds: int = 60,
    ):
        self.target_pid = target_pid
        self.cpu_limit = cpu_limit_percent
        self.mem_limit_bytes = mem_limit_mb * 1024 * 1024
        self.patience_seconds = patience_seconds

        self.violation_start_time: float | None = None
        self.monitor_error_count = 0
        self.max_monitor_errors = 3
        self.process: "psutil.Process | None" = None

        try:
            if psutil is not None:
                self.process = psutil.Process(target_pid)
                process_name = self.process.name()
            else:
                os.kill(target_pid, 0)
                process_name = "unknown (ps fallback)"
            logger.info(
                f"🛡️  [Watchdog] Locked onto Target PID: {target_pid} ({process_name})"
            )
        except ProcessLookupError:
            logger.error(f"[Watchdog] PID {target_pid} not found.")
            sys.exit(1)
        except Exception as e:
            if psutil is not None and "NoSuchProcess" in type(e).__name__:
                logger.error(f"[Watchdog] PID {target_pid} not found.")
                sys.exit(1)
            raise

        if psutil is None:
            logger.warning(
                "⚠️  [Watchdog] psutil not available, using `ps` command fallback metrics."
            )

    def _sample_usage(self) -> tuple[float, float]:
        """Returns `(cpu_percent, memory_bytes)` for the target process."""
        if (
            psutil is not None
            and self.process is not None
            and not getattr(self, "_use_ps_fallback", False)
        ):
            cpu_usage = self.process.cpu_percent(interval=1.0)
            mem_usage = self.process.memory_info().rss
            return cpu_usage, float(mem_usage)

        # Fallback path when psutil is unavailable.
        # macOS/BSD `ps` supports this format and returns RSS in KiB.
        try:
            output = subprocess.check_output(
                ["ps", "-o", "%cpu=,rss=", "-p", str(self.target_pid)],
                text=True,
            ).strip()
        except subprocess.CalledProcessError as exc:
            raise ProcessLookupError from exc

        if not output:
            raise ProcessLookupError

        parts = output.split()
        if len(parts) < 2:
            raise RuntimeError(f"Unexpected `ps` output: {output!r}")

        cpu_usage = float(parts[0])
        rss_kib = float(parts[1])
        mem_usage = rss_kib * 1024.0
        return cpu_usage, mem_usage

    def monitor(self) -> None:
        logger.info("[Watchdog] Monitoring started...")
        logger.info(
            f"   -> Constraints: CPU > {self.cpu_limit}% (for {self.patience_seconds}s) | RAM > {self.mem_limit_bytes / 1024 / 1024:.0f}MB"
        )

        while True:
            try:
                # Check existence
                if (
                    psutil is not None
                    and self.process is not None
                    and not self.process.is_running()
                ):
                    logger.info("[Watchdog] Target process ended gracefully.")
                    break

                # Get metrics
                cpu_usage, mem_usage = self._sample_usage()
                self.monitor_error_count = 0

                # Check Memory (Instant Kill)
                if mem_usage > self.mem_limit_bytes:
                    logger.critical(
                        f"🚨 [Watchdog] MEMORY VIOLATION: {mem_usage / 1024 / 1024:.1f}MB > {self.mem_limit_bytes / 1024 / 1024:.1f}MB"
                    )
                    self.execute_kill("Memory Overflow")
                    break

                # Check CPU (Patience based)
                if cpu_usage > self.cpu_limit:
                    if self.violation_start_time is None:
                        self.violation_start_time = time.time()
                        logger.warning(
                            f"⚠️  [Watchdog] CPU Spike Detected: {cpu_usage:.1f}%"
                        )

                    assert self.violation_start_time is not None  # Set above
                    duration = time.time() - self.violation_start_time
                    if duration > self.patience_seconds:
                        logger.critical(
                            f"🚨 [Watchdog] CPU VIOLATION: > {self.cpu_limit}% for {duration:.1f}s"
                        )
                        self.execute_kill("CPU Hogging")
                        break
                else:
                    # Reset patience if usage drops
                    if self.violation_start_time is not None:
                        logger.info(
                            f"✅ [Watchdog] CPU usage normalized ({cpu_usage:.1f}%). Patience reset."
                        )
                        self.violation_start_time = None

            except ProcessLookupError:
                logger.info("[Watchdog] Target process vanished.")
                break
            except Exception as e:
                self.monitor_error_count += 1
                logger.error(
                    f"⚠️  [Watchdog] Error during monitoring ({self.monitor_error_count}/{self.max_monitor_errors}): {e}"
                )

                # [Paper Fix] If psutil is failing internally (macOS bug), switch to 'ps' fallback immediately
                if "cpu_count_logical" in str(e) or "exception set" in str(e).lower():
                    logger.warning(
                        "🚨 [Watchdog] psutil internal error detected. Switching to `ps` fallback."
                    )
                    # Disable psutil
                    import sys

                    sys.modules["psutil_backup"] = psutil
                    # We can't easily 'import' None, but we can set a flag
                    self._use_ps_fallback = True

                if self.monitor_error_count >= self.max_monitor_errors:
                    logger.critical(
                        "🚨 [Watchdog] Telemetry failure persisted. Executing fail-closed kill."
                    )
                    self.execute_kill("Telemetry Failure")
                    break
                time.sleep(1)

    def execute_kill(self, reason: str) -> None:
        logger.critical(
            f"💀 [Watchdog] EXECUTING HARD KILL on PID {self.target_pid}. Reason: {reason}"
        )
        try:
            os.kill(self.target_pid, signal.SIGKILL)
            logger.info("[Watchdog] Target neutralized.")

            # Send alert (Simulated)
            # In real system: requests.post("https://api.telegram.org/...", data={"text": "EMERGENCY FREEZE"})
        except Exception as e:
            logger.error(f"[Watchdog] Kill failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python watchdog.py <PID> [cpu_limit] [mem_limit_mb] [patience_seconds]"
        )
        sys.exit(1)

    pid = int(sys.argv[1])
    cpu = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
    mem = float(sys.argv[3]) if len(sys.argv) > 3 else 2048.0
    patience = int(sys.argv[4]) if len(sys.argv) > 4 else 60

    dog = Watchdog(
        pid,
        cpu_limit_percent=cpu,
        mem_limit_mb=mem,
        patience_seconds=patience,
    )
    dog.monitor()
