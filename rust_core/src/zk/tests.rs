//! Integration tests for the ZK module.

use super::prover::{Prover, TrustedSetup};
use super::types::{DecisionType, GovernancePublicInputs, SerializedProof};
use super::verifier::Verifier;
use super::*;
use super::{GovernanceCircuit, QuorumCircuit, VetoCircuit};
use ark_relations::r1cs::{ConstraintSynthesizer, ConstraintSystem};

/// Full integration test: setup -> prove -> verify
#[test]
fn test_full_governance_proof_flow() {
    // 1. Create governance decision inputs
    let public_inputs = GovernancePublicInputs {
        decision_hash: sha3_hash(b"decision_data_here"),
        policy_hash: sha3_hash(b"policy_rules_v1"),
        decision_type: DecisionType::PolicyCompliance,
        epoch: 86000, // WarmLogic Era
        node_id: sha3_hash(b"node_alpha"),
        model_hash: [1u8; 32],
    };

    // 2. Create circuit with private witness
    let circuit = GovernanceCircuit::new(
        public_inputs,
        10,    // authority_level
        5,     // threshold
        7,     // approval_count (>= threshold)
        false, // no veto
    );

    // 3. Validate circuit satisfiability
    assert!(circuit.validate().is_ok());

    // 4. Trusted setup (generates proving/verifying keys)
    let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 12345).unwrap();

    // 5. Generate proof
    let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

    // 6. Verify proof
    let valid = Verifier::verify(&proof, &inputs, &vk).unwrap();
    assert!(valid, "Proof should be valid");

    println!("Governance proof verified successfully!");
}

/// Test proof serialization roundtrip
#[test]
fn test_proof_serialization() {
    let public_inputs = GovernancePublicInputs {
        decision_hash: [0xAB; 32],
        policy_hash: [0xCD; 32],
        decision_type: DecisionType::VetoAuthority,
        epoch: 1000,
        node_id: [0xEF; 32],
        model_hash: [1u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
    let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
    let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

    // Serialize
    let serialized =
        SerializedProof::from_proof(&proof, &inputs, GovernanceCircuit::CIRCUIT_ID).unwrap();

    // Check size
    let proof_size = serialized.size();
    println!("Proof size: {} bytes", proof_size);
    assert!(
        proof_size < 500,
        "Groth16 proof should be small (< 500 bytes)"
    );

    // Deserialize and verify
    let valid = Verifier::verify_serialized(&serialized, &vk).unwrap();
    assert!(valid, "Serialized proof should verify");
}

/// Test veto circuit
#[test]
fn test_veto_circuit() {
    let circuit = VetoCircuit::new(
        sha3_hash(b"decision_to_veto"),
        sha3_hash(b"veto_authority_pubkey"),
        sha3_hash(b"veto_authority_secret"),
        86000,
    );

    let cs = ConstraintSystem::<Fr>::new_ref();
    circuit.generate_constraints(cs.clone()).unwrap();
    assert!(
        cs.is_satisfied().unwrap(),
        "Veto circuit should be satisfiable"
    );
}

/// Test quorum circuit
#[test]
fn test_quorum_circuit() {
    // 2/3 quorum with 7/10 approvals (should pass)
    let circuit = QuorumCircuit::new(
        10, // total_nodes
        2,  // numerator (2/3)
        3,  // denominator
        7,  // approvals
        sha3_hash(b"consensus_decision"),
    );

    assert!(circuit.is_quorum_met());

    let cs = ConstraintSystem::<Fr>::new_ref();
    circuit.generate_constraints(cs.clone()).unwrap();
    assert!(
        cs.is_satisfied().unwrap(),
        "Quorum circuit should be satisfiable"
    );
}

/// Test that invalid proofs fail verification
#[test]
fn test_invalid_proof_detection() {
    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs.clone(), 5, 3, 5, false);
    let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
    let (proof, _original_inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

    // Try to verify with tampered inputs
    let tampered_inputs = GovernancePublicInputs {
        decision_hash: [99u8; 32], // TAMPERED!
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
        model_hash: [1u8; 32],
    };
    let tampered_vec = tampered_inputs.to_field_elements();

    let valid = Verifier::verify(&proof, &tampered_vec, &vk).unwrap();
    assert!(!valid, "Tampered proof should NOT verify");
}

/// Test circuit constraint count
#[test]
fn test_circuit_complexity() {
    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);

    let cs = ConstraintSystem::<Fr>::new_ref();
    circuit.generate_constraints(cs.clone()).unwrap();

    let num_constraints = cs.num_constraints();
    let num_variables = cs.num_instance_variables() + cs.num_witness_variables();

    println!("Circuit complexity:");
    println!("  Constraints: {}", num_constraints);
    println!("  Variables: {}", num_variables);
    println!("  Public inputs: {}", cs.num_instance_variables() - 1); // -1 for constant

    // Governance circuit should be relatively simple
    assert!(
        num_constraints < 100,
        "Circuit too complex: {} constraints",
        num_constraints
    );
}

/// Benchmark proof generation time
#[test]
fn test_proof_generation_time() {
    use std::time::Instant;

    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
    let (pk, _vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();

    // Warm up
    let _ = Prover::prove_governance(&circuit, &pk).unwrap();

    // Measure
    let iterations = 5;
    let start = Instant::now();
    for _ in 0..iterations {
        let _ = Prover::prove_governance(&circuit, &pk).unwrap();
    }
    let elapsed = start.elapsed();
    let avg_ms = elapsed.as_millis() / iterations as u128;

    println!("Proof generation: {} ms average", avg_ms);

    // Target: < 500ms per proof
    assert!(avg_ms < 1000, "Proof generation too slow: {} ms", avg_ms);
}

/// Benchmark verification time
#[test]
fn test_verification_time() {
    use std::time::Instant;

    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
    let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
    let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

    // Prepare VK for faster verification
    let prepared_vk = Verifier::prepare_verifying_key(&vk);

    // Warm up
    let _ = Verifier::verify_prepared(&proof, &inputs, &prepared_vk).unwrap();

    // Measure
    let iterations = 100;
    let start = Instant::now();
    for _ in 0..iterations {
        let _ = Verifier::verify_prepared(&proof, &inputs, &prepared_vk).unwrap();
    }
    let elapsed = start.elapsed();
    let avg_us = elapsed.as_micros() / iterations as u128;

    println!("Verification: {} us average", avg_us);

    // Target: < 100ms (100000 us) per verification (debug build tolerance)
    assert!(avg_us < 100000, "Verification too slow: {} us", avg_us);
}

// Helper: compute SHA3-256 hash
fn sha3_hash(data: &[u8]) -> [u8; 32] {
    use sha3::{Digest, Sha3_256};
    let mut hasher = Sha3_256::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut hash = [0u8; 32];
    hash.copy_from_slice(&result);
    hash
}

/// Test that proving key can be reused for different public inputs
#[test]
fn test_proving_key_reusability() {
    // 1. Generate proving key with first set of inputs
    let setup_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [0u8; 32],
        policy_hash: [0u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 0,
        node_id: [0u8; 32],
    };

    let setup_circuit = GovernanceCircuit::new(setup_inputs, 10, 1, 1, false);
    let (pk, vk) = TrustedSetup::generate_keys_deterministic(setup_circuit, 42).unwrap();

    // 2. Create a DIFFERENT circuit with different public inputs
    let prove_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: sha3_hash(b"different_decision"),
        policy_hash: sha3_hash(b"different_policy"),
        decision_type: DecisionType::VetoAuthority,
        epoch: 86000,
        node_id: sha3_hash(b"node_123"),
    };

    let prove_circuit = GovernanceCircuit::new(prove_inputs, 10, 1, 1, false);

    // 3. Try to generate proof with reused key
    let result = Prover::prove_governance(&prove_circuit, &pk);
    assert!(
        result.is_ok(),
        "Proof should succeed with reused key: {:?}",
        result.err()
    );

    let (proof, inputs) = result.unwrap();

    // 4. Verify the proof
    let valid = Verifier::verify(&proof, &inputs, &vk).unwrap();
    assert!(valid, "Proof with different inputs should verify");
}

/// Test that proving key reusability works with entropy-based setup (like production)
#[test]
fn test_proving_key_reusability_entropy() {
    // 1. Generate proving key with first set of inputs using generate_keys (entropy)
    let setup_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [0u8; 32],
        policy_hash: [0u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 0,
        node_id: [0u8; 32],
    };

    let setup_circuit = GovernanceCircuit::new(setup_inputs, 10, 1, 1, false);
    let (pk, vk) = TrustedSetup::generate_keys_dev(setup_circuit).unwrap();

    // 2. Create a DIFFERENT circuit with different public inputs
    let prove_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: sha3_hash(b"different_decision"),
        policy_hash: sha3_hash(b"different_policy"),
        decision_type: DecisionType::VetoAuthority,
        epoch: 86000,
        node_id: sha3_hash(b"node_123"),
    };

    let prove_circuit = GovernanceCircuit::new(prove_inputs, 10, 1, 1, false);

    // 3. Try to generate proof with reused key
    let result = Prover::prove_governance(&prove_circuit, &pk);
    assert!(
        result.is_ok(),
        "Proof should succeed with entropy-based key: {:?}",
        result.err()
    );

    let (proof, inputs) = result.unwrap();

    // 4. Verify the proof
    let valid = Verifier::verify(&proof, &inputs, &vk).unwrap();
    assert!(valid, "Proof with entropy-based key should verify");
}

// ============================================================================
// ADDITIONAL TESTS FOR 80% COVERAGE
// ============================================================================

/// Test governance circuit with zero authority (should fail validation)
#[test]
fn test_governance_circuit_zero_authority() {
    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(
        public_inputs,
        0, // ZERO authority - should fail
        3,
        5,
        false,
    );

    let result = circuit.validate();
    assert!(result.is_err(), "Zero authority should fail validation");

    let err = result.unwrap_err();
    assert!(
        format!("{}", err).contains("Authority level cannot be zero"),
        "Error message should mention authority level"
    );
}

/// Test governance circuit below threshold without veto (should fail)
#[test]
fn test_governance_circuit_below_threshold_no_veto() {
    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(
        public_inputs,
        5,     // authority_level
        10,    // threshold = 10
        5,     // approval_count = 5 (below threshold)
        false, // NO veto
    );

    let result = circuit.validate();
    assert!(result.is_err(), "Below threshold without veto should fail");
}

/// Test batch verification
#[test]
fn test_batch_verification() {
    let setup_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [0u8; 32],
        policy_hash: [0u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 0,
        node_id: [0u8; 32],
    };

    let setup_circuit = GovernanceCircuit::new(setup_inputs, 10, 1, 1, false);
    let (pk, vk) = TrustedSetup::generate_keys_deterministic(setup_circuit, 42).unwrap();

    // Generate multiple proofs
    let mut proofs_and_inputs = Vec::new();
    for i in 0..3 {
        let inputs = GovernancePublicInputs {
            decision_hash: sha3_hash(&[i as u8; 8]),
            policy_hash: sha3_hash(&[(i + 100) as u8; 8]),
            decision_type: DecisionType::PolicyCompliance,
            epoch: 1000 + i as u64,
            node_id: sha3_hash(&[(i + 200) as u8; 8]),
            model_hash: [1u8; 32],
        };
        let circuit = GovernanceCircuit::new(inputs, 10, 1, 1, false);
        let (proof, public_inputs) = Prover::prove_governance(&circuit, &pk).unwrap();
        proofs_and_inputs.push((proof, public_inputs));
    }

    // Batch verify
    let results = Verifier::batch_verify(&proofs_and_inputs, &vk).unwrap();
    assert_eq!(results.len(), 3);
    for (i, valid) in results.iter().enumerate() {
        assert!(valid, "Proof {} should be valid", i);
    }
}

/// Test quorum circuit exact threshold (boundary case)
#[test]
fn test_quorum_circuit_exact_threshold() {
    // Exactly 2/3: 6/9 = 2/3
    let circuit = QuorumCircuit::new(
        9, // total_nodes
        2, // numerator (2/3)
        3, // denominator
        6, // approvals (6/9 = exactly 2/3)
        sha3_hash(b"boundary_decision"),
    );

    assert!(circuit.is_quorum_met(), "Exact 2/3 should meet quorum");

    let cs = ConstraintSystem::<Fr>::new_ref();
    circuit.generate_constraints(cs.clone()).unwrap();
    assert!(cs.is_satisfied().unwrap());
}

/// Test quorum circuit just below threshold
#[test]
fn test_quorum_circuit_below_threshold() {
    // Just below 2/3: 5/9 < 2/3
    let circuit = QuorumCircuit::new(
        9, // total_nodes
        2, // numerator (2/3)
        3, // denominator
        5, // approvals (5/9 < 2/3)
        sha3_hash(b"below_threshold_decision"),
    );

    assert!(!circuit.is_quorum_met(), "5/9 should NOT meet 2/3 quorum");
}

/// Test all decision types
#[test]
fn test_all_decision_types() {
    let decision_types = [
        (DecisionType::PolicyCompliance, "wl_policy_v1"),
        (DecisionType::VetoAuthority, "wl_veto_v1"),
        (DecisionType::QuorumReached, "wl_quorum_v1"),
        (DecisionType::RegulatoryCompliance, "wl_compliance_v1"),
        (DecisionType::IdentityAttestation, "wl_identity_v1"),
    ];

    for (dt, expected_id) in decision_types.iter() {
        assert_eq!(
            dt.circuit_id(),
            *expected_id,
            "Decision type {:?} should have correct circuit_id",
            dt
        );
    }
}

/// Test ZKError display
#[test]
fn test_zk_error_display() {
    use super::error::ZKError;

    let errors = vec![
        (
            ZKError::ConstraintViolation("test".to_string()),
            "Constraint violation: test",
        ),
        (
            ZKError::WitnessError("witness".to_string()),
            "Witness generation failed: witness",
        ),
        (
            ZKError::ProvingError("prove".to_string()),
            "Proving error: prove",
        ),
        (ZKError::VerificationFailed, "Proof verification failed"),
        (
            ZKError::SerializationError("ser".to_string()),
            "Serialization error: ser",
        ),
        (
            ZKError::InvalidPublicInputs("inputs".to_string()),
            "Invalid public inputs: inputs",
        ),
        (
            ZKError::SetupError("setup".to_string()),
            "Setup error: setup",
        ),
        (
            ZKError::CircuitNotFound("circuit".to_string()),
            "Circuit not found: circuit",
        ),
        (
            ZKError::InvalidParameters("params".to_string()),
            "Invalid parameters: params",
        ),
    ];

    for (err, expected) in errors {
        assert_eq!(format!("{}", err), expected);
    }
}

/// Test Solidity proof conversion
#[test]
fn test_solidity_proof_conversion() {
    use super::verifier::onchain::SolidityProof;

    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
    let (pk, _vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
    let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

    // Convert to Solidity format
    let sol_proof = SolidityProof::from_proof(&proof).unwrap();

    // Check sizes
    assert_eq!(sol_proof.a.len(), 64);
    assert_eq!(sol_proof.b.len(), 128);
    assert_eq!(sol_proof.c.len(), 64);

    // Convert inputs to Solidity format
    let sol_inputs = SolidityProof::inputs_to_solidity(&inputs);
    assert_eq!(sol_inputs.len(), inputs.len());
}

/// Test key file operations (save/load)
#[test]
fn test_key_file_operations() {
    use super::prover::keys;
    // use std::path::PathBuf;

    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
    let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();

    // Create temp directory
    let temp_dir = std::env::temp_dir();
    let pk_path = temp_dir.join("test_pk.bin");
    let vk_path = temp_dir.join("test_vk.bin");

    // Save keys
    keys::save_proving_key(&pk, &pk_path).unwrap();
    keys::save_verifying_key(&vk, &vk_path).unwrap();

    // Load keys
    let loaded_pk = keys::load_proving_key(&pk_path).unwrap();
    let loaded_vk = keys::load_verifying_key(&vk_path).unwrap();

    // Verify loaded keys work
    let (proof, inputs) = Prover::prove_governance(&circuit, &loaded_pk).unwrap();
    let valid = Verifier::verify(&proof, &inputs, &loaded_vk).unwrap();
    assert!(valid, "Proof with loaded keys should verify");

    // Cleanup
    let _ = std::fs::remove_file(&pk_path);
    let _ = std::fs::remove_file(&vk_path);
}

/// Test verification result struct
#[test]
fn test_verification_result_new() {
    use super::verifier::VerificationResult;

    let result = VerificationResult::new(true, "test_circuit", 5);
    assert!(result.valid);
    assert_eq!(result.circuit_id, "test_circuit");
    assert_eq!(result.num_public_inputs, 5);
    assert!(result.timestamp > 0);
}

/// Test prepared verifying key
#[test]
fn test_prepared_verifying_key() {
    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
    let (pk, vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
    let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

    // Prepare VK
    let prepared_vk = Verifier::prepare_verifying_key(&vk);

    // Verify with prepared key
    let valid = Verifier::verify_prepared(&proof, &inputs, &prepared_vk).unwrap();
    assert!(valid, "Proof should verify with prepared VK");
}

/// Test circuit builder
#[test]
fn test_circuit_builder_enforce_equal() {
    use super::circuit::CircuitBuilder;
    // use ark_ff::One;

    let mut builder = CircuitBuilder::new("test_eq");
    let a = builder.alloc_public();
    let b = builder.alloc_public();

    builder.enforce_equal(a, b);

    assert_eq!(builder.num_constraints(), 1);
    assert_eq!(builder.circuit_id, "test_eq");
}

/// Test circuit builder boolean enforcement
#[test]
fn test_circuit_builder_enforce_boolean() {
    use super::circuit::CircuitBuilder;

    let mut builder = CircuitBuilder::new("test_bool");
    let var = builder.alloc_private();

    builder.enforce_boolean(var);

    assert_eq!(builder.num_constraints(), 1);
}

/// Test governance public inputs conversion
#[test]
fn test_governance_public_inputs_to_field_elements() {
    let inputs = GovernancePublicInputs {
        decision_hash: [0xAB; 32],
        policy_hash: [0xCD; 32],
        decision_type: DecisionType::QuorumReached,
        epoch: u64::MAX,
        node_id: [0xEF; 32],
        model_hash: [1u8; 32],
    };

    let elements = inputs.to_field_elements();

    // Should have 9 elements: 2 for decision_hash, 2 for policy_hash, 1 for decision_type, 1 for epoch, 1 for node_id prefix, 2 for model_hash
    assert_eq!(elements.len(), 9);

    // Check decision type encoding
    assert_eq!(elements[4], Fr::from(DecisionType::QuorumReached as u64));

    // Check epoch encoding
    assert_eq!(elements[5], Fr::from(u64::MAX));
}

/// Test veto circuit with different epochs
#[test]
fn test_veto_circuit_edge_cases() {
    // Test with zero epoch (edge case)
    let circuit = VetoCircuit::new(
        sha3_hash(b"decision"),
        sha3_hash(b"authority"),
        sha3_hash(b"secret"),
        0, // Zero epoch
    );

    let cs = ConstraintSystem::<Fr>::new_ref();
    // Should fail because epoch must be positive
    let result = circuit.generate_constraints(cs.clone());
    // Note: The circuit enforces epoch != 0, so this might fail satisfaction
    if result.is_ok() {
        // If constraints generated, check if satisfied
        let satisfied = cs.is_satisfied().unwrap_or(false);
        assert!(
            !satisfied,
            "Veto circuit with zero epoch should not be satisfied"
        );
    }
}

/// Test serialized proof size constraint
#[test]
fn test_serialized_proof_size_constraint() {
    let public_inputs = GovernancePublicInputs {
        model_hash: [1u8; 32],
        decision_hash: [1u8; 32],
        policy_hash: [2u8; 32],
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [3u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false);
    let (pk, _vk) = TrustedSetup::generate_keys_deterministic(circuit.clone(), 42).unwrap();
    let (proof, inputs) = Prover::prove_governance(&circuit, &pk).unwrap();

    let serialized = SerializedProof::from_proof(&proof, &inputs, "test").unwrap();

    // Groth16 proofs should be approximately 192 bytes (2 G1 + 1 G2 point)
    assert!(serialized.size() > 0);
    assert!(serialized.size() < 1000, "Proof should be compact");

    // Check hex encoding
    let hex = serialized.proof_hex();
    assert!(!hex.is_empty());
    assert_eq!(hex.len(), serialized.size() * 2); // hex doubles byte length
}

/// Test circuit with preimage
#[test]
fn test_governance_circuit_with_preimage() {
    let public_inputs = GovernancePublicInputs {
        decision_hash: sha3_hash(b"decision_preimage_data"),
        policy_hash: sha3_hash(b"policy"),
        decision_type: DecisionType::PolicyCompliance,
        epoch: 1000,
        node_id: [1u8; 32],
        model_hash: [1u8; 32],
    };

    let circuit = GovernanceCircuit::new(public_inputs, 5, 3, 5, false)
        .with_preimage(b"decision_preimage_data".to_vec());

    assert!(circuit.decision_preimage.is_some());
    assert_eq!(circuit.decision_preimage.as_ref().unwrap().len(), 22);
}

/// Test quorum calculation edge cases
#[test]
fn test_quorum_calculation_edge_cases() {
    // 100% quorum requirement
    let full_quorum = QuorumCircuit::new(10, 1, 1, 10, [0u8; 32]);
    assert!(full_quorum.is_quorum_met());

    // 100% quorum with one missing
    let almost_full = QuorumCircuit::new(10, 1, 1, 9, [0u8; 32]);
    assert!(!almost_full.is_quorum_met());

    // 1/1 quorum (always pass if any approval)
    let single_needed = QuorumCircuit::new(10, 1, 10, 1, [0u8; 32]);
    assert!(single_needed.is_quorum_met());

    // Zero approvals
    let no_approvals = QuorumCircuit::new(10, 2, 3, 0, [0u8; 32]);
    assert!(!no_approvals.is_quorum_met());
}
