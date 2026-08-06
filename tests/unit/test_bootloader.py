# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""
[P0xx] Unit tests for bootloader module.
Tests: bootloader.py - Hardware validation and Rust core initialization
"""

import os
import unittest
from unittest import mock


class TestBootloaderInit(unittest.TestCase):
    """Test Bootloader initialization."""

    def test_bootloader_rejects_simulation_mode(self):
        """Test bootloader rejects simulation mode."""
        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "1"}):
            from warm_logic.kernel import bootloader

            # Need to reimport to trigger __init__
            with self.assertRaises(SystemError) as ctx:
                # Force new instance creation
                bootloader.Bootloader()
            self.assertIn("Simulation Mode", str(ctx.exception))

    def test_bootloader_accepts_normal_mode(self):
        """Test bootloader accepts normal mode."""
        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            from warm_logic.kernel.bootloader import Bootloader

            loader = Bootloader()
            self.assertEqual(loader.state, "OFFLINE")
            self.assertIsNone(loader._core)


class TestBootloaderStates(unittest.TestCase):
    """Test Bootloader state transitions."""

    def setUp(self):
        """Create bootloader with mocked environment."""
        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            from warm_logic.kernel.bootloader import Bootloader

            self.Bootloader = Bootloader

    def test_initial_state(self):
        """Test initial state is OFFLINE."""
        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            loader = self.Bootloader()
            self.assertEqual(loader.state, "OFFLINE")

    @mock.patch("warm_logic.kernel.bootloader.HAS_RUST_CORE", False)
    def test_run_init_without_rust_core(self):
        """Test run_init fails without Rust core."""
        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            loader = self.Bootloader()
            with self.assertRaises(RuntimeError) as ctx:
                loader.run_init()
            self.assertIn("Rust Core missing", str(ctx.exception))

    @mock.patch("warm_logic.kernel.bootloader.HAS_RUST_CORE", True)
    @mock.patch("warm_logic.kernel.bootloader.load_rust_core")
    def test_run_init_with_rust_core(self, mock_load):
        """Test run_init succeeds with Rust core."""
        mock_rs = mock.MagicMock()
        mock_rs.KineticCore.return_value = "mock_core"
        mock_load.return_value = mock_rs

        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            loader = self.Bootloader()
            result = loader.run_init()
            self.assertTrue(result)
            self.assertEqual(loader.state, "INITIALIZED")
            self.assertEqual(loader._core, "mock_core")

    @mock.patch("warm_logic.kernel.bootloader.HardwareGuard")
    def test_verify_secure_boot_success(self, mock_guard):
        """Test verify_secure_boot on success."""
        mock_guard.verify_system_integrity.return_value = (True, "Verified")

        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            loader = self.Bootloader()
            success, msg = loader.verify_secure_boot()
            self.assertTrue(success)
            self.assertEqual(loader.state, "SECURE_BOOT_VERIFIED")

    @mock.patch("warm_logic.kernel.bootloader.HardwareGuard")
    def test_verify_secure_boot_failure(self, mock_guard):
        """Test verify_secure_boot on failure."""
        mock_guard.verify_system_integrity.return_value = (False, "Hardware mismatch")

        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            loader = self.Bootloader()
            success, msg = loader.verify_secure_boot()
            self.assertFalse(success)
            self.assertEqual(loader.state, "ATTESTATION_FAILED")

    def test_jump_to_kernel_blocked_without_verification(self):
        """Test jump_to_kernel blocked without secure boot."""
        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            loader = self.Bootloader()
            with self.assertRaises(RuntimeError) as ctx:
                loader.jump_to_kernel()
            self.assertIn("Kernel jump blocked", str(ctx.exception))

    @mock.patch("warm_logic.kernel.bootloader.HardwareGuard")
    def test_jump_to_kernel_after_verification(self, mock_guard):
        """Test jump_to_kernel succeeds after verification."""
        mock_guard.verify_system_integrity.return_value = (True, "OK")

        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            loader = self.Bootloader()
            loader._core = "test_core"
            loader.verify_secure_boot()
            result = loader.jump_to_kernel()
            self.assertEqual(result, "test_core")
            self.assertEqual(loader.state, "RUNNING")


class TestBootSystem(unittest.TestCase):
    """Test boot_system function."""

    @mock.patch("warm_logic.kernel.bootloader.enforce_hardware_lock")
    @mock.patch("warm_logic.kernel.bootloader.HardwareGuard")
    @mock.patch("warm_logic.kernel.bootloader.HAS_RUST_CORE", True)
    @mock.patch("warm_logic.kernel.bootloader.load_rust_core")
    def test_boot_system_success(self, mock_load, mock_guard, mock_lock):
        """Test successful system boot."""
        mock_rs = mock.MagicMock()
        mock_rs.KineticCore.return_value = "kinetic_core"
        mock_load.return_value = mock_rs
        mock_guard.verify_system_integrity.return_value = (True, "OK")

        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            from warm_logic.kernel.bootloader import boot_system

            result = boot_system()
            self.assertEqual(result, "kinetic_core")
            mock_lock.assert_called_once()

    @mock.patch("warm_logic.kernel.bootloader.enforce_hardware_lock")
    @mock.patch("warm_logic.kernel.bootloader.HardwareGuard")
    @mock.patch("warm_logic.kernel.bootloader.HAS_RUST_CORE", True)
    @mock.patch("warm_logic.kernel.bootloader.load_rust_core")
    def test_boot_system_attestation_failure(self, mock_load, mock_guard, mock_lock):
        """Test boot_system fails on attestation failure."""
        mock_rs = mock.MagicMock()
        mock_load.return_value = mock_rs
        mock_guard.verify_system_integrity.return_value = (False, "TPM mismatch")

        with mock.patch.dict(os.environ, {"WARM_LOGIC_SIMULATION": "0"}, clear=False):
            from warm_logic.kernel.bootloader import boot_system

            with self.assertRaises(RuntimeError) as ctx:
                boot_system()
            self.assertIn("Attestation Failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
