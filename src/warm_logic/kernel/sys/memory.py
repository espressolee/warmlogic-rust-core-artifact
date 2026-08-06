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
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("SovereignMemory")


class SovereignMemoryEngine:
    """
    Sovereign Memory System (SMS).
    Manages short-term (Ephemeris) and long-term (Chronicle) project memory.
    """

    def __init__(self, root_dir: str, identity: Any):
        self.root_dir = Path(root_dir)
        self.mem_dir = self.root_dir / "meta" / "memory"
        self.ephemeris_dir = self.mem_dir / "ephemeris"
        self.chronicle_path = self.mem_dir / "chronicle.md"
        self.identity = identity  # SovereignIdentity

        self.ephemeris_dir.mkdir(parents=True, exist_ok=True)

    def log_event(
        self, event_type: str, detail: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """Logs a granular project event to today's Ephemeris."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_path = self.ephemeris_dir / f"{today}.md"

        timestamp = time.time()
        entry_id = f"MEM-{int(timestamp)}"

        # Construct Payload
        payload = {
            "id": entry_id,
            "ts": timestamp,
            "type": event_type,
            "detail": detail,
            "meta": metadata or {},
        }

        # PQC Sign the entry if identity is available
        signature = "UNSIGNED"
        if self.identity:
            signature = self.identity.sign(json.dumps(payload))

        header = f"### [{datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')}] {event_type}\n"
        body = f"- **Detail**: {detail}\n"
        if metadata:
            body += f"- **Meta**: {json.dumps(metadata)}\n"
        body += f"- **Sig**: `{signature[:16]}...` (PQC)\n\n"

        # Append to file
        with open(log_path, "a") as f:
            if log_path.stat().st_size == 0:
                f.write(f"# Ephemeris: {today}\n\n")
            f.write(header + body)

        logger.info(f"[SMS] Recorded event {entry_id} in Ephemeris")

    def get_session_summary(self, date_str: str) -> str:
        """Retrieves and summarizes a daily log for chronicle compaction."""
        log_path = self.ephemeris_dir / f"{date_str}.md"
        if not log_path.exists():
            return ""
        return log_path.read_text()

    def compact_to_chronicle(self, summary: str):
        """Appends a compacted session summary to the permanent Chronicle."""
        with open(self.chronicle_path, "a") as f:
            f.write(f"\n## Session Summary: {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(summary + "\n")
        logger.info("[SMS] Compaction to Chronicle complete.")
