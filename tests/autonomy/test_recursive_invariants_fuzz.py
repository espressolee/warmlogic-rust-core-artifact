import os
import random
import shutil
import string
import sys
import tempfile
import unittest

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from warm_logic.kernel.autonomy.auditor import RecursiveDebtAuditor


class TestRecursiveInvariantsFuzz(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.td)

    def test_auditor_fuzz_stability(self):
        """Invariant: Auditor never crashes on random file content."""
        auditor = RecursiveDebtAuditor(root_path=self.td)

        for i in range(100):
            # Generate random filename and content
            fname = "".join(random.choices(string.ascii_lowercase, k=8)) + ".py"
            content = "".join(
                random.choices(
                    string.ascii_letters + string.punctuation.replace("\\", "") + "\n",
                    k=random.randint(10, 1000),
                )
            )

            p = os.path.join(self.td, fname)
            with open(p, "w") as f:
                f.write(content)

            try:
                auditor.scan_all()
            except Exception as e:
                self.fail(
                    f"Auditor crashed on iteration {i} with content len {len(content)}: {e}"
                )

            # Cleanup for next iter
            os.remove(p)

        print("\n✅ [Fuzz] Auditor survived 100 iterations of garbage input.")


if __name__ == "__main__":
    unittest.main()
