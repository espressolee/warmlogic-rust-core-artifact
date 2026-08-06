from warm_logic.kernel.constitution import ConstitutionalGuard, constitutional_audit


def _make_guard() -> ConstitutionalGuard:
    guard = ConstitutionalGuard()
    # Keep tests deterministic even if local signed constitution is missing/invalid.
    guard.constitution = {
        "sensitive_keywords": ["BANANA"],
        "entropy_threshold": 5.5,
        "defense_level": 100,
    }
    return guard


def test_keyword_blocking():
    guard = _make_guard()
    text = "I have a BANANA in my hand."
    safe_text, violations = guard.sanitize(text)

    print(f"Original: {text}")
    print(f"Sanitized: {safe_text}")
    print(f"Violations: {violations}")

    assert "BANANA" not in safe_text
    assert "[REDACTED_BY_CONSTITUTION]" in safe_text
    assert violations == 1


def test_entropy_blocking():
    guard = _make_guard()
    # Very high entropy string
    high_entropy_text = (
        'asdfghjkl1234567890!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:"ZXCVBNM<>?±'
    )
    safe_text, violations = guard.sanitize(high_entropy_text)

    print(
        f"High Entropy Text Entropy: {guard.calculate_entropy(high_entropy_text):.2f}"
    )
    print(f"Sanitized: {safe_text}")
    print(f"Violations: {violations}")

    assert "[❌ OUTPUT BLOCKED: HIGH ENTROPY DETECTED]" in safe_text
    assert violations == 1


def test_safe_text():
    guard = _make_guard()
    text = "This is a normal sentence with low entropy."
    safe_text, violations = guard.sanitize(text)

    assert safe_text == text
    assert violations == 0


if __name__ == "__main__":
    print("Running Constitutional Guard Tests...")
    test_keyword_blocking()
    print("-" * 20)
    test_entropy_blocking()
    print("-" * 20)
    test_safe_text()
    print("✅ All tests passed.")
