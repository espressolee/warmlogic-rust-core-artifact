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
WarmLogic Kernel Exception Hierarchy (Hardened)
Defines specialized exceptions for sovereign OS operations.
"""

class WarmLogicError(Exception):
    """Base exception for all WarmLogic errors."""
    pass

class SovereignError(WarmLogicError):
    """Errors related to sovereign identity and proofs."""
    pass

class ConstitutionalBreach(WarmLogicError):
    """Errors raised when a constitutional guard is breached."""
    pass

class MeshNetworkingError(WarmLogicError):
    """Errors related to P2P mesh and DHT."""
    pass

class PersistenceError(WarmLogicError):
    """Errors related to the sovereign ledger or database."""
    pass

class IntegrityError(WarmLogicError):
    """Errors related to data lineage or ZK proof verification."""
    pass

class RateLimitExceeded(WarmLogicError):
    """Errors raised when the sovereign rate limiter is triggered."""
    pass
