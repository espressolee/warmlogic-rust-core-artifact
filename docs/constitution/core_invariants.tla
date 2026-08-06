---------------- MODULE core_invariants ----------------
EXTENDS Naturals, Sequences

CONSTANTS 
    Artifacts,          \* Set of all possible artifacts (data, models)
    Signatures,         \* Set of valid cryptographic signatures
    TrustedRoots        \* Set of initial trusted artifacts

VARIABLES 
    ledger,             \* The Refusal Spine (Sequence of Events)
    execution_state,    \* Current execution status
    provenance_graph    \* Graph of artifact lineage

----------------------------------------------------------------

\* Type Invariants
TypeOK == 
    /\ ledger \in Seq([type: {"REFUSAL", "EXECUTION"}, reason: STRING])
    /\ execution_state \in {"IDLE", "RUNNING", "BLOCKED"}
    /\ provenance_graph \in [Artifacts -> SUBSET Artifacts]

\* lineage(a) is the set of all ancestors of artifact a
RECURSIVE lineage(_)
lineage(a) == 
    let parents == provenance_graph[a] IN
    parents \cup UNION {lineage(p) : p \in parents}

\* Trusted(a) is true iff all lineage paths lead to a trusted root
Trusted(a) ==
    /\ lineage(a) \ne {}
    /\ \A ancestor \in lineage(a): 
        (provenance_graph[ancestor] = {}) => (ancestor \in TrustedRoots)

----------------------------------------------------------------

\* SAFETY INVARIANT: No Execution Without Provenance
\* "If the system is executing artifact a, then a must be Trusted."
MethodologicalIntegrity == 
    (execution_state = "RUNNING") => 
    (\A a \in Artifacts: (Running(a) => Trusted(a)))

\* SAFETY INVARIANT: The Refusal Ledger is Append-Only
LedgerImmutable == 
    Len(ledger') >= Len(ledger) /\ 
    \A i \in 1..Len(ledger): ledger'[i] = ledger[i]

\* LIVENESS: If an artifact is Untrusted, it MUST be Blocked
RefusalInevitability ==
    \A a \in Artifacts: 
        (~Trusted(a) /\ RequestExecution(a)) ~> (execution_state = "BLOCKED")

----------------------------------------------------------------
THEOREM Spec => []MethodologicalIntegrity
THEOREM Spec => []LedgerImmutable
================================================================
