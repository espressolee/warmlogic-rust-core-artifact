import warm_logic_rs
from warm_logic_rs import WeightDistillery, GeneticSelector
import random
import time

class SovereignBrain:
    def __init__(self, brain_id, weights):
        self.id = brain_id
        self.weights = weights
        self.fitness = 0.0
        self.sparsity = 0.0

def ignite_distillation(generations=5, population_size=10):
    print("[Distillery] Starting Genetic Distillation Loop...")
    
    distillery = WeightDistillery()
    selector = GeneticSelector(tournament_size=3)
    
    # 1. Initialize Random Population
    # Mocking a small layer of 1000 weights
    print(f"Initializing population of {population_size} brains...")
    population = []
    base_weights = [random.uniform(-1, 1) for _ in range(1000)]
    
    for i in range(population_size):
        # Initial population has random variations
        mutated = distillery.jitter_weights(base_weights, 0.1)
        population.append(SovereignBrain(f"brain_gen0_{i}", mutated))

    # 2. The Evolution Loop
    for gen in range(generations):
        print(f"\n--- ⏳ Generation {gen} ---")
        
        # A. Evaluation (Fitness)
        for brain in population:
            # We want: High Sparsity (small model) AND High "Logic" (simulated)
            brain.sparsity = distillery.calculate_sparsity(brain.weights)
            
            # Simulated logic score: higher if weights sum to something 'stable'
            logic_score = sum(w for w in brain.weights if abs(w) > 0.1) / 100.0
            
            # Fitness = Logic Score + (Sparsity Bonus)
            brain.fitness = logic_score + (brain.sparsity * 5.0)
        
        # B. Selection
        # Convert to ID/Fitness tuples for Rust selector
        data = [(b.id, b.fitness) for b in population]
        ranked_ids = selector.rank_agents(data)
        
        print(f"Best Brain: {ranked_ids[0]} (Fitness: {next(b.fitness for b in population if b.id == ranked_ids[0]):.4f})")
        print(f"Average Sparsity: {sum(b.sparsity for b in population)/len(population):.2%}")

        # C. Reproduction (Create next gen from winners)
        winners = ranked_ids[:population_size // 2]
        new_population = []
        
        for i in range(population_size):
            parent_id = random.choice(winners)
            parent = next(b for b in population if b.id == parent_id)
            
            # Mutate and Prune (Distill)
            # We increase pruning pressure as generations pass
            pruning_threshold = 0.01 + (gen * 0.02)
            
            new_weights = distillery.jitter_weights(parent.weights, 0.05)
            new_weights = distillery.prune_weights(new_weights, pruning_threshold)
            
            new_population.append(SovereignBrain(f"brain_gen{gen+1}_{i}", new_weights))
            
        population = new_population
        time.sleep(0.5) # Simulated compute time

    # Final Result
    print("\nDistillation Loop Complete.")
    print(f"Champion Brain evolved from Generation {generations}.")
    print(f"Final Sparsity Goal: {population[0].sparsity:.2%}")

if __name__ == "__main__":
    ignite_distillation()
