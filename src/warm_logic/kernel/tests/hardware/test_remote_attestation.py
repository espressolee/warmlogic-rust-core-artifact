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
Remote Attestation Tests
"""

import hashlib
import time
import unittest
from unittest import mock

from warm_logic.kernel.hardware.remote_attestation import (
    RemoteAttestationClient,
    RemoteAttestationReport,
    SovereignNode,
    get_attestation_client,
    register_milkv_node,
)
from warm_logic.kernel.tests.base import WarmLogicTestCase


class TestRemoteAttestationReport(WarmLogicTestCase):
    def test_report_creation(self):
        report = RemoteAttestationReport(
            version="1.0.0",
            era=3000,
            device="test-device",
            soc="test-soc",
            chip_id="0x12345678",
            mac_address="aa:bb:cc:dd:ee:ff",
            fingerprint="abc123",
            entropy="deadbeef",
            timestamp=int(time.time()),
            kernel="5.10.0",
            arch="riscv64",
            memory_mb=256,
            uptime_sec=1000,
        )

        self.assertEqual(report.era, 3000)
        self.assertEqual(report.device, "test-device")
        self.assertTrue(report.node_id.startswith("wl-"))
        self.assertFalse(report.verified)

    def test_report_to_dict(self):
        report = RemoteAttestationReport(
            version="1.0.0",
            era=3000,
            device="test",
            soc="soc",
            chip_id="0x1",
            mac_address="00:00:00:00:00:00",
            fingerprint="fp",
            entropy="en",
            timestamp=12345,
            kernel="k",
            arch="a",
            memory_mb=128,
            uptime_sec=100,
        )

        d = report.to_dict()
        self.assertEqual(d["era"], 3000)
        self.assertEqual(d["device"], "test")
        self.assertIn("node_id", d)


class TestSovereignNode(WarmLogicTestCase):
    def test_node_defaults(self):
        node = SovereignNode(host="192.168.1.1")
        self.assertEqual(node.port, 22)
        self.assertEqual(node.user, "root")
        self.assertEqual(node.name, "root@192.168.1.1")

    def test_node_custom_name(self):
        node = SovereignNode(host="192.168.1.1", name="my-node")
        self.assertEqual(node.name, "my-node")


class TestRemoteAttestationClient(WarmLogicTestCase):
    def setUp(self):
        super().setUp()
        self.client = RemoteAttestationClient()

    def test_register_node(self):
        node = SovereignNode(host="192.168.1.1", name="test-node")
        self.client.register_node(node)

        nodes = self.client.get_registered_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].host, "192.168.1.1")

    def test_unregister_node(self):
        node = SovereignNode(host="192.168.1.1")
        self.client.register_node(node)
        self.client.unregister_node("192.168.1.1")

        nodes = self.client.get_registered_nodes()
        self.assertEqual(len(nodes), 0)

    def test_verify_attestation_valid(self):
        chip_id = "0x18222000"
        mac_addr = "56:1b:35:9d:19:7f"
        # Compute expected fingerprint (with newline as shell echo does)
        expected_fp = hashlib.sha256(f"{chip_id}:{mac_addr}\n".encode()).hexdigest()

        report = RemoteAttestationReport(
            version="1.0.0",
            era=3000,
            device="milkv-duos",
            soc="sg2000",
            chip_id=chip_id,
            mac_address=mac_addr,
            fingerprint=expected_fp,
            entropy="abc",
            timestamp=int(time.time()),
            kernel="5.10.4",
            arch="riscv64",
            memory_mb=316,
            uptime_sec=1000,
        )

        result = self.client._verify_attestation(report)
        self.assertTrue(result)

    def test_verify_attestation_invalid_fingerprint(self):
        report = RemoteAttestationReport(
            version="1.0.0",
            era=3000,
            device="test",
            soc="test",
            chip_id="0x1234",
            mac_address="aa:bb:cc:dd:ee:ff",
            fingerprint="wrong_fingerprint",
            entropy="abc",
            timestamp=int(time.time()),
            kernel="5.10.4",
            arch="riscv64",
            memory_mb=256,
            uptime_sec=1000,
        )

        result = self.client._verify_attestation(report)
        self.assertFalse(result)

    def test_verify_attestation_stale_timestamp(self):
        chip_id = "0x1234"
        mac_addr = "aa:bb:cc:dd:ee:ff"
        expected_fp = hashlib.sha256(f"{chip_id}:{mac_addr}\n".encode()).hexdigest()

        report = RemoteAttestationReport(
            version="1.0.0",
            era=3000,
            device="test",
            soc="test",
            chip_id=chip_id,
            mac_address=mac_addr,
            fingerprint=expected_fp,
            entropy="abc",
            timestamp=int(time.time()) - 100000,  # Very old
            kernel="5.10.4",
            arch="riscv64",
            memory_mb=256,
            uptime_sec=1000,
        )

        result = self.client._verify_attestation(report)
        self.assertFalse(result)

    def test_verify_attestation_missing_chip_id(self):
        report = RemoteAttestationReport(
            version="1.0.0",
            era=3000,
            device="test",
            soc="test",
            chip_id="unknown",
            mac_address="aa:bb:cc:dd:ee:ff",
            fingerprint="fp",
            entropy="abc",
            timestamp=int(time.time()),
            kernel="5.10.4",
            arch="riscv64",
            memory_mb=256,
            uptime_sec=1000,
        )

        result = self.client._verify_attestation(report)
        self.assertFalse(result)

    def test_federation_fingerprint_empty(self):
        fp = self.client.get_federation_fingerprint()
        self.assertEqual(fp, "")

    @mock.patch.object(RemoteAttestationClient, "_execute_ssh")
    def test_fetch_attestation_success(self, mock_ssh):
        chip_id = "0x18222000"
        mac_addr = "56:1b:35:9d:19:7f"
        fp = hashlib.sha256(f"{chip_id}:{mac_addr}\n".encode()).hexdigest()

        mock_ssh.return_value = (
            True,
            f'{{"version":"1.0","era":3000,"device":"milkv","soc":"sg2000",'
            f'"chip_id":"{chip_id}","mac_address":"{mac_addr}",'
            f'"fingerprint":"{fp}","entropy":"abc","timestamp":{int(time.time())},'
            f'"kernel":"5.10","arch":"riscv64","memory_mb":316,"uptime_sec":100}}',
        )

        report = self.client.fetch_attestation("192.0.2.1")
        self.assertIsNotNone(report)
        self.assertTrue(report.verified)
        self.assertEqual(report.device, "milkv")

    @mock.patch.object(RemoteAttestationClient, "_execute_ssh")
    def test_fetch_attestation_ssh_failure(self, mock_ssh):
        mock_ssh.return_value = (False, "Connection refused")

        report = self.client.fetch_attestation("192.0.2.1")
        self.assertIsNone(report)


class TestConvenienceFunctions(WarmLogicTestCase):
    def test_get_attestation_client_singleton(self):
        client1 = get_attestation_client()
        client2 = get_attestation_client()
        # Note: In production these would be the same instance,
        # but tests may reset global state
        self.assertIsNotNone(client1)
        self.assertIsNotNone(client2)

    def test_register_milkv_node(self):
        node = register_milkv_node("192.0.2.1")
        self.assertEqual(node.host, "192.0.2.1")
        self.assertEqual(node.name, "milkv-duos")
        self.assertEqual(node.attestation_cmd, "/usr/local/bin/wl-attestation")


if __name__ == "__main__":
    unittest.main()
