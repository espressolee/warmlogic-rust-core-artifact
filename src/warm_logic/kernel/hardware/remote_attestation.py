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
Remote Hardware Attestation Client

Connects to sovereign hardware nodes (Milk-V DuoS, RISC-V) to fetch
hardware attestation reports for silicon-bound identity verification.
"""

import hashlib
import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("RemoteAttestation")


@dataclass
class RemoteAttestationReport:
    """Hardware attestation report from a remote sovereign node."""

    version: str
    era: int
    device: str
    soc: str
    chip_id: str
    mac_address: str
    fingerprint: str
    entropy: str
    timestamp: int
    kernel: str
    arch: str
    memory_mb: int
    uptime_sec: int
    # Computed fields
    node_id: str = ""
    verified: bool = False
    verification_timestamp: float = 0.0

    def __post_init__(self) -> None:
        # Generate deterministic node ID from hardware fingerprint
        self.node_id = f"wl-{self.fingerprint[:16]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "era": self.era,
            "device": self.device,
            "soc": self.soc,
            "chip_id": self.chip_id,
            "mac_address": self.mac_address,
            "fingerprint": self.fingerprint,
            "entropy": self.entropy,
            "timestamp": self.timestamp,
            "kernel": self.kernel,
            "arch": self.arch,
            "memory_mb": self.memory_mb,
            "uptime_sec": self.uptime_sec,
            "node_id": self.node_id,
            "verified": self.verified,
            "verification_timestamp": self.verification_timestamp,
        }


@dataclass
class SovereignNode:
    """Configuration for a sovereign hardware node."""

    host: str
    port: int = 22
    user: str = "root"
    name: str = ""
    attestation_cmd: str = "/usr/local/bin/wl-attestation"

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"{self.user}@{self.host}"


class RemoteAttestationClient:
    """
    Client for fetching hardware attestation from sovereign nodes.

    Supports:
    - SSH-based attestation fetching
    - Attestation verification and caching
    - Multi-node federation
    - Fingerprint validation
    """

    def __init__(self, ssh_timeout: int = 15):
        self.ssh_timeout = ssh_timeout
        self._nodes: Dict[str, SovereignNode] = {}
        self._cache: Dict[str, RemoteAttestationReport] = {}
        self._cache_ttl: int = 300  # 5 minutes

    def register_node(self, node: SovereignNode) -> None:
        """Register a sovereign node for attestation."""
        self._nodes[node.host] = node
        logger.info(f"[Attestation] Registered node: {node.name} ({node.host})")

    def unregister_node(self, host: str) -> None:
        """Remove a node from the registry."""
        if host in self._nodes:
            del self._nodes[host]
            if host in self._cache:
                del self._cache[host]

    def get_registered_nodes(self) -> List[SovereignNode]:
        """Get all registered nodes."""
        return list(self._nodes.values())

    def _execute_ssh(self, node: SovereignNode, command: str) -> Tuple[bool, str]:
        """Execute command on remote node via SSH."""
        ssh_cmd = [
            "ssh",
            "-o",
            f"ConnectTimeout={self.ssh_timeout}",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "BatchMode=yes",
            f"{node.user}@{node.host}",
            command,
        ]

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=self.ssh_timeout + 5,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "SSH_TIMEOUT"
        except Exception as e:
            return False, str(e)

    def fetch_attestation(
        self, host: str, use_cache: bool = True
    ) -> Optional[RemoteAttestationReport]:
        """
        Fetch attestation report from a sovereign node.

        Args:
            host: Node IP or hostname
            use_cache: Whether to use cached attestation if valid

        Returns:
            RemoteAttestationReport or None on failure
        """
        # Check cache
        if use_cache and host in self._cache:
            cached = self._cache[host]
            age = time.time() - cached.verification_timestamp
            if age < self._cache_ttl:
                logger.debug(
                    f"[Attestation] Using cached report for {host} (age: {age:.0f}s)"
                )
                return cached

        # Get node config
        node = self._nodes.get(host)
        if not node:
            # Auto-register with defaults
            node = SovereignNode(host=host)
            self.register_node(node)

        # Fetch attestation
        logger.info(f"[Attestation] Fetching from {node.name}...")
        success, output = self._execute_ssh(node, node.attestation_cmd)

        if not success:
            logger.error(f"[Attestation] Failed to fetch from {host}: {output}")
            return None

        # Parse JSON response
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(f"[Attestation] Invalid JSON from {host}: {e}")
            return None

        # Create report
        try:
            report = RemoteAttestationReport(
                version=data.get("version", "unknown"),
                era=data.get("era", 0),
                device=data.get("device", "unknown"),
                soc=data.get("soc", "unknown"),
                chip_id=data.get("chip_id", "unknown"),
                mac_address=data.get("mac_address", "unknown"),
                fingerprint=data.get("fingerprint", ""),
                entropy=data.get("entropy", ""),
                timestamp=data.get("timestamp", 0),
                kernel=data.get("kernel", "unknown"),
                arch=data.get("arch", "unknown"),
                memory_mb=data.get("memory_mb", 0),
                uptime_sec=data.get("uptime_sec", 0),
            )
        except Exception as e:
            logger.error(f"[Attestation] Failed to parse report: {e}")
            return None

        # Verify attestation
        report.verified = self._verify_attestation(report)
        report.verification_timestamp = time.time()

        # Cache result
        self._cache[host] = report

        logger.info(
            f"[Attestation] {host}: {report.device} ({report.soc}) "
            f"fingerprint={report.fingerprint[:16]}... verified={report.verified}"
        )

        return report

    def _verify_attestation(self, report: RemoteAttestationReport) -> bool:
        """
        Verify attestation report integrity.

        Checks:
        1. Fingerprint matches chip_id + mac_address hash
        2. Timestamp is recent (within 24 hours)
        3. Required fields are present
        """
        # Check required fields
        if not report.chip_id or report.chip_id == "unknown":
            logger.warning("[Attestation] Missing chip_id")
            return False

        if not report.mac_address or report.mac_address == "unknown":
            logger.warning("[Attestation] Missing mac_address")
            return False

        # Verify fingerprint
        # Note: shell 'echo' adds newline, so we include it in hash computation
        expected_input = f"{report.chip_id}:{report.mac_address}\n"
        expected_fingerprint = hashlib.sha256(expected_input.encode()).hexdigest()

        if report.fingerprint != expected_fingerprint:
            logger.warning(
                f"[Attestation] Fingerprint mismatch: "
                f"expected={expected_fingerprint[:16]}..., "
                f"got={report.fingerprint[:16]}..."
            )
            return False

        # Check timestamp freshness (within 24 hours)
        age = time.time() - report.timestamp
        if age > 86400:  # 24 hours
            logger.warning(f"[Attestation] Stale timestamp: {age:.0f}s old")
            return False

        return True

    def fetch_all(self) -> Dict[str, RemoteAttestationReport]:
        """Fetch attestation from all registered nodes."""
        results = {}
        for host in self._nodes:
            report = self.fetch_attestation(host)
            if report:
                results[host] = report
        return results

    def get_federation_fingerprint(self) -> str:
        """
        Generate a combined fingerprint for all verified nodes.

        This creates a unique identifier for the entire sovereign federation.
        """
        fingerprints = []
        for host in sorted(self._nodes.keys()):
            report = self._cache.get(host)
            if report and report.verified:
                fingerprints.append(report.fingerprint)

        if not fingerprints:
            return ""

        combined = ":".join(fingerprints)
        return hashlib.sha256(combined.encode()).hexdigest()


# Default client instance
_default_client: Optional[RemoteAttestationClient] = None
_default_client_lock = threading.Lock()


def get_attestation_client() -> RemoteAttestationClient:
    """Get the global attestation client instance (thread-safe)."""
    global _default_client
    if _default_client is None:
        with _default_client_lock:
            if _default_client is None:  # Double-checked locking
                _default_client = RemoteAttestationClient()
    return _default_client


def register_milkv_node(host: str = "192.0.2.1") -> SovereignNode:
    """Convenience function to register a Milk-V DuoS node."""
    node = SovereignNode(
        host=host,
        user="root",
        name="milkv-duos",
        attestation_cmd="/usr/local/bin/wl-attestation",
    )
    get_attestation_client().register_node(node)
    return node
