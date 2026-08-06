#![cfg_attr(not(feature = "std"), no_std)]

use core::f64::consts::PI;

#[derive(Clone, Debug, Copy)]
pub struct LowPassFilter {
    alpha: f64,
    prev_output: f64,
}

impl LowPassFilter {
    #[must_use]
    pub fn new(cutoff_freq_hz: f64, dt: f64) -> Self {
        let rc = 1.0 / (2.0 * PI * cutoff_freq_hz);
        let alpha = dt / (rc + dt);
        LowPassFilter {
            alpha,
            prev_output: 0.0,
        }
    }

    pub fn update(&mut self, input: f64) -> f64 {
        let output = self.alpha * input + (1.0 - self.alpha) * self.prev_output;
        self.prev_output = output;
        output
    }

    pub fn reset(&mut self) {
        self.prev_output = 0.0;
    }
}
