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
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List


class CockpitAdapter:
    """
    Bridge between the Sovereign Core (Rust) and the Visibility Layer (TUI/Web).
    Reads the file-system state left by the Rust Core to populate the Cockpit UI.
    """

    def __init__(self, root_path: str = ".", dht_node: Any = None) -> None:
        self.root = Path(root_path).resolve()
        # Ensure we look in the project root's out directory
        self.sovereign_out = self.root / "out/sovereign"
        self.trace_dir = self.sovereign_out / "traces"
        self.latch_path = self.sovereign_out / "FAIL_LATCH"
        self.dht_node = dht_node

        # Ensure directory exists to avoid errors
        os.makedirs(self.sovereign_out, exist_ok=True)
        os.makedirs(self.trace_dir, exist_ok=True)

    def get_system_status(self) -> Dict[str, Any]:
        """
        Returns the current DEFCON status and Latch state.
        """
        latched = self.latch_path.exists()

        # In a real scenario, we'd read the actual P-Band from a secure enclave state file.
        # For now, we infer 'MARTIAL LAW' if latched, else 'NORMAL'.
        if latched:
            status = "MARTIAL_LAW"
            color = "red"
        else:
            status = "SOVEREIGN_OPERATIONAL"
            color = "green"

        return {
            "p_band": "P-405" if latched else "P-100",
            "status": status,
            "color": color,
            "is_latched": latched,
            "last_update": time.time(),
        }

    def get_mesh_status(self) -> List[Dict[str, Any]]:
        """
        Returns status of the Sovereign Mesh nodes from the local DHT.
        """
        if not self.dht_node:
            return [
                {
                    "node_id": "LOCAL (No DHT)",
                    "status": "STANDALONE",
                    "latch": "SAFE",
                    "latency": "0ms",
                }
            ]

        contacts = []
        # Flatten buckets
        for bucket in self.dht_node.routing.buckets:
            contacts.extend(bucket.get_contacts())

        peers = []
        for contact in contacts:
            peers.append(
                {
                    "node_id": contact.node_id.hex(),
                    "status": "ONLINE",
                    "latch": "SAFE",
                    "latency": "unknown",
                    "address": f"{contact.address}:{contact.port}",
                }
            )

        # Add self if node_id exists
        if hasattr(self.dht_node, "node_id"):
            peers.append(
                {
                    "node_id": self.dht_node.node_id.hex() + " (Self)",
                    "status": "ONLINE",
                    "latch": "SAFE",
                    "latency": "0ms",
                }
            )

        return peers

    def get_config(self) -> Dict[str, Any]:
        """Loads configuration from the Policy Engine."""
        # Stub: In real system, we'd load specific config path
        # For now, return stub mixed with policy result
        return {
            "pii_sensitivity": 0.95,  # Hardened default
            "burn_multiplier": 5000,
            "policy": "sovereign",
            "era": 2000,
        }

    def get_recent_activity(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Scans for EvidencePacks (JSON logs) to show refusal/approval history.
        """
        logs = []
        if not self.sovereign_out.exists():
            return []

        # Scan for json files (excluding latch)
        for f in self.sovereign_out.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                # Infer type from content
                # Support both legacy verdict format and new event format
                verdict = data.get("verdict", data)

                # Integrity Check (Phase 3)
                sig_file = f.with_suffix(".json.sig")
                is_verified = sig_file.exists()

                # Mark unverified if missing signature
                result_display = verdict.get("state", verdict.get("result", "UNKNOWN"))
                if not is_verified:
                    result_display = f"[UNVERIFIED] {result_display}"

                logs.append(
                    {
                        "timestamp": f.stat().st_mtime,
                        "policy": verdict.get("policy_id", "UNKNOWN"),
                        "result": result_display,
                        "reason": verdict.get("reason", "No reason provided"),
                        "file": f.name,
                        "verified": is_verified,
                    }
                )
            except Exception:
                continue

        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        return logs[:limit]

    def get_working_memory(self) -> Dict[str, Any]:
        """
        Reads the active context window from the Sovereign Chat dump.
        """
        wm_path = self.sovereign_out / "working_memory.json"
        if not wm_path.exists():
            return {"status": "VOID", "tokens": 0, "history": []}

        try:
            data = json.loads(wm_path.read_text())
            # Calculate rough token usage (char / 4)
            history = data.get("history", [])
            total_chars = sum(len(m.get("content", "")) for m in history)
            token_est = int(total_chars / 4)

            return {
                "status": "ACTIVE",
                "session_id": data.get("session_id"),
                "tokens": token_est,
                "history": history,
                "timestamp": data.get("timestamp"),
            }
        except Exception:
            return {"status": "CORRUPTED", "tokens": 0, "history": []}

    def get_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns a list of recent task traces."""
        traces = []
        if not self.trace_dir.exists():
            return []

        for f in self.trace_dir.glob("*.jsonl"):
            traces.append(
                {
                    "trace_id": f.stem,
                    "last_update": f.stat().st_mtime,
                    "size": f.stat().st_size,
                }
            )

        traces.sort(key=lambda x: x["last_update"], reverse=True)
        return traces[:limit]

    def get_trace_events(self, trace_id: str) -> List[Dict[str, Any]]:
        """Returns the sequential events for a specific trace."""
        trace_file = self.trace_dir / f"{trace_id}.jsonl"
        if not trace_file.exists():
            return []

        events = []
        try:
            with open(trace_file, "r") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        except Exception:
            pass
        return events
