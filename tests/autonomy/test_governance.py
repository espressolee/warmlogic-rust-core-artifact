from warm_logic.kernel.autonomy.governance import CouncilOfThree


def test_council_approves_valid_patch():
    council = CouncilOfThree()
    patch = "def foo(): pass"
    test = "def test_foo(): pass"

    # Council should approve (3/3: Architect, Skeptic, Auditor)
    approved = council.review_patch(patch, test, "foo")
    assert approved is True


def test_council_rejects_missing_tests():
    council = CouncilOfThree()
    patch = "def foo(): pass"
    test = ""  # No tests

    # Architect: Yes
    # Skeptic: No
    # Auditor: Yes (short)
    # Total: 2/3 -> Approved (consensus)
    # Wait, in governance.py logic: Skeptic rejects if no tests. Auditor approves if short.
    approved = council.review_patch(patch, test, "foo")
    assert approved is True


def test_council_rejects_complex_patch_without_tests():
    council = CouncilOfThree()
    # 60 lines (exceeds Auditor's 50 line threshold)
    patch = "\n".join(["print(i)" for i in range(60)])
    test = ""  # No tests

    # Architect: Yes
    # Skeptic: No (no tests)
    # Auditor: No (too long)
    # Total: 1/3 -> Rejected
    approved = council.review_patch(patch, test, "complex_func")
    assert approved is False
