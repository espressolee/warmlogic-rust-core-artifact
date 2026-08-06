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
import os
import tempfile
import unittest
from unittest import mock

from warm_logic.kernel.zanzibar import RelationTuple, ZanzibarEngine, check_permission


class TestZanzibarSaturation(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.engine = ZanzibarEngine(self.db_path)

    def tearDown(self):
        self.engine.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_init_db_memory(self):
        eng = ZanzibarEngine(":memory:")
        self.assertIsNotNone(eng.conn)

    def test_relation_tuple_pqc_verification(self):
        # Invalid signatures
        t1 = RelationTuple("ns", "obj", "rel", "user", "u1", signature=None)
        self.assertFalse(self.engine.verify_signature(t1))

        t2 = RelationTuple(
            "ns",
            "obj",
            "rel",
            "user",
            "u1",
            signature="BAD",
            authority="did:warm:root:1",
        )
        self.assertFalse(self.engine.verify_signature(t2))

        # Valid signature
        t3 = RelationTuple(
            "ns",
            "obj",
            "rel",
            "user",
            "u1",
            signature="ROOT_AUTHORITY_SIG",
            authority="did:warm:root:42",
        )
        self.assertTrue(self.engine.verify_signature(t3))

    def test_write_tuple_rejection(self):
        t = RelationTuple("ns", "obj", "rel", "user", "u1", signature="BAD")
        self.assertFalse(self.engine.write_tuple(t))

    def test_write_tuple_success_and_replication(self):
        t = RelationTuple(
            "ns",
            "obj",
            "view",
            "user",
            "u1",
            signature="ROOT_AUTHORITY_SIG",
            authority="did:warm:root:1",
        )

        mock_dht = mock.MagicMock()
        # Success with replication
        self.assertTrue(self.engine.write_tuple(t, dht=mock_dht, replicate=True))
        mock_dht.broadcast.assert_called()

        # Replication failure graceful
        mock_dht.broadcast.side_effect = Exception("network down")
        self.assertTrue(self.engine.write_tuple(t, dht=mock_dht, replicate=True))

    def test_check_rbac_expansion(self):
        """Tests the core Zanzibar logic: Groups/Inheritance."""
        t_root = {"signature": "ROOT_AUTHORITY_SIG", "authority": "did:warm:root:1"}

        # 1. Direct permission
        self.engine.write_tuple(
            RelationTuple("file", "f1", "read", "user", "u1", **t_root)
        )
        self.assertTrue(self.engine.check("file", "f1", "read", "u1"))

        # 2. Group membership expansion
        # To have 'read' on 'f1', one must be a 'member' of 'group1'
        self.engine.write_tuple(
            RelationTuple(
                "file",
                "f1",
                "read",
                "group",
                "group1",
                subject_relation="member",
                **t_root,
            )
        )
        # u2 is a member of group1
        self.engine.write_tuple(
            RelationTuple("group", "group1", "member", "user", "u2", **t_root)
        )

        self.assertTrue(self.engine.check("file", "f1", "read", "u2"))

    def test_check_depth_limit(self):
        """Line 128: if depth <= 0: return False"""
        # Linear chain: f1:access -> g1:member -> g2:member -> g3:member -> g4:member -> g5:member -> user:u_deep
        t_root = {"signature": "ROOT_AUTHORITY_SIG", "authority": "did:warm:root:1"}

        self.engine.write_tuple(
            RelationTuple(
                "file",
                "f1",
                "access",
                "group",
                "g1",
                subject_relation="member",
                **t_root,
            )
        )
        self.engine.write_tuple(
            RelationTuple(
                "group",
                "g1",
                "member",
                "group",
                "g2",
                subject_relation="member",
                **t_root,
            )
        )
        self.engine.write_tuple(
            RelationTuple(
                "group",
                "g2",
                "member",
                "group",
                "g3",
                subject_relation="member",
                **t_root,
            )
        )
        self.engine.write_tuple(
            RelationTuple(
                "group",
                "g3",
                "member",
                "group",
                "g4",
                subject_relation="member",
                **t_root,
            )
        )
        self.engine.write_tuple(
            RelationTuple(
                "group",
                "g4",
                "member",
                "group",
                "g5",
                subject_relation="member",
                **t_root,
            )
        )
        self.engine.write_tuple(
            RelationTuple("group", "g5", "member", "user", "u_deep", **t_root)
        )

        # Steps:
        # 1. file:f1:access -> group:g1 (next: group:g1:member)
        # 2. group:g1:member -> group:g2 (next: group:g2:member)
        # 3. group:g2:member -> group:g3 (next: group:g3:member)
        # 4. group:g3:member -> group:g4 (next: group:g4:member)
        # 5. group:g4:member -> group:g5 (next: group:g5:member)
        # 6. group:g5:member -> user:u_deep (SUCCESS)
        # Total depth required: 6

        self.assertFalse(self.engine.check("file", "f1", "access", "u_deep", depth=5))
        self.assertTrue(self.engine.check("file", "f1", "access", "u_deep", depth=7))

    def test_global_helper(self):
        with mock.patch("warm_logic.kernel.zanzibar.zanzibar.check", return_value=True):
            self.assertTrue(check_permission("ns", "o", "r", "u"))


if __name__ == "__main__":
    unittest.main()
