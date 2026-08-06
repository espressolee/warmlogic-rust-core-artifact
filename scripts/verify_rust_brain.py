import warm_logic_rs
from warm_logic_rs import BFTEngine, Vote, GeneticSelector
import random

def test_rust_brain():
    print("[Verification] Initializing Rust Brain Components...")

    # 1. Test Consensus (BFT)
    print("\n--- Testing Rust Consensus (BFT) ---")
    bft = BFTEngine(quorum_size=3)

    # Round 1
    bft.start_round(1)
    proposal_hash = "hash_of_block_123"
    bft.propose(proposal_hash)

    # Vote 1 (Honest)
    v1 = Vote("node_A", proposal_hash, "sig_A")
    committed = bft.cast_vote(v1)
    print(f" Vote 1 Cast. Committed? {committed}")

    # Vote 2 (Honest)
    v2 = Vote("node_B", proposal_hash, "sig_B")
    committed = bft.cast_vote(v2)
    print(f" Vote 2 Cast. Committed? {committed}")

    # Vote 3 (Honest - Should Commit)
    v3 = Vote("node_C", proposal_hash, "sig_C")
    committed = bft.cast_vote(v3)
    print(f" Vote 3 Cast. Committed? {committed}")

    if committed:
        print("Consensus Reached (Quorum Met).")
    else:
        print("Consensus Failed (Expected Commit).")
        raise Exception("BFT Failed")

    # 2. Test Evolution (Genetic Selection)
    print("\n--- Testing Rust Evolution (Genetics) ---")
    selector = GeneticSelector(tournament_size=3)

    # Generate population: (AgentID, Fitness)
    population = [(f"agent_{i}", float(i)) for i in range(10)] # Fitness 0.0 to 9.0
    random.shuffle(population)

    print(f"Population Size: {len(population)}")

    # Select Best
    best_id = selector.tournament_select(population)
    print(f"Selected Agent: {best_id}")

    # Rank Agents
    ranked_ids = selector.rank_agents(population)
    print(f"Top 3 Ranked: {ranked_ids[:3]}")

    if ranked_ids[0] == "agent_9":
        print("Ranking Correct (Max Fitness at top).")
    else:
        print("Ranking Failed.")
        raise Exception("Evolution Failed")

    print("\nRust Brain Verification COMPLETE.")

if __name__ == "__main__":
    test_rust_brain()
