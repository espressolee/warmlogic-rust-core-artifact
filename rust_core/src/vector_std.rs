// Soft-Vector Abstraction Layer
// This module provides a portable SIMD interface for cryptographic primitives.
// In the future, this will map to `core::arch::riscv64::v` intrinsics.

#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

/// The VectorOp trait abstracts the core mathematical operations required by
/// our cryptographic primitives (SHA3 and ML-DSA).
pub trait VectorOp {
    /// Absorbs a block of data into a state using XOR (SHA3 primitive).
    /// Performs `state[i] ^= input[i]` for the slice length.
    fn absorb_xor(state: &mut [u64], input: &[u64]);

    /// Performs matrix multiplication for ML-DSA verification (A * z = t).
    /// Deterministic O(N^3) (or N^2 for vector) reference implementation.
    /// Result is accumulated into `result`.
    fn matrix_vec_mul(matrix: &[Vec<i32>], vector: &[i32], result: &mut [i32]);
}

/// Scalar Implementation (Portable Fallback)
/// Guaranteed O(1) correctness, but O(N) performance.
pub struct ScalarEngine;

impl VectorOp for ScalarEngine {
    fn absorb_xor(state: &mut [u64], input: &[u64]) {
        let len = core::cmp::min(state.len(), input.len());
        for i in 0..len {
            state[i] ^= input[i];
        }
    }

    fn matrix_vec_mul(matrix: &[Vec<i32>], vector: &[i32], result: &mut [i32]) {
        // Assume square matrix for simplicity in this abstract layer
        let rows = matrix.len();
        if rows == 0 {
            return;
        }
        let cols = matrix[0].len();

        // Safety check
        if vector.len() != cols || result.len() != rows {
            return; // Fail silently or panic in debug? strict kernel -> silent fail or checked upper layer
        }

        for i in 0..rows {
            let mut sum: i32 = 0;
            for j in 0..cols {
                // In real ML-DSA this is polynomial multiplication,
                // here we execute the linear algebraic cost structure.
                sum = sum.wrapping_add(matrix[i][j].wrapping_mul(vector[j]));
            }
            result[i] = sum;
        }
    }
}

/// Dynamic dispatch or compile-time selection can happen here.
/// Here we default to ScalarEngine until RVV intrinsics are stable.
pub type SystemVector = ScalarEngine;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_absorb_xor() {
        let mut state = [0xAA; 4];
        let input = [0x55; 4];
        ScalarEngine::absorb_xor(&mut state, &input);
        assert_eq!(state, [0xFF, 0xFF, 0xFF, 0xFF]);
    }

    #[test]
    fn test_matrix_vec_mul() {
        // [ 1 2 ]   [ 2 ]   [ 1*2 + 2*3 ]   [ 8 ]
        // [ 3 4 ] * [ 3 ] = [ 3*2 + 4*3 ] = [ 18 ]
        let matrix = vec![vec![1, 2], vec![3, 4]];
        let vector = vec![2, 3];
        let mut result = vec![0; 2];

        ScalarEngine::matrix_vec_mul(&matrix, &vector, &mut result);
        assert_eq!(result, vec![8, 18]);
    }
}
