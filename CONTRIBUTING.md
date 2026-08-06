# Contributing to WarmLogic

Thank you for your interest in contributing to WarmLogic. This document covers the development setup, PR workflow, commit conventions, and project rules you need to know before opening issues or pull requests.

---

## Prerequisites

- **Python 3.12+**
- **Rust 1.75+** (stable toolchain)
- **maturin** (for building the Rust extension)
- **Git** with commit hooks support

---

## Development Setup

```bash
# Clone the repository
git clone https://github.com/espressolee/WarmLogic
cd warmlogic

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install Python dependencies
pip install -r requirements.txt

# Build the Rust core in development mode
pip install maturin
cd rust_core && maturin develop && cd ..

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Verify Setup

```bash
# Run quick tests
pytest -m "not slow"

# Check linting
flake8 && black --check . && isort --check .

# Type checking
mypy --strict warm_logic/
```

---

## SSOT Hierarchy

WarmLogic follows a strict Single Source of Truth hierarchy. Changes at a higher level take precedence:

```
1. Schema  (spec/schema/)         -- highest authority
2. Spec    (docs/)                -- must conform to schema
3. Code    (warm_logic/, rust_core/)  -- implements spec
4. Test    (tests/)               -- validates spec
```

When making changes, ensure consistency across all affected layers. If your change contradicts a higher layer, the higher layer wins — propose a schema/spec change first.

---

## How to Contribute

### 1. Open an Issue First

For significant changes (new features, architectural changes, protocol modifications), open an issue before writing code. Use the templates in `.github/ISSUE_TEMPLATE/`.

### 2. Create a Focused PR

Each pull request should:

- Target a single concern (one feature, one bug fix)
- Include tests (unit and/or integration)
- Pass lint and format checks (`flake8`, `black`, `isort`)
- Pass type checking (`mypy --strict` for core modules)
- Update documentation if the change is user-facing
- Reference the related issue number

### 3. P-Series Rules

WarmLogic uses a P-Series system to track features and milestones:

| Range     | Status  | Modification Allowed |
| --------- | ------- | -------------------- |
| P0-P299   | Sealed  | Bug fixes only       |
| P300-P399 | Active  | Free to modify       |
| P400+     | Planned | Documentation only   |

For changes that touch sealed P-Series (P0-P299), include justification in the PR description and link to a GOVDEC document if one exists.

### 4. Tier-0 Changes

The following paths are Tier-0 (highest governance):

- `spec/**`
- `docs/protocol/**`
- `meta/**`
- `spec/schema/**`

Meaningful changes to Tier-0 files **must** be linked to a P-Series ID in the commit message.

---

## Commit Message Format

```
<type>(<scope>): [Pxx] summary

Body explaining what and why (not how).

Implements: P[XXX]-P[YYY]
Evidence: [path to evidence artifacts]

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### Types

| Type       | Usage                                   |
| ---------- | --------------------------------------- |
| `feat`     | New feature                             |
| `fix`      | Bug fix                                 |
| `docs`     | Documentation only                      |
| `refactor` | Code restructuring (no behavior change) |
| `test`     | Adding or updating tests                |
| `perf`     | Performance improvement                 |
| `chore`    | Build, CI, tooling changes              |
| `revert`   | Reverting a previous commit             |

### Scope

Use the subsystem or module name: `os`, `devloop`, `evidence`, `console`, `runtime-suite`, `governance`, `schema`, `crypto`, `consensus`, etc.

### Examples

```
feat(crypto): [P302] add ML-KEM key exchange support
fix(consensus): [P245] handle duplicate vote edge case in BFT engine
docs(protocol): fix typo in WLPv3 scope section (non-P)
test(ledger): [P310] add chaos testing for network partition recovery
```

### Gitlint

The script `scripts/gitlint_warmlogic.py` enforces commit message rules. Set up the hook:

```bash
# .git/hooks/commit-msg
#!/usr/bin/env bash
scripts/gitlint_warmlogic.py "$1"
```

---

## Branch Naming

| Branch        | Purpose                                       |
| ------------- | --------------------------------------------- |
| `main`        | Single source of truth. Must never break.     |
| `pXX-<slug>`  | P-Series feature branch (e.g., `p302-ml-kem`) |
| `fix/<slug>`  | Hotfix branch                                 |
| `exp/<slug>`  | Experimental branch                           |
| `docs/<slug>` | Documentation-only branch                     |

One branch targets one P-Series item.

---

## Coding Standards

### Python

- Python 3.12+, 4-space indentation
- Explicit imports (no wildcard `from x import *`)
- Core modules (`warm_logic/`) must pass `mypy --strict`
- Format with `black`, sort with `isort --profile black`
- Lint with `flake8`
- Prefer reproducible outputs under `out/`
- No network I/O in unit tests

### Rust

- Follow `clippy` warnings — the project uses `#![deny(clippy::unwrap_used)]`
- No `.unwrap()` or `.expect()` in library code
- Use `thiserror` for error types
- Run `cargo clippy --all-targets` before submitting

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run -a  # Run on all files
```

Hooks include: `black`, `flake8`, `isort`, Rust formatting checks.

---

## Testing

```bash
# Quick tests (default for PRs)
pytest -m "not slow"

# Full suite
pytest

# Rust tests (requires std and persistence features)
cd rust_core && cargo test --features "std,persistence" && cd ..

# Coverage report
pytest --cov=warm_logic --cov-report=html
```

Tests should be reproducible and not depend on external services. Mock network calls. Use fixtures for temporary databases.

---

## Where to Contribute

| Area                                 | Difficulty | Impact   | Status   |
| ------------------------------------ | ---------- | -------- | -------- |
| P2P block propagation (StitchServer) | Hard       | Critical | Open     |
| Third-party security audit           | Hard       | Critical | Open     |
| CLI tool (`wlctl`) improvements      | Medium     | High     | Open     |
| WASM target support                  | Medium     | High     | Alpha    |
| Documentation and tutorials          | Easy       | High     | Open     |
| Cross-platform hardware attestation  | Hard       | Medium   | Open     |
| AI framework integration (LangChain) | Medium     | Medium   | Open     |
| UC security proof for ZK protocol    | Hard       | Medium   | Open     |
| Kani harness expansion               | Medium     | Medium   | Open     |
| ML-KEM-768 performance optimization  | Medium     | Medium   | Open     |

---

## Governance and Evidence

When touching governance, consensus, or evidence paths:

- Link to the relevant GOVDEC document
- Include a minimal evidence set (manifests, audit JSON)
- For protocol changes, propose an RFC with design rationale and backward compatibility analysis

---

## CI

Pull requests trigger:
- Lint checks (`flake8`, `black`, `isort`, `mypy`)
- Quick test suite (`pytest -m "not slow"`)
- Rust build and test (`cargo test`)
- Security scanning (`detect-secrets`)

Nightly builds run the full test suite, coverage reports, and dashboard audits.

---

## Security Reporting

**Do not create public issues for security vulnerabilities.** See [SECURITY.md](SECURITY.md) for the reporting process.

---

## Getting Help

- **GitHub Discussions**: Questions, ideas, RFC proposals
- **Issues**: Bug reports and feature requests
- [Docs Index](docs/INDEX.md)
- [Troubleshooting Guide](docs/ops/TROUBLESHOOTING.md)

---

## License

By contributing to WarmLogic, you agree that your contributions will be licensed under the **Apache License 2.0**, matching this repository's `LICENSE` file. That is the only licence this repository is offered under; if you find any other licence named anywhere in this tree, it is an error — please report it.
