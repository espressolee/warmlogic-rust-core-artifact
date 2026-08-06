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
import time

from prometheus_client import Counter, Gauge, Histogram

# --- System Metrics ---
UPTIME_SECONDS = Gauge("warm_logic_uptime_seconds", "Time since kernel boot")
KERNEL_INFO = Gauge("warm_logic_kernel_info", "Kernel version info", ["version", "era"])

# --- Mesh Metrics ---
PEER_COUNT = Gauge(
    "warm_logic_mesh_peer_count", "Number of connected peers", ["region"]
)
MESSAGE_SENT = Counter(
    "warm_logic_mesh_message_sent_total", "Total P2P messages sent", ["type"]
)
MESSAGE_RECEIVED = Counter(
    "warm_logic_mesh_message_received_total", "Total P2P messages received", ["type"]
)

# --- Consensus Metrics ---
BLOCK_HEIGHT = Gauge("warm_logic_ledger_height", "Current block height")
QUORUM_ROUNDS = Counter("warm_logic_consensus_rounds_total", "Total consensus rounds")
JITTER = Histogram("warm_logic_consensus_jitter_seconds", "Jitter in consensus timing")

# --- Initialization ---
_START_TIME = time.time()


def update_uptime() -> None:
    UPTIME_SECONDS.set(time.time() - _START_TIME)


def set_info(version: str, era: str) -> None:
    KERNEL_INFO.labels(version=version, era=era).set(1)
