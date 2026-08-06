# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic Silicon Health Monitor."""

import time
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.sys.diagnostics import SiliconHealthMonitor


class TestSiliconHealthMonitor:
    """Test SiliconHealthMonitor class."""

    def test_init_records_start_time(self):
        """Records start time on initialization."""
        before = time.time()
        monitor = SiliconHealthMonitor()
        after = time.time()

        assert before <= monitor.start_time <= after

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_returns_dict(self, mock_psutil):
        """Returns dictionary with expected keys."""
        mock_psutil.boot_time.return_value = time.time() - 1000
        mock_psutil.cpu_percent.return_value = 25.5
        mock_vm = MagicMock()
        mock_vm.percent = 45.0
        mock_vm.available = 4 * 1024 * 1024 * 1024  # 4GB
        mock_psutil.virtual_memory.return_value = mock_vm

        stats = SiliconHealthMonitor.get_stats()

        assert "uptime" in stats
        assert "cpu_usage_pct" in stats
        assert "memory_usage_pct" in stats
        assert "memory_available_mb" in stats
        assert "load_avg" in stats
        assert "timestamp" in stats

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_cpu_usage(self, mock_psutil):
        """Correctly reports CPU usage percentage."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 75.5
        mock_vm = MagicMock()
        mock_vm.percent = 50.0
        mock_vm.available = 1024 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm

        stats = SiliconHealthMonitor.get_stats()

        assert stats["cpu_usage_pct"] == 75.5

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_memory_available_mb(self, mock_psutil):
        """Correctly calculates available memory in MB."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 30.0
        mock_vm.available = 2048 * 1024 * 1024  # 2GB
        mock_psutil.virtual_memory.return_value = mock_vm

        stats = SiliconHealthMonitor.get_stats()

        assert stats["memory_available_mb"] == 2048

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_handles_boot_time_error(self, mock_psutil):
        """Handles psutil.boot_time() exception."""
        mock_psutil.boot_time.side_effect = Exception("No boot time")
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 20.0
        mock_vm.available = 1024 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm

        stats = SiliconHealthMonitor.get_stats()

        assert stats["uptime"] == 0

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_handles_cpu_error(self, mock_psutil):
        """Handles psutil.cpu_percent() exception."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.side_effect = Exception("CPU error")
        mock_vm = MagicMock()
        mock_vm.percent = 20.0
        mock_vm.available = 1024 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm

        stats = SiliconHealthMonitor.get_stats()

        assert stats["cpu_usage_pct"] == 0.0

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_handles_memory_error(self, mock_psutil):
        """Handles psutil.virtual_memory() exception."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.virtual_memory.side_effect = Exception("Memory error")

        stats = SiliconHealthMonitor.get_stats()

        assert stats["memory_usage_pct"] == 0.0
        assert stats["memory_available_mb"] == 0

    @patch("warm_logic.kernel.sys.diagnostics.os")
    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_load_avg_unix(self, mock_psutil, mock_os):
        """Reports load average on Unix systems."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 20.0
        mock_vm.available = 1024 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm
        mock_os.getloadavg.return_value = (1.5, 2.0, 2.5)

        stats = SiliconHealthMonitor.get_stats()

        assert stats["load_avg"] == (1.5, 2.0, 2.5)

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_verify_safety_bounds_pass(self, mock_psutil):
        """Returns True when within safety bounds."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 50.0
        mock_vm = MagicMock()
        mock_vm.percent = 50.0
        mock_vm.available = 500 * 1024 * 1024  # 500MB (above 50MB threshold)
        mock_psutil.virtual_memory.return_value = mock_vm

        monitor = SiliconHealthMonitor()
        result = monitor.verify_safety_bounds()

        assert result is True

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_verify_safety_bounds_critical_memory(self, mock_psutil):
        """Returns False when memory below 50MB."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 95.0
        mock_vm.available = 30 * 1024 * 1024  # 30MB (below 50MB threshold)
        mock_psutil.virtual_memory.return_value = mock_vm

        monitor = SiliconHealthMonitor()
        result = monitor.verify_safety_bounds()

        assert result is False

    @patch("warm_logic.kernel.sys.diagnostics.platform")
    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_verify_safety_bounds_thermal_limit(self, mock_psutil, mock_platform):
        """Returns False when thermal exceeds 85C."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 20.0
        mock_vm.available = 500 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm
        mock_platform.system.return_value = "Linux"

        # Mock thermal reading
        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                "90000"  # 90C
            )

            monitor = SiliconHealthMonitor()
            result = monitor.verify_safety_bounds()

        assert result is False

    @patch("warm_logic.kernel.sys.diagnostics.platform")
    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_thermal_linux(self, mock_psutil, mock_platform):
        """Reads thermal data on Linux."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 20.0
        mock_vm.available = 500 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm
        mock_platform.system.return_value = "Linux"

        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                "45000"  # 45C
            )

            stats = SiliconHealthMonitor.get_stats()

        assert stats.get("thermal_c") == 45.0

    @patch("warm_logic.kernel.sys.diagnostics.platform")
    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_thermal_error(self, mock_psutil, mock_platform):
        """Handles thermal read errors gracefully."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 20.0
        mock_vm.available = 500 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm
        mock_platform.system.return_value = "Linux"

        with patch("builtins.open", side_effect=FileNotFoundError):
            stats = SiliconHealthMonitor.get_stats()

        assert "thermal_c" not in stats

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_load_avg_exception(self, mock_psutil):
        """Handles os.getloadavg() exception."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 20.0
        mock_vm.available = 500 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm

        with patch("warm_logic.kernel.sys.diagnostics.os") as mock_os:
            mock_os.getloadavg.side_effect = OSError("Not supported")

            stats = SiliconHealthMonitor.get_stats()

        assert stats["load_avg"] == (0, 0, 0)

    @patch("warm_logic.kernel.sys.diagnostics.psutil")
    def test_get_stats_no_getloadavg(self, mock_psutil):
        """Handles systems without os.getloadavg."""
        mock_psutil.boot_time.return_value = time.time()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_vm = MagicMock()
        mock_vm.percent = 20.0
        mock_vm.available = 500 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_vm

        with patch("warm_logic.kernel.sys.diagnostics.os") as mock_os:
            # Simulate Windows where getloadavg doesn't exist
            del mock_os.getloadavg

            stats = SiliconHealthMonitor.get_stats()

        # Should use fallback (0, 0, 0)
        assert stats["load_avg"] == (0, 0, 0)
