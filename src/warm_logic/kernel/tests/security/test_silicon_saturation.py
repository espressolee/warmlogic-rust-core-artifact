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
import hashlib
import os
import unittest
from unittest import mock

from warm_logic.kernel.security.silicon import SG2000Binder


class TestSiliconSaturation(unittest.TestCase):
    def setUp(self):
        if "STRICT_HARDWARE" in os.environ:
            del os.environ["STRICT_HARDWARE"]

    def test_get_fingerprint_simulated(self):
        """Tests the simulated/fallback fingerprint generation."""
        # Mock file opens to fail so it hits fallback
        with mock.patch("builtins.open", side_effect=FileNotFoundError()):
            # Fallback will try to import warm_logic_rs
            mock_rs = mock.MagicMock()
            mock_rs.HardwareRealityBinder.get_hardware_fingerprint.return_value = (
                "RUST_FP"
            )
            with mock.patch.dict("sys.modules", {"warm_logic_rs": mock_rs}):
                fp = SG2000Binder.get_fingerprint()
                # Rust fingerprint is now hashed for consistent 64-char output
                expect = hashlib.sha3_256(b"RUST_FP").hexdigest()
                self.assertEqual(fp, expect)

            # Final fallback to VIRTUAL_REALITY
            with mock.patch.dict("sys.modules", {"warm_logic_rs": None}):
                fp = SG2000Binder.get_fingerprint()
                expect = hashlib.sha3_256(b"VIRTUAL_REALITY").hexdigest()
                self.assertEqual(fp, expect)

    def test_get_fingerprint_strict_fail(self):
        """Line 62-68: STRICT_HARDWARE check."""
        with mock.patch.dict(os.environ, {"STRICT_HARDWARE": "1"}):
            with mock.patch("builtins.open", side_effect=FileNotFoundError()):
                with self.assertRaises(RuntimeError) as cm:
                    SG2000Binder.get_fingerprint()
                self.assertIn("Hardware Binding Failed", str(cm.exception))

    def test_get_fingerprint_hardware_markers(self):
        """Simulates Milk-V Duo S hardware files."""

        def mock_open_impl(path, mode="r"):
            if path == "/proc/cpuinfo":
                return mock.mock_open(read_data="riscv\nSerial: 12345").return_value
            elif path == "/etc/machine-id":
                return mock.mock_open(read_data="machine123").return_value
            elif "/sys/class/net/" in path:
                return mock.mock_open(read_data="00:11:22:33:44:55").return_value
            elif "/sys/class/block/mmcblk0" in path:
                return mock.mock_open(read_data="CID:abc").return_value
            else:
                raise FileNotFoundError()

        with mock.patch("builtins.open", side_effect=mock_open_impl):
            with mock.patch(
                "os.path.exists", side_effect=lambda p: p == "/etc/machine-id"
            ):
                # verify cross-validation branch
                mock_rs = mock.MagicMock()
                mock_rs.HardwareRealityBinder.get_hardware_fingerprint.return_value = (
                    "RUST_FP"
                )
                with mock.patch.dict("sys.modules", {"warm_logic_rs": mock_rs}):
                    fp = SG2000Binder.get_fingerprint()
                    self.assertIsNotNone(fp)

    def test_get_fingerprint_exceptions(self):
        """Hit the except blocks."""
        # 1. Machine ID exception
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch("builtins.open", side_effect=PermissionError("no read")):
                SG2000Binder.get_fingerprint()

        # 2. Cross-validation exception
        # Inject mock_rs into sys.modules so 'import warm_logic_rs' works but method fails
        mock_rs = mock.MagicMock()
        mock_rs.HardwareRealityBinder.get_hardware_fingerprint.side_effect = (
            RuntimeError("rust fail")
        )
        with mock.patch.dict("sys.modules", {"warm_logic_rs": mock_rs}):
            # Ensure markers are not empty to hit the cross-validation logic
            with mock.patch(
                "builtins.open",
                return_value=mock.mock_open(read_data="riscv").return_value,
            ):
                SG2000Binder.get_fingerprint()

    def test_seal_unseal_wrappers(self):
        """Covers seal/unseal delegation and exceptions."""
        data = b"secret"
        mock_rs = mock.MagicMock()
        mock_rs.HardwareRealityBinder.seal_to_silicon.return_value = b"sealed"
        mock_rs.HardwareRealityBinder.unseal_from_silicon.return_value = data

        with mock.patch.dict("sys.modules", {"warm_logic_rs": mock_rs}):
            self.assertEqual(SG2000Binder.seal_data(data), b"sealed")
            self.assertEqual(SG2000Binder.unseal_data(b"sealed"), data)

        # Exception branches
        mock_rs.HardwareRealityBinder.seal_to_silicon.side_effect = Exception("fail")
        mock_rs.HardwareRealityBinder.unseal_from_silicon.side_effect = Exception(
            "fail"
        )

        with mock.patch.dict("sys.modules", {"warm_logic_rs": mock_rs}):
            self.assertEqual(SG2000Binder.seal_data(data), data)
            with self.assertRaises(ValueError):
                SG2000Binder.unseal_data(b"sealed")

    def test_verify_reality(self):
        fp = SG2000Binder.get_fingerprint()
        self.assertTrue(SG2000Binder.verify_reality(fp))
        self.assertFalse(SG2000Binder.verify_reality("wrong"))


if __name__ == "__main__":
    unittest.main()
