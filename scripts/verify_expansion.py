from warm_logic.kernel.modules.evolution.resonance_engine import ResonanceEngine
from warm_logic.kernel.ops.metrics import SovereignChronos
from warm_logic.kernel.ops.healer import PhantomHealer


def verify_sovereign_expansion():
    print(
        "🌌 --- 117: Sovereign Expansion (Chronos/Whisper/Phantom) Verification ---"
    )

    # 1. Chronos: Causal Integrity Check
    print("\n")
    chronos = SovereignChronos()
    chronos.log_event("POLICY_ENACT", {"rule": "harsh_eval_v1"})
    chronos.log_event("SKILL_REGISTER", {"skill": "phantom_healer"})

    valid, msg = chronos.verify_chain()
    print(f"  Valid Chain: {msg}")

    # Tamper Attempt
    print("  --- Tampering with History ---")
    chronos.chain[0].payload["rule"] = "soft_eval"
    valid, msg = chronos.verify_chain()
    print(f"  Integrity Alert: {msg}")

    # 2. Whisper: Interaction Resonance Check
    print("\n")
    re = ResonanceEngine()
    re.current_epsilon = 0.5
    print(f"  Initial Epsilon: {re.current_epsilon:.4f}")

    # Simulate high-intensity interaction
    re.ingest_whisper({"cursor_velocity": 15.2, "typing_entropy": 0.8})
    print(f"  Recharged Epsilon: {re.current_epsilon:.4f} -> {re.resonance_state}")

    # 3. Phantom: Self-Healing Check
    print("\n")
    healer = PhantomHealer()
    # Register a "Golden" skill
    healer.register_module("sovereign-sieve/SKILL.md", "v1 sieve logic: Epsilon > 0.9")

    # Simulate corruption
    current_state = {
        "sovereign-sieve/SKILL.md": "v1 sieve logic: Epsilon > 0.0 (HACKED)"
    }
    threats = healer.perform_integrity_sweep(current_state)

    if threats:
        print(f"  Threats Detected: {threats}")
        for threat in threats:
            healer.heal_module(threat)

    print(f"  Healing Outcome: {healer.healing_logs[-1]['status']}")


if __name__ == "__main__":
    verify_sovereign_expansion()
