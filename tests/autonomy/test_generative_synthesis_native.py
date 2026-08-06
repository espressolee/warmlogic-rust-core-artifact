import asyncio
import os
import shutil
import sys
import tempfile
import unittest

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from warm_logic.kernel.autonomy.codex import LogicGap
from warm_logic.kernel.autonomy.patcher import AutonomousPatcher
from warm_logic.kernel.autonomy.reasoning import ReasoningSynthesizer


class TestGenerativeSynthesisNative(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        sys.path.insert(0, self.td)

    def tearDown(self):
        shutil.rmtree(self.td)
        sys.path.remove(self.td)

    def test_reasoning_synthesizer_heuristic(self):
        rs = ReasoningSynthesizer()
        code, test = rs.synthesize_logic("add_numbers", "Adds two numbers")
        self.assertIn("return a + b", code)
        self.assertIn("assert 1 + 1 == 2", test)

    def test_reasoning_synthesizer_noop(self):
        rs = ReasoningSynthesizer()
        code, test = rs.synthesize_logic("unknown_func", "idk")
        self.assertIn("pass", code)
        self.assertIn("def test_noop(): pass", test)

    def test_patch_application(self):
        # Create stub
        stub_file = os.path.join(self.td, "math_logic.py")
        with open(stub_file, "w") as f:
            f.write("def add(a, b):\n    raise NotImplementedError()\n")

        patcher = AutonomousPatcher(root_path=self.td)
        gap = LogicGap(
            file_path=stub_file, line_number=2, description="add stub", gap_type="Stub"
        )

        async def run_patch():
            return await patcher.apply_patch(gap, strategy="generative")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(run_patch())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        self.assertTrue(success)

        # Verify content
        with open(stub_file, "r") as f:
            content = f.read()
        self.assertIn("return a + b", content)


if __name__ == "__main__":
    unittest.main()
