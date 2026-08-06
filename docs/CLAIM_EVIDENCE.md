# Claim ↔ Evidence Ledger

Every capability claim this repository makes, graded against evidence you can
re-run. Grades are deliberately harsh; a claim without a passing, currently-
executing check does not get credit for intention.

**Grades**
- `VERIFIED_IN_CI` — a green, currently-triggering CI job exercises it on every push
- `TESTED_LOCAL` — reproducible local test exists and passed at the stated commit; not in CI
- `IMPLEMENTED_UNVERIFIED` — code exists and compiles; no test exercises the claim
- `GATED_OFF` — code exists behind a feature flag that default and release builds do not enable
- `STUB` — the code path returns fixed/fake values
- `NOT_PRESENT` — nothing implements the claim

| Claim | Grade | Evidence / how to re-check |
|---|---|---|
| ML-DSA-65 (FIPS 204) keygen, sign, verify | `TESTED_LOCAL` — **downgraded from `VERIFIED_IN_CI`** | `fips204` crate (real lattice implementation, not a wrapper stub). The roundtrip runs as the last step of `scripts/ci_core.sh`, verified on a clean checkout with `VIRTUAL_ENV` unset and `maturin` absent. It is **not** `VERIFIED_IN_CI`: by the grade's own definition that needs a *green* run, and this repository has no green Core CI run yet. The previous text also cited a job — CI Core "Verify Rust Core exports" — that exists only in the private 54-workflow repo, not here. Upgrades to `VERIFIED_IN_CI` when Core CI is green on the exact commit. Re-check: `bash scripts/ci_core.sh` |
| ML-KEM-768 (FIPS 203) encapsulation | `TESTED_LOCAL` | `fips203` crate, `MLKEM` class exported to Python. Unit-tested; no dedicated CI job asserts KEM roundtrips. |
| AES-256-GCM authenticated encryption | `TESTED_LOCAL` | `aes-gcm` crate (real AEAD). Exercised inside crypto unit tests; no dedicated CI assertion. |
| BFT consensus | `TESTED_LOCAL`, single-host only | 34 unit tests in `consensus/bft.rs` pass. No multi-node deployment has ever been exercised by a currently-enabled CI job (the multinode E2E gate is deliberately disabled — see below). |
| Zero-knowledge proofs (Groth16 / BLS12-381) | `DOES_NOT_BUILD` | Measured 2026-08-06: `cargo check --features zk` fails (21 errors). Arkworks Groth16 code exists, but the feature has never compiled in this state, is not enabled in default builds or the Python wheel, and `zk/aggregator.rs` holds a fixed `[0x11; 32]` placeholder. Two modules importing a `dusk_plonk` crate that is not a dependency at all were deleted as unbuildable; the remaining errors are consumers of that removed module. The wheel ships the *deprecated* Sigma-protocol `proof_zk` instead. Treat every ZK claim as unimplemented. |
| Kani formal verification harnesses | `IMPLEMENTED_UNVERIFIED` | Harness code exists (`verification_kani.rs`); **no CI job runs `cargo kani`**. The runtime `#[test]`s in that file do run; the proofs do not. |
| TLA+ model checking | `NOT_PRESENT` (as verification) | Three `.tla` spec files exist as documents. The workflow that referenced TLC could never trigger (its path filters point at directories that do not exist) and its target model path was absent; it has been removed. Specs are design documents, not checked models. |
| Hardware attestation (TPM 2.0 / Apple Secure Enclave) | `GATED_OFF` / platform-conditional | Code paths exist (`tpm` feature, macOS SEP). Default builds fall back to a software HSM. CI runners exercise the software path only. |
| Post-quantum federation (mesh, Kademlia DHT, gossip) | `TESTED_LOCAL`, single-host | Unit and loopback tests pass; `RustDHT` Python bridge is **not** exported (its implementation drifted from the current kademlia API and is retained un-wired). |
| Conviction voting / governance engine | `TESTED_LOCAL` | `voting.rs` + Python governance layer, exercised by kernel test suites. |
| Test suite | measured 2026-08-06 | Rust: the CI-exercised `-p <pkg> --lib` set is green. Python: 3,051 tests collected; the CI-exercised subset (`tests/ci`, `tests/docs`, 57 tests) is green. **22 modules fail to collect** (imports of `warm_logic_core.performance` / `.plugins.enhanced_loader` / `.os.event_bus` etc. that do not exist — a pre-existing debt, not from this cleanup) and `test_autonomy_surgical` fails on hosts without a TPM. The full strict suite is NOT green; do not read "tests pass" as more than the CI-exercised subset. |
| Line coverage | 6.76% (1,226 / 18,145) | Last measured snapshot; see README Validation Snapshot. This number is the strongest single argument against production use. |
| Multi-node production readiness | `NOT_PRESENT` | The full-suite live-E2E gate (`ci-production-gate`) is deliberately disabled: it cannot pass on this codebase today. Single-host research prototype is the accurate description. |
| Independent security review | `NOT_PRESENT` | Never performed. Known debt is public: bandit 64 medium findings, 49 pip-audit findings on the pinned lockfile, three RUSTSEC waivers with no upstream fix (documented in `rust_core/deny.toml` / `.cargo/audit.toml`). |

| SDK signing path (`SovereignClient`) | `NOT_REACHABLE` | Measured on a clean checkout 2026-08-06: `propose_action(..., require_signature=True)` raises. The hardened bridge calls a Rust `MoralGateway` that is deliberately **not** registered (the Rust implementation is a fail-open stub that ALLOWed `delete_all`), so evaluation falls back to the Python path, which refuses to sign. On the default path `decision.signature` is `None`. ML-DSA-65 signing itself works when called directly (`warm_logic_rs.generate_keypair` / `sign` / `verify`). |

## What this repository is

A **single-host research prototype of a post-quantum signing and governance
kernel**: real ML-DSA-65 signatures, real AES-256-GCM, a BFT implementation
tested in-process, and a Python governance layer — with low test coverage and
no independent review. Claims above that grade below `VERIFIED_IN_CI` should
be treated as engineering intent, not delivered capability.

## Standing decisions this ledger records

- The publication lineage is a **squashed single commit**. This intentionally
  severs git-level merge ancestry with any prior history; synchronization with
  other working copies is by file content, not by merge. (Content-hash
  comparison, not path comparison, is the correct way to diff against it.)
- Provenance signing keys were rotated on 2026-08-06 (the prior keys
  were treated as leaked). The tracked public keys and signed
  constitution/manifest are the post-rotation set; the private keys are
  local-only and gitignored.
- `ci-security` and `ci-production-gate` are disabled on purpose; re-enabling
  them without fixing the debt they measure would produce red noise, and
  deleting the debt from this ledger without fixing it would be a lie.

## On patents and prior art

The components this repository builds on are individually well-covered by
published prior art: the authorization model follows Google's Zanzibar paper
(2019); consensus follows Raft (2014) and PBFT (1999); the ZK-friendly hash is
Poseidon (2019); the post-quantum primitives are NIST standards (FIPS 203/204)
consumed from third-party crates; the signed-policy pattern is the shape used by
TUF, in-toto, Sigstore and signed OPA bundles.

No patent has been applied for, and none is planned. The reason is economic —
any claim that survived would be narrow, easy to design around, and there is no
product, licensee, or enforcement capacity behind it, so the expected value is
below the cost of filing and maintenance.

That is a business decision, **not** a legal finding. This project has not run a
prior-art search or produced a claim chart, so the novelty of the *combination*
is unmeasured (novelty and inventive step are assessed differently, and neither
was assessed here). Nothing here is a freedom-to-operate opinion either: no
third-party patent clearance has been performed.

*Maintained under the rule: no claim outlives its evidence. If you re-measure
and a row is wrong, the row — not the measurement — is the bug.*
