# External Coder Protocol (Rule-Only, No-Arbitration) — v1.0 (2025-12-31)

Purpose
- Evaluate applicability and failure boundaries of PASS under adversarial/federated settings.
- Characterization, not optimization; disagreement is expected and preserved.

Role of External Coder
- Independent applier of the frozen rulebook; not a co-author/validator/adjudicator.

Inputs Provided
1) PASS rulebook (v1.x, frozen)
2) Case packets (public artifacts only; synthetic cases explicitly labeled)
3) Coding sheet template (CSV)
4) Claim–evidence map (IDs only; no author labels)

Prohibited Actions
- Inferring author intent or expected labels
- Introducing weights/repairs/reinterpretations
- Arbitrating disagreements or “fixing” ambiguous rules
- Using non-provided private sources (optional public search allowed if logged)

Outputs Required
- Completed CSV (one row per ⟨case × stage × indicator⟩)
- ≤5 brief comments on ambiguity/boundaries
- Submission deadline: T+72 hours

Independence & Ethics
- Declare no conflicts; conflicting outcomes are acceptable and published.
- Public/synthetic inputs only; no personal data; coder anonymity by default.

Time Budget
- 3–4 hours total.

Result Handling
- κ reported at node, aggregation, and overall levels (3-class incl. INDET + decidable-only).
- No arbitration or post-hoc tuning; disagreements preserved verbatim.
