// tests/test_tpu_policy.rs
// Phase 10.2: Verification of Accelerated Policy Check

use warm_logic_rs::governance::{GovernanceVerdict, VetoEngine};

#[test]
fn test_tpu_policy_initialization() {
    let engine = VetoEngine::new();

    // Initialize TPU model
    let result = engine.init_tpu_model();
    assert!(result.is_ok(), "Failed to initialize TPU model");
}

#[test]
fn test_accelerated_policy_thresholds() {
    let engine = VetoEngine::new();
    engine.init_tpu_model().unwrap();

    // 1. Critical Halt: e_stab < 0.3
    // tau_ethics = 0.8 (valid), epsilon_c = 0.0
    // e_stab = 0.5*0.0 + 0.5*(1.0-0.8) = 0.1
    let decision = engine.evaluate(0.8, 0.0);
    assert_eq!(
        decision.verdict,
        GovernanceVerdict::CriticalHalt,
        "Should trigger CriticalHalt for e_stab=0.1"
    );

    // 2. Block: 0.3 <= e_stab < 0.5
    // tau_ethics = 0.6, epsilon_c = 0.4
    // e_stab = 0.5*0.4 + 0.5*(1.0-0.6) = 0.2 + 0.2 = 0.4
    let decision = engine.evaluate(0.6, 0.4);
    assert_eq!(
        decision.verdict,
        GovernanceVerdict::Block,
        "Should trigger Block for e_stab=0.4"
    );

    // 3. Review: 0.5 <= e_stab < 0.7
    // tau_ethics = 0.2, epsilon_c = 0.4
    // e_stab = 0.5*0.4 + 0.5*(1.0-0.2) = 0.2 + 0.4 = 0.6
    let decision = engine.evaluate(0.2, 0.4);
    assert_eq!(
        decision.verdict,
        GovernanceVerdict::Review,
        "Should trigger Review for e_stab=0.6"
    );

    // 4. Allow: e_stab >= 0.7
    // tau_ethics = 0.0, epsilon_c = 0.6
    // e_stab = 0.5*0.6 + 0.5*(1.0-0.0) = 0.3 + 0.5 = 0.8
    let decision = engine.evaluate(0.0, 0.6);
    assert_eq!(
        decision.verdict,
        GovernanceVerdict::Allow,
        "Should trigger Allow for e_stab=0.8"
    );
}

#[test]
fn test_veto_override() {
    let engine = VetoEngine::new();
    engine.init_tpu_model().unwrap();

    // Even if metrics are perfect, if VETO_LOCK is active, it should return VetoLock
    engine.activate_veto(100, "Manual Override", [0u8; 32]);

    let decision = engine.evaluate(0.0, 1.0); // Perfect metrics
    assert_eq!(
        decision.verdict,
        GovernanceVerdict::VetoLock,
        "VETO_LOCK should override metrics"
    );
}

#[test]
fn test_tau_ethics_threshold_breach() {
    let engine = VetoEngine::new();
    engine.init_tpu_model().unwrap();

    // tau_ethics > 0.85 should trigger VetoLock directly
    let decision = engine.evaluate(0.9, 1.0);
    assert_eq!(
        decision.verdict,
        GovernanceVerdict::VetoLock,
        "High tau_ethics should trigger VetoLock"
    );
    assert!(engine.is_veto_active());
}
