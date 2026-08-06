#![allow(dead_code)]
#[cfg(feature = "python")]
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[cfg(not(feature = "std"))]
use hashbrown::{HashMap, HashSet};
#[cfg(feature = "std")]
use std::collections::{HashMap, HashSet};

#[cfg(not(feature = "std"))]
use alloc::string::String;
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

#[cfg_attr(feature = "python", pyclass)]
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PolicyRecord {
    pub name: String,
    pub version: String,
    pub signature: String,
}

#[cfg(feature = "python")]
#[pymethods]
impl PolicyRecord {
    #[new]
    fn py_new(name: String, version: String, signature: String) -> Self {
        PolicyRecord {
            name,
            version,
            signature,
        }
    }

    #[getter]
    fn name(&self) -> String {
        self.name.clone()
    }

    #[getter]
    fn version(&self) -> String {
        self.version.clone()
    }

    #[getter]
    fn signature(&self) -> String {
        self.signature.clone()
    }
}

#[cfg_attr(feature = "python", pyclass)]
pub struct PolicyEngine {
    pub allowed_plugins: HashMap<String, PolicyRecord>,
    pub required_invariants: HashSet<String>,
}

impl PolicyEngine {
    #[must_use]
    pub fn new() -> Self {
        PolicyEngine {
            allowed_plugins: HashMap::new(),
            required_invariants: HashSet::new(),
        }
    }

    pub fn register_plugin(&mut self, record: PolicyRecord) {
        self.allowed_plugins.insert(record.name.clone(), record);
    }

    #[must_use]
    pub fn verify_plugin(&self, name: &str, signature: &str) -> bool {
        if let Some(record) = self.allowed_plugins.get(name) {
            // hardware attestation enforcement: Real PQC Verification
            // The signature must be a valid ML-DSA-65 signature of the version string
            // using the plugin's public key (stored in name field for this demo)
            return crate::crypto::MLDSA::verify_raw(&record.name, &record.version, signature);
        }
        false
    }

    #[must_use]
    pub fn check_invariants(&self, metrics: &HashMap<String, f64>) -> Vec<String> {
        let mut violations = Vec::new();

        // Example Invariant: CPU Drift
        if let Some(&drift) = metrics.get("cpu_drift") {
            if drift > 0.05 {
                violations.push(format!("CPU_DRIFT_EXCEEDED: {:.4}", drift));
            }
        }

        // Example Invariant: Memory Saturation
        if let Some(&mem) = metrics.get("mem_usage") {
            if mem > 0.95 {
                violations.push(format!("MEMORY_SATURATION_EXCEEDED: {:.2}", mem));
            }
        }

        violations
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl PolicyEngine {
    #[new]
    fn py_new() -> Self {
        Self::new()
    }

    fn register_plugin_py(&mut self, record: PolicyRecord) {
        self.register_plugin(record);
    }

    fn verify_plugin_py(&self, name: &str, signature: &str) -> bool {
        self.verify_plugin(name, signature)
    }

    fn check_invariants_py(&self, metrics: HashMap<String, f64>) -> Vec<String> {
        self.check_invariants(&metrics)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::crypto::{PQCKeypair, MLDSA};

    #[test]
    fn test_policy_engine_registration_and_verification() {
        let mut engine = PolicyEngine::new();
        let kp = PQCKeypair::generate();
        let pk = kp.public_key.clone();
        let sk = kp.private_key.clone();

        let record = PolicyRecord {
            name: pk.clone(), // In this engine, name is the pubkey
            version: "v1.0.0".to_string(),
            signature: MLDSA::sign_raw(&sk, "v1.0.0").expect("Signing Failed"),
        };

        engine.register_plugin(record);
        assert!(engine.verify_plugin(&pk, &MLDSA::sign_raw(&sk, "v1.0.0").unwrap()));
        assert!(!engine.verify_plugin(&pk, "invalid_sig"));
    }

    #[test]
    fn test_policy_engine_invariants() {
        let engine = PolicyEngine::new();
        let mut metrics = HashMap::new();

        metrics.insert("cpu_drift".to_string(), 0.01);
        metrics.insert("mem_usage".to_string(), 0.50);
        assert!(engine.check_invariants(&metrics).is_empty());

        metrics.insert("cpu_drift".to_string(), 0.07);
        let violations = engine.check_invariants(&metrics);
        assert_eq!(violations.len(), 1);
        assert!(violations[0].contains("CPU_DRIFT_EXCEEDED"));

        metrics.insert("mem_usage".to_string(), 0.99);
        let violations = engine.check_invariants(&metrics);
        assert_eq!(violations.len(), 2);
    }

    // ============================================================================
    // ADDITIONAL TESTS FOR 80% COVERAGE
    // ============================================================================

    #[test]
    fn test_policy_engine_new() {
        let engine = PolicyEngine::new();
        assert!(engine.allowed_plugins.is_empty());
        assert!(engine.required_invariants.is_empty());
    }

    #[test]
    fn test_policy_engine_verify_unregistered_plugin() {
        let engine = PolicyEngine::new();
        // Verify unregistered plugin should return false
        assert!(!engine.verify_plugin("unknown_plugin", "some_sig"));
    }

    #[test]
    fn test_policy_engine_multiple_plugins() {
        let mut engine = PolicyEngine::new();

        let kp1 = PQCKeypair::generate();
        let pk1 = kp1.public_key.clone();
        let sk1 = kp1.private_key.clone();

        let kp2 = PQCKeypair::generate();
        let pk2 = kp2.public_key.clone();
        let sk2 = kp2.private_key.clone();

        let record1 = PolicyRecord {
            name: pk1.clone(),
            version: "v1.0.0".to_string(),
            signature: MLDSA::sign_raw(&sk1, "v1.0.0").unwrap(),
        };

        let record2 = PolicyRecord {
            name: pk2.clone(),
            version: "v2.0.0".to_string(),
            signature: MLDSA::sign_raw(&sk2, "v2.0.0").unwrap(),
        };

        engine.register_plugin(record1);
        engine.register_plugin(record2);

        assert_eq!(engine.allowed_plugins.len(), 2);

        // Verify both plugins
        assert!(engine.verify_plugin(&pk1, &MLDSA::sign_raw(&sk1, "v1.0.0").unwrap()));
        assert!(engine.verify_plugin(&pk2, &MLDSA::sign_raw(&sk2, "v2.0.0").unwrap()));

        // Cross-plugin verification should fail
        assert!(!engine.verify_plugin(&pk1, &MLDSA::sign_raw(&sk2, "v2.0.0").unwrap()));
    }

    #[test]
    fn test_policy_engine_invariants_exact_thresholds() {
        let engine = PolicyEngine::new();
        let mut metrics = HashMap::new();

        // Exactly at CPU drift threshold (0.05) - should NOT trigger
        metrics.insert("cpu_drift".to_string(), 0.05);
        metrics.insert("mem_usage".to_string(), 0.50);
        assert!(engine.check_invariants(&metrics).is_empty());

        // Just above CPU drift threshold - should trigger
        metrics.insert("cpu_drift".to_string(), 0.051);
        let violations = engine.check_invariants(&metrics);
        assert_eq!(violations.len(), 1);

        // Exactly at memory threshold (0.95) - should NOT trigger
        metrics.insert("cpu_drift".to_string(), 0.01);
        metrics.insert("mem_usage".to_string(), 0.95);
        assert!(engine.check_invariants(&metrics).is_empty());

        // Just above memory threshold - should trigger
        metrics.insert("mem_usage".to_string(), 0.951);
        let violations = engine.check_invariants(&metrics);
        assert_eq!(violations.len(), 1);
        assert!(violations[0].contains("MEMORY_SATURATION"));
    }

    #[test]
    fn test_policy_engine_empty_metrics() {
        let engine = PolicyEngine::new();
        let metrics = HashMap::new();

        // Empty metrics should produce no violations
        let violations = engine.check_invariants(&metrics);
        assert!(violations.is_empty());
    }

    #[test]
    fn test_policy_engine_partial_metrics() {
        let engine = PolicyEngine::new();
        let mut metrics = HashMap::new();

        // Only CPU drift, no memory
        metrics.insert("cpu_drift".to_string(), 0.10);
        let violations = engine.check_invariants(&metrics);
        assert_eq!(violations.len(), 1);
        assert!(violations[0].contains("CPU_DRIFT"));

        // Only memory, no CPU drift
        let mut metrics2 = HashMap::new();
        metrics2.insert("mem_usage".to_string(), 0.98);
        let violations = engine.check_invariants(&metrics2);
        assert_eq!(violations.len(), 1);
        assert!(violations[0].contains("MEMORY"));
    }

    #[test]
    fn test_policy_record_fields() {
        let record = PolicyRecord {
            name: "test_name".to_string(),
            version: "v3.2.1".to_string(),
            signature: "test_sig".to_string(),
        };

        assert_eq!(record.name, "test_name");
        assert_eq!(record.version, "v3.2.1");
        assert_eq!(record.signature, "test_sig");
    }

    #[test]
    fn test_policy_record_clone() {
        let record = PolicyRecord {
            name: "original".to_string(),
            version: "v1.0.0".to_string(),
            signature: "sig".to_string(),
        };

        let cloned = record.clone();
        assert_eq!(record.name, cloned.name);
        assert_eq!(record.version, cloned.version);
        assert_eq!(record.signature, cloned.signature);
    }

    #[test]
    fn test_policy_engine_plugin_update() {
        let mut engine = PolicyEngine::new();

        let kp = PQCKeypair::generate();
        let pk = kp.public_key.clone();
        let sk = kp.private_key.clone();

        // Register initial version
        let record_v1 = PolicyRecord {
            name: pk.clone(),
            version: "v1.0.0".to_string(),
            signature: MLDSA::sign_raw(&sk, "v1.0.0").unwrap(),
        };
        engine.register_plugin(record_v1);

        // Update to new version (overwrites)
        let record_v2 = PolicyRecord {
            name: pk.clone(),
            version: "v2.0.0".to_string(),
            signature: MLDSA::sign_raw(&sk, "v2.0.0").unwrap(),
        };
        engine.register_plugin(record_v2);

        // Still only 1 plugin (updated)
        assert_eq!(engine.allowed_plugins.len(), 1);

        // v1 signature no longer valid
        assert!(!engine.verify_plugin(&pk, &MLDSA::sign_raw(&sk, "v1.0.0").unwrap()));
        // v2 signature is valid
        assert!(engine.verify_plugin(&pk, &MLDSA::sign_raw(&sk, "v2.0.0").unwrap()));
    }

    #[test]
    fn test_policy_engine_extreme_metrics() {
        let engine = PolicyEngine::new();
        let mut metrics = HashMap::new();

        // Zero values (healthy)
        metrics.insert("cpu_drift".to_string(), 0.0);
        metrics.insert("mem_usage".to_string(), 0.0);
        assert!(engine.check_invariants(&metrics).is_empty());

        // Maximum severity (1.0)
        metrics.insert("cpu_drift".to_string(), 1.0);
        metrics.insert("mem_usage".to_string(), 1.0);
        let violations = engine.check_invariants(&metrics);
        assert_eq!(violations.len(), 2);
    }
}
