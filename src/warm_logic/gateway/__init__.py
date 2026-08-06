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
WarmLogic REST API Gateway

External-facing API for governance, evidence, and consensus operations.
Designed for integration with external systems and services.

research prototype Notice: This is a research prototype API.

Multi-Node Support:
    python -m warm_logic.gateway.multi_node --seed           # Start seed node
    python -m warm_logic.gateway.multi_node --join host:port # Join cluster
    python -m warm_logic.gateway.multi_node --local-cluster 4 # Local test cluster
"""

from warm_logic.gateway.app import create_app, gateway_app
from warm_logic.gateway.multi_node import WarmLogicNode

__all__ = ["create_app", "gateway_app", "WarmLogicNode"]
