//! src/governance/constitution.rs
//! Sovereign Constitution (τ-ethics)
//!
//! Maps high-level governance inputs (drift, security, tests)
//! to thermodynamic kernel metrics (tau_ethics, epsilon_c).

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GovernanceInputs {
    pub drift_alarm: bool,
    pub drift_regime: String,
    pub tests_failing: bool,
    pub security_violation: bool,
    pub ct_action: String,
    pub mode: String,
    pub rstar: Option<f64>,
    pub extra: Option<serde_json::Value>,
}

pub struct ConstitutionResult {
    pub tau_ethics: f64,
    pub epsilon_c: f64,
    pub reason: String,
}

/// Evaluates the constitution based on governance inputs.
/// Logic mirrors `warm_logic_core/governance/gov_vm.py`.
#[must_use]
pub fn evaluate_constitution(inputs: &GovernanceInputs) -> ConstitutionResult {
    let mut tau_ethics = 0.5; // Default baseline
    let mut epsilon_c = 1.0; // Default baseline
    let mut reasons = Vec::new();

    // Priority 1: Security violations (Serious breach)
    if inputs.security_violation {
        tau_ethics = 1.0; // Trigger VETO_LOCK (Threshold: 0.85)
        epsilon_c = 0.0;
        reasons.push("security_violation");
    }

    // Priority 2: Failing tests (Halt)
    if inputs.tests_failing {
        if tau_ethics < 0.9 {
            tau_ethics = 0.9;
        }
        epsilon_c = 0.2;
        reasons.push("tests_failing");
    }

    // Priority 3: Drift alarm (Review)
    if inputs.drift_alarm && tau_ethics < 0.8 {
        tau_ethics = 0.75;
        reasons.push("drift_alarm");
    }

    // Priority 4: Low R* score (Deterioration)
    if let Some(rstar) = inputs.rstar {
        if rstar < 0.25 && tau_ethics < 0.7 {
            tau_ethics = 0.7;
            reasons.push("low_rstar");
        }
    }

    // Priority 5: High penalty upper bound
    if let Some(extra) = &inputs.extra {
        if let Some(penalty) = extra.get("penalty") {
            if let Some(penalty_arr) = penalty.as_array() {
                if penalty_arr.len() == 2 {
                    if let Some(upper) = penalty_arr[1].as_f64() {
                        if upper > 0.5 && tau_ethics < 0.6 {
                            tau_ethics = 0.6;
                            reasons.push("penalty_upper");
                        }
                    }
                }
            }
        }
    }

    if reasons.is_empty() {
        reasons.push("ok");
    }

    ConstitutionResult {
        tau_ethics,
        epsilon_c,
        reason: reasons.join(";"),
    }
}
