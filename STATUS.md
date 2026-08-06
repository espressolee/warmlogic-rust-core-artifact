# Status

**Repository:** `espressolee/warmlogic-rust-core-artifact`

Sanitized, versioned Rust research artifact for bounded post-quantum signing and governance experiments; not the current WarmLogic canonical.

**Versioned research artifact.** This repository is a sanitized snapshot of a
single-host post-quantum signing and governance kernel, exported **without its
private development history**.

- `NOT` the current canonical/authority tree of the project.
- `NOT` an actively supported product; there is no roadmap or support SLA here.
- `NOT` production software and `NOT` externally audited or independently
  reproduced.

What it is: real ML-DSA-65 (FIPS 204) signatures, real AES-256-GCM, an
in-process BFT implementation, and a Python governance layer — with low test
coverage (6.76%) and known gaps. Every capability claim is graded against
re-runnable evidence in [docs/CLAIM_EVIDENCE.md](docs/CLAIM_EVIDENCE.md); read
that before trusting anything else.

Reproduction: built and sanity-checked from a clean checkout by the author
under a recorded environment (see PUBLIC_PROVENANCE.json). **Independent
reproduction has not yet been done.**
