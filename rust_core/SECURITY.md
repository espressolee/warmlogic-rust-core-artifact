# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### Contact

- **Email**: https://github.com/espressolee/warmlogic-rust-core-artifact/security
- **PGP Key**: Available upon request

### What to Include

1. **Description**: Clear description of the vulnerability
2. **Impact**: Potential impact and severity assessment
3. **Steps to Reproduce**: Detailed reproduction steps
4. **Proof of Concept**: Code or screenshots if applicable
5. **Suggested Fix**: Optional but appreciated

### Response Timeline

| Phase | Timeline |
|-------|----------|
| Initial Response | Within 48 hours |
| Severity Assessment | Within 7 days |
| Fix Development | Based on severity |
| Public Disclosure | After fix release |

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| CRITICAL | Remote code execution, key extraction | 24-48 hours |
| HIGH | Authentication bypass, data leak | 7 days |
| MEDIUM | DoS, information disclosure | 14 days |
| LOW | Minor issues | 30 days |

## Scope

### In Scope

- Core cryptographic operations (`crypto.rs`)
- Hardware security modules (`hardware/`)
- Consensus engine (`consensus/`)
- Network transport (`net/`)
- Ledger state machine (`ledger.rs`)
- Governance policy engine (`governance/`)
- Zero-knowledge proofs (`zk/`)

### Out of Scope

- Third-party dependencies (report to upstream)
- Documentation and examples
- Development/testing utilities
- UI/Dashboard components (Python)

## Bug Bounty Program

### Rewards

| Severity | Reward Range |
|----------|--------------|
| CRITICAL | $5,000 - $15,000 |
| HIGH | $2,000 - $5,000 |
| MEDIUM | $500 - $2,000 |
| LOW | $100 - $500 |

### Eligibility

- First reporter of a unique vulnerability
- Responsible disclosure followed
- Valid proof of concept provided
- Not a duplicate of known issue

### Qualifying Vulnerabilities

- Remote code execution
- Private key extraction or exposure
- Consensus manipulation
- Signature bypass or forgery
- Cryptographic weaknesses
- Memory corruption in safe Rust
- Denial of service (significant impact)

### Non-Qualifying Issues

- Issues in test or example code
- Issues requiring physical access
- Social engineering attacks
- Issues in third-party dependencies
- Previously reported issues
- Issues in unsupported versions

## Known Limitations

For transparency, these are known limitations documented in our security audit:

| Limitation | Status | Notes |
|------------|--------|-------|
| vHSM simulated keys | Documented | Use HybridHSM for production |
| TPM 2.0 framework only | Pending | Linux hardware testing needed |
| Single-bucket DHT | Documented | Performance only, not security |
| No formal UC proof | Planned | Academic collaboration |

## Security Audit

Our current security score is **96/100**.

For detailed security information, see:
- [SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md)
- [SECURITY_FINDINGS.md](docs/SECURITY_FINDINGS.md)
- [CHANGELOG.md](CHANGELOG.md)

## Acknowledgments

We thank the following researchers for responsible disclosure:

| Researcher | Vulnerability | Date |
|------------|---------------|------|
| *None yet* | - | - |

## License

This security policy is part of the WarmLogic project under Apache-2.0 license.
