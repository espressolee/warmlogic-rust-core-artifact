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
under a recorded environment (see PUBLIC_PROVENANCE.json), re-verified with
`VIRTUAL_ENV` unset and `maturin` absent. **Independent reproduction has not
yet been done.**

## Support boundary

Naming this explicitly, because "the code is present" was repeatedly read as
"the capability is supported".

**Supported** — exercised by `scripts/ci_core.sh`, which is the same script CI
runs and the one an external reproducer should run:

- ML-DSA-65 keygen / sign / verify via the Rust extension
- building the extension from source and importing it
- the narrow test subset `tests/ci` and `tests/docs`

**Present but NOT supported** — code exists; the capability is not claimed, not
exercised, and should not be relied on or cited:

| Surface | Why not supported |
|---|---|
| Governance enforcement (SDK / `MoralGateway`) | Fail-open paths exist: the Python fallback denies three fixed strings and otherwise allows; hardened evaluation accepts an intent with no signature |
| Constitution amendment / killpulse | Demonstration stubs — an amendment checks only that a signature string is non-empty; the killpulse matches a fixed string |
| BFT consensus | In-process only; never deployed across hosts |
| Zero-knowledge proofs | Does not compile |
| Formal verification (Kani / TLA+) | Harnesses and specs exist; no job runs them |
| Hardware-rooted trust | Host-identifier-derived demonstration seal, not TPM/SEP-backed |
| Audit trail | Writes to stdout; not a durable or tamper-evident ledger |
| MCP server (`src/warm_logic/app/sdk/mcp-server`) | Fail-open by construction: `check_veto` maps only five action strings to the `finance` and `ops` packs, and everything else returns `allowed: true, reason: "no_governance_policy_found"`. A caller cannot distinguish that from a policy that ran, because an allow that passed the pack returns `reason: "validated_by_warmlogic"`. Never built or exercised by `scripts/ci_core.sh` |

Reporting a bug in the second table is welcome as an accuracy correction. It
will not be fixed as a product defect — see the maintenance scope in
`CONTRIBUTING.md`.
