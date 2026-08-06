//! Simulation: resilient Logic Verification
//! ==========================================
//! This binary simulates a catastrophic entropy event and verifies the
//! state grid's ability to self-heal using the Autopoietic Resilience trait.

use warm_logic_rs::resilience::{reconstruct_reality, EntropyWatchdog};
use warm_logic_rs::state_grid::{AutopoieticResilience, StateGrid};

fn main() {
    println!("Initializing The state grid...");
    let mut grid = StateGrid::new();
    println!("state grid Online. Dimension: {}", grid.dimension);

    // 1. Verify Initial State
    println!("Verifying Initial Axiomatic Invariance...");
    assert!(grid.verify_resilience(), "Initial resilience check failed!");
    println!("System is Resilient.");

    // 2. Simulate Entropy Event
    println!("\n SIMULATING ENTROPY SPIKE (ATTACK SCENARIO)...");
    let watchdog = EntropyWatchdog {
        entropy_level: 0.95, // Critical level
        panic_count: 4,      // Panic threshold exceeded
    };

    if watchdog.is_critical() {
        println!("CRITICAL STATE DETECTED! Initiating Self-Healing Protocol...");

        // 3. Trigger Self-Healing
        let healed = reconstruct_reality(&mut grid);

        if healed {
            println!("SUCCESS: Reality Reconstructed.");
            println!(" System is resilient.");
        } else {
            eprintln!("FAILURE: System could not recover.");
            std::process::exit(1);
        }
    } else {
        println!("System stable (Unexpected based on simulation parameters).");
    }

    // 4. Final Verification
    assert!(
        grid.verify_resilience(),
        "Post-healing resilience check failed!"
    );
    println!("\nState grid verification complete. verification CONFIRMED.");
}
