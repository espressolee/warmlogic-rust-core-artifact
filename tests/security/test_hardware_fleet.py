import os
import sys
import unittest

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from warm_logic.kernel.hardware.confidential import AttestationReport, HardwareGuard


class TestHardwareFleet(unittest.TestCase):
    def test_hardware_report_structure(self):
        """Verify that the hardware report contains the expected provider strings."""
        report = HardwareGuard.get_hardware_report()
        self.assertIsInstance(report, AttestationReport)

        # Should start with KINETIC_TPM or KINETIC_ID
        self.assertTrue(
            report.provider.startswith("KINETIC_TPM")
            or report.provider.startswith("KINETIC_ID"),
            f"Unexpected provider prefix: {report.provider}",
        )

        # On Mac, it should be KINETIC_ID_DARWIN or KINETIC_TPM_STUB_DARWIN
        if sys.platform == "darwin":
            self.assertTrue(
                report.provider in ("KINETIC_ID_DARWIN", "KINETIC_TPM_STUB_DARWIN"),
                f"Unexpected provider: {report.provider}",
            )

        print(
            f"✅ Hardware Report Verified: Provider={report.provider}, Hash={report.pcr_hash}"
        )

    def test_integrity_verification(self):
        """Verify that the system integrity check succeeds on valid hardware."""
        success, msg = HardwareGuard.verify_system_integrity()
        self.assertTrue(success)
        self.assertIn("VERIFICATION_SUCCESS", msg)
        self.assertIn("PCR[", msg)
        print(f"✅ Integrity Check Verified: {msg}")


if __name__ == "__main__":
    unittest.main()
