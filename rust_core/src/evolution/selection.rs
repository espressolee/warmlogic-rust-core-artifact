//! rust_core/src/evolution/selection.rs
//! Genetic Algorithm Selection Engine.
#![allow(dead_code)]
#![allow(unused_imports)]

#[cfg(feature = "python")]
#[cfg(feature = "python")]
use pyo3::prelude::*;
use rand::seq::IteratorRandom;
use rand::thread_rng;
use std::cmp::Ordering;

#[cfg_attr(feature = "python", pyclass)]
pub struct GeneticSelector {
    tournament_size: usize,
}

#[cfg(feature = "python")]
#[pymethods]
impl GeneticSelector {
    #[new]
    #[must_use]
    pub fn new(tournament_size: usize) -> Self {
        GeneticSelector { tournament_size }
    }

    /// Selects the best agent ID from a list of (id, fitness) tuples using Tournament Selection.
    #[must_use]
    pub fn tournament_select(&self, population: Vec<(String, f64)>) -> Option<String> {
        if population.is_empty() {
            return None;
        }

        let mut rng = thread_rng();
        let sample: Vec<&(String, f64)> = population
            .iter()
            .choose_multiple(&mut rng, self.tournament_size);

        // Find max fitness in sample
        sample
            .into_iter()
            .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(Ordering::Equal))
            .map(|(id, _)| id.clone())
    }

    /// Ranks agents by fitness (Descending).
    /// Returns list of IDs.
    #[must_use]
    pub fn rank_agents(&self, mut population: Vec<(String, f64)>) -> Vec<String> {
        population.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(Ordering::Equal));
        population.into_iter().map(|(id, _)| id).collect()
    }
}
