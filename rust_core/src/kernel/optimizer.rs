#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg_attr(feature = "python", pyclass)]
pub struct RustResonanceOptimizer {
    pub alpha: f64,
    pub beta: f64,
}

impl Default for RustResonanceOptimizer {
    fn default() -> Self {
        Self::new()
    }
}

impl RustResonanceOptimizer {
    #[must_use]
    pub fn new() -> Self {
        Self {
            alpha: 0.5,
            beta: 0.5,
        }
    }

    pub fn optimize_raw(&mut self, epsilon_c: f64, tau_ethics: f64) {
        // High resonance -> More stability focus (alpha)
        if epsilon_c > 0.9 {
            self.alpha = (self.alpha + 0.05).min(0.9);
            self.beta = (1.0 - self.alpha).max(0.1);
        }

        // Ethical concerns -> More ethics focus (beta)
        if tau_ethics > 0.5 {
            self.beta = (self.beta + 0.1).min(0.9);
            self.alpha = (1.0 - self.beta).max(0.1);
        }

        // Stability check
        if epsilon_c < 0.4 {
            // Emergency reset to balanced safety
            self.alpha = 0.5;
            self.beta = 0.5;
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl RustResonanceOptimizer {
    #[new]
    #[must_use]
    pub fn py_new() -> Self {
        Self::new()
    }

    #[getter]
    #[must_use]
    pub fn alpha(&self) -> f64 {
        self.alpha
    }

    #[setter]
    pub fn set_alpha(&mut self, val: f64) {
        self.alpha = val;
    }

    #[getter]
    #[must_use]
    pub fn beta(&self) -> f64 {
        self.beta
    }

    #[setter]
    pub fn set_beta(&mut self, val: f64) {
        self.beta = val;
    }

    pub fn optimize(&mut self, epsilon_c: f64, tau_ethics: f64) {
        self.optimize_raw(epsilon_c, tau_ethics);
    }
}
