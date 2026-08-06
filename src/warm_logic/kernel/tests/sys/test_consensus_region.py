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

from warm_logic.kernel.sys.consensus import BFTEngine, Vote
from warm_logic.kernel.sys.cryptography import MLDSA, PQCKeypair
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestConsensusRegion(WarmLogicTestCase):
    USE_RUST_CORE = True

    def setUp(self):
        super().setUp()
        self.node1_pk, self.node1_sk = PQCKeypair.generate()
        self.node2_pk, self.node2_sk = PQCKeypair.generate()
        self.node3_pk, self.node3_sk = PQCKeypair.generate()

    def _sign_vote(self, sk: str, block_hash: str, decision: str) -> str:
        msg = f"VOTE:{block_hash}:{decision}"
        return MLDSA().sign(msg, sk)

    def test_regional_quorum_success(self):
        """Test consensus with regional diversity."""
        # 3 validators, requires 3 votes for 2/3 + 1
        # Require 2 unique regions
        engine = BFTEngine(total_validators=4, min_regions=2)
        block_hash = "block_region_ok"

        # Vote 1 (US-EAST)
        sig1 = self._sign_vote(self.node1_sk, block_hash, "APPROVE")
        v1 = Vote(block_hash, self.node1_pk, "US-EAST", "APPROVE", sig1, time.time())
        engine.submit_vote(v1)

        # Vote 2 (US-EAST)
        sig2 = self._sign_vote(self.node2_sk, block_hash, "APPROVE")
        v2 = Vote(block_hash, self.node2_pk, "US-EAST", "APPROVE", sig2, time.time())
        engine.submit_vote(v2)

        # Not committed yet: 2 votes, 1 region
        self.assertFalse(engine.is_committed(block_hash))

        # Vote 3 (EU-WEST) - Critical for regional quorum
        sig3 = self._sign_vote(self.node3_sk, block_hash, "APPROVE")
        v3 = Vote(block_hash, self.node3_pk, "EU-WEST", "APPROVE", sig3, time.time())
        committed = engine.submit_vote(v3)

        self.assertTrue(committed, "Should commit with 3 votes and 2 regions")
        self.assertTrue(engine.is_committed(block_hash))

    def test_regional_quorum_failure_single_region(self):
        """Test consensus failure if stuck in single region."""
        engine = BFTEngine(total_validators=4, min_regions=2)
        block_hash = "block_region_fail"

        # All 3 votes from US-EAST
        pk4, sk4 = PQCKeypair.generate()

        votes = [
            (self.node1_pk, self.node1_sk),
            (self.node2_pk, self.node2_sk),
            (pk4, sk4),  # 3rd node
        ]

        for pk, sk in votes:
            sig = self._sign_vote(sk, block_hash, "APPROVE")
            v = Vote(block_hash, pk, "US-EAST", "APPROVE", sig, time.time())
            engine.submit_vote(v)

        # 3 votes reachable quorum number, but only 1 region
        self.assertFalse(
            engine.is_committed(block_hash), "Should not commit with only 1 region"
        )
