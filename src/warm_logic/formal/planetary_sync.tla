---------------- MODULE planetary_sync ----------------
EXTENDS Naturals, Sequences, FiniteSets, TTC

CONSTANTS 
    Nodes,         \* Set of participating nodes
    Regions,       \* Set of regions
    RegionOf,      \* Function: Node -> Region
    MinRegions     \* Minimum number of regions for quorum

VARIABLES 
    ledger,        \* Node -> Sequence of Blocks
    votes,         \* Block -> Set of Votes {<node, region>}
    committed      \* Set of committed blocks

TypeOK == 
    /\ ledger \in [Nodes -> Seq(STRING)]
    /\ votes \in [STRING -> SUBSET (Nodes \times Regions)]
    /\ committed \subseteq STRING

Init == 
    /\ ledger = [n \in Nodes |-> <<>>]
    /\ votes = [b \in STRING |-> {}]
    /\ committed = {}

CheckQuorum(block, current_votes) ==
    LET 
        voting_regions == {r[2] : r \in current_votes}
        vote_count == Cardinality(current_votes)
        region_count == Cardinality(voting_regions)
    IN
        /\ vote_count * 3 > Cardinality(Nodes) * 2  \* > 2/3 Total
        /\ region_count >= MinRegions               \* >= Min Regions

ProcessVote(n, block) ==
    LET 
        my_region == RegionOf[n]
        new_vote == <<n, my_region>>
        current_votes == votes[block] \union {new_vote}
    IN
        /\ votes' = [votes EXCEPT ![block] = current_votes]
        /\ IF CheckQuorum(block, current_votes)
           THEN committed' = committed \union {block}
           ELSE committed' = committed
        /\ UNCHANGED ledger

Next == 
    \E n \in Nodes, b \in STRING : ProcessVote(n, b)

Consistency == 
    \A b \in committed : 
        LET v == votes[b] IN
        Cardinality({r[2] : r \in v}) >= MinRegions

=======================================================
