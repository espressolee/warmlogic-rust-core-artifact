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
from typing import Any, Dict, List

logger = logging.getLogger("DHTReasoner")


class DHTReasoner:
    """
    Distributed Reasoning Engine.
    Allows nodes to publish 'Intermediate Thoughts' to the DHT and aggregate them later.
    """

    def __init__(self, dht_client: Any):
        self.dht = dht_client
        self.local_insights: Dict[str, Any] = {}

    def publish_insight(self, topic: str, insight_data: Any) -> None:
        """
        Publishes an insight to the DHT.
        Key format: insight:{topic}:{node_id}
        """
        node_id = self.dht.node_id
        key = f"insight:{topic}:{node_id}"
        logger.info(f"[Reasoning] Publishing insight on '{topic}' to DHT: {key}")

        # Store in local DHT (which propagates via Gossip/Kademlia)
        self.dht.put(key, str(insight_data))

    def gather_insights(self, topic: str) -> List[Any]:
        """
        Scans the DHT for insights related to a topic.
        """
        logger.info(f"[Reasoning] Gathering insights for '{topic}'...")
        # In a real Kademlia, we'd do a prefix search or maintain a topic index.
        # For Phase 62 prototype, we mock the retrieval from the mock DHT

        results = []
        # Mock logic: iterate known keys in mock DHT
        if hasattr(self.dht, "storage"):
            for k, v in self.dht.storage.items():
                if k.startswith(f"insight:{topic}:"):
                    results.append(v)

        logger.info(f"[Reasoning] Gathered {len(results)} insights for '{topic}'.")
        return results

    def synthesize_verdict(self, topic: str) -> str:
        """
        Aggregates insights into a final verdict.
        """
        insights = self.gather_insights(topic)
        if not insights:
            return "No data to reason upon."

        # Simple synthesis: concatenation
        verdict = f"Collective Verdict on {topic}: " + " | ".join(
            [str(i) for i in insights]
        )
        return verdict
