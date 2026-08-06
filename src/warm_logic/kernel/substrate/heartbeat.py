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
import ipaddress
import logging
import os
import re
import subprocess
import time

from warm_logic.kernel.substrate.attestation import CrossNodeAttestation

# Sovereign Heartbeat: root authority-Tower Synchronization
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SovereignHeartbeat")


def _validate_ip_address(ip: str) -> bool:
    """
    SEC-005: Validate IP address to prevent command injection.

    Only allows valid IPv4/IPv6 addresses, no shell metacharacters.
    """
    if not ip:
        return False

    # Check for shell metacharacters
    if re.search(r"[;&|`$(){}\\'\"\n\r]", ip):
        logger.error(f"SEC-005: Shell metacharacters detected in IP: {ip}")
        return False

    try:
        # Validate as proper IP address
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        logger.error(f"SEC-005: Invalid IP address format: {ip}")
        return False


_raw_tailscale_target = os.getenv("CITADEL_IP", "100.116.80.23")
TAILSCALE_TARGET = (
    _raw_tailscale_target
    if _validate_ip_address(_raw_tailscale_target)
    else "127.0.0.1"
)


def check_tailscale() -> bool:
    """Checks if the Tailscale P2P mesh is active."""
    try:
        res = subprocess.run(
            ["ping", "-c", "1", "-t", "2", TAILSCALE_TARGET], capture_output=True
        )
        return res.returncode == 0
    except Exception:
        return False


class HeartbeatMonitor:
    def __init__(self, target_ip: str = TAILSCALE_TARGET):
        # SEC-005: Validate target IP to prevent injection
        if not _validate_ip_address(target_ip):
            logger.warning(f"SEC-005: Invalid target IP '{target_ip}', using localhost")
            target_ip = "127.0.0.1"

        self.target_ip = target_ip
        self.running = False
        self.attestor = CrossNodeAttestation(target_ip=self.target_ip)

    def is_alive(self) -> bool:
        """Checks if the mesh is reachable."""
        return check_tailscale()

    def start(self) -> None:
        """Starts the pulse loop in a thread (mockable)."""
        logger.info("[Heartbeat] Starting (Threaded Mode)...")
        # In a real daemon, we'd spawn a thread here.
        # For now, we mainly expose the check methods.
        self.running = True

    def check_tailscale_latency(self) -> float:
        """
        [Phase 66] Real-time Latency Check (Ping).
        Returns RTT in milliseconds. Returns -1.0 if unreachable.
        """
        try:
            # Ping 1 packet, wait max 1s
            start = time.time()
            res = subprocess.run(
                ["ping", "-c", "1", "-t", "1", self.target_ip],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                # Parse output for time=X.Y ms (macOS/Linux format varies, simpler to measure wall clock here for app-level RTT)
                # Note: subprocess overhead makes this inaccurate for microsecond precision but fine for >10ms checks
                # Better: Parse the output "time=12.3 ms"
                import re

                match = re.search(r"time=([\d\.]+)", res.stdout)
                if match:
                    return float(match.group(1))
                return (time.time() - start) * 1000
            return -1.0
        except Exception:
            return -1.0

    def pulse(self) -> None:
        """Main heartbeat loop (single iteration)."""
        rtt = self.check_tailscale_latency()

        if rtt > 0:
            attested = self.attestor.challenge_tower()

            # Latency Warning
            latency_status = ""
            if rtt > 300:
                latency_status = f" | ⚠️ HIGH LATENCY: {rtt:.1f}ms"
            else:
                latency_status = f" | ⚡ RTT: {rtt:.1f}ms"

            if attested:
                logger.info(
                    f"🟢 [Mesh] Control Tower ({self.target_ip}) is ATTESTED.{latency_status}"
                )
            else:
                logger.error("[Mesh] Control Tower FAILED attestation.")
        else:
            logger.warning(f"[Mesh] Control Tower ({self.target_ip}) is OFFLINE.")


def pulse() -> None:
    """Legacy entry point."""
    monitor = HeartbeatMonitor()
    while True:
        monitor.pulse()
        time.sleep(60)


if __name__ == "__main__":
    pulse()
