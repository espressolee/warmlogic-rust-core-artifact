import ast
import os

import pytest

from warm_logic.kernel.autonomy.auditor import RecursiveDebtAuditor


@pytest.fixture
def test_workspace(tmp_path):
    # Create a mock file with "debt"
    debt_file = tmp_path / "mock_debt.py"
    debt_content = """
def complex_function(x):
    # Complexity > 10
    if x > 0:
        if x > 1:
            if x > 2:
                if x > 3:
                    if x > 4:
                        if x > 5:
                            if x > 6:
                                if x > 7:
                                    if x > 8:
                                        if x > 9:
                                            return "too deep"
    return "ok"

def stub_function():
    \"\"\"TODO: Implement this logic properly\"\"\"
    raise NotImplementedError("Fix me")
"""
    debt_file.write_text(debt_content)
    return tmp_path


def test_auditor_detects_debt(test_workspace):
    auditor = RecursiveDebtAuditor(root_path=str(test_workspace))
    gaps = auditor.scan_all()

    # Should find 1 Complexity gap and 2 Stub gaps (1 NotImplementedError, 1 TODO)
    gap_types = [g.gap_type for g in gaps]
    assert "Complexity" in gap_types
    assert "Stub" in gap_types
    assert len(gaps) == 3

    print("\n✅ [Test] RecursiveDebtAuditor autonomously identified structural debt.")


if __name__ == "__main__":
    # Manual run support
    class MockPath:
        def __init__(self, p):
            self.p = p

        def __truediv__(self, other):
            return MockPath(os.path.join(self.p, other))

        def write_text(self, text):
            with open(self.p, "w") as f:
                f.write(text)

        def __str__(self):
            return self.p

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        ws = test_workspace(MockPath(td))
        test_auditor_detects_debt(ws)
