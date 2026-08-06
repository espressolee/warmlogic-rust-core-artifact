# Contributing to WarmLogic Rust Core

Thank you for your interest in contributing to WarmLogic Rust Core. This document provides guidelines and instructions for contributing.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Coding Standards](#coding-standards)
5. [Commit Guidelines](#commit-guidelines)
6. [Pull Request Process](#pull-request-process)
7. [Testing Requirements](#testing-requirements)
8. [Security](#security)

---

## Code of Conduct

This project adheres to a code of conduct. By participating, you agree to uphold a respectful and inclusive environment.

---

## Getting Started

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Rust | 1.75+ |
| Python | 3.11+ (for bindings) |
| cargo-audit | Latest |

### Quick Start

```bash
# Clone the repository
git clone https://github.com/espressolee/WarmLogic
cd rust_core

# Build
cargo build

# Test
cargo test

# Lint
cargo clippy --all-features
```

---

## Development Setup

### Environment Configuration

```bash
# Install Rust (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Add components
rustup component add clippy rustfmt

# Install cargo-audit for security checks
cargo install cargo-audit

# Optional: Install maturin for Python bindings
pip install maturin
```

### IDE Setup

**VS Code** (Recommended):
- Install rust-analyzer extension
- Install Even Better TOML extension

**Settings**:
```json
{
  "rust-analyzer.checkOnSave.command": "clippy",
  "rust-analyzer.checkOnSave.allFeatures": true
}
```

---

## Coding Standards

### Rust Style

1. **Format**: Always run `cargo fmt` before committing
2. **Linting**: Code must pass `cargo clippy --all-features -- -D warnings`
3. **Documentation**: Public APIs must have doc comments
4. **Error Handling**: Use `Result<T, E>` for fallible operations, not panics

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Structs | PascalCase | `BFTEngine` |
| Functions | snake_case | `cast_vote_verified` |
| Constants | SCREAMING_SNAKE | `MAX_VOTES_PER_ROUND` |
| Features | kebab-case | `sep-hardware` |

### Security Requirements

| Requirement | Mandatory |
|-------------|-----------|
| No hardcoded secrets | Yes |
| Zeroize sensitive data | Yes |
| Use `Result<>` not panics | Yes |
| Validate all inputs | Yes |
| Random nonces (no reuse) | Yes |

### Module Structure

```rust
//! Module documentation
//!
//! Detailed explanation of module purpose.

// Standard library imports
use std::collections::HashMap;

// External crate imports
use sha3::Sha3_256;

// Internal imports
use crate::crypto;
use super::types;

// Type definitions
pub struct MyStruct { ... }

// Implementation
impl MyStruct { ... }

// Tests (at bottom)
#[cfg(test)]
mod tests { ... }
```

---

## Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `security` | Security fix |
| `docs` | Documentation |
| `refactor` | Code refactoring |
| `test` | Adding tests |
| `chore` | Maintenance |

### P-Series Protocol (WarmLogic-specific)

WarmLogic uses P-Series bands for tracking changes:

| Band | Description |
|------|-------------|
| P0xx | Foundation & Identity |
| P1xx | Consensus & Ledger |
| P2xx | Mesh & Networking |
| P3xx | Governance & Sovereignty |
| P4xx | DevOps |

**Example**:
```
P3xx: feat(governance): Add HybridHSM for hardware attestation + PQC

- Combines ECDSA P-256 (SEP) with ML-DSA-65 (software)
- Provides quantum resistance with hardware binding
- Adds sep-hardware feature flag for macOS

Closes #123
```

---

## Pull Request Process

### Before Submitting

1. **Tests Pass**: `cargo test --all-features`
2. **Lint Clean**: `cargo clippy --all-features -- -D warnings`
3. **Format**: `cargo fmt --check`
4. **Security Audit**: `cargo audit`
5. **Documentation**: Update relevant docs if needed

### PR Template

```markdown
## Summary
Brief description of changes

## Changes
- Change 1
- Change 2

## Testing
How was this tested?

## Security Impact
Does this affect security? If yes, describe.

## Checklist
- [ ] Tests pass
- [ ] Clippy clean
- [ ] Documentation updated
- [ ] CHANGELOG updated (if applicable)
```

### Review Process

1. At least 1 approval required
2. CI must pass
3. Security-sensitive changes require security team review

---

## Testing Requirements

### Test Coverage

| Module | Minimum Coverage |
|--------|------------------|
| `crypto` | 85% |
| `consensus` | 80% |
| `hardware` | 75% |
| `net` | 80% |

### Test Types

```bash
# Unit tests
cargo test

# With all features
cargo test --all-features

# Specific module
cargo test consensus::

# With output
cargo test -- --nocapture

# Doc tests
cargo test --doc
```

### Writing Tests

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_function_name() {
        // Arrange
        let input = ...;

        // Act
        let result = function_under_test(input);

        // Assert
        assert_eq!(result, expected);
    }

    #[test]
    #[should_panic(expected = "specific message")]
    fn test_panic_condition() {
        // ...
    }
}
```

### Property-Based Testing

We use `proptest` for property-based tests:

```rust
proptest::proptest! {
    #[test]
    fn test_property(input in 0u64..1000) {
        // Property that must hold for all inputs
        assert!(property_holds(input));
    }
}
```

---

## Security

### Reporting Vulnerabilities

**DO NOT** open public issues for security vulnerabilities.

Contact: https://github.com/espressolee/WarmLogic/security

See [SECURITY.md](SECURITY.md) for full security policy.

### Security Checklist for Contributors

- [ ] No hardcoded keys or secrets
- [ ] Sensitive data wrapped in `Zeroizing<T>`
- [ ] All cryptographic operations use NIST-approved algorithms
- [ ] Input validation on public APIs
- [ ] No `unwrap()` or `expect()` in production code paths
- [ ] Rate limiting on network operations
- [ ] Signature verification before trust

---

## Questions?

- Open a Discussion on GitHub
- Join the community chat (TBD)

---

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 license.
