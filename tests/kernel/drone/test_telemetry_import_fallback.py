"""
Isolated test for Telemetry PQC import fallback.
Used to cover L29-31 of telemetry.py safely.
"""

import importlib
import sys
import unittest
from unittest.mock import patch


class TestTelemetryImport(unittest.TestCase):
    def test_pqc_import_fallback(self):
        # We need the module name
        mod_name = "warm_logic.kernel.drone.telemetry"

        # Ensure it's in sys.modules (it should be)
        if mod_name not in sys.modules:
            import warm_logic.kernel.drone.telemetry

        with patch.dict(sys.modules, {"warm_logic.security.pqc": None}):
            # Use importlib.reload directly on the module in sys.modules
            tel = sys.modules[mod_name]
            importlib.reload(tel)
            self.assertFalse(tel.PQC_AVAILABLE)

        # Restore
        importlib.reload(tel)


if __name__ == "__main__":
    unittest.main()
