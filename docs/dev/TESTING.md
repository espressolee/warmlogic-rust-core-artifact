# 🧪 WarmLogic Testing Guide

> **Purpose**: How to run, write, and understand tests in WarmLogic.

---

## Quick Commands

| Action                 | Command                                            |
| :--------------------- | :------------------------------------------------- |
| Run all tests          | `pytest tests/`                                    |
| Run with coverage      | `pytest tests/ --cov=warm_logic --cov-report=html` |
| Run fast tests only    | `pytest tests/ -m "not slow"`                      |
| Run specific test file | `pytest tests/security/test_slashing.py`           |
| Run Rust tests         | `cd warm_logic_rs && cargo test`                   |

---

## Test Structure

```
tests/
├── e2e/                    # End-to-end integration tests
├── evolution/              # Self-evolution and mutation tests
├── mesh/                   # DHT and networking tests
├── persistence/            # Storage and encryption tests
├── security/               # Cryptography and slashing tests
├── autonomy/               # Autonomous patching tests
└── system/                 # System-level integration tests
```

---

## Running Tests

### Python Tests

```bash
# Activate environment
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with verbose output
pytest tests/ -v --tb=long

# Run tests matching a pattern
pytest tests/ -k "slashing"

# Run parallel (faster)
pytest tests/ -n auto
```

### Rust Tests

```bash
cd warm_logic_rs

# Run all Rust tests
cargo test

# Run specific module
cargo test crypto

# Run with output
cargo test -- --nocapture
```

---

## Test Categories

### Unit Tests
Test individual functions and classes in isolation.

```bash
pytest tests/security/ -v
pytest tests/persistence/ -v
```

### Integration Tests
Test multiple components working together.

```bash
pytest tests/e2e/ -v
pytest tests/system/ -v
```

### Property-Based Tests
Use `hypothesis` for generative testing.

```bash
pytest tests/autonomy/test_formal_verification.py -v
```

---

## Writing New Tests

### Python Test Template

```python
# tests/my_module/test_feature.py
import pytest

class TestMyFeature:
    def test_basic_case(self):
        """Test the basic functionality."""
        result = my_function(input_data)
        assert result == expected_output

    def test_edge_case(self):
        """Test edge cases and error handling."""
        with pytest.raises(ValueError):
            my_function(invalid_input)

    @pytest.mark.slow
    def test_expensive_operation(self):
        """Mark slow tests so they can be skipped."""
        pass
```

### Rust Test Template

```rust
// src/my_module.rs
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_case() {
        let result = my_function(input);
        assert_eq!(result, expected);
    }
}
```

---

## Coverage Reports

```bash
# Generate HTML coverage report
pytest tests/ --cov=warm_logic --cov-report=html

# View report
open htmlcov/index.html

# Generate terminal summary
pytest tests/ --cov=warm_logic --cov-report=term-missing
```

---

## CI/CD Integration

Tests run automatically on:
- Push to `main` branch
- Pull request creation
- Manual trigger via GitHub Actions

See `.github/workflows/ci-main-tests.yml` for configuration.

---

## Troubleshooting Tests

| Issue                 | Solution                                |
| :-------------------- | :-------------------------------------- |
| `ModuleNotFoundError` | Run `pip install -e .`                  |
| Rust tests fail       | Run `maturin develop --release` first   |
| Timeout errors        | Increase timeout: `pytest --timeout=60` |
| Fixture not found     | Check `conftest.py` imports             |

---

## Next Steps

- CONTRIBUTING.md - How to contribute code
- ARCHITECTURE.md - Understand the codebase
