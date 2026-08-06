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
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PolicyZone(Enum):
    PUBLIC = 10
    INTERNAL = 50
    RESTRICTED = 100
    SECRET = 200


logger = logging.getLogger("LineageTracker")


@dataclass
class LineageRecord:
    origin_id: str
    creator_id: str
    zone: PolicyZone
    timestamp: float = field(default_factory=time.time)
    parent_ids: List[str] = field(default_factory=list)  # Multi-source tracking
    tags: Dict[str, str] = field(default_factory=dict)


class LineageTracker:
    """
    Enforces 'Policy Zones' based on data origin.
    Prevents 'Information Leakage' from high-security zones to lower zones.
    """

    def __init__(self) -> None:
        self.records: Dict[str, LineageRecord] = {}

    def track(
        self, data_id: str, zone: PolicyZone, creator: str, parents: Optional[List[str]] = None
    ) -> LineageRecord:
        """Registers a new data object in a specific zone."""
        # If parents exist, the zone must be at least as strict as the strictest parent
        strictest_parent_zone = PolicyZone.PUBLIC
        if parents:
            for p_id in parents:
                if p_id in self.records:
                    p_zone = self.records[p_id].zone
                    if p_zone.value > strictest_parent_zone.value:
                        strictest_parent_zone = p_zone

        # Enforce 'Inheritance' of strictness
        final_zone = (
            zone if zone.value > strictest_parent_zone.value else strictest_parent_zone
        )

        record = LineageRecord(
            origin_id=data_id,
            creator_id=creator,
            zone=final_zone,
            parent_ids=parents or [],
        )
        self.records[data_id] = record
        return record

    def check_flow(self, data_id: str, target_zone: PolicyZone) -> bool:
        """
        Interrogates if data from data_id is allowed to flow into target_zone.
        Rule: Zone(Data) <= Zone(Target)
        Example: SECRET data cannot flow to PUBLIC.
        """
        if data_id not in self.records:
            logger.warning(
                f"🚫 [Lineage] DENY: Untracked data ID {data_id} attempted flow to {target_zone.name}"
            )
            return False  # hardware attestation enforcement: Deny untracked data flow.

        data_zone = self.records[data_id].zone
        return data_zone.value <= target_zone.value

    def get_zone_name(self, data_id: str) -> str:
        if data_id in self.records:
            return self.records[data_id].zone.name
        return "UNKNOWN"


# Global Lineage Tracker Instance
tracker = LineageTracker()


def enforce_lineage_flow(data_id: str, target_zone: PolicyZone) -> bool:
    if not tracker.check_flow(data_id, target_zone):
        print(
            f"🛑 LINEAGE VIOLATION: {data_id} ({tracker.get_zone_name(data_id)}) -> {target_zone.name}"
        )
        return False
    return True
