# Known Limitations

This list is deliberately blunt. It is the honest counterpart to the README.

- **Line coverage is 6.76%** (measured). This is the single strongest argument
  against using this for anything sensitive.
- **No independent security review.** Documented static-analysis debt: bandit
  64 medium, pip-audit 49 findings on the pinned lockfile, three RUSTSEC
  waivers with no upstream fix (see `rust_core/deny.toml`).
- **Single host only.** The BFT code is exercised in-process; no multi-node
  deployment has been run. There is no production multi-node gate.
- **Zero-knowledge proofs do not build.** The `zk` feature fails to compile
  (`cargo check --features zk`), is off in default builds and the Python wheel,
  and an aggregator placeholder remains. The wheel ships a deprecated
  Sigma-protocol path. Treat all ZK claims as unimplemented.
- **SDK signing path is not reachable** through the hardened bridge on the
  default path; `decision.signature` is `None`. ML-DSA-65 signing works when
  called directly (`warm_logic_rs.generate_keypair` / `sign` / `verify`).
- **Formal verification is aspirational.** Kani harnesses exist but no CI runs
  `cargo kani`; TLA+ files are design documents, not checked models.
- **Test suite is not fully green.** 3,051 Python tests collected; the
  CI-exercised subset passes, but 22 modules fail to collect (imports of
  non-existent `warm_logic_core.*` submodules) and hardware-attestation tests
  fail on hosts without a TPM.

See docs/CLAIM_EVIDENCE.md for the per-claim grading.
