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
from unittest import mock

from warm_logic.kernel.ops.quorum_manager import QuorumManager
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestQuorumManagerCoverage(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        self.mock_ledger = mock.MagicMock()
        # Patch BFTEngine's MLDSA instantiation
        self.mldsa_patcher = mock.patch("warm_logic.kernel.sys.consensus.MLDSA")
        self.mldsa_patcher.start()

        # Patch BFTEngine since Rust version is read-only
        self.bft_patcher = mock.patch("warm_logic.kernel.ops.quorum_manager.BFTEngine")
        self.mock_bft_cls = self.bft_patcher.start()
        self.mock_bft = mock.MagicMock()
        self.mock_bft_cls.return_value = self.mock_bft

        self.qm = QuorumManager(self.mock_ledger, total_validators=4)

    def tearDown(self):
        self.bft_patcher.stop()
        self.mldsa_patcher.stop()
        super().tearDown()

    def test_on_receive_block_approve(self):
        payload = {
            "block": {"hash": "abc", "height": 10},
            "balances": {},
            "zk_proof": "proof",
            "transactions": [],
        }
        self.mock_ledger.receive_external_block.return_value = True
        with mock.patch.object(self.qm, "cast_vote") as mock_cast:
            with self.assertLogs("QuorumManager", level="INFO"):
                self.qm.on_receive_block(payload)
                mock_cast.assert_called_once_with("abc", "APPROVE")

    def test_on_receive_block_reject(self):
        payload = {"block": {"hash": "bad"}}
        self.mock_ledger.receive_external_block.return_value = False
        with mock.patch.object(self.qm, "cast_vote") as mock_cast:
            with self.assertLogs("QuorumManager", level="WARNING"):
                self.qm.on_receive_block(payload)
                mock_cast.assert_called_once_with("bad", "REJECT")

    def test_on_receive_vote(self):
        with mock.patch.object(
            self.mock_bft, "submit_vote", side_effect=[False, False, True]
        ):
            payload = {
                "block_hash": "hhh",
                "voter_id": "v1",
                "decision": "APPROVE",
                "signature": "sig",
            }
            self.qm.on_receive_vote(payload)
            self.qm.on_receive_vote(payload)
            with self.assertLogs("QuorumManager", level="INFO"):
                self.qm.on_receive_vote(payload)

    def test_cast_vote_success(self):
        with mock.patch.dict("os.environ", {"VAL_IDENTITY": "v1", "VAL_SECRET": "s1"}):
            with mock.patch("warm_logic.kernel.rust_loader.HAS_RUST_CORE", True):
                with mock.patch(
                    "warm_logic.kernel.identity.kinetic_id.KineticIdentity"
                ) as mock_id:
                    mock_id.HAS_KEY = True
                    mock_id.PUBLIC_KEY = "VALID_PK"
                    mock_id.sign_intent_static.return_value = "SIG_VOTE"
                    with mock.patch.object(self.qm, "on_receive_vote") as mock_recv:
                        with mock.patch(
                            "warm_logic.kernel.ops.quorum_manager.StitchServer.broadcast"
                        ):
                            self.qm.cast_vote("bh", "APPROVE")
                            mock_recv.assert_called_once()

    def test_cast_vote_no_identity(self):
        with mock.patch(
            "warm_logic.kernel.identity.kinetic_id.KineticIdentity"
        ) as mock_id:
            mock_id.HAS_KEY = False
            with self.assertRaises(RuntimeError):
                self.qm.cast_vote("bh", "APPROVE")

    def test_propagate_block(self):
        with mock.patch(
            "warm_logic.kernel.ops.quorum_manager.StitchServer.broadcast"
        ) as mock_b:
            with self.assertLogs("QuorumManager", level="INFO"):
                self.qm.propagate_block({"hash": "m1"}, {}, "zk", [])
                mock_b.assert_called_once()
