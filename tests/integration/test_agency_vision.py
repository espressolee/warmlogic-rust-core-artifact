import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from warm_logic.kernel.intelligence.agency import AgencyExecutor


class TestAgencyVisionIntegration(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.agency = AgencyExecutor(sandbox_dir=self.td.name)

        # Create a dummy image file
        self.image_path = os.path.join(self.td.name, "test_image.png")
        with open(self.image_path, "wb") as f:
            f.write(b"fake_image_bytes")

    def tearDown(self):
        self.td.cleanup()

    @patch("warm_logic.kernel.intelligence.vision.VisionClient")
    def test_observe_visual_success(self, MockVisionClient):
        # Mock setup
        mock_instance = MockVisionClient.return_value
        mock_instance.analyze_image.return_value = (
            "A beautiful sunset over the digital ocean."
        )

        # Execute
        result = self.agency.observe_visual("test_image.png", "Describe this.")

        # Verify
        mock_instance.analyze_image.assert_called_with(
            "Describe this.", os.path.abspath(self.image_path)
        )
        self.assertEqual(result, "A beautiful sunset over the digital ocean.")

    def test_observe_visual_file_not_found(self):
        result = self.agency.observe_visual("missing.png")
        self.assertIn("Error: Image not found", result)

    @patch("warm_logic.kernel.intelligence.vision.VisionClient")
    def test_agency_execute_analyze_image_action(self, MockVisionClient):
        # Mock setup
        mock_instance = MockVisionClient.return_value
        mock_instance.analyze_image.return_value = (
            "Code screenshot containing Python function."
        )

        action = {
            "action": "analyze_image",
            "path": "test_image.png",
            "prompt": "Analyze code.",
        }

        # Execute via generic handler
        result = self.agency.execute(action)

        # Verify
        mock_instance.analyze_image.assert_called_with(
            "Analyze code.", os.path.abspath(self.image_path)
        )
        self.assertEqual(result, "Code screenshot containing Python function.")


if __name__ == "__main__":
    unittest.main()
