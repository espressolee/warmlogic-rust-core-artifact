import os
import sys
import unittest

from warm_logic.kernel.bootloader import Bootloader, boot_system
from warm_logic.kernel.hardware.confidential import HardwareGuard


class TestEra4000Attestation(unittest.TestCase):
    def test_end_to_end_boot(self):
        """
        Verify that the system can boot normally when simulation flags are absent.
        """
        # Ensure we are NOT in simulation mode for this test
        if "WARM_LOGIC_SIMULATION" in os.environ:
            del os.environ["WARM_LOGIC_SIMULATION"]

        print("\n--- Starting Boot Trace ---")
        try:
            core = boot_system()
            self.assertIsNotNone(core)
            print("BOOT_SUCCESS: Kinetic Core reached 'RUNNING' state.")
        except Exception as e:
            self.fail(f"Boot failed unexpectedly: {e}")

    def test_boot_rejection_in_simulation(self):
        """
        Verify that the system halts if WARM_LOGIC_SIMULATION is detected.
        """
        os.environ["WARM_LOGIC_SIMULATION"] = "1"
        print("\n--- Testing hardware attestation enforcement (Simulation) ---")
        try:
            boot_system()
            self.fail("System booted in simulation mode. hardware attestation enforcement FAILED.")
        except SystemError as e:
            print(f"REJECTION_VERIFIED: {e}")
            # Upgrade: We now raise a specific message for simulation rejection
            self.assertTrue(
                "Simulation Mode Detected" in str(e)
                or "Physical Security Violation" in str(e)
            )
        except Exception as e:
            self.fail(f"Unexpected exception during rejection test: {e}")
        finally:
            del os.environ["WARM_LOGIC_SIMULATION"]

    def test_hardware_report_structure(self):
        """
        Verify the structure of the hardware attestation report.
        """
        report = HardwareGuard.get_hardware_report()
        print(f"\n--- Hardware Report Extraction ---")
        print(f"Provider: {report.provider}")
        print(f"PCR Hash: {report.pcr_hash}")
        print(f"Quote:    {report.quote}")

        # Provider names updated to KINETIC_ID format
        if sys.platform == "darwin":
            self.assertTrue(
                report.provider in ("KINETIC_ID_DARWIN", "KINETIC_TPM_STUB_DARWIN"),
                f"Unexpected provider: {report.provider}",
            )
        else:
            self.assertTrue(
                report.provider.startswith("KINETIC_"),
                f"Unexpected provider: {report.provider}",
            )
        self.assertTrue(len(report.pcr_hash) > 0)
        self.assertIn(report.pcr_hash, report.quote)


if __name__ == "__main__":
    unittest.main()
