//! # Legacy Sigma Protocol (DEPRECATED)
//!
//! **WARNING**: This module is deprecated. Use the new `zk` module instead.
//!
//! The `zk` module provides:
//! - Groth16 proofs (not just Sigma protocol)
//! - BLS12-381 curve (industry standard)
//! - Full governance circuit integration
//! - Solidity-compatible proof format
//!
//! ## Migration
//!
//! ```rust,ignore
//! // Old (deprecated):
//! use warm_logic_rs::proof_zk::RustZKProofGenerator;
//!
//! // New (recommended):
//! use warm_logic_rs::zk::{GovernanceCircuit, Prover, Verifier};
//! ```
//!
//! This module will be removed in v2.0.

#![allow(dead_code)]
#![deprecated(since = "1.0.0", note = "Use the `zk` module with Groth16 instead")]

use curve25519_dalek::constants::RISTRETTO_BASEPOINT_POINT;
use curve25519_dalek::ristretto::{CompressedRistretto, RistrettoPoint};
use curve25519_dalek::scalar::Scalar;
use curve25519_dalek::traits::VartimeMultiscalarMul;
use merlin::Transcript;
use rand_core::OsRng;
// use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_512};

#[cfg(feature = "python")]
use crate::pyo3::prelude::*;

#[cfg(not(feature = "std"))]
use alloc::format;
#[cfg(not(feature = "std"))]
use alloc::string::String;
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

lazy_static::lazy_static! {
    static ref G: RistrettoPoint = RISTRETTO_BASEPOINT_POINT;
    static ref H: RistrettoPoint = {
        let mut hasher = Sha3_512::new();
        hasher.update(b"WarmLogic_H_Generator");
        let hash = hasher.finalize();
        let mut bytes = [0u8; 64];
        bytes.copy_from_slice(&hash);
        RistrettoPoint::from_uniform_bytes(&bytes)
    };
}

#[cfg(feature = "zk")]
pub use crate::zk::ZKProof;

#[cfg(not(feature = "zk"))]
#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(serde::Serialize, serde::Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct ZKProof {
    pub challenge: [u8; 32],
    pub z1: [u8; 32],
    pub z2: [u8; 32],
    pub commitment: [u8; 32],
}

#[cfg(feature = "python")]
#[pymethods]
impl ZKProof {
    #[getter]
    fn proof_hex(&self) -> String {
        format!(
            "{}:{}:{}",
            hex::encode(self.challenge),
            hex::encode(self.z1),
            hex::encode(self.z2)
        )
    }

    #[getter]
    fn commitment_hex(&self) -> String {
        hex::encode(self.commitment)
    }
}

#[cfg_attr(feature = "python", pyclass)]
pub struct RustZKProofGenerator;

#[cfg(feature = "python")]
#[pymethods]
impl RustZKProofGenerator {
    #[new]
    pub fn py_new() -> Self {
        Self::new()
    }

    pub fn generate_state_proof(
        &self,
        py: Python<'_>,
        value: u64,
        blinding_hex: &str,
    ) -> PyResult<ZKProof> {
        let blinding_bytes = hex::decode(blinding_hex).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid blinding hex: {}", e))
        })?;

        let mut blinding_arr = [0u8; 32];
        blinding_arr.copy_from_slice(&blinding_bytes[..32]);
        let r = Scalar::from_bytes_mod_order(blinding_arr);
        let v = Scalar::from(value);

        Ok(py.detach(|| self.prove_knowledge(v, r)))
    }

    pub fn verify_state_proof(
        &self,
        py: Python<'_>,
        proof_str: &str,
        commitment_hex: &str,
    ) -> PyResult<bool> {
        let parts: Vec<&str> = proof_str.split(':').collect();
        if parts.len() != 3 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Invalid proof format. Expected 'e:z1:z2'",
            ));
        }

        let e_bytes = hex::decode(parts[0]).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Invalid challenge hex")
        })?;
        let z1_bytes = hex::decode(parts[1])
            .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("Invalid z1 hex"))?;
        let z2_bytes = hex::decode(parts[2])
            .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("Invalid z2 hex"))?;
        let c_bytes = hex::decode(commitment_hex).map_err(|_| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Invalid commitment hex")
        })?;

        if e_bytes.len() != 32
            || z1_bytes.len() != 32
            || z2_bytes.len() != 32
            || c_bytes.len() != 32
        {
            return Ok(false);
        }

        let mut e_arr = [0u8; 32];
        e_arr.copy_from_slice(&e_bytes);
        let mut z1_arr = [0u8; 32];
        z1_arr.copy_from_slice(&z1_bytes);
        let mut z2_arr = [0u8; 32];
        z2_arr.copy_from_slice(&z2_bytes);
        let mut c_arr = [0u8; 32];
        c_arr.copy_from_slice(&c_bytes);

        let proof = ZKProof {
            challenge: e_arr,
            z1: z1_arr,
            z2: z2_arr,
            commitment: c_arr,
        };

        Ok(py.detach(|| self.verify_knowledge(proof)))
    }
}

impl RustZKProofGenerator {
    pub fn new() -> Self {
        Self
    }

    /// Prove knowledge of (v, r) such that Commitment = v*G + r*H
    pub fn prove_knowledge(&self, v: Scalar, r: Scalar) -> ZKProof {
        let mut transcript = Transcript::new(b"WarmLogicSigmaProof");

        // 1. Commitment to value/blinding
        let commitment = (v * *G + r * *H).compress();

        // 2. Prover picks random k, s
        let k = Scalar::random(&mut OsRng);
        let s = Scalar::random(&mut OsRng);

        // 3. Compute announcement R = k*G + s*H
        let announcement = (k * *G + s * *H).compress();

        // 4. Compute challenge e = Hash(G, H, Commitment, Announcement)
        transcript.append_message(b"commitment", commitment.as_bytes());
        transcript.append_message(b"announcement", announcement.as_bytes());

        let mut e_bytes = [0u8; 32];
        transcript.challenge_bytes(b"e", &mut e_bytes);
        let e = Scalar::from_bytes_mod_order(e_bytes);

        // 5. Compute responses
        let z1 = k + e * v;
        let z2 = s + e * r;

        ZKProof {
            challenge: e_bytes,
            z1: z1.to_bytes(),
            z2: z2.to_bytes(),
            commitment: commitment.to_bytes(),
        }
    }

    pub fn verify_knowledge(&self, proof: ZKProof) -> bool {
        let e = Scalar::from_bytes_mod_order(proof.challenge);
        let z1 = Scalar::from_bytes_mod_order(proof.z1);
        let z2 = Scalar::from_bytes_mod_order(proof.z2);

        let commitment = match CompressedRistretto::from_slice(&proof.commitment) {
            Ok(c) => match c.decompress() {
                Some(p) => p,
                None => return false,
            },
            Err(_) => return false,
        };

        // Recompute announcement R' = z1*G + z2*H - e*Commitment
        // Which is (k + e*v)*G + (s + e*r)*H - e*(v*G + r*H) = k*G + s*H = R
        let announcement_prime =
            RistrettoPoint::vartime_multiscalar_mul(&[z1, z2, -e], &[*G, *H, commitment])
                .compress();

        // Recompute challenge e'
        let mut transcript = Transcript::new(b"WarmLogicSigmaProof");
        transcript.append_message(b"commitment", proof.commitment.as_slice());
        transcript.append_message(b"announcement", announcement_prime.as_bytes());

        let mut e_prime_bytes = [0u8; 32];
        transcript.challenge_bytes(b"e", &mut e_prime_bytes);

        e_prime_bytes == proof.challenge
    }
}
#[cfg(test)]
mod tests {
    #![allow(deprecated)]
    use super::*;

    #[test]
    fn test_zk_knowledge_roundtrip() {
        let gen = RustZKProofGenerator::new();
        let value = Scalar::from(1000u64);
        let blinding = Scalar::random(&mut OsRng);

        let proof = gen.prove_knowledge(value, blinding);
        assert!(gen.verify_knowledge(proof));
    }

    #[test]
    fn test_zk_knowledge_tamper() {
        let gen = RustZKProofGenerator::new();
        let value = Scalar::from(1000u64);
        let blinding = Scalar::random(&mut OsRng);

        let mut proof = gen.prove_knowledge(value, blinding);
        // Tamper with response z1
        proof.z1[0] ^= 0xFF;

        assert!(!gen.verify_knowledge(proof));
    }

    #[test]
    fn test_zk_knowledge_wrong_value() {
        let gen = RustZKProofGenerator::new();
        let value = Scalar::from(1000u64);
        let blinding = Scalar::random(&mut OsRng);

        let proof = gen.prove_knowledge(value, blinding);

        // Change commitment to a different value
        let wrong_value = Scalar::from(2000u64);
        let wrong_commitment = (wrong_value * *G + blinding * *H).compress();

        let mut tampered_proof = proof;
        tampered_proof.commitment = wrong_commitment.to_bytes();

        assert!(!gen.verify_knowledge(tampered_proof));
    }
}
